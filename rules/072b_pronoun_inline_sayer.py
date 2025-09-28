# 072b_pronoun_inline_sayer.py — «… — сказала вона / сказав він» → призначення мовця за статтю й контекстом
# -*- coding: utf-8 -*-
"""
Призначає мовця для рядків із #g? за конструкціями типу:
  — … — сказала вона.   |  — … — він сказав.
Визначає стать з займенника (він=M, вона=F) і шукає найближчого попереднього
відомого мовця з такою самою статтю (у вікні CONTEXT_BACK рядків).
Працює після 072/073 (іменні індикатори), до 074 (пара/вокатив).

Вимагає: meta["roles_gender"] = { "#gN": {"gender": "M"/"F", ...}, ... } (див. 052_extract_roles_gender.py)
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 73, 9, "fulltext", "pronoun_inline_sayer"  # запускаємо після 073_leadin

# Дієслова мовлення
VERBS_M = r"(сказав|відповів|спитав|крикнув|вигукнув|прошепотів|буркнув|мовив|пояснив|гукнув)"
VERBS_F = r"(сказала|відповіла|спитала|крикнула|вигукнула|прошепотіла|буркнула|промовила|пояснила|гукнула)"
# Патерни: verb + pronoun  або  pronoun + verb
PAT_M = re.compile(rf"\b(?:{VERBS_M}\s+він|він\s+{VERBS_M})\b", re.IGNORECASE)
PAT_F = re.compile(rf"\b(?:{VERBS_F}\s+вона|вона\s+{VERBS_F})\b", re.IGNORECASE)

TAG_ANY = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
CONTEXT_BACK = 5  # скільки рядків переглядати назад

def _body(line: str):
    m = TAG_ANY.match(line)
    if not m: return None, None, None
    return m.groups()  # indent, gid, body

def _want_gender(text: str):
    low = text.lower()
    if PAT_M.search(low): return "M"
    if PAT_F.search(low): return "F"
    return None

def _roles_gender(ctx):
    meta = getattr(ctx, "metadata", {}) or {}
    return meta.get("roles_gender") or {}

def _gender_of(gid: str, rg: dict):
    rec = rg.get(gid)
    return (rec or {}).get("gender")

def _nearest_prev_gid(lines, i, want_gender, rg):
    # шукаємо найближчого попереднього рядка з призначеним #gN тієї ж статі
    for j in range(i - 1, max(-1, i - CONTEXT_BACK - 1), -1):
        m = TAG_ANY.match(lines[j])
        if not m: 
            continue
        _, gid, _ = m.groups()
        if gid == "?" or gid == "1":  # пропускаємо невідомих і наратора
            continue
        gid_full = f"#g{gid}"
        if _gender_of(gid_full, rg) == want_gender:
            return gid_full
    return None

def apply(text: str, ctx):
    rg = _roles_gender(ctx)
    if not rg:
        return text

    lines = text.splitlines(keepends=True)
    changed = 0

    for i, ln in enumerate(lines):
        ind, gid, body = _body(ln)
        if gid is None or gid != "?":
            continue  # працюємо лише по невизначених
        want = _want_gender(body or "")
        if not want:
            continue

        cand = _nearest_prev_gid(lines, i, want, rg)
        if cand:
            lines[i] = f"{ind}{cand}: {body}"
            changed += 1

    try:
        ctx.logs.append(f"[072b pronoun] resolved:{changed}")
    except Exception:
        pass

    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME  #GPT
