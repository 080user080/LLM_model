# -*- coding: utf-8 -*-
"""Після КІНЦЯ прологу спікер #g4 заборонений → демотуємо в #g?"""
import re

PHASE, PRIORITY, SCOPE, NAME = 74, 2, "fulltext", "block_g4_after_prologue"

ANCHOR_START = re.compile(r"^\s*(?:#g\d+\s*:\s*)?Пролог\.?\s*$", re.IGNORECASE | re.MULTILINE)
ANCHOR_END   = re.compile(r"^\s*(?:Кінець прологу\.?|Розділ\s+\w+|Частина\s+\w+|Глава\s+\w+)\s*$",
                          re.IGNORECASE | re.MULTILINE)
TAG_G4 = re.compile(r"^(\s*)#g4\s*:\s*(.*)$", re.DOTALL | re.MULTILINE)

def apply(text, ctx):
    m1 = ANCHOR_START.search(text)
    if not m1:
        return text
    m2 = ANCHOR_END.search(text, m1.end())
    if not m2:
        # немає явного кінця прологу — не блокуємо #g4
        return text
    head = text[:m2.end()]
    tail = text[m2.end():]
    tail2 = TAG_G4.sub(r"\1#g?: \2", tail)
    return head + tail2

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
