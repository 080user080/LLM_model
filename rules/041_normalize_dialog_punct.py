# -*- coding: utf-8 -*-
#GPT: 041 — Нормалізація тире/лапок/пробілів + межі блоків
"""
Нормалізує корпус перед правилами розпізнавання діалогів:
  • NBSP/zero-width → звичайні пробіли / видалення.
  • Лапки → ASCII " ; апостроф → ’.
  • "..." → "…" (U+2026).
  • На початку репліки після #gX: будь-яке [-–—] → EM DASH (—) + один пробіл.
  • Зайві пробіли стискає до одного, хвостові прибирає.
  • Визначає межі блоків: порожні рядки та технічні роздільники (---, ***, ===, — PAGE N —, тощо)
    згортає у ЄДИНИЙ порожній рядок і фіксує індекси меж у ctx.metadata["block_boundaries"].
НЕ чіпає тег і двокрапку (#gN:), змінює лише "тіло" рядка.
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 41, 0, "fulltext", "normalize_dialog_punct"  #GPT

NBSP = "\u00A0"
ZW_REGEX = re.compile(r"[\u200B-\u200D\uFEFF]")  # zero-width chars
ELLIPSIS = "\u2026"

# Початок репліки після тега: #gN:  — тіло в групі 3
TAG_ANY = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)

# Будь-яке тире на початку тіла діалогу → EM DASH (—) і один пробіл
LEADING_DASH = re.compile(r"^\s*[-\u2012\u2013\u2014\u2015]\s*")

# Уніфікація лапок/апострофа всередині тіла
QUOTES_MAP = str.maketrans({
    "«": '"', "»": '"', "„": '"', "“": '"', "”": '"',
    "′": "’", "ʼ": "’", "'": "’"
})

# Роздільники блоків (після нормалізації)
SEP_CORE = r"\-\=\*\_#~·•\.\u2012\u2013\u2014\u2015"  # дефіси/тире/рівні/зірочки/крапки/тощо
SEPARATOR_RX = re.compile(
    rf"""
    ^\s*(
        [{SEP_CORE} ]{{3,}}                                  # довгі смуги/набори символів
        |
        [\-\u2013\u2014 ]*\b(?:page|сторінка)\b[ \t]*\d+[ \t]*[\-\u2013\u2014 ]*  # — PAGE 77 — / — СТОРІНКА 77 —
    )\s*$""",
    re.IGNORECASE | re.VERBOSE
)

def _normalize_body(s: str) -> str:
    if not s:
        return s
    # NBSP→space; видалити zero-width
    s = s.replace(NBSP, " ")
    s = ZW_REGEX.sub("", s)

    # Лапки/апостроф
    s = s.translate(QUOTES_MAP)

    # Три крапки → …; послідовності >=3 крапок теж
    s = re.sub(r"\.{3,}", ELLIPSIS, s)

    # Стиснути багато пробілів (включно з табами) до одного
    s = re.sub(r"[ \t]{2,}", " ", s)

    # Хвостові пробіли
    s = re.sub(r"[ \t]+$", "", s)

    return s

def _normalize_dialog_lead(s: str) -> str:
    """Якщо тіло починається з діалогового тире, привести до '— '."""
    return LEADING_DASH.sub("— ", s, count=1)

def _is_separator_line(core: str) -> bool:
    """Порожній рядок або технічний роздільник — це межа блоку."""
    if core.strip() == "":
        return True
    # Прибрати повторювані пробіли для стійкіших збігів
    c = re.sub(r"\s+", " ", core.strip())
    return bool(SEPARATOR_RX.match(c))

def apply(text, ctx):
    lines = text.splitlines(keepends=True)

    changed_dash = changed_q = changed_ellipsis = changed_ws = 0

    normalized = []
    for ln in lines:
        m = TAG_ANY.match(ln)
        if m:
            ind, gid, body = m.groups()
            before = body

            body = _normalize_body(body)
            new_body = _normalize_dialog_lead(body)

            # підрахунок змін (груба евристика)
            if LEADING_DASH.match(body) and new_body.startswith("— "):
                changed_dash += 1
            if before != body:
                if '"' in body or '’' in body:
                    changed_q += 1
                if ELLIPSIS in body:
                    changed_ellipsis += 1
                if "  " not in body:
                    changed_ws += 1

            normalized.append(f"{ind}#g{gid}: {new_body}" + ("\n" if ln.endswith("\n") else ""))
        else:
            # Наратив або інший рядок (без #g) — теж нормалізуємо
            tail_nl = "\n" if ln.endswith("\n") else ""
            core = ln[:-1] if tail_nl else ln
            before = core

            core = _normalize_body(core)
            if before != core:
                if '"' in core or '’' in core:
                    changed_q += 1
                if ELLIPSIS in core:
                    changed_ellipsis += 1
                if "  " not in core:
                    changed_ws += 1

            normalized.append(core + tail_nl)

    # Друга фаза: складання меж блоків та згортання послідовностей роздільників у один порожній рядок
    out = []
    block_boundaries = []  # індекси рядків у підсумковому тексті
    prev_was_sep = False
    collapsed = 0

    for ln in normalized:
        tail_nl = "\n" if ln.endswith("\n") else ""
        core = ln[:-1] if tail_nl else ln

        if _is_separator_line(core):
            if not prev_was_sep:
                # ставимо єдиний порожній рядок як маркер межі
                out.append("" + (tail_nl or "\n"))
                block_boundaries.append(len(out) - 1)
                prev_was_sep = True
            else:
                collapsed += 1  # додаткові роздільники згорнуті
            continue

        prev_was_sep = False
        out.append(ln)

    # Зберігаємо межі у метаданих
    try:
        meta = getattr(ctx, "metadata", {}) or {}
        meta["block_boundaries"] = block_boundaries
        setattr(ctx, "metadata", meta)
    except Exception:
        pass

    try:
        ctx.logs.append(
            f"[041 normalize] dash:{changed_dash} quotes:{changed_q} ellipsis:{changed_ellipsis} "
            f"ws:{changed_ws} | block_boundaries:{len(block_boundaries)} collapsed:{collapsed}"
        )
    except Exception:
        pass

    return "".join(out)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME  #GPT
