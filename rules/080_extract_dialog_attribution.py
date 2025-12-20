# 080_extract_dialog_attribution.py — виділення атрибуції діалогу у окремий #g1
# -*- coding: utf-8 -*-
"""
Відокремлює атрибуцію діалогу (дієслово мовлення + мовець) від репліки у окремий #g1 рядок.

Приклади:
  БУЛО: #g3: "Пеґ", — сказав тато.
  СТАЛО: 
    #g3: "Пеґ".
    #g1: Сказав тато.

  БУЛО: #g4: "Я забула, тату! " — тихо спитав тато.
  СТАЛО:
    #g4: "Я забула, тату! "
    #g1: Тихо спитав тато.
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 80, 0, "fulltext", "extract_dialog_attribution"

NBSP = "\u00A0"
TAG = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)

# Дієслова мовлення
VERBS = (
    "сказав|сказала|сказали|відповів|відповіла|відповіли|спитав|спитала|спитали|"
    "запитав|запитала|запитали|крикнув|крикнула|крикнули|вигукнув|вигукнула|вигукнули|"
    "прошепотів|прошепотіла|прошепотіли|буркнув|буркнула|буркнули|промовив|промовила|промовили|"
    "мовив|мовила|мовили|звернувся|звернулась|звернулися|процедив|процедила|процедили|"
    "додав|додала|додали|зазначив|зазначила|зазначили|підтвердив|підтвердила|підтвердили|"
    "заперечив|заперечила|заперечили|погодився|погодилась|погодилися"
)

# Прислівники
ADV = "тихо|голосно|повільно|швидко|різко|сумно|радісно|знову|нарешті|раптово|несподівано|спокійно|нервово"

# Патерни атрибуції (з іменем або займенником)
# Формат: [прислівник?] дієслово ім'я/він/вона/вони
ATTR_PATTERN = re.compile(
    rf'\s*[,—–\-]\s*(?:({ADV})\s+)?({VERBS})\s+((?:[А-ЯЇІЄҐ][\wА-Яа-яЇїІіЄєҐґ\'\-]+(?:\s+[А-ЯЇІЄҐ][\wА-Яа-яЇїІіЄєҐґ\'\-]+)?)|він|вона|вони)\.?\s*$',
    re.IGNORECASE
)

def _normalize(s: str) -> str:
    return (s or "").replace(NBSP, " ")

def _capitalize(s: str) -> str:
    s = s.strip()
    return s[0].upper() + s[1:] if s else s

def _clean_punct(s: str) -> str:
    """Видалити зайві розділові знаки в кінці."""
    s = s.rstrip()
    # Видалити кому/тире в кінці
    while s and s[-1] in ',-—–':
        s = s[:-1].rstrip()
    # Залишити одну крапку/знак оклику/питання
    if s and s[-1] not in '.!?':
        s += '.'
    return s

def _extract_attribution(body: str) -> tuple:
    """
    Витягує атрибуцію з тексту діалогу.
    Повертає: (cleaned_body, attribution) або (body, None)
    """
    body = _normalize(body)
    
    # Пошук атрибуції в кінці рядка
    m = ATTR_PATTERN.search(body)
    if not m:
        return body, None
    
    # Витягти частини
    adverb = m.group(1) or ""
    verb = m.group(2) or ""
    speaker = m.group(3) or ""
    
    # Скласти атрибуцію
    parts = []
    if adverb:
        parts.append(adverb.strip())
    if verb:
        parts.append(verb.strip())
    if speaker:
        parts.append(speaker.strip())
    
    attribution = _capitalize(" ".join(parts))
    
    # Очистити body: прибрати атрибуцію
    cleaned = body[:m.start()].rstrip()
    cleaned = _clean_punct(cleaned)
    
    return cleaned, attribution


def apply(text: str, ctx):
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
        
        # Обробляємо лише діалогові рядки (не #g1)
        if gid == "1":
            out.append(ln)
            continue
        
        # Витягти атрибуцію
        cleaned_body, attribution = _extract_attribution(body)
        
        if attribution:
            # Перевірка: чи залишився текст після очищення
            if cleaned_body.strip() and cleaned_body.strip() not in '.,!?—–-':
                out.append(f"{indent}#g{gid}: {cleaned_body}{eol}")
                out.append(f"{indent}#g1: {attribution}.{eol}")
                extracted += 1
            else:
                # Якщо після видалення атрибуції нічого не залишилось — залишаємо оригінал
                out.append(ln)
        else:
            out.append(ln)
    
    try:
        ctx.logs.append(f"[080 extract_attribution] extracted:{extracted}")
    except Exception:
        pass
    
    return "".join(out)


apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
