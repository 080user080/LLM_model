# 073b_coref_pronouns.py — coref «він/вона/той/ця» → призначення мовця за статтю та найближчим контекстом
# -*- coding: utf-8 -*-
"""
Призначає мовця для #g? за займенниками:
  • «— … — вона/він.» (без дієслова)
  • «— … — … сказала/сказав вона/він…» (резервний шлях, якщо 072b не спрацювало)
  • діалоговий рядок із займенником + близьке дієслово мовлення (каже/сказала/…)
Алгоритм:
  1) Визначає цільовий рід (F/M) із займенника/вказівного «той/ця/цей/та…».
  2) Шукає найближчого попереднього призначеного мовця того самого роду
     в межах того ж «блоку діалогу» (042_detect_dialog_blocks) або вікна CONTEXT_BACK.
  3) Призначає #gN. Не торкається #g1 і вже визначених рядків.

Залежності: 041_normalize_dialog_punct, 042_detect_dialog_blocks (не обов’язково, але бажано),
            050/051 (legend), 052_extract_roles_gender (roles_gender).
Порядок: PHASE=73, priority=10 (після lead-in/inline, перед 074_*).
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 73, 10, "fulltext", "coref_pronouns"  #GPT

NBSP = "\u00A0"
TAG_ANY = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$")
DASHES = r"\-\u2012\u2013\u2014\u2015"
DIALOG_START = re.compile(rf"^\s*(?:[{DASHES}]|[«\"„“”'’])")

P_M = r"(?:він|йому|ним|ньому|нього|ним|цей|цього|цьому|цим|той|того|тому|тим)"
# «та» лишається, але перевіряється лише в кінці рядка (INLINE_TAIL)
P_F = r"(?:вона|її|їй|неї|нею|цій|цією|цієї|цю|ця)"
PRON_M = re.compile(rf"\b{P_M}\b", re.IGNORECASE)
PRON_F = re.compile(rf"\b{P_F}\b", re.IGNORECASE)

# Дієслова мовлення (родові + нейтральні)
VERBS_M = "сказав|відповів|спитав|запитав|крикнув|вигукнув|прошепотів|буркнув|мовив|промовив|пояснив|гукнув|відказав"
VERBS_F = "сказала|відповіла|спитала|запитала|крикнула|вигукнула|прошепотіла|буркнула|промовила|пояснила|гукнула|відказала"
VERBS_N = "каже|говорить|питає|запитує|кричить|вигукує|шепоче|бурчить|мовить|промовляє|пояснює|гукає|відказує|додає|зазначає|просить|велить|нагадує"
VERB_ANY = re.compile(rf"\b(?:{VERBS_M}|{VERBS_F}|{VERBS_N})\b", re.IGNORECASE)

# Патерн «… — він/вона/та .»
END_PRON = re.compile(rf"{PRON_M.pattern}|{PRON_F.pattern}|\bта\b", re.IGNORECASE)
INLINE_TAIL = re.compile(rf"(?:{END_PRON.pattern})\s*[\.!\?…»\"’]*\s*$", re.IGNORECASE)

# Патерн «… — сказала/каже вона/він …» (страхуємо, якщо 072b не встиг)
VERB_PRON = re.compile(
    rf"\b(?:(?:{VERBS_M})\s+{P_M}|(?:{VERBS_F})\s+{P_F}|{P_M}\s+(?:{VERBS_M})|{P_F}\s+(?:{VERBS_F})|(?:{VERBS_N})\s+(?:{P_M}|{P_F}))\b",
    re.IGNORECASE
)

CONTEXT_BACK = 6  # скільки рядків переглядаємо назад

def _roles_gender(ctx):
    return (getattr(ctx, "metadata", {}) or {}).get("roles_gender") or {}

def _dialog_block_id(ctx):
    return (getattr(ctx, "metadata", {}) or {}).get("dialog_block_id_by_line") or {}

def _gender_of(gid_full: str, rg: dict):
    rec = rg.get(gid_full)
    return (rec or {}).get("gender")

def _is_dialog_body(body: str) -> bool:
    return bool(DIALOG_START.match((body or "").replace(NBSP, " ").lstrip()))

def _want_gender(text: str):
    low = (text or "").replace(NBSP, " ").lower()
    # «та» враховується тільки як закриваючий займенник у кінці рядка
    if INLINE_TAIL.search(low) and re.search(r"\bта\b\s*[\.!\?…»\"’]*\s*$", low):
        return "F"
    if PRON_F.search(low): return "F"
    if PRON_M.search(low): return "M"
    return None

def _has_verb_near_pronoun(text: str) -> bool:
    # грубо: якщо в рядку є і займенник, і дієслово мовлення — вважаємо валідним сигналом
    low = (text or "").lower()
    return (PRON_F.search(low) or PRON_M.search(low)) and VERB_ANY.search(low)

def _nearest_prev_same_block(lines, i, want_gender, rg, block_by_line):
    blk = block_by_line.get(i)
    for j in range(i - 1, max(-1, i - CONTEXT_BACK - 1), -1):
        if block_by_line.get(j) != blk:
            break  # не тягнемо через межу блоку
        m = TAG_ANY.match(lines[j])
        if not m:
            continue
        _, gid, _ = m.groups()
        if gid in ("?", "1"):
            continue
        cand = f"#g{gid}"
        if _gender_of(cand, rg) == want_gender:
            return cand
    return None

def _nearest_prev_any(lines, i, want_gender, rg):
    for j in range(i - 1, max(-1, i - CONTEXT_BACK - 1), -1):
        m = TAG_ANY.match(lines[j])
        if not m:
            continue
        _, gid, _ = m.groups()
        if gid in ("?", "1"):
            continue
        cand = f"#g{gid}"
        if _gender_of(cand, rg) == want_gender:
            return cand
    return None

def apply(text: str, ctx):
    rg = _roles_gender(ctx)
    if not rg:
        return text

    block_by_line = _dialog_block_id(ctx)
    lines = text.splitlines(keepends=True)
    resolved_tail = resolved_verb = resolved_generic = 0

    for i, ln in enumerate(lines):
        m = TAG_ANY.match(ln)
        if not m:
            continue
        indent, gid, body = m.groups()
        if gid != "?":
            continue

        # Визначаємо бажаний рід
        want = _want_gender(body)
        if not want:
            continue

        # 1) «— … — вона/він.» без дієслова → сильний сигнал
        if INLINE_TAIL.search(body or ""):
            cand = _nearest_prev_same_block(lines, i, want, rg, block_by_line) or \
                   _nearest_prev_any(lines, i, want, rg)
            if cand:
                lines[i] = f"{indent}{cand}: {body}"
                resolved_tail += 1
                continue

        # 2) Є займенник + дієслово мовлення у рядку (ймовірна атрибуція)
        if _has_verb_near_pronoun(body or "") or _is_dialog_body(body):
            cand = _nearest_prev_same_block(lines, i, want, rg, block_by_line) or \
                   _nearest_prev_any(lines, i, want, rg)
            if cand:
                lines[i] = f"{indent}{cand}: {body}"
                resolved_verb += 1
                continue

        # 3) Генеральний fallback у межах блоку
        cand = _nearest_prev_same_block(lines, i, want, rg, block_by_line)
        if cand:
            lines[i] = f"{indent}{cand}: {body}"
            resolved_generic += 1
            continue

    try:
        ctx.logs.append(f"[073b coref_pronouns] tail:{resolved_tail} verb:{resolved_verb} generic:{resolved_generic}")
    except Exception:
        pass

    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME  #GPT
