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

# ------------------------- CLI -------------------------

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inp", required=True, help="Вхідний текст із #g-тегами")
    p.add_argument("--out", dest="out", required=True, help="Вихідний файл з підстановками")
    p.add_argument("--legend", dest="legend", default=None, help="JSON або TXT легенда")
    p.add_argument("--log", dest="log", default=None, help="TSV лог прогнозів")
    p.add_argument("--threshold", type=float, default=0.38, help="Мін. cosine для присвоєння")
    p.add_argument("--min_margin", type=float, default=0.00, help="Мін. різниця Top1-Top2")
    p.add_argument("--ctx_lines", type=int, default=7, help="Вікно контексту ±N рядків")
    p.add_argument("--topk", type=int, default=2, help="Скільки топ-кандидатів логувати")
    p.add_argument("--model", default="youscan/ukr-roberta-base", help="HF модель ембеддингів")
    p.add_argument("--only_unknown", action="store_true", help="Обробляти лише #g?")
    p.add_argument("--force_when_single", action="store_true", help="Якщо кандидат один — присвоїти завжди")
    p.add_argument("--no_gender_filter", action="store_true", help="Вимкнути фільтр за родом")
    return p.parse_args()

# ------------------------- IO --------------------------

def read_text(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().splitlines(keepends=True)

def _safe_field(s: str) -> str:
    return (s or "").replace("\t", " ").replace("\n", " ").replace("\r", " ")

def _try_json(s: str):
    try:
        return json.loads(s)
    except Exception:
        return None

def _legend_plain_to_json(txt: str) -> Dict[str, Dict]:
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
    return out

def load_legend(path: Optional[str]) -> Dict[str, Dict]:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read().strip()
    if not raw:
        return {}
    obj = _try_json(raw)
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
    return norm

# --------------------- Text utils ----------------------

TAG_ANY = None  # встановлюється в main()

def is_dialog_body(body: str) -> bool:
    b = (body or "").replace(NBSP, " ").lstrip()
    return bool(b[:1] and (b[0] in DASHES or b[0] in '«"„“”\'’'))

def extract_dialogs(lines: List[str]) -> List[Tuple[int, str, str, str]]:
    out = []
    for i, ln in enumerate(lines):
        m = TAG_ANY.match(ln)
        if not m:
            continue
        indent, gid_s, body = m.groups()
        out.append((i, indent, gid_s, body))
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
    return any(v in low for v in SPEECH_VERBS)

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
    return list(forms)

def build_name_forms_map(legend: Dict[str, Dict]) -> Dict[str, str]:
    inv = {}
    for gid, rec in legend.items():
        names = rec.get("names", []) + rec.get("aliases", [])
        for nm in names:
            for form in _gen_name_forms(nm):
                inv[form.lower()] = gid
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
    return seen

def find_addressee(body: str, name_forms_inv: Dict[str, str]) -> Optional[str]:
    if not body:
        return None
    m = re.match(rf"^\s*[{re.escape(DASHES)}]?\s*([A-ZА-ЯЇІЄҐ][\w’']+)[,!]\s", body)
    if not m:
        return None
    form = m.group(1).lower()
    return name_forms_inv.get(form)

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
    rx_tok = re.compile(r"[A-ZА-ЯЇІЄҐ][\w’']+")
    for j in range(lo, hi):
        m = TAG_ANY.match(lines[j])
        text = (m.group(3) if m else lines[j]) or ""
        for tok in rx_tok.findall(text):
            gid = name_forms_inv.get(tok.lower())
            if gid and gid not in found:
                found.append(gid)
    return found

def make_queries(lines: List[str], ctx_lines: int) -> Dict[int, str]:
    queries = {}
    n = len(lines)
    for i, indent, gid_s, body in extract_dialogs(lines):
        if gid_s != "?":
            continue
        parts = [body.strip()]
        for j in range(max(0, i - ctx_lines), min(n, i + ctx_lines + 1)):
            if j == i:
                continue
            m = TAG_ANY.match(lines[j])
            if not m:
                parts.append(lines[j].strip())
            else:
                gidj = m.group(2)
                if gidj == "1":
                    parts.append((m.group(3) or "").strip())
        q = " ".join(p for p in parts if p)
        queries[i] = q
    return queries

def replace_line_gid(lines: List[str], idx: int, new_gid: str):
    m = TAG_ANY.match(lines[idx])
    indent, _, body = m.groups()
    lines[idx] = f"{indent}{new_gid}: {body}"

# --------------------- Embeddings (RoBERTa) ----------------------

class HFEmbedder:
    def __init__(self, model_name: str):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tok = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(self.device)
        self.model.eval()

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
        return torch.cat(outs, dim=0)

def cosine(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    return (a @ b.T).squeeze(0)  # за нормалізації це cosine

# --------------------------- Main ---------------------------

def main():
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    args = parse_args()
    global TAG_ANY
    # Підтримати '#g?: текст' і '#g? - текст'
    TAG_ANY = re.compile(r"^(\s*)#g(\d+|\?)\s*:?[\s]*(.*)$", re.DOTALL)

    lines = read_text(args.inp)
    legend = load_legend(args.legend)
    name_forms_inv = build_name_forms_map(legend)
    gid2name = build_gid_primary_name(legend)
    if not gid2name:
        fallback = seen_gids_from_text(lines)
        gid2name = {g: g for g in fallback}

    # Кандидати (репліки + легенда)
    def build_candidate_texts(lines_: List[str], legend_: Dict[str, Dict]) -> Dict[str, List[str]]:
        spoken = defaultdict(list)
        # беремо ВСІ попередні репліки #gN
        for i, indent, gid_s, body in extract_dialogs(lines_):
            if gid_s not in {"1", "?"}:
                spoken[f"#g{gid_s}"].append((body or "").strip())
        # додати якорі з легенди
        for gid, rec in legend_.items():
            anchors = []
            for x in rec.get("names", []) + rec.get("aliases", []):
                x = (x or "").strip()
                if x:
                    anchors.append(x)
            if anchors:
                spoken.setdefault(gid, []).extend(anchors)
        # очистити порожнє
        return {gid: [t for t in ts if t and t.strip()] for gid, ts in spoken.items() if any((t or "").strip() for t in ts)}

    cand_texts = build_candidate_texts(lines, legend)
    if not cand_texts:
        for g in sorted(gid2name.keys()):
            cand_texts[g] = [gid2name[g]]

    cand_gids_all = sorted(cand_texts.keys())
    cand_flat = [" ".join(cand_texts[g][:6]) for g in cand_gids_all]

    embedder = HFEmbedder(args.model)
    cand_emb_all = embedder.encode(cand_flat)

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
    q_emb = embedder.encode(q_texts)

    logs = []
    changed = 0
    total_unknown = 0

    def classify(idx: int, qvec: torch.Tensor, qtext: str, body_for_hints: str) -> Tuple[str, Dict]:
        # контекстні кандидати
        context_cands = collect_context_candidates(idx, lines, args.ctx_lines, name_forms_inv)
        cand_gids = context_cands if context_cands else list(cand_gids_all)

        # звертання
        addr_gid = find_addressee(body_for_hints, name_forms_inv)
        if addr_gid and addr_gid in cand_gids and len(cand_gids) > 1:
            cand_gids = [g for g in cand_gids if g != addr_gid]

        # фільтр за родом (за наявності)
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

        # ембеди кандидатів у локальному порядку
        idx_in_all = [cand_gids_all.index(g) for g in cand_gids if g in cand_gids_all]
        cand_list = [cand_gids_all[i] for i in idx_in_all]
        if not cand_list:
            # fallback: ембеди по іменах
            cand_list = list(cand_gids)
            cand_emb = embedder.encode([gid2name.get(g, g) for g in cand_list])
        else:
            cand_emb = cand_emb_all[idx_in_all, :]

        sim = cosine(qvec, cand_emb)

        # бусти
        boosts = torch.zeros_like(sim)
        if _has_speech_verb(body_for_hints):
            boosts += 0.03
        prev_gid = prev_speaker_up_to.get(idx)
        if prev_gid and prev_gid in cand_list:
            boosts[cand_list.index(prev_gid)] += 0.06

        final = sim + boosts
        order = torch.argsort(final, descending=True).tolist()
        if not order:
            return "#g?", {"reason": "no_scores", "top": [], "best": 0.0, "margin": 0.0}

        margin = float(final[order[0]].item() - final[order[1]].item()) if len(order) > 1 else 0.0
        best_gid = cand_list[order[0]]
        best_cos = float(sim[order[0]].item())
        topk = [(cand_list[k], float(sim[k].item())) for k in order[:max(1, args.topk)]]

        if args.force_when_single and len(cand_list) == 1:
            return best_gid, {"reason": "force_single", "top": topk, "best": best_cos, "margin": margin}
        if (best_cos >= args.threshold) and (margin >= args.min_margin):
            return best_gid, {"reason": "threshold", "top": topk, "best": best_cos, "margin": margin}
        return "#g?", {"reason": "low_conf", "top": topk, "best": best_cos, "margin": margin}

    # обробка #g?
    for qi, qidx in enumerate(q_idxs):
        m = TAG_ANY.match(lines[qidx])
        if args.only_unknown and (not m or m.group(2) != "?"):
            continue
        body = m.group(3) if m else ""
        qv = q_emb[qi:qi+1]
        total_unknown += 1
        decision, info = classify(qidx, qv, q_texts[qi], body)
        if decision != "#g?":
            replace_line_gid(lines, qidx, decision)
            changed += 1
        logs.append({
            "line": qidx, "decision": decision, "best_gid": decision,
            "best_score": round(info.get("best", 0.0), 4),
            "margin": round(info.get("margin", 0.0), 4),
            "top": [(g, round(s, 4)) for g, s in info.get("top", [])],
            "query": _safe_field(q_texts[qi][:400]),
            "reason": "gq_" + info.get("reason", "")
        })

    # Санітаризація: прибрати службові рядки, нормалізувати формат
    META_RX = re.compile(r"^\s*(?:gid[_\-\s]*to[_\-\s]*names|[A-Za-z_]+_gid)\s*[:：]\s*(.*)$", re.IGNORECASE)
    out_lines = []
    for ln in lines:
        has_nl = ln.endswith("\n")
        m_bad = META_RX.match(ln)
        if m_bad:
            body = m_bad.group(1).lstrip("- ").lstrip()
            out_lines.append(f"#g?: {body}" + ("\n" if has_nl else ""))
            continue
        m = TAG_ANY.match(ln)
        if m:
            indent, gid_s, body = m.groups()
            body = (body or "").lstrip("- ").lstrip()
            out_lines.append(f"{indent}#g{gid_s}: {body}" + ("\n" if has_nl else ""))
        else:
            out_lines.append(ln)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("".join(out_lines))

    if args.log:
        with open(args.log, "w", encoding="utf-8") as f:
            f.write("line_idx\tdecision\tbest_gid\tbest_score\tmargin\ttop\tquery\treason\n")
            for r in logs:
                top_str = ";".join([f"{g}:{p:.3f}" for g, p in r["top"]])
                f.write(f"{r['line']}\t{r['decision']}\t{r['best_gid']}\t{r['best_score']:.3f}\t{r['margin']:.3f}\t{top_str}\t{r['query']}\t{r.get('reason','')}\n")

    print("[roberta_zeroshot] Done. Edited ->", args.out)
    print(f"[roberta_zeroshot] Unknown lines total: {total_unknown}, changed: {changed}")
    if args.log:
        print("[roberta_zeroshot] Log ->", args.log)

if __name__ == "__main__":
    main()
