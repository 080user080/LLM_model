# 073e_rank_title_leadin.py — «…вождь/ватажок…» у наративі → найближча #g? = відповідний персонаж (Той/ватажок)
# -*- coding: utf-8 -*-
import re

PHASE, PRIORITY, SCOPE, NAME = 73, 5, "fulltext", "rank_title_leadin"

NBSP = "\u00A0"
TAG  = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
DASH = "-\u2012\u2013\u2014\u2015"
IS_DLG = re.compile(r"^\s*(?:[" + re.escape(DASH) + r"]|[«\"„“”'’])")
ENDP = r"[\.!\?…\"”»]"
INLINE_NAME_ATTR = re.compile(
    IS_DLG.pattern + r".*?" + ENDP + r"?\s*[" + re.escape(DASH) + r"]\s*[A-ZА-ЯЇІЄҐ][\w’'\-]+",
    re.DOTALL
)
TITLE_RX = re.compile(r"\b(вожд\w*|ватаж\w*|лідер\w*)\b", re.IGNORECASE)

def _nrm(s:str)->str: return (s or "").replace(NBSP, " ").strip()

def _legend_alias_map(ctx):
    amap = (getattr(ctx,"metadata",{}) or {}).get("legend") or {}
    return {(k or "").strip().casefold(): v for k,v in amap.items()}

def _roles_gender(ctx):
    return (getattr(ctx,"metadata",{}) or {}).get("roles_gender") or {}

def _find_name_gid(text, amap, rg):
    t = _nrm(text).casefold()
    # точний збіг по alias/імені
    for key,g in amap.items():
        if key and key in t:
            return g
    for g,rec in rg.items():
        pool = []
        pool += [(_nrm(x).casefold()) for x in (rec.get("names") or [])]
        pool += [(_nrm(x).casefold()) for x in (rec.get("aliases") or [])]
        if any(p and p in t for p in pool):
            return g
    return None

def _find_title_gid(text, rg):
    if not TITLE_RX.search(text): return None
    cand = []
    for g,rec in rg.items():
        roles = " ".join(rec.get("roles") or []).casefold()
        if any(k in roles for k in ("ватаж", "вожд", "лідер")):
            cand.append(g)
    # якщо кілька — беремо перший стабільно (звичайно це #g8)
    return cand[0] if cand else None

def _is_dialog_line(ln: str) -> bool:
    m = TAG.match(ln)
    if not m: return False
    gid, body = m.group(2), m.group(3)
    if gid == "1": return False
    return bool(IS_DLG.match((body or "").lstrip()))

LOOKBACK = 2
LOOKAHEAD = 2

def apply(text: str, ctx):
    amap = _legend_alias_map(ctx); rg = _roles_gender(ctx)
    lines = text.splitlines(keepends=True)
    retag = 0

    for i, ln in enumerate(lines):
        m = TAG.match(ln)
        if not m: 
            continue
        ind, gid_s, body = m.groups()
        if gid_s != "?": 
            continue
        if not _is_dialog_line(ln): 
            continue
        if INLINE_NAME_ATTR.search(body or ""):
            continue

        # дивимось 1–2 рядки вище на наратив / #g1
        gid_target = None
        for j in range(max(0, i-LOOKBACK), i):
            mj = TAG.match(lines[j])
            txt = None
            if mj and mj.group(2) == "1":
                txt = mj.group(3) or ""
            elif not mj:
                txt = lines[j]
            if not txt: 
                continue
            # спершу явне ім'я
            gid_target = _find_name_gid(txt, amap, rg)
            if gid_target: break
            # інакше — титул (вождь/ватажок/лідер)
            gid_target = _find_title_gid(txt, rg)
            if gid_target: break

        if not gid_target: 
            continue

        lines[i] = f"{ind}{gid_target}: {body}"
        retag += 1

    try:
        ctx.logs.append(f"[073e rank_title_leadin] retagged:{retag}")
    except Exception:
        pass

    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
