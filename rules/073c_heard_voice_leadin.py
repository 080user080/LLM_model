# 073c_heard_voice_leadin.py — «… голос Ім'я:» → наступна репліка = Ім'я (з урахуванням відмін)
# -*- coding: utf-8 -*-
import re

PHASE, PRIORITY, SCOPE, NAME = 73, 8, "fulltext", "heard_voice_leadin"

NBSP = "\u00A0"
TAG  = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
DASH = "-\u2012\u2013\u2014\u2015"
IS_DLG = re.compile(r"^\s*(?:[" + re.escape(DASH) + r"]|[«\"„“”'’])")
ENDP = r"[\.!\?…\"”»]"
INLINE_NAME_ATTR = re.compile(
    IS_DLG.pattern + r".*?" + ENDP + r"?\s*[" + re.escape(DASH) + r"]\s*[A-ZА-ЯЇІЄҐ][\w’'\-]+",
    re.DOTALL
)

# Ловимо будь-яке ім'я після "голос ...:"
VOICE_RX = re.compile(
    r"\bголос\s+(?P<name>[A-ZА-ЯЇІЄҐ][\w’'\-]+(?:\s+[A-ZА-ЯЇІЄҐ][\w’'\-]+)?)\s*:\s*$",
    re.IGNORECASE
)

_LAT2CYR = str.maketrans("aceopxyiACEOPXYI", "асеорхуіАСЕОРХУІ")
def _nrm(s:str)->str: return (s or "").translate(_LAT2CYR).strip()

def _legend_map(ctx):
    amap = (getattr(ctx,"metadata",{}) or {}).get("legend") or {}
    return {(k or "").strip().casefold(): v for k,v in amap.items()}

def _roles_gender(ctx):
    return (getattr(ctx,"metadata",{}) or {}).get("roles_gender") or {}

def _pool_names(amap, rg):
    pool = set(amap.keys())
    for _,rec in rg.items():
        for nm in (rec.get("names") or []):   pool.add(_nrm(nm).casefold())
        for al in (rec.get("aliases") or []): pool.add(_nrm(al).casefold())
    # без дужок, помірної довжини
    return {p for p in pool if "(" not in p and ")" not in p and 1 < len(p) <= 50}

def _lev(a,b):
    a,b = a.lower(), b.lower()
    n,m = len(a), len(b)
    if n==0: return m
    if m==0: return n
    dp = list(range(m+1))
    for i in range(1,n+1):
        prev, dp[0] = dp[0], i
        for j in range(1,m+1):
            cur = prev if a[i-1]==b[j-1] else prev+1
            cur = min(cur, dp[j]+1, dp[j-1]+1)
            prev, dp[j] = dp[j], cur
    return dp[m]

def _fuzzy_equal(cand, base):
    c = cand.casefold(); b = base.casefold()
    if c == b: return True
    # спец: «й» ↔ «я» в кінці (Той → Тоя)
    if b.endswith("й") and c.endswith("я") and b[:-1] == c[:-1]:
        return True
    # прості відмінки: приберемо типові фінали
    strip = ["ою","ею","єм","ем","ом","ою","єю","ами","ові","еві","ї","ю","у","а","і","е","ою","ою"]
    for suf in strip:
        if c.endswith(suf) and c[:-len(suf)] == b: return True
        if b.endswith(suf) and b[:-len(suf)] == c: return True
    # дозволимо маленьку різницю
    return _lev(c, b) <= 1

def _gid_by_name_fuzzy(name_txt, amap, rg):
    key = _nrm(name_txt).casefold()
    # точний збіг з легендою
    if key in amap: return amap[key]
    # fuzzy проти всіх імен/аліасів
    pool = _pool_names(amap, rg)
    best, best_gid, best_d = None, None, 10
    for gid_name, gid in amap.items():
        if _fuzzy_equal(key, gid_name):
            return gid
    # якщо не знайшли напряму, пройдемося по roles_gender
    for g, rec in rg.items():
        for nm in (rec.get("names") or []) + (rec.get("aliases") or []):
            base = _nrm(nm).casefold()
            d = _lev(key, base)
            if d < best_d:
                best, best_gid, best_d = base, g, d
    if best_gid and (best_d <= 1 or (best_d == 2 and len(key) >= 6)):
        return best_gid
    return None

def _is_dialog_line(line: str) -> bool:
    m = TAG.match(line)
    if not m: return False
    gid, body = m.group(2), m.group(3)
    if gid == "1": return False
    return bool(IS_DLG.match((body or "").replace(NBSP, " ").lstrip()))

LOOKAHEAD = 2

def apply(text: str, ctx):
    amap = _legend_map(ctx); rg = _roles_gender(ctx)
    lines = text.splitlines(keepends=True)
    retagged = 0

    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped:
            continue

        # підтримуємо як простий рядок, так і #g1-наратив
        body = stripped
        m1 = TAG.match(raw)
        if m1 and m1.group(2) == "1":
            body = (m1.group(3) or "").strip()

        mm = VOICE_RX.search(_nrm(body))
        if not mm:
            continue

        name = _nrm(mm.group("name"))
        gid_target = _gid_by_name_fuzzy(name, amap, rg)
        if not gid_target or gid_target == "#g1":
            continue

        # Перетеглюємо найближчу наступну діалогову репліку (в межах 2 рядків)
        for j in range(i + 1, min(len(lines), i + 1 + LOOKAHEAD)):
            mj = TAG.match(lines[j])
            if not mj:
                continue
            ind, gid_j, body_j = mj.groups()
            if not _is_dialog_line(lines[j]):
                continue
            if INLINE_NAME_ATTR.search(body_j or ""):
                break
            lines[j] = f"{ind}{gid_target}: {body_j}"
            retagged += 1
            break

    try:
        ctx.logs.append(f"[073c heard_voice] retagged:{retagged}")
    except Exception:
        pass

    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
