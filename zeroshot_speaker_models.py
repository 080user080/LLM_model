# ukrroberta_zeroshot_from_files.py — призначення мовця (Ukr-RoBERTa mean-pooling)
# -*- coding: utf-8 -*-

import os
import re
import json
import argparse
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

import torch
from transformers import AutoTokenizer, AutoModel

DASHES = "-\u2012\u2013\u2014\u2015"
NBSP = "\u00A0"

# ------------- DEBUG -------------
DEBUG = True
def dprint(*args, **kwargs):
    try:
        if DEBUG:
            print(*args, **kwargs)
    except Exception:
        pass

# ------------------------- CLI -------------------------

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inp", required=True, help="Вхідний текст із #g-тегами")
    p.add_argument("--out", dest="out", required=True, help="Вихідний файл з підстановками")
    p.add_argument("--legend", dest="legend", default=None, help="JSON або TXT легенда")
    p.add_argument("--log", dest="log", default=None, help="TSV лог прогнозів")
    p.add_argument("--threshold", type=float, default=0.25, help="Мін. cosine для присвоєння")
    p.add_argument("--min_margin", type=float, default=0.01, help="Мін. різниця Top1-Top2")
    p.add_argument("--ctx_lines", type=int, default=11, help="Вікно контексту ±N рядків")
    p.add_argument("--topk", type=int, default=5, help="Скільки топ-кандидатів логувати")
    p.add_argument("--model", default="youscan/ukr-roberta-base", help="HF модель ембеддингів")
    p.add_argument("--only_unknown", action="store_true", help="Обробляти лише #g?")
    p.add_argument("--force_when_single", action="store_true", help="Якщо кандидат один — присвоїти завжди")
    p.add_argument("--no_gender_filter", action="store_true", help="Вимкнути фільтр за родом")
    p.add_argument("--agg_topk", type=int, default=1, help="Агрегація по вербалізаторах: 1=max, >1=mean top-k")
    args = p.parse_args()
    dprint("[DEBUG] parse_args:", vars(args))
    return args

# ------------------------- IO --------------------------

def read_text(path: str) -> List[str]:
    dprint(f"[DEBUG] read_text: path={path}")
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines(keepends=True)
    dprint(f"[DEBUG] read_text: lines={len(lines)}")
    return lines

def _safe_field(s: str) -> str:
    return str(s or "").replace("\t", " ").replace("\n", " ").replace("\r", " ")

def _try_json(s: str):
    try:
        obj = json.loads(s)
        dprint("[DEBUG] _try_json: OK, keys=", list(obj.keys())[:5] if isinstance(obj, dict) else type(obj))
        return obj
    except Exception:
        dprint("[DEBUG] _try_json: not a JSON")
        return None

def _legend_plain_to_json(txt: str) -> Dict[str, Dict]:
    dprint("[DEBUG] _legend_plain_to_json: start")
    rx = re.compile(r"^\s*(#g\d+)\s*[:\-]\s*(.+?)\s*$", re.IGNORECASE)
    out = {}
    for raw in txt.splitlines():
        m = rx.match(raw)
        if not m:
            continue
        gid, name = m.group(1), m.group(2).strip()
        base = name.split("(")[0].split(",")[0].strip()
        if not base:
            continue
        g = None
        low = name.lower()
        if any(x in low for x in (" жін", " f)", "(f", "female")):
            g = "F"
        elif any(x in low for x in (" чол", " m)", "(m", "male")):
            g = "M"
        rec = out.setdefault(gid, {"names": [], "aliases": [], "gender": g})
        if base not in rec["names"]:
            rec["names"].append(base)
        # витягти псевдоніми/ролі з дужок: "Правнучка (дівчинка, онучка)"
        paren = re.findall(r"\(([^)]*)\)", name)
        if paren:
            for chunk in paren:
                for alias in re.split(r"[;,，、]\s*|\s*,\s*", chunk):
                    a = alias.strip()
                    if a and a not in rec["aliases"] and a.lower() != base.lower():
                        rec["aliases"].append(a)
    return out

