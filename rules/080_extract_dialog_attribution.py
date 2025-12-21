# Ключові виправлення:

# 1. ПОЛІПШЕНА ФУНКЦІЯ _find_quote_boundaries
def _find_quote_boundaries(text: str):
    """Знаходить ВСІ пари лапок у тексті"""
    text = _norm(text)
    quotes = []
    i = 0
    while i < len(text):
        if text[i] in QUOTE_OPEN:
            start = i
            # Шукаємо відповідну закриваючу лапку
            j = i + 1
            while j < len(text) and text[j] not in QUOTE_CLOSE:
                j += 1
            if j < len(text):
                end = j
                quotes.append((start, end))
                i = j + 1
                continue
        i += 1
    return quotes

# 2. ПОЛІПШЕНА ФУНКЦІЯ _is_attribution
def _is_attribution(text: str) -> bool:
    """Атрибуція: містить дієслово мовлення + (ім'я або 'він/вона/тато/мама')"""
    if not text:
        return False
    
    # Прибираємо початкові коми, тире
    cleaned = re.sub(r'^[,\—\–\-\s]+', '', text)
    
    # Перевірка дієслова мовлення
    if not _has_speech_verb(cleaned):
        return False
    
    # Перевірка на ім'я або родинний зв'язок
    low = cleaned.lower()
    name_patterns = [
        r'\b[А-ЯІЇЄҐ][а-яіїєґ\']+\b',  # Ім'я з великої літери
        r'\b(тато|мама|батько|мати)\b',
        r'\b(він|вона|вони)\b'
    ]
    
    for pattern in name_patterns:
        if re.search(pattern, low):
            return True
    
    return False

# 3. ПОЛІПШЕНА ФУНКЦІЯ _split_by_structure
def _split_by_structure(body: str):
    """Знаходить всі діалоги та текст між ними"""
    body = _norm(body).strip()
    if not body:
        return []
    
    # Знаходимо всі позиції лапок
    quotes = _find_quote_boundaries(body)
    if not quotes:
        # Немає лапок - весь текст наратив
        return [(body, 'narrative')]
    
    parts = []
    prev_end = 0
    
    for start, end in quotes:
        # Текст перед діалогом
        if start > prev_end:
            before = body[prev_end:start].strip()
            if before:
                parts.append((before, 'narrative'))
        
        # Сам діалог
        dialog = body[start:end+1].strip()
        parts.append((dialog, 'dialog'))
        
        prev_end = end + 1
    
    # Текст після останнього діалогу
    if prev_end < len(body):
        after = body[prev_end:].strip()
        if after:
            # Перевіряємо, чи це атрибуція
            if _is_attribution(after):
                parts.append((after, 'attribution'))
            else:
                parts.append((after, 'narrative'))
    
    return parts