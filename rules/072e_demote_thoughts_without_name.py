# 072e_demote_thoughts_without_name.py — думки після репліки («…» — подумки …) без імені → #g?
# -*- coding: utf-8 -*-
import re

PHASE, PRIORITY, SCOPE, NAME = 72, 12, "fulltext", "demote_thoughts_without_name"  # перед 074_pair_lock

TAG = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
DASHES = "-\u2012\u2013\u2014\u2015"
QUOTE_OPEN  = "«\"„“”'’"
QUOTE_CLOSE = "»\"”'’"
IS_QUOTED = re.compile(r"^\s*[" + re.escape(QUOTE_OPEN) + r"].+[" + re.escape(QUOTE_CLOSE) + r"]")
# «…» ,/— tail
AFTER_QUOTE = re.compile(r"^\s*[" + re.escape(QUOTE_OPEN) + r"].+[" + re.escape(QUOTE_CLOSE) + r"]\s*[, \t]*[" + re.escape(DASHES) + r"]\s*(?P<tail>.+)$", re.DOTALL)

# індикатори «думок» у хвості атрибуції (мінімально: «подумки …», також дозволяємо «подумав/подумала …»)
THOUGHT_CUES = re.compile(r"\b(подумки|подумав|подумала|міркував|міркувала|розмірковував|розмірковувала)\b", re.IGNORECASE)

_LAT2CYR = str.maketrans("aceopxyiACEOPXYI", "асеорхуіАСЕОРХУІ")
def _nrm(s:str)->str: return (s or "").translate(_LAT2CYR).strip()

def _legend_alias_map(ctx):
    amap = (getattr(ctx, "metadata", {}) or {}).get("legend") or {}
    return {(k or "").strip().casefold(): v for k, v in amap.items()}

def _roles_gender(ctx):
    return (getattr(ctx, "metadata", {}) or {}).get("roles_gender") or {}

def _candidate_names(amap, rg):
    s = set(amap.keys())
    for _, rec in rg.items():
        for nm in (rec.get("names") or []):
            if nm: s.add(_nrm(nm).casefold())
        for al in (rec.get("aliases") or []):
            if al: s.add(_nrm(al).casefold())
    return {c for c in s if "(" not in c and ")" not in c and 1 < len(c) <= 50}

def _name_rx(cands):
    if not cands:
        return re.compile(r"(?P<name>[A-ZА-ЯЇІЄҐ][\w’'\-]+(?:\s+[A-ZА-ЯЇІЄҐ][\w’'\-]+)?)", re.IGNORECASE)
    alt = "|".join(re.escape(c) for c in sorted(cands, key=len, reverse=True))
    return re.compile(rf"(?P<name>{alt})", re.IGNORECASE)

def apply(text: str, ctx):
    amap = _legend_alias_map(ctx); rg = _roles_gender(ctx)
    name_rx = _name_rx(_candidate_names(amap, rg))

    lines = text.splitlines(keepends=True)
    demoted = 0

    for i, ln in enumerate(lines):
        m = TAG.match(ln)
        if not m: continue
        indent, gid_s, body = m.groups()
        if gid_s == "1": continue  # наратив не чіпаємо

        b = (body or "").strip()
        if not IS_QUOTED.match(b): 
            continue

        mm = AFTER_QUOTE.match(b)
        if not mm: 
            continue

        tail = _nrm(mm.group("tail"))
        if not THOUGHT_CUES.search(tail):
            continue  # це не «думки», лишаємо як є

        # якщо в хвості є ім'я з легенди — хай вирішує 072d (ім'я + дієслово)
        if name_rx.search(tail):
            continue

        # без імені: це внутрішні думки → не нав'язуємо мовця
        lines[i] = f"{indent}#g?: {body}"
        demoted += 1

    try:
        ctx.logs.append(f"[072e thoughts_no_name] demoted:{demoted}")
    except Exception:
        pass

    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
