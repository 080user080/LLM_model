# 080_extract_dialog_attribution.py — Спростіть версія без синтаксичних помилок
# -*- coding: utf-8 -*-
"""
Спрощена версія для виділення атрибуції діалогу без складних регулярних виразів.
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 80, 0, "fulltext", "extract_dialog_attribution"

NBSP = "\u00A0"
TAG_LINE = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)

# Символи тире
DASHES = "-\u2010\u2011\u2012\u2013\u2014\u2015"

# Основні дієслова мовлення
VERBS = [
    'сказав', 'сказала', 'сказали', 'відповів', 'відповіла', 'відповіли',
    'спитав', 'спитала', 'спитали', 'запитав', 'запитала', 'запитали',
    'крикнув', 'крикнула', 'крикнули', 'вигукнув', 'вигукнула', 'вигукнули',
    'прошепотів', 'прошепотіла', 'прошепотіли', 'буркнув', 'буркнула', 'буркнули',
    'промовив', 'промовила', 'промовили', 'мовив', 'мовила', 'мовили',
    'звернувся', 'звернулась', 'звернулися', 'процедив', 'процедила', 'процедили',
    'додав', 'додала', 'додали', 'зазначив', 'зазначила', 'зазначили',
    'підтвердив', 'підтвердила', 'підтвердили', 'заперечив', 'заперечила', 'заперечили',
    'погодився', 'погодилась', 'погодилися', 'повторив', 'повторила', 'повторили',
    'висловив', 'висловила', 'висловили', 'шепотів', 'шепотіла', 'шепотіли',
    'гукнув', 'гукнула', 'гукнули', 'відказав', 'відказала', 'відказали',
    'запевнив', 'запевнила', 'запевнили', 'нагадав', 'нагадала', 'нагадали',
    'зауважив', 'зауважила', 'зауважили', 'пояснив', 'пояснила', 'пояснили',
    'уточнив', 'уточнила', 'уточнили', 'він', 'вона', 'вони'
]

# Прислівники
ADVERBS = [
    'тихо', 'голосно', 'повільно', 'швидко', 'різко', 'сумно', 'радісно',
    'знову', 'нарешті', 'раптово', 'несподівано', 'спокійно', 'нервово',
    'глибоко', 'легко', 'важко', 'ясно', 'невпевнено', 'впевнено',
    'ласкаво', 'суворо', 'іронічно', 'серйозно', 'жартівливо', 'злісно',
    'доброзичливо', 'невдоволено', 'здивовано', 'сердито', 'весело', 'лагідно'
]

def _clean_text(text):
    """Очищує текст від зайвих пробілів та NBSP."""
    if not text:
        return text
    return text.replace(NBSP, ' ').strip()

def _add_punctuation(text):
    """Додає пунктуацію в кінець тексту, якщо потрібно."""
    if not text:
        return text
    
    text = text.strip()
    if not text:
        return text
    
    # Якщо вже є пунктуація - не додаємо
    if text[-1] in '.!?…':
        return text
    
    # Якщо закінчується лапками - не додаємо
    if text[-1] in '"\'»”':
        return text
    
    return text + '.'

def _capitalize(text):
    """Робить першу літеру великою."""
    if not text:
        return text
    return text[0].upper() + text[1:]

def _find_attribution(text):
    """
    Знаходить атрибуцію в тексті.
    Повертає (replica, attribution, остаток) або (None, None, None)
    """
    # Нормалізуємо текст
    text = _clean_text(text)
    
    # Шукаємо тире в тексті
    for dash in DASHES:
        if dash in text:
            # Знаходимо позицію останнього тире (щоб захопити всю атрибуцію)
            dash_pos = text.rfind(dash)
            
            if dash_pos > 0:
                replica = text[:dash_pos].strip()
                after_dash = text[dash_pos+1:].strip()
                
                # Спробуємо знайти атрибуцію після тире
                # Шукаємо дієслово в тексті після тире
                for verb in VERBS:
                    # Перевіряємо, чи починається текст після тире з дієслова (з урахуванням прислівників)
                    lower_after = after_dash.lower()
                    
                    # Може бути прислівник перед дієсловом
                    found_verb = False
                    verb_pos = -1
                    
                    # Спочатку шукаємо сам дієслово
                    if verb in lower_after:
                        verb_pos = lower_after.find(verb)
                        found_verb = True
                    
                    # Якщо знайшли дієслово
                    if found_verb and verb_pos >= 0:
                        # Знаходимо кінець атрибуції - шукаємо крапку після дієслова
                        dot_pos = after_dash.find('.', verb_pos)
                        if dot_pos == -1:
                            dot_pos = len(after_dash)
                        
                        attribution = after_dash[:dot_pos].strip()
                        remaining = after_dash[dot_pos:].strip()
                        
                        # Видаляємо крапку з початку залишку, якщо є
                        if remaining.startswith('.'):
                            remaining = remaining[1:].strip()
                        
                        # Перевіряємо, чи attribution містить дійсно атрибуцію
                        # Повинно бути пробіл після дієслова (дієслово + хтось)
                        if ' ' in attribution and len(attribution.split()) >= 2:
                            # Очищаємо репліку
                            replica = _add_punctuation(replica)
                            
                            # Форматуємо атрибуцію
                            attribution = _capitalize(attribution)
                            attribution = _add_punctuation(attribution)
                            
                            # Аналізуємо залишок
                            if remaining:
                                # Перевіряємо, чи залишок починається з нової репліки (лапки або тире)
                                if (remaining.startswith('"') or remaining.startswith("'") or 
                                    remaining.startswith('«') or remaining.startswith('„') or
                                    remaining.startswith('"') or remaining[0] in DASHES):
                                    # Це нова репліка
                                    remaining = _add_punctuation(remaining)
                                    return replica, attribution, remaining, True
                                else:
                                    # Це наратив, додаємо до атрибуції
                                    if attribution.endswith('.'):
                                        attribution = attribution[:-1]
                                    attribution += ' ' + remaining
                                    attribution = _add_punctuation(attribution)
                                    remaining = ""
                                    return replica, attribution, remaining, False
                            else:
                                return replica, attribution, "", False
    
    return None, None, None, False

def apply(text, ctx):
    """
    Головна функція обробки тексту.
    """
    lines = text.splitlines(keepends=True)
    output_lines = []
    extracted_count = 0
    
    for line in lines:
        # Перевіряємо, чи це тегований рядок
        tag_match = TAG_LINE.match(line)
        if not tag_match:
            output_lines.append(line)
            continue
        
        indent, gid, content = tag_match.groups()
        
        # Пропускаємо рядки оповідача
        if gid == "1":
            output_lines.append(line)
            continue
        
        # Шукаємо атрибуцію в рядку
        replica, attribution, remaining, is_new_replica = _find_attribution(content)
        
        if replica and attribution:
            # Додаємо репліку
            output_lines.append(f"{indent}#g{gid}: {replica}\n")
            
            # Додаємо атрибуцію
            output_lines.append(f"{indent}#g1: {attribution}\n")
            extracted_count += 1
            
            # Додаємо залишок, якщо є
            if remaining:
                if is_new_replica:
                    # Це нова репліка - той же тег
                    output_lines.append(f"{indent}#g{gid}: {remaining}\n")
                else:
                    # Це вже додано до атрибуції
                    pass
        else:
            # Якщо атрибуцію не знайшли, додаємо оригінальний рядок
            output_lines.append(line)
    
    # Логуємо результат
    try:
        ctx.logs.append(f"[080 extract_attribution] extracted: {extracted_count}")
    except Exception:
        pass
    
    return "".join(output_lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME