# 077c_fill_gap_between_same_speaker.py — #gX … #g? … #gX → підставляємо «іншого» з недавнього контексту
# -*- coding: utf-8 -*-
import re

PHASE, PRIORITY, SCOPE, NAME = 77, 2, "fulltext", "fill_gap_between_same_speaker"

NBSP = "\u00A0"
TAG  = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
DASH = "-\u2012\u2013\u2014\u2015"
IS_DLG = re.compile(r"^\s*(?:[" + re.escape(DASH) + r"]|[«\"„“”'’])")
ENDP = r"[\.!\?…\"”»]"

# не торкаємось реплік з явною інлайн-атрибуцією
VERBS_ANY = r"(?:сказав|сказала|каже|відповів|відповіла|говорить|питає|запитав|запитала|крикнув|крикнула|закричала|вигукнув|вигукнула|прошепотів|прошепотіла|буркнув|буркнула|промовив|промовила|пояснив|пояснила|гукнув|гукнула|відказав|відказала|додав|додала|зазначив|зазначила|просить|велить|нагадує)"
INLINE_NAME_ATTR = re.compile(
    r"" + ENDP + r"\s*[" + re.escape(DASH) + r"]\s*(?:" + VERBS_ANY + r"\s+[A-ZА-ЯЇІЄҐ][\w’'\-]+|[A-ZА-ЯЇІЄҐ][\w’'\-]+\s*(?:,\s*)?" + VERBS_ANY + r")",
    re.IGNORECASE | re.DOTALL
)

# слабі індикатори, що це питання/звертання до співрозмовника
SECOND_PERSON_HINT = re.compile(r"\b(ти|ви)\b", re.IGNORECASE)
HAS_QMARK = re.compile(r"\?")

def _nrm(s:str)->str: return (s or "").replace(NBSP, " ").strip()

def _is_dialog_line(ln: str) -> bool:
    m = TAG.match(ln)
    if not m: return False
    gid, body = m.group(2), m.group(3)
    if gid == "1": return False
    return bool(IS_DLG.match((body or "").lstrip()))

def _prev_known(lines, i, max_skip=2):
    """знайти найближчий зверху тег #gN (N!=1,?); дозволити до max_skip порожніх/#g1 рядків між ними"""
    skipped = 0
    j = i - 1
    while j >= 0 and skipped <= max_skip:
        ln = lines[j]
        if not ln.strip(): 
            skipped += 1; j -= 1; continue
        m = TAG.match(ln)
        if m:
            gid = m.group(2)
            if gid == "1": 
                skipped += 1; j -= 1; continue
            if _is_dialog_line(ln) and gid != "?":
                return f"#g{gid}", j
        else:
            skipped += 1
        j -= 1
    return None, None

def _next_known(lines, i, max_skip=2):
    skipped = 0
    j = i + 1
    n = len(lines)
    while j < n and skipped <= max_skip:
        ln = lines[j]
        if not ln.strip():
            skipped += 1; j += 1; continue
        m = TAG.match(ln)
        if m:
            gid = m.group(2)
            if gid == "1":
                skipped += 1; j += 1; continue
            if _is_dialog_line(ln) and gid != "?":
                return f"#g{gid}", j
        else:
            skipped += 1
        j += 1
    return None, None

def _recent_other(lines, i, cur_gid, back=20):
    """знайти найближчого зверху «іншого» спікера (≠ cur_gid) в останніх back рядках"""
    j = i - 1
    cnt = 0
    while j >= 0 and cnt < back:
        m = TAG.match(lines[j])
        if m:
            gid = m.group(2)
            if gid not in ("1","?"):
                g = f"#g{gid}"
                if g != cur_gid and _is_dialog_line(lines[j]):
                    return g
        j -= 1; cnt += 1
    return None

def apply(text: str, ctx):
    lines = text.splitlines(keepends=True)
    fixed = 0

    for i, ln in enumerate(lines):
        m = TAG.match(ln)
        if not m: 
            continue
        ind, gid_s, body = m.groups()
        if gid_s != "?":
            continue
        if not _is_dialog_line(ln):
            continue
        b = _nrm(body)
        if INLINE_NAME_ATTR.search(b or ""):
            continue

        # шаблон «#gX …   #g? …   #gX …» (допускаємо 1–2 порожні / #g1 між)
        left_gid, _ = _prev_known(lines, i, max_skip=2)
        right_gid,_ = _next_known(lines, i, max_skip=2)
        if not left_gid or not right_gid:
            continue
        if left_gid != right_gid:
            continue  # не «сендвіч» одного і того ж

        # кого підставляти? шукаємо «іншого» з недавнього контексту
        other = _recent_other(lines, i, left_gid, back=20)
        if not other:
            continue

        # мінімальні змістові ознаки: питання або звертання «ти/ви»
        if not (HAS_QMARK.search(b) or SECOND_PERSON_HINT.search(b)):
            continue

        # підставляємо
        lines[i] = f"{ind}{other}: {body}"
        fixed += 1

    try:
        ctx.logs.append(f"[077c fill_gap_between_same] fixed:{fixed}")
    except Exception:
        pass

    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME