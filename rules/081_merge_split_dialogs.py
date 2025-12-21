"""
081_merge_split_dialogs.py — об'єднання розірваних діалогів
Паттерн: #gN: "частина1" → #g1: атрибуція → #gN: "частина2"
Об'єднує в: #gN: "частина1. Частина2" → #g1: атрибуція
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 81, 0, "fulltext", "merge_split_dialogs"

def apply(text, ctx):
    lines = text.splitlines(keepends=True)
    out = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Шукаємо патерн: діалог → атрибуція → діалог (той самий тег)
        if i + 2 < len(lines):
            m1 = re.match(r'^(\s*)(#g\d+)\s*:\s*(.*)$', lines[i])
            m2 = re.match(r'^(\s*)#g1\s*:\s*(.*)$', lines[i+1])
            m3 = re.match(r'^(\s*)(#g\d+)\s*:\s*(.*)$', lines[i+2])
            
            if (m1 and m2 and m3 and 
                m1.group(2) == m3.group(2) and  # однакові теги
                '«' in m1.group(3) and '«' in m3.group(3)):  # обидва діалоги
                
                # Об'єднуємо діалоги
                dialog1 = m1.group(3).strip()
                dialog2 = m3.group(3).strip()
                
                # Видаляємо зайві лапки з другого діалогу
                if dialog2.startswith('«') and dialog1.endswith('»'):
                    dialog2 = dialog2[1:]
                if dialog2.endswith('»') and dialog1.endswith('»'):
                    dialog2 = dialog2[:-1]
                
                # Об'єднаний діалог
                merged_dialog = f"{dialog1} {dialog2}".strip()
                
                # Додаємо об'єднаний діалог
                out.append(f"{m1.group(1)}{m1.group(2)}: {merged_dialog}\n")
                # Додаємо атрибуцію
                out.append(f"{m2.group(1)}#g1: {m2.group(2)}\n")
                
                i += 3  # пропускаємо оброблені 3 рядки
                continue
        
        out.append(line)
        i += 1
    
    return "".join(out)

# ДОДАЙ ЦЕ В КІНЕЦЬ:
apply.phase = PHASE
apply.priority = PRIORITY
apply.scope = SCOPE
apply.name = NAME