# 080_extract_dialog_attribution.py — виділення атрибуції діалогу для TTS (v2)
# -*- coding: utf-8 -*-
"""
Відокремлює атрибуцію від діалогу для TTS-озвучення.
Універсальна обробка: діалог → [наратив] → [атрибуція] → [наратив]

Логіка розпізнавання:
1. Діалог = текст у лапках або після тире
2. Атрибуція = фрагмент з дієсловом мовлення + ім'я/займенник
3. Наратив = все інше (описи, думки, дії)

Вихід:
  #gN: <чистий діалог>
  #g1: <наратив, якщо є>
  #g1: <атрибуція, якщо є>
  #g1: <наратив після атрибуції, якщо є>
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 80, 0, "fulltext", "extract_dialog_attribution"

NBSP = "\u00A0"
TAG = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)

# Всі види тире та лапок
DASH_CHARS = "—–-\u2012\u2013\u2014\u2015"
QUOTE_OPEN = '«"„"\''
QUOTE_CLOSE = '»""\''

# Дієслова мовлення (розширений список)
SPEECH_VERBS = [
    'сказав', 'сказала', 'відповів', 'відповіла', 'спитав', 'спитала',
    'запитав', 'запитала', 'крикнув', 'крикнула', 'вигукнув', 'вигукнула',
    'прошепотів', 'прошепотіла', 'буркнув', 'буркнула', 'промовив', 'промовила',
    'мовив', 'мовила', 'звернувся', 'звернулась', 'процедив', 'процедила',
    'додав', 'додала', 'зазначив', 'зазначила', 'гукнув', 'гукнула',
    'відказав', 'відказала', 'пояснив', 'пояснила', 'шепотів', 'шепотіла',
    'торохтів', 'торохтіла', 'каже', 'кажу', 'говорить', 'говорю',
    'відповідає', 'відповідаю', 'питає', 'питаю'
]

def _norm(s):
    """Нормалізація: NBSP → пробіл"""
    return (s or "").replace(NBSP, " ")

def _has_speech_verb(text):
    """Перевірка наявності дієслова мовлення"""
    low = text.lower()
    return any(f'\\b{v}\\b' for v in SPEECH_VERBS if re.search(rf'\b{v}\b', low))

def _has_name_or_pronoun(text):
    """Перевірка наявності імені (велика літера) або займенника"""
    # Ім'я: слово з великої літери
    if re.search(r'\b[A-ZА-ЯЇІЄҐ][а-яїієґ\''\-]+\b', text):
        return True
    # Займенники: я, він, вона, ти, ви
    if re.search(r'\b(я|він|вона|ти|ви|його|її|йому|їй)\b', text.lower()):
        return True
    return False

def _is_attribution(text):
    """
    Атрибуція = дієслово мовлення + (ім'я або займенник)
    Приклади:
      - "сказала маленька Пеґґі"
      - "крикнув він"
      - "відповіла вона"
    """
    return _has_speech_verb(text) and _has_name_or_pronoun(text)

def _find_quote_boundaries(text):
    """
    Знаходить межі цитати (лапки).
    Повертає: (start_idx, end_idx) або (None, None)
    """
    text = _norm(text)
    
    # Шукаємо відкриваючу лапку
    open_idx = None
    for i, char in enumerate(text):
        if char in QUOTE_OPEN:
            open_idx = i
            break
    
    if open_idx is None:
        return None, None
    
    # Шукаємо закриваючу лапку
    close_idx = None
    for i in range(open_idx + 1, len(text)):
        if text[i] in QUOTE_CLOSE:
            close_idx = i
            break
    
    if close_idx is None:
        # Лапка не закрита — беремо до кінця
        close_idx = len(text) - 1
    
    return open_idx, close_idx

def _split_by_structure(body):
    """
    Розбиває тіло на структурні частини.
    Повертає: [(text, type), ...]
    type = 'dialog' | 'attribution' | 'narrative'
    
    Алгоритм:
    1. Якщо є лапки — виділяємо діалог у лапках
    2. Якщо починається з тире — діалог до першого тире всередині
    3. Все після діалогу аналізуємо на наратив/атрибуцію
    """
    body = _norm(body).strip()
    if not body:
        return []
    
    parts = []
    
    # === КРОК 1: Виділяємо діалог ===
    
    # Варіант A: діалог у лапках
    open_idx, close_idx = _find_quote_boundaries(body)
    if open_idx is not None:
        # Діалог = від відкриваючої до закриваючої лапки (включно)
        dialog = body[open_idx:close_idx+1].strip()
        parts.append((dialog, 'dialog'))
        
        # Залишок після діалогу
        rest = body[close_idx+1:].strip()
    else:
        # Варіант B: діалог починається з тире
        if body[0] in DASH_CHARS:
            # Шукаємо наступне тире (початок атрибуції) або кінець
            next_dash = None
            for i in range(1, len(body)):
                if body[i] in DASH_CHARS:
                    # Перевіряємо, чи це не просто дефіс у слові
                    if i > 0 and body[i-1] in '.!?…"»"\' ':
                        next_dash = i
                        break
            
            if next_dash:
                dialog = body[:next_dash].strip()
                rest = body[next_dash:].strip()
            else:
                # Тире тільки на початку — весь текст діалог
                dialog = body.strip()
                rest = ""
            
            parts.append((dialog, 'dialog'))
        else:
            # Немає ні лапок, ні тире — це не діалог, а наратив
            # Але ми в контексті #gN (не #g1), тому це помилка розмітки
            # Повертаємо як є
            return [(body, 'narrative')]
    
    # === КРОК 2: Аналізуємо залишок ===
    if not rest:
        return parts
    
    # Прибираємо початкове тире, якщо є
    rest = rest.lstrip(''.join(DASH_CHARS)).strip()
    
    # Розбиваємо на речення (по крапці/знаку оклику/питання + велика літера)
    sentences = re.split(r'([.!?…]\s+(?=[A-ZА-ЯЇІЄҐ]))', rest)
    
    # Склеюємо назад (split розбиває і роздільник теж потрапляє)
    reconstructed = []
    i = 0
    while i < len(sentences):
        if i + 1 < len(sentences) and re.match(r'[.!?…]\s+$', sentences[i+1]):
            # Це роздільник — склеюємо з попереднім
            reconstructed.append(sentences[i] + sentences[i+1])
            i += 2
        else:
            reconstructed.append(sentences[i])
            i += 1
    
    # Тепер аналізуємо кожне речення
    for sent in reconstructed:
        sent = sent.strip()
        if not sent:
            continue
        
        if _is_attribution(sent):
            parts.append((sent, 'attribution'))
        else:
            parts.append((sent, 'narrative'))
    
    return parts

def _merge_consecutive(parts):
    """Об'єднує послідовні частини одного типу"""
    if not parts:
        return []
    
    merged = []
    current_text, current_type = parts[0]
    
    for text, ptype in parts[1:]:
        if ptype == current_type:
            # Об'єднуємо
            current_text += " " + text
        else:
            # Зберігаємо попередню і починаємо нову
            merged.append((current_text.strip(), current_type))
            current_text, current_type = text, ptype
    
    # Додаємо останню
    merged.append((current_text.strip(), current_type))
    
    return merged

def _clean_dialog(text):
    """Прибирає зайві тире/пунктуацію з діалогу"""
    text = text.strip()
    
    # Прибираємо початкове тире
    if text and text[0] in DASH_CHARS:
        text = text[1:].strip()
    
    # Прибираємо кінцеве тире перед лапкою
    text = re.sub(rf'\s*[{re.escape(DASH_CHARS)}]\s*([{re.escape(QUOTE_CLOSE)}])$', r'\1', text)
    
    return text.strip()

def _add_period(text):
    """Додає крапку в кінець, якщо немає пунктуації"""
    text = text.strip()
    if text and text[-1] not in '.!?…':
        text += '.'
    return text

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
        
        # Пропускаємо наратив (#g1)
        if gid == "1":
            out.append(ln)
            continue
        
        # === Обробляємо діалог (#gN, #g?) ===
        parts = _split_by_structure(body)
        
        if not parts:
            out.append(ln)
            continue
        
        # Об'єднуємо однотипні частини
        parts = _merge_consecutive(parts)
        
        # Якщо є тільки діалог — залишаємо як є
        if len(parts) == 1 and parts[0][1] == 'dialog':
            out.append(ln)
            continue
        
        # Якщо немає діалогу взагалі — помилка розмітки, пропускаємо
        if not any(p[1] == 'dialog' for p in parts):
            out.append(ln)
            continue
        
        # === Формуємо вихід ===
        dialog_text = None
        narrative_parts = []
        attribution_parts = []
        
        for text, ptype in parts:
            if ptype == 'dialog':
                dialog_text = _clean_dialog(text)
            elif ptype == 'narrative':
                narrative_parts.append(text)
            elif ptype == 'attribution':
                attribution_parts.append(text)
        
        # Перевіряємо, що залишився діалог
        if not dialog_text or len(dialog_text.strip()) < 3:
            out.append(ln)
            continue
        
        # Виводимо діалог
        out.append(f"{indent}#g{gid}: {dialog_text}{eol}")
        
        # Виводимо наратив (якщо є)
        if narrative_parts:
            for narr in narrative_parts:
                narr_clean = _add_period(narr)
                out.append(f"{indent}#g1: {narr_clean}{eol}")
        
        # Виводимо атрибуцію (якщо є)
        if attribution_parts:
            for attr in attribution_parts:
                attr_clean = _add_period(attr)
                out.append(f"{indent}#g1: {attr_clean}{eol}")
        
        extracted += 1
    
    try:
        ctx.logs.append(f"[080 extract_attribution] extracted:{extracted}")
    except Exception:
        pass
    
    return "".join(out)


apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
