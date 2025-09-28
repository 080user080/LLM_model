# 098_remove_block_markers.py — прибрати службові маркери меж діалогів з фінального тексту
# -*- coding: utf-8 -*-

import re

PHASE, PRIORITY, SCOPE, NAME = 98, 0, "fulltext", "remove_block_markers"  # найпізніше

MARK = "[[DIALOG_BOUNDARY]]"
RX = re.compile(rf"^\s*#g1\s*:\s*{re.escape(MARK)}\s*$")

def apply(text: str, ctx):
    out = []
    removed = 0
    for ln in text.splitlines(keepends=True):
        core = ln.rstrip("\n")
        if RX.match(core):
            removed += 1
            continue
        out.append(ln)

    try:
        ctx.logs.append(f"[098 rm_block_markers] removed:{removed}")
    except Exception:
        pass
    return "".join(out)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
