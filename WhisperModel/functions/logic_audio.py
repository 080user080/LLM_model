# functions/logic_audio.py
"""Робота з аудіо"""
import re
import numpy as np
from colorama import Fore
from .config import (
    VOLUME_THRESHOLD, MIN_COMMAND_LENGTH, IGNORE_PHRASES, 
    WHISPER_CORRECTIONS, ACTIVATION_WORD, ACTIVATION_SIMILARITY_THRESHOLD
)

def check_volume(audio):
    """Перевірити чи є звук (не тиша)"""
    return np.abs(audio).mean() > VOLUME_THRESHOLD

def should_ignore_command(text):
    """Перевірити чи команду потрібно ігнорувати"""
    if not text or not text.strip():
        return True
    
    # Очистити текст
    cleaned = text.strip().lower()
    cleaned = re.sub(r'[^\w\sа-яґєії]', '', cleaned, flags=re.IGNORECASE)
    
    # Перевірити довжину (без пробілів)
    text_without_spaces = re.sub(r'\s+', '', cleaned)
    if len(text_without_spaces) < MIN_COMMAND_LENGTH:
        return True
    
    # Перевірити чи це ігнорована фраза
    for phrase in IGNORE_PHRASES:
        phrase_lower = phrase.lower().strip()
        if phrase_lower in cleaned:
            if cleaned == phrase_lower or \
               cleaned.startswith(phrase_lower + " ") or \
               cleaned.endswith(" " + phrase_lower) or \
               f" {phrase_lower} " in f" {cleaned} ":
                return True
    
    # Якщо текст містить лише цифри або символи
    if re.match(r'^[\d\s]+$', cleaned):
        return True
    
    return False

def correct_whisper_text(text):
    """Виправити помилки розпізнавання Whisper"""
    text_lower = text.lower()
    
    # Виправити помилки
    for wrong, correct in WHISPER_CORRECTIONS.items():
        if wrong in text_lower:
            text_lower = text_lower.replace(wrong, correct)
    
    # Відновити першу букву велику
    if text_lower and text_lower[0].isalpha():
        text_lower = text_lower[0].upper() + text_lower[1:]
    
    return text_lower

def text_similarity(text1, text2):
    """Обчислити схожість між двома текстами (Levenshtein distance)"""
    text1 = text1.lower().strip()
    text2 = text2.lower().strip()
    
    if text1 == text2:
        return 1.0
    
    # Перевірити чи одне слово містить інше
    if text1 in text2 or text2 in text1:
        return 0.8
    
    # Levenshtein distance
    def levenshtein_distance(s1, s2):
        if len(s1) < len(s2):
            return levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    distance = levenshtein_distance(text1, text2)
    max_len = max(len(text1), len(text2))
    
    if max_len == 0:
        return 1.0
    
    similarity = 1.0 - (distance / max_len)
    return max(0.0, similarity)

def check_activation_word(text):
    """Перевірити чи текст містить активаційне слово"""
    if not ACTIVATION_WORD:
        return True  # 🔥 Якщо активація вимкнена - завжди true
    
    text_lower = text.lower().strip()
    
    # Ігнорувати дуже короткі тексти
    if len(text_lower) < 2:
        return False
    
    words = text_lower.split()
    activation_word_lower = ACTIVATION_WORD.lower()
    
    # 🔥 НОВИЙ: Точне співпадіння слова
    if activation_word_lower in words:
        return True
    
    # 🔥 НОВИЙ: Перевірка на початку тексту
    if text_lower.startswith(activation_word_lower + " "):
        return True
    
    # Стара логіка з similarity для помилок розпізнавання
    min_length = max(2, len(activation_word_lower) - 2)
    
    for word in words:
        if len(word) < min_length:
            continue
            
        similarity = text_similarity(word, activation_word_lower)
        if similarity >= ACTIVATION_SIMILARITY_THRESHOLD:
            return True
    
    return False

def remove_activation_word(text):
    """Видалити активаційне слово з тексту"""
    if not ACTIVATION_WORD:
        return text
    
    activation_lower = ACTIVATION_WORD.lower()
    text_lower = text.lower()
    
    # 🔥 НОВИЙ: Точне видалення на початку
    if text_lower.startswith(activation_lower + " "):
        result = text[len(activation_lower):].strip()
        return result
    
    if text_lower.startswith(activation_lower + ","):
        result = text[len(activation_lower) + 1:].strip()
        return result
    
    # Видалити як окреме слово
    words = text.split()
    filtered_words = []
    
    for word in words:
        word_lower = word.lower().strip(',.!?;:')
        
        # Точне співпадіння
        if word_lower == activation_lower:
            continue
        
        # Similarity перевірка
        similarity = text_similarity(word_lower, activation_lower)
        if similarity < ACTIVATION_SIMILARITY_THRESHOLD:
            filtered_words.append(word)
    
    result = " ".join(filtered_words).strip()
    
    # 🔥 НОВИЙ: Якщо результат порожній, повернути оригінал без першого слова
    if not result and len(words) > 1:
        return " ".join(words[1:]).strip()
    
    return result if result else text