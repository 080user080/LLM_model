# 099_metrics_report.py — метрики покриття/точності для розмітки діалогів
# -*- coding: utf-8 -*-
"""
Що рахує (нічого в тексті не змінює):
  • Покриття: частка діалогових рядків, де мовець призначений (#gN, N>=2).
  • Unknown: скільки #g? серед діалогів.
  • За сценами: покриття по кожній сцені (якщо meta.scenes/scene_spans є).
  • Точність (якщо є "gold"): accuracy, macro/micro P/R/F1, confusion.
      Джерела "gold":
        - ctx.metadata["gold_labels_by_line"] = {line_idx:int -> "#gN":str}
        - Інлайн у тексті (будь-де в рядку):
            ⟦#gN⟧   |   {gold:#gN}   |   // GOLD: #gN   |   # GOLD #gN
Лог: один рядок з агрегатами. Деталізований звіт кладеться у ctx.metadata["metrics"].
"""

import re
from collections import defaultdict, Counter

PHASE, PRIORITY, SCOPE, NAME = 99, 0, "fulltext", "metrics_report"  # запускати найпізніше

NBSP = "\u00A0"
TAG = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
DASHES = r"\-\u2012\u2013\u2014\u2015"
IS_DIALOG_BODY = re.compile(rf"^\s*(?:[{DASHES}]|[«\"„“”'’])")

# Інлайн-«gold» маркери
GOLD_PATTERNS = [
    re.compile(r"⟦\s*(#g\d+)\s*⟧", re.IGNORECASE),
    re.compile(r"\{gold\s*:\s*(#g\d+)\}", re.IGNORECASE),
    re.compile(r"//\s*gold\s*:\s*(#g\d+)", re.IGNORECASE),
    re.compile(r"#\s*gold\s*(#g\d+)", re.IGNORECASE),
]

def _meta(ctx): return getattr(ctx, "metadata", {}) or {}

def _scene_of_line(i, meta):
    for sp in (meta.get("scene_spans") or []):
        if sp["start"] <= i <= sp["end"]:
            return sp["label"]
    return meta.get("scene")

def _is_dialog_line(line: str) -> bool:
    m = TAG.match(line)
    if not m: return False
    gid, body = m.group(2), m.group(3)
    if gid == "1": return False
    return bool(IS_DIALOG_BODY.match((body or "").replace(NBSP, " ").lstrip()))

def _collect_gold(text: str, meta):
    # 1) з метаданих
    gold = {}
    md_gold = meta.get("gold_labels_by_line") or {}
    for k, v in md_gold.items():
        try:
            i = int(k)
            if isinstance(v, str) and v.startswith("#g"):
                gold[i] = v
        except Exception:
            continue
    # 2) з інлайн-маркерів у тексті
    for i, raw in enumerate(text.splitlines(keepends=False)):
        for rx in GOLD_PATTERNS:
            m = rx.search(raw)
            if m:
                gold[i] = m.group(1)
                break
    return gold

def _per_gid_prf(tp, fp, fn):
    prf = {}
    gids = set(tp) | set(fp) | set(fn)
    for g in gids:
        t, p, n = tp.get(g, 0), fp.get(g, 0), fn.get(g, 0)
        prec = (t / (t + p)) if (t + p) > 0 else None
        rec  = (t / (t + n)) if (t + n) > 0 else None
        f1   = (2*prec*rec/(prec+rec)) if (prec is not None and rec is not None and (prec+rec)>0) else None
        prf[g] = {"precision": prec, "recall": rec, "f1": f1, "tp": t, "fp": p, "fn": n}
    return prf

def _micro_prf(tp, fp, fn):
    T = sum(tp.values()); P = T + sum(fp.values()); N = T + sum(fn.values())
    prec = (T / P) if P > 0 else None
    rec  = (T / N) if N > 0 else None
    f1   = (2*prec*rec/(prec+rec)) if (prec is not None and rec is not None and (prec+rec)>0) else None
    return {"precision": prec, "recall": rec, "f1": f1}

def _macro_prf(per_gid):
    vals = [v for v in per_gid.values() if v["precision"] is not None and v["recall"] is not None and v["f1"] is not None]
    if not vals:
        return {"precision": None, "recall": None, "f1": None}
    n = len(vals)
    return {
        "precision": sum(v["precision"] for v in vals)/n,
        "recall":    sum(v["recall"]    for v in vals)/n,
        "f1":        sum(v["f1"]        for v in vals)/n,
    }

