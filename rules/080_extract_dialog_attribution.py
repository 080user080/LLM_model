# 080_extract_dialog_attribution.py — виділення атрибуції діалогу для TTS (v2) — виправлена версія
# -*- coding: utf-8 -*-
"""
Відокремлює атрибуцію від діалогу для TTS-озвучення.
Універсальна обробка: діалог → [наратив] → [атрибуція] → [наратив]

Виправлення у цій версії:
- усунено помилку в _has_speech_verb (було повернення генератора замість булевого)
- покращено набір лапок/закриваючих символів
- захищено регулярні вирази через re.escape в динамічних патернах
- підвищено стійкість до пробілів/NBSP
- інші дрібні стабілізації
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 80, 0, "fulltext", "extract_dialog_attribution"

NBSP = "\u00A0"
TAG = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)

# Всі види тире та лапок
DASH_CHARS = "\u2014\u2013\u2012\u2015\u2010-—–"
# Явний набір відкривних/закривних лапок — включає ASCII і типові юнікод-лапки
QUOTE_OPEN = set(["\u00AB", '«', '“', '„', '"', "'", '’'])
QUOTE_CLOSE = set(["\u00BB", '»', '”', '"', "'", '’'])

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


def _norm(s: str) -> str:
    """Нормалізація: NBSP/інші невидимі пробіли → звичайний пробіл"""
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


def _has_speech_verb(text: str) -> bool:
    """Перевірка наявності дієслова мовлення (стійко, з екрануванням шаблонів).
    Повертає True, якщо знайдено будь-яке зі SPEECH_VERBS як окреме слово.
    """
    if not text:
        return False
    low = text.lower()
    for v in SPEECH_VERBS:
        # екраніруємо, щоб уникнути спецсимволів у слові
        pat = rf"\b{re.escape(v)}\b"
        if re.search(pat, low):
            return True
    return False


def _has_name_or_pronoun(text: str) -> bool:
    """Перевірка наявності імені (перша буква велика) або займенника.
    Ім'я — слово, що починається з великої літери українського/латинського алфавіту.
    """
    if not text:
        return False
    # Перевірка імені: слово з великої літери (укр/лат)
    # Допускаємо апостроф, дефіс і подвійні прізвища
    name_pattern = re.compile(r"\b[А-ЯA-ZІЇЄҐ][а-яa-zіїєґ'’\-]+\b")
    if name_pattern.search(text):
        return True
    # Перевірка займенників (виконуємо по нижньому регістру)
    pronouns = r"\b(я|він|вона|ти|ви|його|її|йому|їй|ми|вони)\b"
    if re.search(pronouns, text.lower()):
        return True
    return False


def _is_attribution(text: str) -> bool:
    """Атрибуція = дієслово мовлення + (ім'я або займенник).
    Виконуємо незалежно від порядку частин — якщо в реченні є слово мовлення
    та є ім'я/займенник, трактуємо як атрибуцію.
    """
    return _has_speech_verb(text) and _has_name_or_pronoun(text)


def _find_quote_boundaries(text: str):
    """Знаходить межі цитати (лапки). Повертає кортеж (open_idx, close_idx) або (None, None).
    Обираємо першу відкриваючу лапку і першу наступну закриваючу після неї.
    """
    text = _norm(text)
    open_idx = None
    for i, ch in enumerate(text):
        if ch in QUOTE_OPEN:
            open_idx = i
            break
    if open_idx is None:
        return None, None
    close_idx = None
    for i in range(open_idx + 1, len(text)):
        if text[i] in QUOTE_CLOSE:
            close_idx = i
            break
    if close_idx is None:
        close_idx = len(text) - 1
    return open_idx, close_idx


def _split_by_structure(body: str):
    """Розбиває тіло на структурні частини: [(text, type), ...]
    type = 'dialog' | 'attribution' | 'narrative'
    """
    body = _norm(body).strip()
    if not body:
        return []

    parts = []

    # Крок 1: виділити діалог у лапках
    open_idx, close_idx = _find_quote_boundaries(body)
    if open_idx is not None:
        dialog = body[open_idx:close_idx+1].strip()
        parts.append((dialog, 'dialog'))
        rest = body[close_idx+1:].strip()
    else:
        # Варіант: починається з тире — діалог
        if body and body[0] in DASH_CHARS:
            # беремо до першого розриву (коли після тире іде коротка фраза атрибуції)
            # якщо немає — весь рядок діалог
            # знайдемо інші тире, які ймовірно відокремлюють частини
            next_pos = None
            for i in range(1, len(body)):
                if body[i] in DASH_CHARS:
                    # перевірка – перед цим може стояти пробіл або знак пунктуації
                    prev = body[i-1]
                    if prev.isspace() or prev in '.!?:;"\'':
                        next_pos = i
                        break
            if next_pos:
                dialog = body[:next_pos].strip()
                rest = body[next_pos:].strip()
            else:
                dialog = body.strip()
                rest = ''
            parts.append((dialog, 'dialog'))
        else:
            # не діалог — повертаємо як наратив
            return [(body, 'narrative')]

    if not rest:
        return parts

    # Прибираємо провідні тире/пробіли
    rest = rest.lstrip(''.join(DASH_CHARS)).strip()

    # Розбиваємо решту на логічні фрагменти (речення). Простий підхід: split по крапках/знаках
    # разом із збереженням роздільників
    segs = re.split(r'([.!?…](?:\s+|$))', rest)
    # склеїмо назад сегменти у повні речення
    sentences = []
    buf = ''
    for s in segs:
        if not s:
            continue
        buf += s
        if re.search(r'[.!?…]\s*$', s):
            sentences.append(buf.strip())
            buf = ''
    if buf:
        sentences.append(buf.strip())

    for sent in sentences:
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
    cur_text, cur_type = parts[0]
    for text, ptype in parts[1:]:
        if ptype == cur_type:
            cur_text = (cur_text + ' ' + text).strip()
        else:
            merged.append((cur_text.strip(), cur_type))
            cur_text, cur_type = text, ptype
    merged.append((cur_text.strip(), cur_type))
    return merged


def _clean_dialog(text: str) -> str:
    text = _norm(text).strip()
    # Прибираємо початкові тире
    while text and text[0] in DASH_CHARS:
        text = text[1:].strip()
    # Прибираємо зайві пробіли перед закриваючою лапкою
    text = re.sub(r"\s+([\u00BB»\"'’])$", r"\1", text)
    return text.strip()


def _add_period(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    if text[-1] not in '.!?…':
        text += '.'
    return text


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
        parts = _split_by_structure(body)
        if not parts:
            out.append(ln)
            continue
        parts = _merge_consecutive(parts)
        # Якщо є тільки діалог — залишаємо як є
        if len(parts) == 1 and parts[0][1] == 'dialog':
            out.append(ln)
            continue
        # Якщо немає діалогу — пропускаємо
        if not any(p[1] == 'dialog' for p in parts):
            out.append(ln)
            continue
        dialog_text = None
        narrative_parts = []
        attribution_parts = []
        for text_part, ptype in parts:
            if ptype == 'dialog':
                dialog_text = _clean_dialog(text_part)
            elif ptype == 'narrative':
                narrative_parts.append(text_part)
            elif ptype == 'attribution':
                attribution_parts.append(text_part)
        if not dialog_text or len(dialog_text.strip()) < 1:
            out.append(ln)
            continue
        out.append(f"{indent}#g{gid}: {dialog_text}{eol}")
        # Виводимо наративи
        if narrative_parts:
            for narr in narrative_parts:
                narr_clean = _add_period(narr)
                out.append(f"{indent}#g1: {narr_clean}{eol}")
        # Виводимо атрибуцію
        if attribution_parts:
            for attr in attribution_parts:
                attr_clean = _add_period(attr)
                out.append(f"{indent}#g1: {attr_clean}{eol}")

    return ''.join(out)


# ДОДАЙ ЦЕ В КІНЕЦЬ ФАЙЛУ:
apply.phase = PHASE
apply.priority = PRIORITY
apply.scope = SCOPE
apply.name = NAME