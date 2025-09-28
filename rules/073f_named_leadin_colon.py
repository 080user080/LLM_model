# 073f_named_leadin_colon.py — «… Ім'я … поцікавився/повідомила/… :» → наступна репліка = це Ім'я
# -*- coding: utf-8 -*-
import re

PHASE, PRIORITY, SCOPE, NAME = 73, 8, "fulltext", "named_leadin_colon"

NBSP = "\u00A0"
TAG  = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
DASH = "-\u2012\u2013\u2014\u2015"
IS_DLG = re.compile(r"^\s*(?:[" + re.escape(DASH) + r"]|[«\"„“”'’])")
ENDP = r"[\.!\?…\"”»]"
# Якщо в самій репліці вже є явна інлайн-атрибуція — не перетираємо
INLINE_NAME_ATTR = re.compile(
    IS_DLG.pattern + r".*?" + ENDP + r"?\s*[" + re.escape(DASH) + r"]\s*[A-ZА-ЯЇІЄҐ][\w’'\-]+",
    re.DOTALL
)

# Дієслова мовлення/повідомлення (розширений список)
VERBS_M = r"(сказав|повідомив|запитав|спитав|поцікавився|крикнув|вигукнув|прошепотів|промовив|відповів|буркнув|процедив|торохтів|заторохтів)"
VERBS_F = r"(сказала|повідомила|запитала|спитала|поцікавилася|крикнула|вигукнула|прошепотіла|промовила|відповіла|буркнула|процедила|торохтіла|заторохтіла)"
VERBS_N = r"(каже|говорить|повідомляє|питає|запитує|відповідає|вигукує|кричить|шепоче|промовляє|бурчить|торохтить)"
VERB_ANY = re.compile(rf"(?:{VERBS_M}|{VERBS_F}|{VERBS_N})", re.IGNORECASE)

def _nrm(s: str) -> str: return (s or "").replace(NBSP, " ").strip()

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

def _gid_by_name(name_txt, amap, rg):
    key = _nrm(name_txt).casefold()
    gid = amap.get(key)
    if gid: return gid
    for g, rec in rg.items():
        pool = set()
        pool.update(_nrm(x).casefold() for x in (rec.get("names") or []))
        pool.update(_nrm(x).casefold() for x in (rec.get("aliases") or []))
        if key in pool: return g
    return None

def _extract_name_from_leadin(lead: str, name_rx: re.Pattern) -> str | None:
    """З рядка-наративу, що закінчується на «:», дістає останнє ім'я перед двокрапкою за умови наявності дієслова мовлення."""
    t = _nrm(lead)
    if ":" not in t: 
        return None
    pre = t.rsplit(":", 1)[0]
    # перевіряємо, що поблизу кінця є дієслово мовлення
    tail = pre[-120:]  # достатньо останніх 120 символів
    if not VERB_ANY.search(tail):
        return None
    last = None
    for m in name_rx.finditer(pre):
        last = m.group("name")
    return last

def _is_dialog_line(line: str) -> bool:
    m = TAG.match(line)
    if not m: return False
    gid, body = m.group(2), m.group(3)
    if gid == "1": return False
    return bool(IS_DLG.match((body or "").lstrip()))

LOOKAHEAD = 2  # наскільки далеко шукати наступну репліку

def apply(text: str, ctx):
    amap = _legend_alias_map(ctx); rg = _roles_gender(ctx)
    name_rx = _name_rx(_candidate_names(amap, rg))

    lines = text.splitlines(keepends=True)
    retagged = 0

    for i in range(len(lines)):
        raw = lines[i]
        # беремо або чистий наратив, або #g1 як лідін
        m = TAG.match(raw)
        lead = None
        if m and m.group(2) == "1":
            lead = m.group(3) or ""
        elif not m:
            lead = raw

        if not lead:
            continue

        name_txt = _extract_name_from_leadin(lead, name_rx)
        if not name_txt:
            continue

        gid_target = _gid_by_name(name_txt, amap, rg)
        if not gid_target or gid_target == "#g1":
            continue

        # перетеглюємо найближчу наступну діалогову репліку
        for j in range(i + 1, min(len(lines), i + 1 + LOOKAHEAD)):
            mj = TAG.match(lines[j])
            if not mj:
                continue
            ind, gid_s, body = mj.groups()
            if not _is_dialog_line(lines[j]):
                continue
            if INLINE_NAME_ATTR.search(body or ""):
                break  # є явна атрибуція у самій репліці — не чіпаємо
            if f"#g{gid_s}" == gid_target:
                break  # вже правильно
            lines[j] = f"{ind}{gid_target}: {body}"
            retagged += 1
            break

    try:
        ctx.logs.append(f"[073f named_leadin_colon] retagged:{retagged}")
    except Exception:
        pass

    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