def apply(text: str, ctx):
    meta = _meta(ctx)
    lines = text.splitlines(keepends=True)

    # --- Покриття загалом та по сценах ---
    dialog_idx = []
    assigned_idx = []
    unknown_idx = []

    by_scene_total = Counter()
    by_scene_assigned = Counter()
    by_scene_unknown = Counter()

    for i, ln in enumerate(lines):
        if not _is_dialog_line(ln): 
            continue
        dialog_idx.append(i)
        m = TAG.match(ln)
        gid = m.group(2)
        scene = _scene_of_line(i, meta) or "(без сцени)"
        by_scene_total[scene] += 1
        if gid == "?":
            unknown_idx.append(i)
            by_scene_unknown[scene] += 1
        else:
            assigned_idx.append(i)
            by_scene_assigned[scene] += 1

    cov_total = (len(assigned_idx) / len(dialog_idx)) if dialog_idx else None
    unk_rate  = (len(unknown_idx)  / len(dialog_idx)) if dialog_idx else None

    coverage_by_scene = {}
    for s in sorted(by_scene_total.keys()):
        tot = by_scene_total[s]
        asc = by_scene_assigned[s]
        unk = by_scene_unknown[s]
        coverage_by_scene[s] = {
            "dialog_total": tot,
            "assigned": asc,
            "unknown": unk,
            "coverage": (asc/tot) if tot else None,
            "unknown_rate": (unk/tot) if tot else None,
        }

    # --- Точність (якщо є gold) ---
    gold = _collect_gold(text, meta)
    gold_dialog_lines = [i for i in gold.keys() if i < len(lines) and _is_dialog_line(lines[i])]
    correct = 0
    conf = defaultdict(int)  # (pred,gold) → count
    tp = Counter(); fp = Counter(); fn = Counter()

    for i in gold_dialog_lines:
        m = TAG.match(lines[i]); 
        if not m: 
            continue
        pred_gid = f"#g{m.group(2)}"
        gold_gid = gold[i]
        conf[(pred_gid, gold_gid)] += 1
        if pred_gid == gold_gid:
            correct += 1
            tp[gold_gid] += 1
        else:
            # Не рахуємо #g1 у класифікаційні метрики
            if pred_gid not in {"#g1"}:
                fp[pred_gid] += 1
            if gold_gid not in {"#g1"}:
                fn[gold_gid] += 1

    acc = (correct / len(gold_dialog_lines)) if gold_dialog_lines else None
    per_gid = _per_gid_prf(tp, fp, fn)
    micro = _micro_prf(tp, fp, fn) if gold_dialog_lines else {"precision": None, "recall": None, "f1": None}
    macro = _macro_prf(per_gid) if gold_dialog_lines else {"precision": None, "recall": None, "f1": None}

    # --- Пакуємо у метадані ---
    report = {
        "coverage": {
            "dialog_total": len(dialog_idx),
            "assigned": len(assigned_idx),
            "unknown": len(unknown_idx),
            "coverage": cov_total,
            "unknown_rate": unk_rate,
            "by_scene": coverage_by_scene,
        },
        "accuracy": {
            "gold_lines": len(gold_dialog_lines),
            "correct": correct,
            "accuracy": acc,
            "micro": micro,
            "macro": macro,
            "per_gid": per_gid,
            "confusion": {f"{k[0]}->{k[1]}": v for k, v in conf.items()},
        },
    }
    meta["metrics"] = report
    setattr(ctx, "metadata", meta)

    # --- Лог (коротко) ---
    try:
        cov_pct = f"{(cov_total*100):.1f}%" if cov_total is not None else "n/a"
        unk_pct = f"{(unk_rate*100):.1f}%" if unk_rate is not None else "n/a"
        acc_pct = f"{(acc*100):.1f}%" if acc is not None else "n/a"
        ctx.logs.append(f"[099 metrics] coverage:{cov_pct} unknown:{unk_pct} | gold:{len(gold_dialog_lines)} acc:{acc_pct} microF1:{(report['accuracy']['micro']['f1']*100):.1f}%"
                        if report['accuracy']['micro']['f1'] is not None else
                        f"[099 metrics] coverage:{cov_pct} unknown:{unk_pct} | gold:0 acc:n/a")
    except Exception:
        pass

    return text

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME  #GPT
