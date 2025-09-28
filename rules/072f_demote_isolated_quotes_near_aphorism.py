# 072f_demote_isolated_quotes_near_aphorism.py — «"…"/«…»» як внутрішня думка поруч з "афоризм/подумав" → #g?
# -*- coding: utf-8 -*-
import re

PHASE, PRIORITY, SCOPE, NAME = 72, 13, "fulltext", "demote_isolated_quotes_near_aphorism"

TAG = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)

DASHES = "-\u2012\u2013\u2014\u2015"
OPEN_Q  = "«\"„“”'’"
CLOSE_Q = "»\"”'’"

# суто «цитата» без початкового тире (тобто не нормальний діалог)
PURE_QUOTE = re.compile(
    r"^\s*[" + re.escape(OPEN_Q) + r"].+[" + re.escape(CLOSE_Q) + r"]\s*[\.!\?…]*\s*$"
)

# сусідні наративи з підказками, що це думка/афоризм
CUES = re.compile(
    r"\b(афоризм\w*|прислів'я|приказк\w*|цитат\w*|думк\w*|подумав|подумала|подумки|міркував|міркувала|розмірковував|розмірковувала)\b",
    re.IGNORECASE
)

def apply(text: str, ctx):
    lines = text.splitlines(keepends=True)
    demoted = 0

    for i, ln in enumerate(lines):
        m = TAG.match(ln)
        if not m: 
            continue
        indent, gid_s, body = m.groups()
        if gid_s in ("1", "?"):
            continue

        b = (body or "").strip()

        # Має вигляд «"…"/«…»», але НЕ починається з тире (і не містить явної атрибуції)
        if not PURE_QUOTE.match(b):
            continue
        if re.search(r"^\s*[" + re.escape(DASHES) + r"]", b):
            continue  # це нормальний діалог — пропускаємо

        # Перевіряємо сусідні рядки (до 2 зверху/знизу) на наратив з підказками
        cue_found = False
        for j in (i-1, i+1, i-2, i+2):
            if j < 0 or j >= len(lines): 
                continue
            mj = TAG.match(lines[j])
            if not mj:
                # чистий наративний рядок
                if CUES.search(lines[j]):
                    cue_found = True; break
                continue
            if mj.group(2) == "1":  # #g1: … (наратив)
                if CUES.search(mj.group(3) or ""):
                    cue_found = True; break

        if not cue_found:
            continue

        # Демотуємо — нехай ML/подальші правила вирішують, чия це думка
        lines[i] = f"{indent}#g?: {body}"
        demoted += 1

    try:
        ctx.logs.append(f"[072f quotes_near_aphorism] demoted:{demoted}")
    except Exception:
        pass

    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
