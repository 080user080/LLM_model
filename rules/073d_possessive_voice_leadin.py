# 073d_possessive_voice_leadin.py — «… Ім'я … (його/її) голос:» → наступна репліка = Ім'я
# -*- coding: utf-8 -*-
import re

PHASE, PRIORITY, SCOPE, NAME = 73, 9, "fulltext", "possessive_voice_leadin"

NBSP = "\u00A0"
TAG  = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
DASH = "-\u2012\u2013\u2014\u2015"
IS_DLG = re.compile(r"^\s*(?:[" + re.escape(DASH) + r"]|[«\"„“”'’])")
VOICE_COLON = re.compile(r"\bголос\s*:\s*$", re.IGNORECASE)

_LAT2CYR = str.maketrans("aceopxyiACEOPXYI", "асеорхуіАСЕОРХУІ")
def _nrm(s:str)->str: return (s or "").translate(_LAT2CYR).strip()

def _legend_map(ctx):
    amap = (getattr(ctx,"metadata",{}) or {}).get("legend") or {}
    return {(k or "").strip().casefold(): v for k,v in amap.items()}

def _roles_gender(ctx):
    return (getattr(ctx,"metadata",{}) or {}).get("roles_gender") or {}

def _cand_names(amap, rg):
    s = set(amap.keys())
    for _, rec in rg.items():
        for nm in (rec.get("names") or []):   s.add(_nrm(nm).casefold())
        for al in (rec.get("aliases") or []): s.add(_nrm(al).casefold())
    return {c for c in s if "(" not in c and ")" not in c and 1 < len(c) <= 50}

def _name_rx(cands):
    if not cands:
        return re.compile(r"(?P<name>[A-ZА-ЯЇІЄҐ][\w’'\-]+(?:\s+[A-ZА-ЯЇІЄҐ][\w’'\-]+)?)", re.IGNORECASE)
    alt = "|".join(re.escape(c) for c in sorted(cands, key=len, reverse=True))
    return re.compile(rf"(?P<name>{alt})", re.IGNORECASE)

def _gid_by_name(name_txt, amap, rg):
    key = _nrm(name_txt).casefold()
    if key in amap: return amap[key]
    for g, rec in rg.items():
        pool = set()
        pool.update(_nrm(x).casefold() for x in (rec.get("names") or []))
        pool.update(_nrm(x).casefold() for x in (rec.get("aliases") or []))
        if key in pool: return g
    return None

def _closest_name_to_voice(line_nrm, name_rx):
    """Знаходимо ім'я, найближче до слова 'голос' ліворуч (працює для «… Тіба … голос:» і «її голос:»)."""
    m_col = VOICE_COLON.search(line_nrm)
    if not m_col: return None
    cut = line_nrm[:m_col.start()]  # все, що ЛІВОРУЧ від «голос:»
    best, best_pos = None, -1
    for m in name_rx.finditer(cut):
        pos = m.start()
        if pos > best_pos:
            best, best_pos = m.group("name"), pos
    return best

def _is_dialog_line(line: str) -> bool:
    m = TAG.match(line)
    if not m: return False
    gid, body = m.group(2), m.group(3)
    if gid == "1": return False
    return bool(IS_DLG.match((body or "").replace(NBSP," ").lstrip()))

LOOKAHEAD = 2

def apply(text: str, ctx):
    amap = _legend_map(ctx); rg = _roles_gender(ctx)
    name_rx = _name_rx(_cand_names(amap, rg))

    lines = text.splitlines(keepends=True)
    retag = 0

    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped:
            continue

        # підтримуємо і чистий рядок, і #g1-наратив як лідін
        body = stripped
        m1 = TAG.match(raw)
        if m1 and m1.group(2) == "1":
            body = (m1.group(3) or "").strip()

        bnorm = _nrm(body)
        if not VOICE_COLON.search(bnorm):
            continue

        name_txt = _closest_name_to_voice(bnorm, name_rx)
        if not name_txt:
            continue
        gid_target = _gid_by_name(name_txt, amap, rg)
        if not gid_target or gid_target == "#g1":
            continue

        # Перетеглюємо найближчу наступну діалогову репліку
        for j in range(i + 1, min(len(lines), i + 1 + LOOKAHEAD)):
            mj = TAG.match(lines[j])
            if not mj: 
                continue
            ind, gid_j, body_j = mj.groups()
            if not _is_dialog_line(lines[j]):
                continue
            lines[j] = f"{ind}{gid_target}: {body_j}"
            retag += 1
            break

    try:
        ctx.logs.append(f"[073d possessive_voice] retagged:{retag}")
    except Exception:
        pass

    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
