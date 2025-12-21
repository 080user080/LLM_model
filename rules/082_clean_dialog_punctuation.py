# 082_clean_dialog_punctuation.py — очищення пунктуації діалогів (v5)
# -*- coding: utf-8 -*-
"""
1. Видаляє порожні рядки
2. Додає крапку до діалогів без пунктуації
3. Прибирає пробіли перед лапками
4. Об'єднує діалоги в одному рядку
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
        body_stripped = body.strip()
        if body_stripped in [".", ",", "—", "–", "-", ""]:
            continue
        
        # Прибираємо пробіли перед закриваючими лапками
        body = re.sub(r'\s+([»”"])', r'\1', body)
        
        # Прибираємо пробіли після відкриваючих лапок
        body = re.sub(r'([«"“])\s+', r'\1', body)
        
        # Для #g1 (оповідач)
        if tag == "#g1":
            # Прибираємо зайві символи на початку та в кінці
            body = re.sub(r'^[,\—\–\-\s]+', '', body)
            body = re.sub(r'[,\—\–\-\s]+$', '', body)
            body = body.strip()
            
            if not body:
                continue
            
            # Додаємо крапку, якщо немає
            if body and body[-1] not in '.!?…':
                body += '.'
            
            out.append(f"{indent}{tag}: {body}{eol}")
        
        # Для діалогів
        else:
            # Прибираємо зайві пробіли всередині
            body = re.sub(r'\s+', ' ', body)
            
            # Додаємо крапку, якщо немає
            if body and body[-1] not in '.!?…':
                # Перевіряємо, чи не закінчується на лапку
                if body[-1] in ['»', '"', '”']:
                    # Вставляємо крапку перед лапкою
                    body = body[:-1] + '.' + body[-1]
                else:
                    body += '.'
            
            out.append(f"{indent}{tag}: {body}{eol}")
    
    return ''.join(out)

apply.phase = PHASE
apply.priority = PRIORITY
apply.scope = SCOPE
apply.name = NAME