# 080_extract_dialog_attribution.py — виділення атрибуції діалогу для TTS (v4)
# -*- coding: utf-8 -*-
"""
ПРОСТА ВЕРСІЯ: Знаходить діалоги у лапках і відокремлює атрибуцію.
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

def _extract_dialog_and_attribution(body: str):
    """Повертає (діалог, атрибуція, залишок)"""
    body = _norm(body).strip()
    
    # Шукаємо перші лапки
    quote_chars = ['«', '»', '"', '“', '”']
    start = -1
    for i, char in enumerate(body):
        if char in quote_chars:
            start = i
            break
    
    if start == -1:
        return None, None, body  # Немає діалогу
    
    # Шукаємо закриваючу лапку
    end = -1
    for i in range(start + 1, len(body)):
        if body[i] in quote_chars:
            end = i
            break
    
    if end == -1:
        return None, None, body  # Лапка не закрита
    
    dialog = body[start:end+1].strip()
    before = body[:start].strip()
    after = body[end+1:].strip()
    
    return dialog, before, after

def _is_attribution(text: str) -> bool:
    """Визначає, чи є текст атрибуцією"""
    if not text:
        return False
    
    # Дієслова мовлення
    speech_verbs = ['сказав', 'сказала', 'спитав', 'спитала', 'відповів', 'відповіла', 
                    'крикнув', 'крикнула', 'прошепотів', 'прошепотіла', 'додав', 'додала',
                    'запитав', 'запитала', 'промовив', 'промовила', 'відповів', 'відповіла']
    
    # Слова, які вказують на атрибуцію
    attribution_words = ['він', 'вона', 'вони', 'тато', 'мама', 'батько', 'мати', 
                         'Пеґґі', 'Пеґ', 'Горас', 'Мері']
    
    text_lower = text.lower()
    
    # Перевірка на наявність дієслова мовлення
    has_speech = any(verb in text_lower for verb in speech_verbs)
    
    # Перевірка на наявність слів атрибуції
    has_attribution = any(word in text_lower for word in attribution_words)
    
    # Атрибуція, якщо є дієслово мовлення І (ім'я або займенник)
    return has_speech and has_attribution

def _clean_attribution(text: str) -> str:
    """Очищає атрибуцію від зайвих символів"""
    if not text:
        return ""
    
    # Прибираємо початкові коми, тире, пробіли
    text = re.sub(r'^[,\—\–\-\s]+', '', text)
    
    # Прибираємо зайві символи в кінці
    text = re.sub(r'[,\—\–\-\s]+$', '', text)
    
    return text.strip()

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
        
        # Витягуємо діалог
        dialog, before, after = _extract_dialog_and_attribution(body)
        
        if not dialog:
            # Немає діалогу - залишаємо як є
            out.append(ln)
            continue
        
        # Текст перед діалогом (атрибуція)
        if before and _is_attribution(before):
            cleaned = _clean_attribution(before)
            out.append(f"{indent}#g1: {cleaned}{eol}")
        
        # Сам діалог
        out.append(f"{indent}#g{gid}: {dialog}{eol}")
        
        # Текст після діалогу
        if after:
            # Перевіряємо, чи це атрибуція
            if _is_attribution(after):
                cleaned = _clean_attribution(after)
                out.append(f"{indent}#g1: {cleaned}{eol}")
            else:
                # Якщо текст після діалогу не атрибуція, додаємо його до діалогу
                # (це може бути продовження діалогу)
                # Але спочатку перевіримо, чи це не наратив
                if after.startswith('—') or after.startswith('--'):
                    # Якщо починається з тире - це продовження діалогу
                    out.append(f"{indent}#g{gid}: {dialog} {after}{eol}")
                else:
                    # Інакше - це наратив
                    out.append(f"{indent}#g1: {after}{eol}")
    
    return ''.join(out)

apply.phase = PHASE
apply.priority = PRIORITY
apply.scope = SCOPE
apply.name = NAME