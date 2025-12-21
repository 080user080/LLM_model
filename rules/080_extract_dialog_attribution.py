# 080_extract_dialog_attribution.py — Остаточна версія з правильним перенесенням наративу
# -*- coding: utf-8 -*-
"""
Остаточна версія:
- Якщо після атрибуції є нові лапки/тире - це нова репліка, залишаємо з оригінальним тегом
- Якщо після атрибуції немає нових лапок - це наратив, переносимо весь текст до #g1
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 80, 0, "fulltext", "extract_dialog_attribution"

NBSP = "\u00A0"
TAG_LINE = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)

# Символи тире та лапок
DASHES = r"[-–—\u2010\u2011\u2012\u2013\u2014\u2015]"
QUOTES = r'[«»"„"'\'']'  # Всі типи лапок
DIALOG_START = re.compile(rf"^\s*(?:{DASHES}|{QUOTES})", re.IGNORECASE)

# Словники
VERBS = (
    r"сказав|сказала|сказали|відповів|відповіла|відповіли|спитав|спитала|спитали|"
    r"запитав|запитала|запитали|крикнув|крикнула|крикнули|вигукнув|вигукнула|вигукнули|"
    r"прошепотів|прошепотіла|прошепотіли|буркнув|буркнула|буркнули|промовив|промовила|"
    r"мовив|мовила|мовили|звернувся|звернулась|звернулися|процедив|процедила|процедили|"
    r"додав|додала|додали|зазначив|зазначила|зазначили|підтвердив|підтвердила|підтвердили|"
    r"заперечив|заперечила|заперечили|погодився|погодилась|погодилися|промовляв|вимовив|"
    r"повторив|повторила|повторили|висловив|висловила|висловили|шепотів|шепотіла|"
    r"гукнув|гукнула|гукнули|відказав|відказала|відказали|запевнив|запевнила|запевнили|"
    r"вибачився|вибачилась|вибачились|запитував|запитувала|звітував|звітувала|коментував|"
    r"нагадав|нагадала|нагадали|зауважив|зауважила|зауважили|відреагував|пояснив|уточнив|"
    r"викликав|спонукав|подумав|подумала|подумали|зітхнув|зітхнула|усміхнувся|розсміявся|"
    r"відповів|відповіла|відповіли|вимовив|вимовила|вимовили|відповідав|відповідала|відповідали"
)

ADVERBS = (
    r"тихо|голосно|повільно|швидко|різко|сумно|радісно|знову|нарешті|раптово|несподівано|"
    r"спокійно|нервово|глибоко|легко|важко|ясно|невпевнено|впевнено|ласкаво|суворо|"
    r"іронічно|серйозно|жартівливо|злісно|доброзичливо|невдоволено|здивовано|сердито|"
    r"весело|лагідно|зосереджено|уважно|неохоче|байдуже|захоплено|тривожно|чітко"
)

SPEAKER = r'(?:[А-ЯЇІЄҐ][А-Яа-яЇїІіЄєҐґ\-\'\s]+|він|вона|вони|воно|ми|ви|я|ти)'

# Основний патерн для атрибуції
PATTERN_END = re.compile(
    rf'(?P<replica>.*?)'  # Репліка
    rf'\s*'  # Пробіли
    rf'(?:[,;]?\s*{DASHES})'  # Розділювач
    rf'\s*'  # Пробіли
    rf'(?P<attr>(?:{ADVERBS}\s+)?{VERBS}\s+{SPEAKER})'  # Атрибуція
    rf'(?P<tail>.*?)$',  # Залишок тексту
    re.IGNORECASE | re.DOTALL
)

def _clean_dialog(text: str) -> str:
    """Очищує діалог для TTS."""
    if not text:
        return text
    text = text.strip()
    # Видаляємо зайві коми/тире в кінці
    while text and text[-1] in ',;—–-':
        text = text[:-1].rstrip()
    # Додаємо крапку, якщо немає завершального знака
    if text and text[-1] not in '.!?…':
        if text[-1] not in '"\'»”':
            text += '.'
    return text

def _clean_narrative(text: str) -> str:
    """Очищує наративний текст."""
    if not text:
        return text
    text = text.strip()
    # Не додаємо крапку - може бути частина речення
    return text

def _process_line(body: str):
    """Обробляє один рядок, повертає список частин."""
    parts = []
    
    # Нормалізуємо пробіли
    body = body.replace(NBSP, ' ').strip()
    
    # Шукаємо атрибуцію в кінці
    match = PATTERN_END.search(body)
    if match:
        replica = match.group('replica')
        attr = match.group('attr')
        tail = match.group('tail').strip() if match.group('tail') else ''
        
        # Очищуємо репліку
        replica_clean = _clean_dialog(replica)
        if replica_clean:
            parts.append(('replica', replica_clean))
        
        # Очищуємо атрибуцію
        attr_clean = attr.strip()
        if attr_clean:
            # Капіталізуємо
            if attr_clean[0].isalpha():
                attr_clean = attr_clean[0].upper() + attr_clean[1:]
            # Додаємо крапку, якщо немає
            if attr_clean[-1] not in '.!?…':
                attr_clean += '.'
        
        # Обробляємо залишок (tail)
        if tail:
            # Перевіряємо, чи tail починається з нового діалогу
            if DIALOG_START.match(tail):
                # Якщо так, то це нова репліка
                tail_clean = _clean_dialog(tail)
                if tail_clean:
                    # Додаємо атрибуцію
                    if attr_clean:
                        parts.append(('attr', attr_clean))
                    # Додаємо нову репліку
                    parts.append(('replica', tail_clean))
            else:
                # Якщо tail не починається з діалогу - це наратив
                # Додаємо весь tail до атрибуції
                narrative = _clean_narrative(tail)
                if narrative:
                    if attr_clean:
                        # Додаємо наратив до атрибуції
                        # Видаляємо крапку з кінця атрибуції, якщо є
                        if attr_clean.endswith('.'):
                            attr_clean = attr_clean[:-1]
                        attr_clean += ' ' + narrative
                        # Додаємо крапку в кінець
                        if not attr_clean.endswith('.'):
                            attr_clean += '.'
                    else:
                        # Якщо атрибуції не було (малоймовірно)
                        attr_clean = narrative
                if attr_clean:
                    parts.append(('attr', attr_clean))
        else:
            # Якщо tail немає, просто додаємо атрибуцію
            if attr_clean:
                parts.append(('attr', attr_clean))
        
        return parts
    
    # Якщо атрибуцію не знайдено, повертаємо оригінал
    return [('replica', _clean_dialog(body))]

def apply(text: str, ctx):
    lines = text.splitlines(keepends=True)
    output_lines = []
    extracted_count = 0
    
    for line in lines:
        m = TAG_LINE.match(line)
        if not m:
            output_lines.append(line)
            continue
        
        indent, gid, body = m.groups()
        
        # Пропускаємо оповідача та рядки, що не починаються з діалогу
        if gid == "1" or not DIALOG_START.match(body):
            output_lines.append(line)
            continue
        
        parts = _process_line(body)
        
        for part_type, part_text in parts:
            if part_type == 'attr':
                output_lines.append(f"{indent}#g1: {part_text}\n")
                extracted_count += 1
            else:
                output_lines.append(f"{indent}#g{gid}: {part_text}\n")
    
    try:
        ctx.logs.append(f"[080 extract_attribution] extracted: {extracted_count}")
    except Exception:
        pass
    
    return "".join(output_lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME