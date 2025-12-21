# 086_merge_all_dialogs.py — об'єднання всіх розділених діалогів
# -*- coding: utf-8 -*-
"""
Об'єднує діалоги, розділені атрибуціями або порожніми рядками.
Виконує всі можливі об'єднання.
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 86, 0, "fulltext", "merge_all_dialogs"

def apply(text: str, ctx):
    lines = text.splitlines(keepends=True)
    out = []
    i = 0
    
    while i < len(lines):
        # Пошук патерну: #gN + діалог → (#g1 + атрибуція)? → #gN + діалог
        current_line = lines[i]
        m_current = re.match(r'^(\s*)(#g\d+|\?)\s*:\s*(.*)$', current_line)
        
        if not m_current:
            out.append(current_line)
            i += 1
            continue
        
        current_indent, current_tag, current_body = m_current.groups()
        
        # Перевіряємо, чи поточний рядок містить діалог (лапки)
        if not any(q in current_body for q in ['«', '"', '“']):
            out.append(current_line)
            i += 1
            continue
        
        # Збираємо послідовні діалоги одного тегу
        dialogs = [current_body]
        j = i + 1
        tags_to_skip = []
        
        while j < len(lines):
            next_line = lines[j]
            m_next = re.match(r'^(\s*)(#g\d+|\?|g1)\s*:\s*(.*)$', next_line)
            
            if not m_next:
                break
            
            next_indent, next_tag, next_body = m_next.groups()
            
            # Якщо наступний рядок має той самий тег і містить діалог
            if next_tag == current_tag and any(q in next_body for q in ['«', '"', '“']):
                dialogs.append(next_body)
                tags_to_skip.append(j)
                j += 1
                continue
            
            # Якщо наступний рядок - #g1 з атрибуцією
            if next_tag == "#g1" and j + 1 < len(lines):
                # Перевіряємо рядок після #g1
                m_after = re.match(r'^(\s*)(#g\d+|\?)\s*:\s*(.*)$', lines[j+1])
                if m_after and m_after.group(2) == current_tag and \
                   any(q in m_after.group(3) for q in ['«', '"', '“']):
                    # Пропускаємо #g1 і додаємо наступний діалог
                    dialogs.append(m_after.group(3))
                    tags_to_skip.extend([j, j+1])
                    j += 2
                    continue
            
            # Якщо наступний рядок - #g1 з діалогом всередині
            if next_tag == "#g1" and any(q in next_body for q in ['«', '"', '“']):
                # Знаходимо діалог у рядку #g1
                # Шукаємо перші лапки
                first_quote = -1
                for idx, ch in enumerate(next_body):
                    if ch in ['«', '"', '“']:
                        first_quote = idx
                        break
                
                if first_quote > 0:
                    # Розділяємо атрибуцію та діалог
                    attribution = next_body[:first_quote].strip()
                    dialog_in_g1 = next_body[first_quote:].strip()
                    
                    # Додаємо діалог
                    dialogs.append(dialog_in_g1)
                    tags_to_skip.append(j)
                    
                    # Якщо є атрибуція, додаємо її окремо
                    if attribution:
                        # Очищаємо атрибуцію
                        attribution_clean = re.sub(r'^[,\—\–\-\s]+', '', attribution)
                        attribution_clean = re.sub(r'[,\—\–\-\s.]+$', '', attribution_clean)
                        if attribution_clean:
                            out.append(f"{next_indent}#g1: {attribution_clean}\n")
                    
                    j += 1
                    continue
            
            break
        
        # Об'єднуємо всі діалоги
        if len(dialogs) > 1:
            merged_dialog = dialogs[0]
            for d in dialogs[1:]:
                # Прибираємо зайві лапки
                if (merged_dialog.endswith('»') or merged_dialog.endswith('"') or merged_dialog.endswith('”')) and \
                   (d.startswith('«') or d.startswith('"') or d.startswith('“')):
                    d = d[1:]
                if merged_dialog.endswith('»') and d.endswith('»'):
                    d = d[:-1]
                
                merged_dialog = f"{merged_dialog} {d}".strip()
            
            # Додаємо об'єднаний діалог
            out.append(f"{current_indent}{current_tag}: {merged_dialog}\n")
            i = j  # Переходимо до наступного необробленого рядка
        else:
            out.append(current_line)
            i += 1
    
    return "".join(out)

apply.phase = PHASE
apply.priority = PRIORITY
apply.scope = SCOPE
apply.name = NAME