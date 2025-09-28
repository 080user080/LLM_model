# 074a_inject_block_boundaries.py — вставка маркерів меж діалогів (щоб не тягнути пару)
# -*- coding: utf-8 -*-

import re

PHASE, PRIORITY, SCOPE, NAME = 74, 1, "fulltext", "inject_block_boundaries"  # до 074_pair_lock (prio 6)

TAG_ANY = re.compile(r"^\s*#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
MARK = "[[DIALOG_BOUNDARY]]"  # зручно потім видаляти
MARK_LINE = f"#g1: {MARK}\n"

def apply(text: str, ctx):
    meta = getattr(ctx, "metadata", {}) or {}
    blocks = meta.get("dialog_blocks") or []
    if not blocks or len(blocks) < 2:
        return text

    # Створюємо множину індексів початків усіх блоків, крім першого
    starts = {b["start"] for b in blocks[1:] if isinstance(b.get("start"), int)}
    lines = text.splitlines(keepends=True)
    out = []
    inserted = 0

    for i, ln in enumerate(lines):
        if i in starts:
            # якщо попередній рядок уже пустий/наратив — не дублюємо межу
            prev = out[-1] if out else ""
            if not prev.strip():
                pass  # вже є пустий рядок — норм
            elif prev.lstrip().startswith("#g1:"):
                pass  # вже наратив
            else:
                out.append(MARK_LINE); inserted += 1
        out.append(ln)

    meta["inserted_block_markers"] = inserted
    setattr(ctx, "metadata", meta)
    try:
        ctx.logs.append(f"[074a block_mark] inserted:{inserted}")
    except Exception:
        pass
    return "".join(out)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