def load_legend(path: Optional[str]) -> Dict[str, Dict]:
    if not path or not os.path.exists(path):
        dprint("[DEBUG] load_legend: path missing -> {}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read().strip()
    if not raw:
        dprint("[DEBUG] load_legend: file empty")
        return {}
    obj = _try_json(raw)
    if isinstance(obj, dict) and ("gid_to_names" in obj or "name_to_gid" in obj):
        # Bridge форматів: очікуємо {gid_to_names: {"#gN": [names…]}, name_to_gid: {...}, narrator_gid: "#gX"}
        gid2names = obj.get("gid_to_names", {})
        norm = {}
        for gid, names in gid2names.items():
            norm[str(gid)] = {
                "names": [x for x in (names or []) if x],
                "aliases": [],
                "gender": None,
            }
        nar = obj.get("narrator_gid")
        if isinstance(nar, str) and nar in norm:
            # Додати текстові аліаси, щоб знайти оповідача через пошук слів
            norm[nar]["aliases"] += ["наратив", "оповідач", "оповідачка"]
        dprint("[DEBUG] load_legend(JSON-bridge): norm keys=", list(norm.keys())[:10])
        return norm
    if obj is None:
        obj = _legend_plain_to_json(raw)
    norm = {}
    for gid, rec in obj.items():
        r = {"names": [], "aliases": [], "gender": None}
        if isinstance(rec, dict):
            r["names"] = [x for x in rec.get("names", []) if x]
            r["aliases"] = [x for x in rec.get("aliases", []) if x]
            g = rec.get("gender")
            r["gender"] = g if g in ("M", "F") else None
        elif isinstance(rec, list):
            r["names"] = [x for x in rec if x]
        elif isinstance(rec, str):
            r["names"] = [rec]
        norm[str(gid)] = r
    dprint("[DEBUG] load_legend: norm keys=", list(norm.keys())[:10])
    return norm

# --------------------- Text utils ----------------------

TAG_ANY = None  # встановлюється в main()

APOS_SRC = ("ʼ", "′", "`", "'")
QUOTE_SRC = ("“", "”", "„", "«", "»")
def normalize_for_embed(s: str) -> str:
    """Нормалізація для ембеддингів: апостроф, пробіли, лапки."""
    if not s:
        return ""
    s = s.replace(NBSP, " ")
    for ch in APOS_SRC:
        s = s.replace(ch, "’")
    for ch in QUOTE_SRC:
        s = s.replace(ch, '"')
    s = re.sub(r"\s+", " ", s).strip()
    out = s
    # dprint("[DEBUG] normalize_for_embed:", out[:80])
    return out

def is_dialog_body(body: str) -> bool:
    b = (body or "").replace(NBSP, " ").lstrip()
    res = bool(b[:1] and (b[0] in DASHES or b[0] in '«"„“”\'’'))
    # dprint("[DEBUG] is_dialog_body:", res)
    return res

def extract_dialogs(lines: List[str]) -> List[Tuple[int, str, str, str]]:
    out = []
    for i, ln in enumerate(lines):
        m = TAG_ANY.match(ln)
        if not m:
            continue
        indent, gid_s, body = m.groups()
        out.append((i, indent, gid_s, body))
    dprint(f"[DEBUG] extract_dialogs: found={len(out)}")
    return out

SPEECH_VERBS = (
    "сказав","сказала","сказали","казав","казала","відповів","відповіла","відповіли",
    "запитав","запитала","запитали","спитав","спитала","спитали","промовив","промовила","промовили",
    "крикнув","крикнула","крикнули","кричав","кричала","кричали","вигукнув","вигукнула","вигукнули",
    "прошепотів","прошепотіла","прошепотіли","буркнув","буркнула","буркнули","звернувся","звернулась","звернулися",
    "мовив","мовила","мовили","процедив","процедила","процедили","відказав","відказала","відказали",
    "зазначив","зазначила","зазначили","погодився","погодилась","погодилися","гомонів","гомоніла","гомоніли"
)

def _has_speech_verb(txt: str) -> bool:
    low = (txt or "").lower()
    res = any(v in low for v in SPEECH_VERBS)
    # dprint("[DEBUG] _has_speech_verb:", res)
    return res

def _gen_name_forms(name: str) -> List[str]:
    base = name.strip()
    forms = {base, base.replace("’", "'"), base.lower(), base.lower().replace("’", "'")}
    if base.endswith(("а", "я")):
        stem = base[:-1]
        for suf in ("и","і","ю","єю","е","є","ою"):
            forms.add(stem + suf); forms.add((stem + suf).lower())
    else:
        for suf in ("а","у","ом","ові","е","ю","і"):
            forms.add(base + suf); forms.add((base + suf).lower())
    out = list(forms)
    # dprint(f"[DEBUG] _gen_name_forms('{name}'): {len(out)} forms")
    return out

def build_name_forms_map(legend: Dict[str, Dict]) -> Dict[str, str]:
    inv = {}
    for gid, rec in legend.items():
        names = rec.get("names", []) + rec.get("aliases", [])
        for nm in names:
            for form in _gen_name_forms(nm):
                inv[form.lower()] = gid
    dprint("[DEBUG] build_name_forms_map: entries=", len(inv))
    return inv

def build_gid_primary_name(legend: Dict[str, Dict]) -> Dict[str, str]:
    out = {}
    for gid, rec in legend.items():
        if rec.get("names"):
            out[gid] = rec["names"][0]
        elif rec.get("aliases"):
            out[gid] = rec["aliases"][0]
        else:
            out[gid] = gid
    return out

def seen_gids_from_text(lines: List[str]) -> List[str]:
    seen = []
    for ln in lines:
        m = TAG_ANY.match(ln)
        if not m:
            continue
        gid_s = m.group(2)
        if gid_s != "?":
            g = f"#g{gid_s}"
            if g not in seen:
                seen.append(g)
    dprint("[DEBUG] seen_gids_from_text:", seen[:10])
    return seen

def find_addressee(body: str, name_forms_inv: Dict[str, str]) -> Optional[str]:
    if not body:
        return None
    m = re.match(rf"^\s*[{re.escape(DASHES)}]?\s*([A-ZА-ЯЇІЄҐ][\w’']+)[,!]\s", body)
    if not m:
        return None
    form = m.group(1).lower()
    gid = name_forms_inv.get(form)
    # dprint("[DEBUG] find_addressee:", gid)
    return gid

def gender_hint(line: str) -> Optional[str]:
    t = (line or "").lower()
    if re.search(r"\b(сказав|відповів|промовив|крикнув|вигукнув|прошепотів|буркнув|звернувся|процедив|відказав|зазначив|погодився)\b", t):
        return "M"
    if re.search(r"\b(сказала|відповіла|промовила|крикнула|вигукнула|прошепотіла|буркнула|звернулась|процедила|відказала|зазначила|погодилась)\b", t):
        return "F"
    if "чоловічий голос" in t: return "M"
    if "жіночий голос" in t: return "F"
    return None

def collect_context_candidates(idx: int, lines: List[str], ctx: int, name_forms_inv: Dict[str, str]) -> List[str]:
    lo, hi = max(0, idx - ctx), min(len(lines), idx + ctx + 1)
    found = []
    # Враховуємо й слова, що починаються з малих літер (щоб ловити аліаси на кшталт "правнучка")
    rx_tok = re.compile(r"[A-Za-zА-Яа-яЇїІіЄєҐґ][\w’']+")
    for j in range(lo, hi):
        m = TAG_ANY.match(lines[j])
        text = (m.group(3) if m else lines[j]) or ""
        for tok in rx_tok.findall(text):
            gid = name_forms_inv.get(tok.lower())
            if gid and gid not in found:
                found.append(gid)
    dprint(f"[DEBUG] collect_context_candidates idx={idx}:", found[:10])
    return found

def count_context_mentions(idx: int, lines: List[str], ctx: int, name_forms_inv: Dict[str, str]) -> Dict[str, int]:
    """Повертає лічильник згадок кожного gid у ±ctx рядках (включно з поточним)."""
    lo, hi = max(0, idx - ctx), min(len(lines), idx + ctx + 1)
    # Так само дозволяємо слова, що починаються з малих літер
    rx_tok = re.compile(r"[A-Za-zА-Яа-яЇїІіЄєҐґ][\w’']+")
    counts: Dict[str, int] = {}
    for j in range(lo, hi):
        m = TAG_ANY.match(lines[j])
        text = (m.group(3) if m else lines[j]) or ""
        for tok in rx_tok.findall(text):
            gid = name_forms_inv.get(tok.lower())
            if gid:
                counts[gid] = counts.get(gid, 0) + 1
    # dprint(f"[DEBUG] count_context_mentions idx={idx}:", list(counts.items())[:5])
    return counts

_VERB_NAME_RX = re.compile(
    r"^\s*[—\-–]?\s*(сказав|сказала|відповів|відповіла|запитав|запитала|спитав|спитала|промовив|промовила|вигукнув|вигукнула|прошепотів|прошепотіла)\s+([A-ZА-ЯЇІЄҐ][\w’']+(?:\s+[A-ZА-ЯЇІЄҐ][\w’']+)?)",
    re.IGNORECASE
)
def explicit_speaker_by_rule(body: str, name_forms_inv: Dict[str, str]) -> Optional[str]:
    """Правило 4: 'сказав ... Ім'я' → пріоритетний спікер."""
    if not body:
        return None
    m = _VERB_NAME_RX.match(body)
    if not m:
        return None
    name = m.group(2).strip().lower()
    gid = name_forms_inv.get(name)
    # dprint("[DEBUG] explicit_speaker_by_rule ->", gid)
    return gid

def make_queries(lines: List[str], ctx_lines: int) -> Dict[int, str]:
    queries = {}
    n = len(lines)
    for i, indent, gid_s, body in extract_dialogs(lines):
        if gid_s != "?":
            continue
        parts = [normalize_for_embed(body.strip())]
        for j in range(max(0, i - ctx_lines), min(n, i + ctx_lines + 1)):
            if j == i:
                continue
            m = TAG_ANY.match(lines[j])
            if m:
                gidj = m.group(2)
                if gidj != "?":
                    parts.append(normalize_for_embed((m.group(3) or "").strip()))
        q = " ".join(p for p in parts if p)
        queries[i] = q
    dprint("[DEBUG] make_queries: count=", len(queries))
    return queries

def replace_line_gid(lines: List[str], idx: int, new_gid: str):
    ln = lines[idx]
    m = TAG_ANY.match(ln)
    indent, _, body = m.groups()
    # збереження оригінального завершення рядка
    eol = "\r\n" if ln.endswith("\r\n") else ("\n" if ln.endswith("\n") else "")
    lines[idx] = f"{indent}{new_gid}: {body}{eol}"
    dprint(f"[DEBUG] replace_line_gid idx={idx} -> {new_gid}")

# --------------------- Embeddings (RoBERTa) ----------------------

class HFEmbedder:
    def __init__(self, model_name: str):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tok = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(self.device)
        self.model.eval()
        dprint(f"[DEBUG] HFEmbedder: model={model_name} device={self.device}")

    @torch.no_grad()
    def encode(self, texts: List[str], batch_size: int = 16, max_length: int = 256) -> torch.Tensor:
        if not texts:
            return torch.zeros((0, self.model.config.hidden_size))
        outs = []
        for i in range(0, len(texts), batch_size):
            chunk = texts[i:i+batch_size]
            enc = self.tok(chunk, padding=True, truncation=True, max_length=max_length, return_tensors="pt").to(self.device)
            out = self.model(**enc).last_hidden_state  # [B,T,H]
            mask = enc["attention_mask"].unsqueeze(-1)  # [B,T,1]
            summed = (out * mask).sum(dim=1)            # [B,H]
            counts = mask.sum(dim=1).clamp(min=1)       # [B,1]
            mean = summed / counts
            mean = torch.nn.functional.normalize(mean, p=2, dim=1)
            outs.append(mean.detach().cpu())
        embs = torch.cat(outs, dim=0)
        dprint(f"[DEBUG] encode: batch_out shape={embs.shape}")
        return embs

def cosine(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    res = (a @ b.T).squeeze(0)
    # dprint("[DEBUG] cosine shape=", tuple(res.shape))
    return res  # за нормалізації це cosine

# --------------------- Verbalizers & aggregation ----------------------

def _gendered_verbs(g: Optional[str]) -> List[str]:
    if g == "M":
        return ["Сказав"]
    if g == "F":
        return ["Сказала"]
    return ["Сказав", "Сказала"]

def generate_verbalizers(gid: str, rec: Dict) -> List[str]:
    """Мінімальні вербалізатори на основі імені/аліасів."""
    names = list(dict.fromkeys((rec.get("names") or []) + (rec.get("aliases") or [])))
    if not names:
        names = [gid]
    verbs = _gendered_verbs(rec.get("gender"))
    ph: List[str] = []
    for nm in names:
        nm = nm.strip()
        if not nm:
            continue
        # Базові
        ph.append(nm)
        ph.append(f"Це говорить {nm}.")
        ph.append(f"Репліка {nm}.")
        for v in verbs:
            ph.append(f"{v} {nm}.")
        # Форми імені (мінімальні відмінки з _gen_name_forms)
        for f in _gen_name_forms(nm):
            ph.append(f)
    # Нормалізація + унікалізація
    uniq = []
    seen = set()
    for s in ph:
        s2 = normalize_for_embed(s)
        if s2 and s2 not in seen:
            seen.add(s2); uniq.append(s2)
    dprint(f"[DEBUG] generate_verbalizers {gid}: n={len(uniq)}")
    return uniq

def agg_sim(qvec: torch.Tensor, embs: torch.Tensor, topk: int) -> float:
    """Повертає max або mean(top-k) косайн подібностей qvec до множини ембедів."""
    if embs.numel() == 0:
        return 0.0
    sims = (qvec @ embs.T).squeeze(0)  # [M]
    if sims.ndim == 0:
        return float(sims.item())
    if topk <= 1:
        return float(torch.max(sims).item())
    k = int(min(topk, sims.shape[0]))
    vals = torch.topk(sims, k=k).values
    val = float(vals.mean().item())
    # dprint("[DEBUG] agg_sim:", val)
    return val

# --------------------------- Main ---------------------------

def main():
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    args = parse_args()
    # забезпечуємо наявність нових аргументів у старих скриптах
    if not hasattr(args, "novelty_penalty"):
        args.novelty_penalty = 0.08
    if not hasattr(args, "name_prefix_in_ctx"):
        args.name_prefix_in_ctx = False
    global TAG_ANY
    # Підтримати '#g?: текст' і '#g? - текст'
    TAG_ANY = re.compile(r"^(\s*)#g(\d+|\?)\s*:?[\s]*(.*)$", re.DOTALL)

    lines = read_text(args.inp)
    legend = load_legend(args.legend) or {}
    if not legend and args.legend and os.path.exists(args.legend):
        # fallback: простий текстовий формат "#gN - Ім'я (aliases…)"
        parsed = {}
        with open(args.legend, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or not line.startswith("#g"):
                    continue
                try:
                    gid, rest = line.split("-", 1)
                except ValueError:
                    continue
                gid = gid.strip()
                name_part = rest.strip()
                if "(" in name_part and name_part.endswith(")"):
                    name, aliases = name_part.split("(", 1)
                    aliases = aliases.rstrip(")")
                    aliases = [a.strip() for a in aliases.split(",") if a.strip()]
                else:
                    name, aliases = name_part, []
                parsed[gid] = {"names": [name.strip()], "aliases": aliases}
        legend = parsed
    dprint("[DEBUG] legend keys:", list(legend.keys())[:10])

    name_forms_inv = build_name_forms_map(legend)
    dprint("[DEBUG] name_forms_inv size:", len(name_forms_inv))
    gid2name = build_gid_primary_name(legend)
    if not gid2name:
        fallback = seen_gids_from_text(lines)
        gid2name = {g: g for g in fallback}

    # Допоміжне: валідність #gN та мапа для «оповідача»
    GID_RX = re.compile(r"^#g\d+$")
    def valid_gid(x: str) -> bool:
        return bool(x) and bool(GID_RX.match(x))

    # Пошук тегу для оповідача за легендою (імена/аліаси містять «наратив» або «оповідач»)
    narrator_terms = {"наратив", "оповідач", "оповідачка"}
    NARRATOR_GID = None
    for _gid, _rec in legend.items():
        pool = [*(_rec.get("names") or []), *(_rec.get("aliases") or [])]
        pool = [str(x).strip().lower() for x in pool]
        if any(t in pool for t in narrator_terms):
            NARRATOR_GID = _gid
            break

    def normalize_gid(g: str) -> str:
        """Повертає #gN або #g?; замінює службові псевдо-ідентифікатори на тег оповідача, якщо знайдено."""
        if valid_gid(g):
            return g
        if g in {"narrator_gid", "narrator", "narration"} and NARRATOR_GID:
            return NARRATOR_GID
        return "#g?"

    # Вербалізатори та їх ембеди (п.2,4)
    embedder = HFEmbedder(args.model)
    verbalizers: Dict[str, List[str]] = {}
    for gid, rec in legend.items():
        verbalizers[gid] = generate_verbalizers(gid, rec)
    # запасний варіант, якщо легенда порожня
    if not verbalizers:
        for g in sorted(gid2name.keys()):
            verbalizers[g] = [normalize_for_embed(gid2name[g])]
    gid_list_all = sorted(verbalizers.keys())
    dprint("[DEBUG] gid_list_all size:", len(gid_list_all), gid_list_all[:10])
    verb_embs_all: Dict[str, torch.Tensor] = {}
    for g in gid_list_all:
        verb_embs_all[g] = embedder.encode(verbalizers[g], batch_size=32)
    dprint("[DEBUG] verb_embs_all built for:", list(verb_embs_all.keys())[:10])

    # попередній мовець
    prev_speaker_up_to = {}
    last_gid = None
    for i, indent, gid_s, body in extract_dialogs(lines):
        if gid_s not in {"1", "?"}:
            last_gid = f"#g{gid_s}"
        prev_speaker_up_to[i] = last_gid

    # #g? запити
    queries = make_queries(lines, args.ctx_lines)
    q_idxs = list(queries.keys())
    q_texts = [queries[i] for i in q_idxs]
    q_emb = embedder.encode([normalize_for_embed(q) for q in q_texts])
    dprint(f"[DEBUG] queries: n={len(q_idxs)}")

    logs = []
    changed = 0
    total_unknown = 0

    # індекс першої появи кожного відомого #gN у тексті (для штрафу новизни)
    first_seen_idx: Dict[str, int] = {}
    for i0, _indent0, gid_s0, _body0 in extract_dialogs(lines):
        if gid_s0 not in {"?", "1"}:
            g0 = f"#g{gid_s0}"
            if g0 not in first_seen_idx:
                first_seen_idx[g0] = i0
    dprint("[DEBUG] first_seen_idx size:", len(first_seen_idx))

    def classify(idx: int, qvec: torch.Tensor, qtext: str, body_for_hints: str,
                 first_seen_idx: Dict[str, int]) -> Tuple[str, Dict]:
        dprint(f"[DEBUG] classify idx={idx} body[:60]=", (body_for_hints or "")[:60])
        # 0) Явне правило: «дієслово мовлення + Ім'я» на початку рядка
        gid_rule = explicit_speaker_by_rule(body_for_hints, name_forms_inv)
        if gid_rule:
            dprint("[DEBUG] explicit rule ->", gid_rule)
            return gid_rule, {"reason": "explicit_verb_name", "top": [(gid_rule, 1.0)], "best": 1.0, "margin": 1.0}

        # 1) контекстні кандидати
        context_cands = collect_context_candidates(idx, lines, args.ctx_lines, name_forms_inv)
        cand_gids = context_cands if context_cands else list(gid_list_all)
        # Відфільтрувати сміттєві кандидати, залишити лише #gN
        cand_gids = [g for g in cand_gids if valid_gid(g)] or list(gid_list_all)
        dprint("[DEBUG] cand_gids:", cand_gids[:10])

        # 2) звертання
        addr_gid = find_addressee(body_for_hints, name_forms_inv)
        if addr_gid and addr_gid in cand_gids and len(cand_gids) > 1:
            cand_gids = [g for g in cand_gids if g != addr_gid]

        # 3) фільтр за родом (за наявності)
        if not args.no_gender_filter:
            hint = gender_hint(lines[idx - 1] if idx - 1 >= 0 else "") or gender_hint(body_for_hints)
            if hint:
                filtered = []
                for g in cand_gids:
                    gmeta = legend.get(g, {})
                    if gmeta.get("gender") in (hint, None):
                        filtered.append(g)
                if filtered:
                    cand_gids = filtered

        if not cand_gids:
            return "#g?", {"reason": "no_candidates", "top": [], "best": 0.0, "margin": 0.0}

        # обчислення sim по множині вербалізаторів кожного кандидата (п.6)
        cand_list = list(cand_gids)
        sims = []
        for g in cand_list:
            embs = verb_embs_all.get(g)
            if embs is None or embs.numel() == 0:
                embs = embedder.encode([normalize_for_embed(gid2name.get(g, g))])
                verb_embs_all[g] = embs
            s = agg_sim(qvec, embs, args.agg_topk)
            sims.append(s)
        sim = torch.tensor(sims)
        dprint("[DEBUG] sim shape:", tuple(sim.shape))

        # 4) бусти
        boosts = torch.zeros_like(sim)
        # 4.1 Верб мовлення в рядку → невеликий бонус
        if _has_speech_verb(body_for_hints):
            boosts += 0.03
        # 4.2 Попередній/наступний відомий спікер поруч
        prev_gid = prev_speaker_up_to.get(idx)
        next_gid = prev_speaker_up_to.get(idx + 1)  # легкий погляд уперед
        if prev_gid and prev_gid in cand_list:
            boosts[cand_list.index(prev_gid)] += 0.06
        if next_gid and next_gid in cand_list:
            boosts[cand_list.index(next_gid)] += 0.03
        # 4.3 Згадки персонажів у поточному контексті → підсилення їх кандидатів
        mention_counts = count_context_mentions(idx, lines, args.ctx_lines, name_forms_inv)
        for gi, g in enumerate(cand_list):
            c = mention_counts.get(g, 0)
            if c:
                boosts[gi] += min(0.30, 0.04 * c)  # до +0.10 за часті згадки
        # 4.4 Для явних лексичних хітів (імен/аліасів у рядку) — максимальний бонус 0.70
        rx_word = re.compile(r"[A-Za-zА-Яа-яЇїІіЄєҐґ][\w’']+")
        lexical_hit = None
        for tok in rx_word.findall(body_for_hints or ""):
            gid_hit = name_forms_inv.get(tok.lower())
            if not gid_hit or not valid_gid(gid_hit):
                continue
            if gid_hit not in cand_list:
                cand_list.append(gid_hit)
                # ініціалізувати ембеди вербалізаторів для нового кандидата
                if gid_hit not in verb_embs_all:
                    rec = legend.get(gid_hit, {"names": [gid2name.get(gid_hit, gid_hit)], "aliases": []})
                    verbalizers[gid_hit] = generate_verbalizers(gid_hit, rec)
                    verb_embs_all[gid_hit] = embedder.encode(verbalizers[gid_hit], batch_size=32)
                # розширити sim та boosts синхронно
                s_hit = agg_sim(qvec, verb_embs_all[gid_hit], args.agg_topk)
                sim = torch.cat([sim, torch.tensor([s_hit])], dim=0)
                boosts = torch.cat([boosts, torch.zeros(1, dtype=sim.dtype)], dim=0)
            boosts[cand_list.index(gid_hit)] = 0.70
            lexical_hit = gid_hit
        # 4.5 Штраф за "нового" мовця, що ще не говорив до цього рядка
        if args.novelty_penalty > 0 and first_seen_idx:
            any_spoken_before = any(first_seen_idx.get(g, 10**9) < idx for g in cand_list)
            if any_spoken_before:
                for gi, g in enumerate(cand_list):
                    if first_seen_idx.get(g, 10**9) >= idx:
                        pen = args.novelty_penalty * (0.5 if mention_counts.get(g, 0) else 1.0)
                        boosts[gi] -= pen

        final = sim + boosts
        order = torch.argsort(final, descending=True).tolist()
        dprint("[DEBUG] final top candidates:", [(cand_list[k], float(final[k])) for k in order[:min(5, len(order))]])
        if not order:
            return "#g?", {"reason": "no_scores", "top": [], "best": 0.0, "margin": 0.0}

        margin = float(final[order[0]].item() - final[order[1]].item()) if len(order) > 1 else 0.0
        best_gid = normalize_gid(cand_list[order[0]])
        best_cos = float(final[order[0]].item())
        # Лог: показуємо тільки #gN; псевдоніми замінюємо через normalize_gid
        topk = [(normalize_gid(cand_list[k]), float(final[k].item())) for k in order[:max(1, args.topk)]]

        if lexical_hit is not None and normalize_gid(lexical_hit) == best_gid:
            return best_gid, {"reason": "lexical_hit", "top": topk, "best": best_cos, "margin": margin}

        if args.force_when_single and len(cand_list) == 1:
            return best_gid, {"reason": "force_single", "top": topk, "best": best_cos, "margin": margin}
        if (best_cos >= args.threshold) and (margin >= args.min_margin):
            return best_gid, {"reason": "threshold", "top": topk, "best": best_cos, "margin": margin}
        # якщо є суттєве підсилення згадками — повідомити у причині
        if any(mention_counts.get(g, 0) for g in cand_list):
            return best_gid, {"reason": "mention_boost", "top": topk, "best": best_cos, "margin": margin}
        return "#g?", {"reason": "low_conf", "top": topk, "best": best_cos, "margin": margin}

    # обробка #g?
    for qi, qidx in enumerate(q_idxs):
        m = TAG_ANY.match(lines[qidx])
        if args.only_unknown and (not m or m.group(2) != "?"):
            continue
        body = m.group(3) if m else ""
        qv = q_emb[qi:qi+1]
        total_unknown += 1
        decision, info = classify(qidx, qv, q_texts[qi], body, first_seen_idx)
        if decision != "#g?":
            replace_line_gid(lines, qidx, normalize_gid(decision))
            changed += 1
        else:
            dprint(f"[DEBUG] keep unknown at line {qidx}")
        logs.append({
            "line": qidx, "decision": decision, "best_gid": decision,
            "best_score": round(info.get("best", 0.0), 4),
            "margin": round(info.get("margin", 0.0), 4),
            "top": [(normalize_gid(g), round(s, 4)) for g, s in info.get("top", [])],
            "query": _safe_field(q_texts[qi][:400]),
            "reason": "gq_" + info.get("reason", "")
        })

    # Санітаризація: прибрати службові рядки, нормалізувати формат
    META_RX = re.compile(r"^\s*(?:gid[_\-\s]*to[_\-\s]*names|[A-Za-z_]+_gid)\s*[:：]\s*(.*)$", re.IGNORECASE)
    def _eol(s: str) -> str:
        return "\r\n" if s.endswith("\r\n") else ("\n" if s.endswith("\n") else "")
    out_lines = []
    for ln in lines:
        eol = _eol(ln)
        m_bad = META_RX.match(ln)
        if m_bad:
            body = re.sub(r"^\s*-\s*", "", m_bad.group(1)).lstrip()
            out_lines.append(f"#g?: {body}{eol}")
            continue
        m = TAG_ANY.match(ln)
        if m:
            indent, gid_s, body = m.groups()
            body = re.sub(r"^\s*-\s*", "", (body or "")).lstrip()
            out_lines.append(f"{indent}#g{gid_s}: {body}{eol}")
        else:
            out_lines.append(ln)

    # --- Фікс зайвих порожніх рядків ---
    # Збираємо текст, уніфікуємо EOL, схлопуємо 3+ \n до \n\n, повертаємо стиль EOL.
    text_out = "".join(out_lines)
    prefer_crlf = "\r\n" in text_out
    text_out = text_out.replace("\r\n", "\n").replace("\r", "\n")
    text_out = re.sub(r"\n{3,}", "\n\n", text_out)
    if prefer_crlf:
        text_out = text_out.replace("\n", "\r\n")
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        f.write(text_out)

    if args.log:
        with open(args.log, "w", encoding="utf-8") as f:
            f.write("line_idx\tdecision\tbest_gid\tbest_score\tmargin\ttop\tquery\treason\n")
            for r in logs:
                top_str = ";".join([f"{g}:{p:.3f}" for g, p in r["top"]])
                f.write(f"{r['line']}\t{r['decision']}\t{r['best_gid']}\t{r['best_score']:.3f}\t{r['margin']:.3f}\t{top_str}\t{r['query']}\t{r.get('reason','')}\n")

    print(f"[ML_model] Готово. Записано ->", args.out)
    print(f"[ML_model] Невідомих мовців: {total_unknown}, замінено: {changed}")
    if args.log:
        print("[ML_model] Log ->", args.log)

if __name__ == "__main__":
    main()
