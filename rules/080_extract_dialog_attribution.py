# 080_extract_dialog_attribution.py — виділення атрибуції діалогу для TTS
# -*- coding: utf-8 -*-
"""
Відокремлює атрибуцію від діалогу для TTS-озвучення.
Працює з будь-якими лапками та тире.
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 80, 0, "fulltext", "extract_dialog_attribution"

NBSP = "\u00A0"
TAG = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)

# Всі види тире та лапок
DASH = "—–-"
QUOTE_END = '»""\''
QUOTE_START = '«"„"\''

def _norm(s):
    return (s or "").replace(NBSP, " ")

def _cap(s):
    s = s.strip()
    return s[0].upper() + s[1:] if s else s

def _has_verb(text):
    """Перевірка наявності дієслова мовлення."""
    verbs = [
        'сказав', 'сказала', 'відповів', 'відповіла', 'спитав', 'спитала',
        'запитав', 'запитала', 'крикнув', 'крикнула', 'вигукнув', 'вигукнула',
        'прошепотів', 'прошепотіла', 'буркнув', 'буркнула', 'промовив', 'промовила',
        'мовив', 'мовила', 'звернувся', 'звернулась', 'процедив', 'процедила',
        'додав', 'додала', 'зазначив', 'зазначила', 'гукнув', 'гукнула',
        'відказав', 'відказала', 'пояснив', 'пояснила'
    ]
    low = text.lower()
    return any(v in low for v in verbs)

def _split_by_dash(body):
    """
    Розбиває текст по тире та шукає атрибуцію.
    Повертає: [(частина_тексту, is_attribution), ...]
    """
    body = _norm(body)
    parts = []
    current = ""
    
    i = 0
    while i < len(body):
        char = body[i]
        
        # Якщо знайшли тире
        if char in DASH:
            # Зберігаємо попередню частину
            if current.strip():
                parts.append((current.strip(), False))
                current = ""
            
            # Знаходимо кінець атрибуції після тире
            i += 1
            attr_start = i
            
            # Пропускаємо пробіли після тире
            while i < len(body) and body[i] == ' ':
                i += 1
            
            # Шукаємо кінець атрибуції (крапка або нова лапка)
            attr_end = i
            has_attr = False
            
            while attr_end < len(body):
                if body[attr_end] == '.':
                    # Знайшли крапку - перевіряємо, чи це атрибуція
                    potential_attr = body[i:attr_end].strip()
                    if _has_verb(potential_attr):
                        parts.append((potential_attr, True))
                        has_attr = True
                        i = attr_end + 1
                        break
                    else:
                        attr_end += 1
                elif body[attr_end] in QUOTE_START:
                    # Знайшли нову лапку - все до неї може бути атрибуцією
                    potential_attr = body[i:attr_end].strip().rstrip('.')
                    if _has_verb(potential_attr):
                        parts.append((potential_attr, True))
                        has_attr = True
                        i = attr_end
                        break
                    else:
                        attr_end += 1
                else:
                    attr_end += 1
            
            # Якщо не знайшли атрибуцію, можливо вона до кінця рядка
            if not has_attr and i < len(body):
                potential_attr = body[i:].strip().rstrip('.')
                if _has_verb(potential_attr):
                    parts.append((potential_attr, True))
                    i = len(body)
                else:
                    current = body[attr_start-1:attr_end] if attr_end > attr_start else ""
                    i = attr_end
        else:
            current += char
            i += 1
    
    # Додаємо залишок
    if current.strip():
        parts.append((current.strip(), False))
    
    return parts

def _process_body(body):
    """
    Обробляє тіло діалогу, відокремлює атрибуцію.
    Повертає: (cleaned_body, attribution)
    """
    parts = _split_by_dash(body)
    
    if not parts:
        return body, None
    
    # Шукаємо атрибуцію
    dialog_parts = []
    attributions = []
    
    for text, is_attr in parts:
        if is_attr:
            attributions.append(_cap(text))
        else:
            dialog_parts.append(text)
    
    # Якщо знайшли атрибуцію
    if attributions:
        # З'єднуємо частини діалогу
        cleaned = " ".join(dialog_parts).strip()
        
        # Видаляємо зайві коми перед крапкою
        cleaned = re.sub(r',\s*([.!?»"\'])', r'\1', cleaned)
        
        # Додаємо крапку після закритої лапки, якщо немає
        cleaned = re.sub(rf'([{QUOTE_END}])\s+([{QUOTE_START}])', r'\1 \2', cleaned)
        
        # Беремо першу атрибуцію
        attr = attributions[0]
        
        return cleaned, attr
    
    return body, None

def _clean_trailing_narrative(body):
    """
    Відокремлює наратив після атрибуції.
    Приклад: "крикнула Пеґґі. Чи, принаймні..." -> ("крикнула Пеґґі", "Чи, принаймні...")
    """
    # Шукаємо крапку після дієслова + ім'я
    if not _has_verb(body):
        return body, None
    
    # Знаходимо першу крапку після дієслова
    match = re.search(r'\.\s+[А-ЯЇ]', body)
    if match:
        split_pos = match.start() + 1
        attr_part = body[:split_pos].strip()
        narrative_part = body[split_pos:].strip()
        return attr_part, narrative_part
    
    return body, None

def apply(text, ctx):
    lines = text.splitlines(keepends=True)
    out = []
    extracted = 0
    
    for ln in lines:
        eol = "\n" if ln.endswith("\n") else ("\r\n" if ln.endswith("\r\n") else "")
        
        m = TAG.match(ln)
        if not m:
            out.append(ln)
            continue
        
        indent, gid, body = m.groups()
        
        # Пропускаємо наратив
        if gid == "1":
            out.append(ln)
            continue
        
        # Обробляємо діалог
        cleaned, attr = _process_body(body)
        
        if attr:
            # Перевіряємо, чи є наратив після атрибуції
            attr_clean, narrative = _clean_trailing_narrative(attr)
            
            # Перевіряємо, що залишилось щось від діалогу
            test_cleaned = cleaned.strip().rstrip('.!?,—–-')
            if test_cleaned and len(test_cleaned) > 2:
                out.append(f"{indent}#g{gid}: {cleaned}{eol}")
                out.append(f"{indent}#g1: {attr_clean}.{eol}")
                
                # Додаємо наратив окремим рядком, якщо є
                if narrative:
                    out.append(f"{indent}#g1: {narrative}{eol}")
                
                extracted += 1
            else:
                # Якщо нічого не залишилось — оригінал
                out.append(ln)
        else:
            out.append(ln)
    
    try:
        ctx.logs.append(f"[080 extract_attribution] extracted:{extracted}")
    except Exception:
        pass
    
    return "".join(out)


apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
