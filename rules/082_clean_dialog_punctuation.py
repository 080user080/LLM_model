"""
082_clean_dialog_punctuation.py — очищення пунктуації діалогів
1. Прибирає `, —` з початку атрибуцій
2. Додає крапку до діалогів без пунктуації
3. Нормалізує пробіли в лапках
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 82, 0, "fulltext", "clean_dialog_punctuation"

def apply(text, ctx):
    lines = text.splitlines(keepends=True)
    out = []
    
    for line in lines:
        # 1. Прибрати `, —` з початку атрибуцій (#g1)
        m = re.match(r'^(\s*)#g1\s*:\s*(.*)$', line)
        if m:
            body = m.group(2)
            # Прибираємо початкові коми, тире, пробіли
            cleaned = re.sub(r'^[,\—\–\-\s]+', '', body)
            out.append(f"{m.group(1)}#g1: {cleaned}\n")
            continue
        
        # 2. Додати крапку до діалогів без пунктуації (#gN, #g?)
        m = re.match(r'^(\s*)(#g\d+|\?)\s*:\s*(.*)$', line)
        if m and '«' in m.group(3):
            dialog = m.group(3).strip()
            # Якщо діалог закінчується на лапку без пунктуації
            if dialog.endswith('»') and dialog[-2] not in '.!?…':
                dialog = dialog[:-1] + '.»'
            out.append(f"{m.group(1)}{m.group(2)}: {dialog}\n")
            continue
        
        out.append(line)
    
    return "".join(out)