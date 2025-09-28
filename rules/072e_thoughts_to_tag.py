# 072e_thoughts_to_tag.py — цитатні «думки» → тег з легенди (напр. #g20 «думки»)
# -*- coding: utf-8 -*-
import re

PHASE, PRIORITY, SCOPE, NAME = 72, 13, "fulltext", "thoughts_to_tag"

NBSP = "\u00A0"
TAG  = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)

DASHES = "-\u2012\u2013\u2014\u2015"
OPEN_Q  = "«\"„“”'’"
CLOSE_Q = "»\"”'’"
IS_DLG = re.compile(r"^\s*(?:[" + re.escape(DASHES) + r"]|[" + re.escape(OPEN_Q) + r"])")

# «…» або "…" (без перевірки на початкове тире)
IS_QUOTED = re.compile(r"^\s*[" + re.escape(OPEN_Q) + r"].+[" + re.escape(CLOSE_Q) + r"]", re.DOTALL)

# «…»  — tail
AFTER_QUOTE = re.compile(
    r"^\s*[" + re.escape(OPEN_Q) + r"].+[" + re.escape(CLOSE_Q) + r"]\s*[, \t]*[" + re.escape(DASHES) + r"]\s*(?P<tail>.+)$",
    re.DOTALL
)

# індикатори «думок»
THOUGHT_CUES = re.compile(
    r"\b(подумки|подумав|подумала|міркував|міркувала|розмірковував|розмірковувала|про себе|в думках|майнула думка)\b",
    re.IGNORECASE
)

# «чисті» цитати (без початкового тире) — часто вставні думки/афоризми
PURE_QUOTE_LINE = re.compile(r'^\s*["«„].+["»”]\s*[\.!\?…]*\s*$')

# наративні підказки поряд із «чистою» цитатою
NEARBY_CUES = re.compile(
    r"\b(афоризм\w*|прислів'я|приказк\w*|думк\w*|подумав|подумала|подумки|міркував|міркувала|розмірковував|розмірковувала)\b",
    re.IGNORECASE
)

def _nrm(s:str)->str: return (s or "").replace(NBSP, " ").strip()

def _roles_gender(ctx):
    return (getattr(ctx, "metadata", {}) or {}).get("roles_gender") or {}

def _thought_gid(ctx):
    rg = _roles_gender(ctx)
    # 1) явний #g20 у легенді
    if "#g20" in rg:
        rec = rg["#g20"]; roles = " ".join(rec.get("roles") or []).lower()
        if "думк" in roles or any((n or "").lower() == "думки" for n in (rec.get("names") or [])):
            return "#g20"
    # 2) будь-який персонаж з роллю/назвою «думки»
    for gid, rec in rg.items():
        roles = " ".join(rec.get("roles") or []).lower()
        names = " ".join(rec.get("names") or []).lower()
        if "думк" in roles or "думки" in names:
            return gid
    # 3) запасний — якщо є #g20, все одно використати його
    if "#g20" in rg:
        return "#g20"
    return None  # інакше не чіпаємо

def apply(text: str, ctx):
    tgt = _thought_gid(ctx)
    if not tgt:
        return text  # немає спеціального тега для «думок» у легенді

    lines = text.splitlines(keepends=True)
    changed = 0
    n = len(lines)

    for i, ln in enumerate(lines):
        m = TAG.match(ln)
        if not m: 
            continue
        indent, gid_s, body = m.groups()
        if gid_s == "1":  # наратив не чіпаємо
            continue

        b = _nrm(body)

        # 1) «…» — подумки/подумав … → ставимо тег «думки»
        mm = AFTER_QUOTE.match(b)
        if mm and THOUGHT_CUES.search(_nrm(mm.group("tail"))):
            if f"#g{gid_s}" != tgt:
                lines[i] = f"{indent}{tgt}: {body}"
                changed += 1
            continue

        # 2) «чиста» цитата і поруч наратив із підказкою → теж «думки»
        if PURE_QUOTE_LINE.match(b) and not re.match(r"^\s*[" + re.escape(DASHES) + r"]", b):
            cue = False
            for j in (i-1, i+1, i-2, i+2):
                if 0 <= j < n:
                    mj = TAG.match(lines[j])
                    if mj and mj.group(2) == "1":
                        if NEARBY_CUES.search(_nrm(mj.group(3) or "")):
                            cue = True; break
                    elif not mj:
                        if NEARBY_CUES.search(_nrm(lines[j])):
                            cue = True; break
            if cue and f"#g{gid_s}" != tgt:
                lines[i] = f"{indent}{tgt}: {body}"
                changed += 1
                continue

    try:
        ctx.logs.append(f"[072e thoughts_to_tag] retagged:{changed} → {tgt}")
    except Exception:
        pass

    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
