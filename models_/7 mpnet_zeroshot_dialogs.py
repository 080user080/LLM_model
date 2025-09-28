# mpnet_zeroshot_from_files_to_dialogues.py
#GPT: mpnet + cosine; читає Dialog_test.txt і Legenda_test.txt, пише у Dialog_dialogues.txt

# pip install sentence-transformers torch
import re
import torch
from sentence_transformers import SentenceTransformer, util

# ---- Налаштування ----
MODEL_ID = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
DIALOG_PATH = "Dialog_test.txt"
LEGEND_PATH = "Legenda_test.txt"
OUTPUT_PATH = "Dialog_dialogues.txt"
TOP_K = 3
THRESH = 0.4
AS_PERCENT = True
DECIMALS = 1

device = "cuda" if torch.cuda.is_available() else "cpu"
model = SentenceTransformer(MODEL_ID, device=device)

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

def encode_verbalizers(verbalizers: dict):
    labels, texts = [], []
    for tag, phrases in verbalizers.items():
        for p in phrases:
            labels.append(tag)
            texts.append(p)
    emb = model.encode(texts, convert_to_tensor=True, normalize_embeddings=True)
    return labels, emb

def classify_line(text: str, all_labels, emb_verbalizers):
    q = model.encode(f"{text} [Хто говорить?]", convert_to_tensor=True, normalize_embeddings=True)
    sims = util.cos_sim(q, emb_verbalizers).squeeze(0)
    scores_by_tag = {}
    for idx, tag in enumerate(all_labels):
        val = float(sims[idx])
        if tag not in scores_by_tag or val > scores_by_tag[tag]:
            scores_by_tag[tag] = val
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
out.append(f"Device: {device} | рядків: {len(lines)} | тегів: {len(LEGEND)}\n")
for i, t in enumerate(lines, 1):
    tags, vals = classify_line(t, _all_labels, _emb_verbalizers)
    names = [LEGEND.get(tag, '#g?').split('(')[0].strip() for tag in tags]
    probs = fmt(vals)
    suffix = " %" if AS_PERCENT else ""
    out.append(f"{i:02d}. {t}")
    out.append("   Теги: " + ", ".join(f"{tag} ({name})" for tag, name in zip(tags, names)))
    out.append("   Ймовірності: " + str(probs) + suffix)
    out.append("-" * 50)

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(out))

print(f"Готово: {OUTPUT_PATH}")
