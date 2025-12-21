# 084_merge_dialog_lines.py — об'єднання розділених рядків діалогу
# -*- coding: utf-8 -*-
"""
Об'єднує розділені рядки діалогу одного персонажа.
Наприклад:
  #g2: "Бачиш? ".
  #g1: сказала мама. —.
  #g2: "Їй і так погано".
  #g1: .
Стає:
  #g2: "Бачиш?. Їй і так погано".
  #g1: Сказала мама.
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 84, 0, "fulltext", "merge_dialog_lines"

def apply(text: str, ctx):
    lines = text.splitlines(keepends=True)
    out = []
    i = 0
    
    while i < len(lines):
        current_line = lines[i]
        
        # Шукаємо патерн: #gN + діалог → #g1 + атрибуція → #gN + діалог
        if i + 2 < len(lines):
            m1 = re.match(r'^(\s*)(#g\d+|\?)\s*:\s*(.*)$', lines[i])
            m2 = re.match(r'^(\s*)#g1\s*:\s*(.*)$', lines[i+1])
            m3 = re.match(r'^(\s*)(#g\d+|\?)\s*:\s*(.*)$', lines[i+2])
            
            if m1 and m2 and m3:
                dialog1 = m1.group(3).strip()
                attr = m2.group(3).strip()
                dialog2 = m3.group(3).strip()
                
                # Перевіряємо, що це діалоги (є лапки)
                has_quotes1 = any(q in dialog1 for q in ['«', '»', '"', '“', '”'])
                has_quotes2 = any(q in dialog2 for q in ['«', '»', '"', '“', '”'])
                
                if has_quotes1 and has_quotes2 and m1.group(2) == m3.group(2):
                    # Об'єднуємо діалоги
                    # Видаляємо зайві лапки з другого діалогу
                    if (dialog1.endswith('»') or dialog1.endswith('"') or dialog1.endswith('”')) and \
                       (dialog2.startswith('«') or dialog2.startswith('"') or dialog2.startswith('“')):
                        dialog2 = dialog2[1:]  # Видаляємо першу лапку
                    
                    merged_dialog = f"{dialog1} {dialog2}"
                    
                    # Додаємо об'єднаний діалог
                    out.append(f"{m1.group(1)}{m1.group(2)}: {merged_dialog}\n")
                    
                    # Додаємо атрибуцію (очищену)
                    attr_clean = re.sub(r'[,\—\–\-\s.]+$', '', attr)
                    attr_clean = re.sub(r'^[,\—\–\-\s]+', '', attr_clean)
                    if attr_clean:
                        out.append(f"{m2.group(1)}#g1: {attr_clean}\n")
                    
                    i += 3  # Пропускаємо оброблені 3 рядки
                    continue
        
        # Якщо не патерн - додаємо поточний рядок
        out.append(current_line)
        i += 1
    
    return "".join(out)

apply.phase = PHASE
apply.priority = PRIORITY
apply.scope = SCOPE
apply.name = NAME