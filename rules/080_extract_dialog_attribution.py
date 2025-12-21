# 080_extract_dialog_attribution.py — виділення атрибуції діалогу для TTS (v5)
# -*- coding: utf-8 -*-
"""
Основна логіка: знаходить діалоги, атрибуції, об'єднує розділені діалоги
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 80, 0, "fulltext", "extract_dialog_attribution"

NBSP = "\u00A0"
TAG = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)

def _norm(s: str) -> str:
    """Нормалізація пробілів"""
    if s is None:
        return ""
    return (
        s.replace(NBSP, " ")
         .replace('\u202F', ' ')
         .replace('\u2009', ' ')
         .replace('\u2007', ' ')
         .replace('\u200A', ' ')
         .replace('\u200B', '')
    )

def _find_all_dialogs_in_line(body: str):
    """Знаходить всі діалоги в рядку та позиції"""
    body = _norm(body)
    dialogs = []
    i = 0
    
    while i < len(body):
        # Шукаємо відкриваючу лапку
        if body[i] in ['«', '"', '“', "'"]:
            start = i
            i += 1
            # Шукаємо закриваючу лапку
            while i < len(body) and body[i] not in ['»', '"', '”', "'"]:
                i += 1
            if i < len(body):
                end = i
                dialog_text = body[start:end+1]
                dialogs.append((start, end, dialog_text))
        i += 1
    
    return dialogs

def _is_attribution(text: str) -> bool:
    """Визначає, чи є текст атрибуцією"""
    if not text:
        return False
    
    # Дієслова мовлення
    speech_verbs = ['сказав', 'сказала', 'спитав', 'спитала', 'відповів', 'відповіла', 
                    'крикнув', 'крикнула', 'прошепотів', 'прошепотіла', 'додав', 'додала',
                    'запитав', 'запитала', 'промовив', 'промовила', 'відповів', 'відповіла',
                    'зазначив', 'зазначила', 'повторив', 'повторила', 'гукнув', 'гукнула']
    
    # Слова, які вказують на атрибуцію
    attribution_words = ['він', 'вона', 'вони', 'тато', 'мама', 'батько', 'мати', 
                         'Пеґґі', 'Пеґ', 'Горас', 'Мері', 'мене', 'тебе', 'нам', 'вам']
    
    text_lower = text.lower()
    
    # Перевірка на наявність дієслова мовлення
    has_speech = any(verb in text_lower for verb in speech_verbs)
    
    # Перевірка на наявність слів атрибуції
    has_attribution = any(re.search(rf'\b{re.escape(word)}\b', text_lower) 
                         for word in attribution_words)
    
    # Атрибуція, якщо є дієслово мовлення І (ім'я або займенник)
    return has_speech and has_attribution

def _extract_attribution_and_dialog(text: str):
    """Виділяє атрибуцію та діалог з тексту"""
    text = _norm(text).strip()
    dialogs = _find_all_dialogs_in_line(text)
    
    if not dialogs:
        return text, None  # Тільки текст (можливо атрибуція)
    
    # Якщо є діалоги, розділяємо текст навколо них
    result = []
    current_pos = 0
    
    for start, end, dialog in dialogs:
        # Текст перед діалогом
        before = text[current_pos:start].strip()
        if before:
            result.append(('text', before))
        
        # Діалог
        result.append(('dialog', dialog))
        current_pos = end + 1
    
    # Текст після останнього діалогу
    after = text[current_pos:].strip()
    if after:
        result.append(('text', after))
    
    return result

def apply(text: str, ctx):
    lines = text.splitlines(keepends=True)
    out = []
    
    for ln in lines:
        eol = "\n" if ln.endswith("\n") else ("\r\n" if ln.endswith("\r\n") else "")
        m = TAG.match(ln)
        if not m:
            out.append(ln)
            continue
        
        indent, gid, body = m.groups()
        
        # Пропускаємо наратив (#g1)
        if gid == "1":
            out.append(ln)
            continue
        
        # Витягуємо всі частини рядка
        parts = _extract_attribution_and_dialog(body)
        
        if isinstance(parts, str):
            # Немає діалогів
            out.append(ln)
            continue
        
        # Обробляємо частини
        for part_type, part_text in parts:
            if part_type == 'dialog':
                # Діалог - залишаємо з оригінальним тегом
                out.append(f"{indent}#g{gid}: {part_text}{eol}")
            else:
                # Текст - перевіряємо, чи це атрибуція
                if _is_attribution(part_text):
                    # Очищаємо атрибуцію
                    cleaned = re.sub(r'^[,\—\–\-\s]+', '', part_text)
                    cleaned = re.sub(r'[,\—\–\-\s]+$', '', cleaned)
                    if cleaned:
                        out.append(f"{indent}#g1: {cleaned}{eol}")
                else:
                    # Не атрибуція - додаємо як #g1
                    if part_text:
                        out.append(f"{indent}#g1: {part_text}{eol}")
    
    return ''.join(out)

apply.phase = PHASE
apply.priority = PRIORITY
apply.scope = SCOPE
apply.name = NAME