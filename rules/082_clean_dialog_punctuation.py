# 082_clean_dialog_punctuation.py — очищення пунктуації діалогів (v3)
# -*- coding: utf-8 -*-
"""
1. Видаляє порожні рядки (#g1: .)
2. Додає крапку до діалогів без пунктуації
3. Очищає атрибуції
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 82, 0, "fulltext", "clean_dialog_punctuation"

def apply(text: str, ctx):
    lines = text.splitlines(keepends=True)
    out = []
    
    for ln in lines:
        eol = "\n" if ln.endswith("\n") else ("\r\n" if ln.endswith("\r\n") else "")
        
        # Перевіряємо, чи це рядок з тегом
        m = re.match(r'^(\s*)(#g\d+|\?)\s*:\s*(.*)$', ln)
        if not m:
            out.append(ln)
            continue
        
        indent, tag, body = m.groups()
        
        # Видаляємо порожні рядки
        if body.strip() in [".", ",", "—", "–", "-", ""]:
            continue
        
        # Для #g1 (оповідач) - прибираємо зайві символи
        if tag == "#g1":
            body = re.sub(r'^[,\—\–\-\s]+', '', body)  # Початок
            body = re.sub(r'[,\—\–\-\s]+$', '', body)  # Кінець
            body = body.strip()
            
            if not body:
                continue
            
            # Додаємо крапку, якщо немає
            if body and body[-1] not in '.!?…':
                body += '.'
            
            out.append(f"{indent}{tag}: {body}{eol}")
        
        # Для діалогів (#gN, #g?)
        else:
            # Додаємо крапку до діалогів без пунктуації
            if body and body[-1] not in '.!?…':
                body += '.'
            
            out.append(f"{indent}{tag}: {body}{eol}")
    
    return ''.join(out)

apply.phase = PHASE
apply.priority = PRIORITY
apply.scope = SCOPE
apply.name = NAME