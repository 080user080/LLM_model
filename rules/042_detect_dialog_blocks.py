# 042_detect_dialog_blocks.py — детектор блоків діалогів (start/end + мапа рядків)
# -*- coding: utf-8 -*-

import re

PHASE, PRIORITY, SCOPE, NAME = 42, 0, "fulltext", "detect_dialog_blocks"  # після 041

NBSP = "\u00A0"
TAG_ANY = re.compile(r"^\s*#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
DASHES = r"\-\u2012\u2013\u2014\u2015"
DIALOG_START = re.compile(rf"^\s*(?:[{DASHES}]|[«\"„“”'’])")

def _is_dialog_line(raw: str) -> bool:
    m = TAG_ANY.match(raw)
    if not m:
        return False
    gid, body = m.groups()
    if gid == "1":  # оповідач не вважається діалогом
        return False
    b = (body or "").replace(NBSP, " ")
    return bool(DIALOG_START.match(b))

def apply(text: str, ctx):
    lines = text.splitlines(keepends=True)
    blocks = []
    ids_by_line = {}
    in_block = False
    start = None
    for i, ln in enumerate(lines):
        is_d = _is_dialog_line(ln)
        if is_d and not in_block:
            in_block, start = True, i
        if (not is_d) and in_block:
            blocks.append({"start": start, "end": i - 1})
            in_block, start = False, None
        if is_d and in_block:
            ids_by_line[i] = len(blocks) if start is not None else (len(blocks)-1)
    if in_block:
        blocks.append({"start": start, "end": len(lines) - 1})

    meta = getattr(ctx, "metadata", {}) or {}
    meta["dialog_blocks"] = blocks
    meta["dialog_block_id_by_line"] = ids_by_line
    meta["dialog_block_count"] = len(blocks)
    setattr(ctx, "metadata", meta)

    try:
        ctx.logs.append(f"[042 dlg_blocks] blocks:{len(blocks)}")
    except Exception:
        pass
    return text

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
