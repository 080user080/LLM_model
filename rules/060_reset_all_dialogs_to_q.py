# -*- coding: utf-8 -*-
"""
Будь-який діалоговий рядок → #g?, наратив #g1 не чіпаємо.
Мета: далі всі перетегування робимо тільки з #g?.
"""
import re

PHASE, PRIORITY, SCOPE, NAME = 60, 1, "fulltext", "reset_all_dialogs_to_q"

NBSP = "\u00A0"
DASH = r"\-\u2012\u2013\u2014\u2015"
DIALOG = re.compile(rf"^\s*(?:[{DASH}]|[«\"„“”'’])")

TAGGED = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
UNTAG  = re.compile(r"^(\s*)(.*)$", re.DOTALL)

def _is_dialog(s: str) -> bool:
    return bool(DIALOG.match(s.replace(NBSP, " ").lstrip()))

def apply(text, ctx):
    out = []
    for ln in text.splitlines(keepends=True):
        m = TAGGED.match(ln)
        if m:
            indent, gid, body = m.groups()
            if _is_dialog(body):
                out.append(f"{indent}#g?: {body}")
            else:
                out.append(ln)
            continue
        # без тегу: якщо діалог — префіксуємо #g?
        if _is_dialog(ln):
            m2 = UNTAG.match(ln)
            out.append(f"{m2.group(1)}#g?: {m2.group(2)}")
        else:
            out.append(ln)
    return "".join(out)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME