# 072g_inline_first_person_sayer.py — «— … — Повторюю/кажу/…» → first_person_gid
# -*- coding: utf-8 -*-
import re
PHASE, PRIORITY, SCOPE, NAME = 72, 12, "fulltext", "inline_first_person_sayer"

NBSP = "\u00A0"
TAG  = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
DASH = "-\u2012\u2013\u2014\u2015"
OPEN = "«\"„“”'’"
CLOS = "»\"”'’"
IS_DLG = re.compile(r"^\s*(?:[" + re.escape(DASH) + r"]|[" + re.escape(OPEN) + r"])")

# дієслова 1-ї особи одн. (додавай за потреби)
FP_VERBS = r"(повторюю|кажу|говорю|відповідаю|питаю|запитую|показую|обзиваю|киваю|наголошую|зазначаю|прошу|гукаю|відказую)"

# «початкова репліка» + інлайн-частина з 1-ою особою:
#  — … [".!?]  —  <tail з 1-ої особи>  (перед наступним тире або кінцем рядка)
PAT = re.compile(
    r"^\s*(?:[" + re.escape(DASH) + r"]|[" + re.escape(OPEN) + r"]).+?(?:[" + re.escape(CLOS) + r"]|[\.!\?…])?"
    r"\s*[" + re.escape(DASH) + r"]\s*(?P<tail>.+?)\s*(?:[" + re.escape(DASH) + r"]|$)",
    re.DOTALL
)

def _first_gid(ctx):
    return (getattr(ctx, "metadata", {}) or {}).get("hints", {}).get("first_person_gid")

def _is_dialog_line(line: str) -> bool:
    m = TAG.match(line); 
    if not m: return False
    gid, body = m.group(2), m.group(3)
    if gid == "1": return False
    return bool(IS_DLG.match((body or "").replace(NBSP," ").lstrip()))

def apply(text: str, ctx):
    fp = _first_gid(ctx)
    if not fp: return text

    lines = text.splitlines(keepends=True)
    changed = 0

    for i, ln in enumerate(lines):
        m = TAG.match(ln)
        if not m: continue
        ind, gid_s, body = m.groups()
        if gid_s == "1": continue
        if not _is_dialog_line(ln): continue

        mm = PAT.search(body or "")
        if not mm: continue
        tail = (mm.group("tail") or "").strip()

        if not re.search(r"\b" + FP_VERBS + r"\b", tail, flags=re.IGNORECASE):
            continue

        # перетеглюємо на first_person_gid (до pair-lock)
        lines[i] = f"{ind}{fp}: {body}"
        changed += 1

    try:
        ctx.logs.append(f"[072g inline_first_person] retagged:{changed}")
    except Exception:
        pass
    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
