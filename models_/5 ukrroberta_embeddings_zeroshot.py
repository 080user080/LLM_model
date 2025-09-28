# ukrroberta_zeroshot_from_files.py
#GPT: ukr-roberta-base → sentence embeddings → cosine → MAX по тегу; читає Dialog_test.txt і Legenda_test.txt; пише Dialog_dialogues.txt
# pip install transformers torch

import re
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel

# ---- Налаштування ----
MODEL_ID = "youscan/ukr-roberta-base"
DIALOG_PATH = "Dialog_test.txt"
LEGEND_PATH = "Legenda_test.txt"
OUTPUT_PATH = "Dialog_dialogues.txt"
TOP_K = 3
THRESH = 0.40
AS_PERCENT = True
DECIMALS = 1

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
tok = AutoTokenizer.from_pretrained(MODEL_ID)
mdl = AutoModel.from_pretrained(MODEL_ID).to(device).eval()

def read_dialog_lines(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return [ln.rstrip("\n") for ln in f if ln.strip()]

SEP_RE = re.compile(r"\s*[:\-—]\s*|\t")
def read_legend(path: str):
    legend = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("//"):
                continue
            parts = SEP_RE.split(line, maxsplit=1)
            if len(parts) == 2 and parts[0].startswith("#g"):
                legend[parts[0].strip()] = parts[1].strip()
    if not legend:
        raise ValueError(f"Порожня легенда у файлі: {path}")
    return legend

def build_verbalizers(legend: dict):
    v = {}
    for tag, desc in legend.items():
        name = desc.split("(")[0].strip()
        v[tag] = [
            f"Мовець — {name}.",
            f"Це висловлювання належить: {name}.",
            f"Автор репліки: {desc}.",
        ]
    return v

@torch.no_grad()
def mean_pool(texts):
    enc = tok(texts, padding=True, truncation=True, return_tensors="pt").to(device)
    out = mdl(**enc).last_hidden_state                       # [B, T, H]
    mask = enc["attention_mask"].unsqueeze(-1)               # [B, T, 1]
    emb = (out * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
    emb = F.normalize(emb, p=2, dim=1)                       # L2-нормалізація
    return emb                                               # [B, H] на device

def encode_verbalizers(verbalizers: dict):
    labels, texts = [], []
    for tag, phrases in verbalizers.items():
        for p in phrases:
            labels.append(tag)
            texts.append(p)
    emb = mean_pool(texts)                                   # [N_verbalizers, H]
    return labels, emb

def classify_line(text: str, all_labels, emb_verbalizers):
    q = mean_pool([f"{text} [Хто говорить?]"])              # [1, H]
    # Для нормалізованих ембеддингів cos(q,V) == q @ V^T
    sims = (q @ emb_verbalizers.T).squeeze(0).tolist()      # [N_verbalizers]
    scores_by_tag = {}
    for s, tag in zip(sims, all_labels):
        scores_by_tag[tag] = max(scores_by_tag.get(tag, -1.0), s)
    ranked = sorted(scores_by_tag.items(), key=lambda x: x[1], reverse=True)
    if not ranked or ranked[0][1] < THRESH:
        return ["#g?"], [0.0]
    tags = [t for t, _ in ranked[:TOP_K]]
    vals = [v for _, v in ranked[:TOP_K]]
    return tags, vals

def fmt(xs): 
    return [round(x * 100 if AS_PERCENT else x, DECIMALS) for x in xs]

# ---- Зчитування ----
lines = read_dialog_lines(DIALOG_PATH)
LEGEND = read_legend(LEGEND_PATH)
VERBALIZERS = build_verbalizers(LEGEND)
_all_labels, _emb_verbalizers = encode_verbalizers(VERBALIZERS)

# ---- Обчислення та запис ----
out = []
out.append(f"Device: {device.type} | рядків: {len(lines)} | тегів: {len(LEGEND)}\n")
for i, t in enumerate(lines, 1):
    tags, vals = classify_line(t, _all_labels, _emb_verbalizers)
    names = [LEGEND.get(tag, "#g?").split("(")[0].strip() for tag in tags]
    probs = fmt(vals)
    suffix = " %" if AS_PERCENT else ""
    out.append(f"{i:02d}. {t}")
    out.append("   Теги: " + ", ".join(f"{tag} ({name})" for tag, name in zip(tags, names)))
    out.append("   Ймовірності: " + str(probs) + suffix)
    out.append("-" * 50)

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(out))

print(f"Готово: {OUTPUT_PATH}")
