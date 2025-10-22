#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SFX auto-markup v2
- Злиття повторів у абзаці (вставка одного тега після об'єднаного фрагменту).
- YAML-конфіг створюється автоматично з вбудованого варіанту, якщо відсутній файл.
- Структурні теги (#r + #p2) вставляються на окремі рядки перед/після заголовка.
Всі правки позначені #GPT
"""

import re
import os
import shutil
from tkinter import Tk, filedialog
from datetime import datetime
import pathlib
import json

# ---------- Вбудований YAML-перелік (резерв) #GPT
# Якщо нема PyYAML, цей текст буде записано у sfx_tags.yaml автоматично
TAGS_YAML_TEXT = """structural:
# sfx_tags.yaml
# Приклади правил з варіантами вставки (position)
# position:
#   - "precede_line"         -> вставити тег у окремому рядку *перед* знайденим рядком (для заголовків)
#   - "after_punctuation_newline" -> вставити тег у окремому рядку *після* найближчої пунктуації праворуч від збігу
#   - "after_match"          -> вставити тег одразу після кінця match (без пошуку пунктуації)
#   - "after_paragraph"      -> вставити тег у кінці абзацу (як fallback)
#   - "before_match"         -> вставити тег безпосередньо перед match (в середині рядка)
#   - "previous_punctuation" -> знайти останній знак пунктуації ліворуч від match і вставити тег відразу після нього
#   - "replace_match"        -> видалити match і замінити його на тег

  - tag: "#r"
    keywords: '^\\s*(РОЗДІЛ|ЧАСТИНА|ГЛАВА)\\b.*$'
    flags: MULTILINE|IGNORECASE
    post_tag: "#p2"
    position: "precede_line"
    confidence: 1.0
actions:
  - tag: "#d_"
    keywords: '(\\b\\w+\\s+(відчинив|зачинив|заскрипіли|стук у)\\s+двері\\b|\\bвідчинив\\b)'
    flags: IGNORECASE
    position: "after_punctuation_newline"   # classic: вставка після найближчої пунктуації справа від збігу
    confidence: 0.95
  - tag: "#d4_"
    keywords: '(\\bвідчинив\\b)'
    flags: IGNORECASE
    position: "after_match"                 # вставка відразу після збігу (без пошуку пунктуації)
    confidence: 0.8
  - tag: "#d2_"
    keywords: '(\\bвідчинив\\b)'
    flags: IGNORECASE
    position: "before_match"                # вставка перед місцем збігу всередині рядка
    confidence: 0.8
  - tag: "#d1_"
    keywords: '(\\bвідчинив\\b)'
    flags: IGNORECASE
    position: "previous_punctuation"        # вставка після останньої пунктуації зліва (перед реченням)
    confidence: 0.8
  - tag: "#d3_"
    keywords: '(\\bвідчинив\\b)'
    flags: IGNORECASE
    position: "replace_match"               # заміна знайденої фрази на тег
    confidence: 0.5
  - tag: "#v"
    keywords: '(прогримів вибух|голосно бахнуло|постріл пролунав|грім вдарив|крик пролунав)'
    flags: IGNORECASE
    position: "after_punctuation_newline"
    confidence: 0.9
  - tag: "#heart"
    keywords: '(серце шалено калатало|прискорене серцебиття|завмерло серце|жах охопив)'
    flags: IGNORECASE
    position: "after_punctuation_newline"
    confidence: 0.85
  - tag: "#rain"
    keywords: '(за вікном зашумів дощ|тихо падає дощ|шум дощу|вітер завив)'
    flags: IGNORECASE
    position: "after_punctuation_newline"
    confidence: 0.8
  - tag: "#step"
    keywords: '(кроки пролунали|чути кроки|ступив на підлогу|тихий стукіт каблуків)'
    flags: IGNORECASE
    position: "after_punctuation_newline"
    confidence: 0.8
"""

DEFAULT_YAML_FILENAME = "sfx_tags.yaml"  # #GPT

# ---------- Вбудований словник як резерв (якщо парсинг YAML не доступний) #GPT
FALLBACK_TAGS = {
    "structural": [
        {
            "tag": "#r",
            "keywords": re.compile(r"^\s*(РОЗДІЛ|ЧАСТИНА|ГЛАВА)\b.*$", re.IGNORECASE | re.MULTILINE),
            "flags": re.IGNORECASE | re.MULTILINE,
            "post_tag": "#p2",
            "position": "precede_line",
            "confidence": 1.0,
            "description": "Розділ/Глава + Пауза"
        }
    ],
    "actions": [
        {
            "tag": "#d",
            "keywords": re.compile(r"(\b\w+\s+(відчинив|зачинив|заскрипіли|стук у)\s+двері\b|\bвідчинив\b)", re.IGNORECASE),
            "flags": re.IGNORECASE,
            "position": "after_punctuation_newline",
            "confidence": 0.95,
            "description": "Двері/Скрип"
        },
        # Приклади додаткових режимів вставки (fallback / приклади). Можна активувати додаванням правил у YAML.
        {
            "tag": "#d_after_match",
            "keywords": re.compile(r"\bвідчинив\b", re.IGNORECASE),
            "flags": re.IGNORECASE,
            "position": "after_match",
            "confidence": 0.8,
            "description": "Вставити відразу після збігу (без пунктуації)"
        },
        {
            "tag": "#d_before_match",
            "keywords": re.compile(r"\bвідчинив\b", re.IGNORECASE),
            "flags": re.IGNORECASE,
            "position": "before_match",
            "confidence": 0.8,
            "description": "Вставити безпосередньо перед збіговим словом"
        },
        {
            "tag": "#d1_",
            "keywords": re.compile(r"\bвідчинив\b", re.IGNORECASE),
            "flags": re.IGNORECASE,
            "position": "previous_punctuation",
            "confidence": 0.8,
            "description": "Вставити після попередньої пунктуації (перед реченням із збігом)"
        },
        {
            "tag": "#d_replace",
            "keywords": re.compile(r"\bвідчинив\b", re.IGNORECASE),
            "flags": re.IGNORECASE,
            "position": "replace_match",
            "confidence": 0.5,
            "description": "Замінити знайдену фразу на тег"
        },
        {
            "tag": "#v",
            "keywords": re.compile(r"(прогримів вибух|голосно бахнуло|постріл пролунав|грім вдарив|крик пролунав)", re.IGNORECASE),
            "flags": re.IGNORECASE,
            "position": "after_punctuation_newline",
            "confidence": 0.9,
            "description": "Вибух/Постріл/Різка дія"
        },
        {
            "tag": "#heart",
            "keywords": re.compile(r"(серце шалено калатало|прискорене серцебиття|завмерло серце|жах охопив)", re.IGNORECASE),
            "flags": re.IGNORECASE,
            "position": "after_punctuation_newline",
            "confidence": 0.85,
            "description": "Серцебиття/Напруга"
        },
        {
            "tag": "#rain",
            "keywords": re.compile(r"(за вікном зашумів дощ|тихо падає дощ|шум дощу|вітер завив)", re.IGNORECASE),
            "flags": re.IGNORECASE,
            "position": "after_punctuation_newline",
            "confidence": 0.8,
            "description": "Дощ/Вітер (Атмосфера)"
        },
        {
            "tag": "#step",
            "keywords": re.compile(r"(кроки пролунали|чути кроки|ступив на підлогу|тихий стукіт каблуків)", re.IGNORECASE),
            "flags": re.IGNORECASE,
            "position": "after_punctuation_newline",
            "confidence": 0.8,
            "description": "Кроки/Рух"
        },
    ]
}

# ---------- Зчитування YAML (якщо є PyYAML) або створення/завантаження файлу з вбудованого варіанту #GPT
def ensure_yaml_file(path: str = DEFAULT_YAML_FILENAME) -> dict:
    """
    Повертає структуру правил. Якщо файл не існує, створює його з вбудованого TAGS_YAML_TEXT.
    Працює з PyYAML, якщо встановлено. Якщо PyYAML немає або парсинг не вдається, повертає FALLBACK_TAGS.
    """
    p = pathlib.Path(path)
    if not p.exists():
        try:
            p.write_text(TAGS_YAML_TEXT, encoding="utf-8")
        except Exception:
            # якщо не вдалося записати, просто продовжимо без файлу
            pass
    # спробуємо парсити з файлу через PyYAML
    try:
        import yaml  # type: ignore
    except Exception:
        print("⚠️ PyYAML не встановлений. Використовую FALLBACK_TAGS.")
        return FALLBACK_TAGS

    # Якщо є PyYAML — парсимо і валідуємо структуру
    try:
        raw = p.read_text(encoding="utf-8")
    except Exception as e:
        print(f"❌ Неможливо прочитати конфіг '{path}': {e}")
        print("ℹ️ Використовую FALLBACK_TAGS.")
        return FALLBACK_TAGS

    try:
        parsed = yaml.safe_load(raw)
    except Exception as e:
        print(f"❌ Помилка парсингу YAML-конфігу '{path}': {e}")
        print("ℹ️ Використовую FALLBACK_TAGS. Перевірте синтаксис sfx_tags.yaml.")
        return FALLBACK_TAGS

    # Перевірка базової структури
    if not isinstance(parsed, dict) or "structural" not in parsed or "actions" not in parsed:
        print(f"❌ Невірний формат конфіга '{path}'. Очікуються ключі 'structural' та 'actions'.")
        print("ℹ️ Використовую FALLBACK_TAGS. Перевірте структуру sfx_tags.yaml.")
        return FALLBACK_TAGS

    # нормалізуємо у структури з компільованими regex-ами
    result = {"structural": [], "actions": []}
    for section in ("structural", "actions"):
        items = parsed.get(section) or []
        if not isinstance(items, list):
            print(f"❌ Блок '{section}' у конфігу має бути списком правил.")
            print("ℹ️ Використовую FALLBACK_TAGS.")
            return FALLBACK_TAGS
        for idx, itm in enumerate(items):
            if not isinstance(itm, dict):
                print(f"❌ Правило #{idx} у блоці '{section}' має бути мапою (dict). Пропускаю конфіг.")
                return FALLBACK_TAGS

            pattern = itm.get("keywords")
            flags = 0
            fstr = itm.get("flags")
            if isinstance(fstr, str):
                for token in fstr.split("|"):
                    token = token.strip()
                    if token and hasattr(re, token):
                        flags |= getattr(re, token)
            elif isinstance(fstr, int):
                flags = fstr

            # Компілюємо regex та ловимо помилки
            if isinstance(pattern, str):
                try:
                    compiled = re.compile(pattern, flags)
                except re.error as re_e:
                    print(f"❌ Некоректний regex у правилі '{itm.get('tag','?')}' в '{path}': {re_e}")
                    print("ℹ️ Використовую FALLBACK_TAGS. Виправте regex у sfx_tags.yaml.")
                    return FALLBACK_TAGS
            else:
                try:
                    compiled = re.compile(str(pattern), flags)
                except re.error as re_e:
                    print(f"❌ Некоректний regex у правилі '{itm.get('tag','?')}' в '{path}': {re_e}")
                    print("ℹ️ Використовую FALLBACK_TAGS. Виправте regex у sfx_tags.yaml.")
                    return FALLBACK_TAGS

            new = dict(itm)
            new["keywords"] = compiled
            new["flags"] = flags
            result[section].append(new)

    return result

# Завантажуємо правило
TAG_MAP = ensure_yaml_file(DEFAULT_YAML_FILENAME)

# ---------- Підготовка скомпільованих правил (компілюємо один раз) #GPT
SFX_RULES = []
for section, items in TAG_MAP.items():
    for it in items:
        if isinstance(it.get("keywords"), re.Pattern):
            keywords_re = it["keywords"]
            flags = it.get("flags", keywords_re.flags)
            pattern_str = keywords_re.pattern
        else:
            pattern_str = it.get("keywords")
            flags = it.get("flags", 0)
            keywords_re = re.compile(pattern_str, flags)

        rule = dict(it)
        rule["keywords_re"] = keywords_re
        # Для after_punctuation_newline готуємо шаблони які включають текст до першого пунктуаційного знаку
        if rule.get("position") == "after_punctuation_newline":
            wrapped = f"(?:{pattern_str})"
            rule["_full_pattern"] = re.compile(rf'({wrapped})([\s\S]*?)([.,?!])', flags=flags | re.IGNORECASE)
            rule["_no_punct_pattern"] = re.compile(rf'({wrapped})(?![\s\S]*[.,?!])', flags=flags | re.IGNORECASE)
        SFX_RULES.append(rule)

# ---------- Головна функція обробки тексту #GPT
def process_text(text: str) -> (str, int):
    """
    Повертає (processed_text, tags_inserted_count).
    Логіка:
     - 1) Обробка структурних рядків: якщо рядок починається з РОЗДІЛ/ЧАСТИНА/ГЛАВА -> вставити #r перед рядком і #p2 після.
     - 2) Розбити текст на абзаци (поділ по подвійних переносах).
     - 3) Для кожного абзацу знайти всі збіги правил дії/ефекту, об'єднати близькі/перекриваючіся збіги в один span,
          вставити один тег після першого пунктуаційного знаку в об'єднаному span або після span, якщо пунктуації нема.
     - 4) Видалити старі дублікати однакових тегів у межах абзацу перед вставкою а також після всієї обробки очистити зайві переносы.
    """
    tags_added = 0

    # 1) Структурні теги: працюємо по рядках, вставляємо окремі рядки з тегами #GPT
    lines = text.splitlines(keepends=True)
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        # перевіряємо structural правила
        applied_struct = False
        if stripped:
            for rule in SFX_RULES:
                if rule.get("position") == "precede_line":
                    if rule["keywords_re"].match(line):  # строго початок рядка
                        # перед рядком має стояти тег у власному рядку
                        if not (out and out[-1].strip() == rule["tag"]):
                            out.append(f"{rule['tag']}\n")
                            tags_added += 1
                        out.append(line if line.endswith("\n") else line + "\n")
                        # вставляємо post_tag якщо є
                        if rule.get("post_tag"):
                            # наступна лінія має бути пост-тег у власному рядку
                            out.append(f"{rule['post_tag']}\n")
                            tags_added += 1
                        applied_struct = True
                        break
        if not applied_struct:
            out.append(line)
        i += 1

    processed = "".join(out)

    # 2) Розбиваємо на абзаци (зберігаємо роздільники) #GPT
    # використовуємо розбиття, яке зберігає кінці абзаців
    paragraphs = re.split(r'(\n\s*\n)', processed)  # зберігає роздільники як окремі елементи

    new_paragraphs = []
    for chunk in paragraphs:
        # якщо це роздільник (подвійний новий рядок), просто додаємо
        if re.fullmatch(r'\n\s*\n', chunk):
            new_paragraphs.append(chunk)
            continue

        para = chunk
        # чистимо від зайвих тегів того ж самого типу всередині абзацу (щоб потім вставити один контрольований тег)
        # але зберігаємо інші теги
        for r in {r['tag'] for r in SFX_RULES if r.get("position") == "after_punctuation_newline"}:
            para = re.sub(rf'\n{re.escape(r)}\n', '\n', para)

        # Зберемо спіски всіх збігів для всіх правил у цьому абзаці
        spans_by_rule = []
        # Збираємо збіги для всіх правил позицій (підтримуються нові позиції: after_match, after_paragraph,
        # before_match, previous_punctuation, replace_match, after_punctuation_newline)
        for rule in SFX_RULES:
            if rule.get("position") not in {
                "after_punctuation_newline",
                "after_match",
                "after_paragraph",
                "before_match",
                "previous_punctuation",
                "replace_match"
            }:
                continue
            for m in rule["keywords_re"].finditer(para):
                start = m.start()
                end = m.end()
                insert_mode = rule.get("position")
                has_punct = False

                if insert_mode == "after_punctuation_newline":
                    rest = para[m.end():]
                    punct_match = re.search(r'[.,?!]', rest)
                    if punct_match:
                        # включаємо сам знак пунктуації у span, щоб потім вставити тег після нього
                        end = m.end() + punct_match.start() + 1
                        has_punct = True
                    else:
                        nl = re.search(r'\n', rest)
                        end = m.end() + (nl.start() if nl else len(rest))
                        has_punct = False
                    spans_by_rule.append({"rule": rule, "start": start, "end": end, "has_punct": has_punct, "mode": insert_mode})

                elif insert_mode == "after_match":
                    # вставка відразу після збігу
                    spans_by_rule.append({"rule": rule, "start": start, "end": end, "has_punct": False, "mode": insert_mode})

                elif insert_mode == "after_paragraph":
                    # вставка в кінці абзацу
                    spans_by_rule.append({"rule": rule, "start": start, "end": len(para), "has_punct": False, "mode": insert_mode})

                elif insert_mode == "before_match":
                    # вставка перед місцем збігу (параметр: вставити на позицію start)
                    spans_by_rule.append({"rule": rule, "start": start, "end": start, "has_punct": False, "mode": insert_mode, "insert_before": True})

                elif insert_mode == "previous_punctuation":
                    # знайти останню пунктуацію лівіше від start; якщо нема — позиція 0
                    left = para[:start]
                    pm = list(re.finditer(r'[.,?!]', left))
                    if pm:
                        pos = pm[-1].end()  # після останнього знаку
                    else:
                        pos = 0
                    spans_by_rule.append({"rule": rule, "start": pos, "end": pos, "has_punct": False, "mode": insert_mode, "insert_pos": pos})

                elif insert_mode == "replace_match":
                    # замінити повний match на тег
                    spans_by_rule.append({"rule": rule, "start": start, "end": end, "has_punct": False, "mode": insert_mode, "replace": True})

        # Якщо немає збігів — додаємо абзац як є
        if not spans_by_rule:
            new_paragraphs.append(para)
            continue

        # Зливаймо перехресні і близькі спани для кожного тега незалежно, але щоб різні теги не конфліктували
        # Групуємо спани по тегу
        grouped = {}
        for s in spans_by_rule:
            tag = s["rule"]["tag"]
            grouped.setdefault(tag, []).append(s)

        # Для кожної групи: сортуємо і зливаємо інтервали, якщо вони перекриваються або відстань між ними <= threshold
        merged_spans = []
        for tag, lst in grouped.items():
            lst_sorted = sorted(lst, key=lambda x: x["start"])
            merged = []
            thresh = 40  # символів: якщо відстань між кінцем одного і початком іншого <= thresh -> зливаємо #GPT
            for item in lst_sorted:
                if not merged:
                    merged.append(item.copy())
                else:
                    last = merged[-1]
                    if item["start"] <= last["end"] or (item["start"] - last["end"]) <= thresh:
                        # зливаємо: новий кінець = max
                        last["end"] = max(last["end"], item["end"])
                        last["has_punct"] = last["has_punct"] or item["has_punct"]
                    else:
                        merged.append(item.copy())
            for m in merged:
                # зберігаємо посилання на rule та тег
                merged_spans.append({
                    "tag": tag,
                    "rule": m["rule"],
                    "start": m["start"],
                    "end": m["end"],
                    "has_punct": m["has_punct"]
                })

        # Тепер маємо набір merged_spans; сортуємо їх і вставляємо теги по-спадному за індексами (щоб позиції не зрушувалися)
        merged_spans = sorted(merged_spans, key=lambda x: x["start"])

        # Виключаємо перетини між різними тегами: якщо перетинаються, обираємо той, що має вищу confidence
        final_spans = []
        for s in merged_spans:
            if not final_spans:
                final_spans.append(s)
                continue
            last = final_spans[-1]
            if s["start"] <= last["end"]:
                # конфлікт, вибираємо вище confidence
                if s["rule"].get("confidence", 0) > last["rule"].get("confidence", 0):
                    # заміна
                    last = s
                    final_spans[-1] = last
                else:
                    # інакше ігноруємо s
                    continue
            else:
                final_spans.append(s)

        # Вставка: працюємо зі строкою, накопичуємо частини. Підтримуються режими в 'mode'.
        out_parts = []
        idx = 0
        for s in final_spans:
            mode = s.get("mode", s["rule"].get("position"))
            tag_line = f"\n{s['tag']}\n"

            if mode == "replace_match" and s.get("replace"):
                # Додаємо текст до початку replace span, потім тег, пропускаємо саму фразу
                out_parts.append(para[idx:s["start"]])
                out_parts.append(tag_line)
                idx = s["end"]
                tags_added += 1
                continue

            if mode == "before_match" and s.get("insert_before"):
                # Додаємо текст до місця вставки (перед match), вставляємо тег, не пропускаючи match
                out_parts.append(para[idx:s["start"]])
                out_parts.append(tag_line)
                idx = s["start"]
                tags_added += 1
                continue

            if mode == "previous_punctuation":
                pos = s.get("insert_pos", s["start"])
                out_parts.append(para[idx:pos])
                out_parts.append(tag_line)
                idx = pos
                tags_added += 1
                continue

            # режими які вставляють після діапазону (after_match, after_punctuation_newline, after_paragraph)
            out_parts.append(para[idx:s["end"]])
            out_parts.append(tag_line)
            idx = s["end"]
            tags_added += 1

        out_parts.append(para[idx:])  # додати залишок абзацу
        new_para = ''.join(out_parts)

        # Очищення: видалити подвійні однакові теги поспіль
        for rtag in {r['tag'] for r in SFX_RULES if r.get("position") == "after_punctuation_newline"}:
            new_para = re.sub(rf'(\n{re.escape(rtag)}\n)+', f'\n{rtag}\n', new_para)

        new_paragraphs.append(new_para)

    # Збираємо назад
    final_text = ''.join(new_paragraphs)

    # ВИПРАВЛЕННЯ: прибираємо пробіли/переноси перед знаками пунктуації,
    # щоб не опинити крапку або кому на окремому рядку перед тегом.
    final_text = re.sub(r'\s+([.,?!])', r'\1', final_text)

    # Очищення пробілів і зайвих переносів
    final_text = re.sub(r'[ \t]+', ' ', final_text)
    final_text = re.sub(r'\n{3,}', '\n\n', final_text).strip() + "\n"

    return final_text, tags_added

# ---------- Файлова логіка та UI (відокремлено) #GPT
def make_backup(path: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"{path}.{ts}.bak"
    shutil.copy2(path, bak)
    return bak

def process_file_dialog():
    root = Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="Виберіть текстовий файл (.txt) для автоматичної розмітки",
        filetypes=(("Текстові файли", "*.txt"), ("Всі файли", "*.*"))
    )
    if not file_path:
        print("Операцію скасовано.")
        return
    print(f"Вибрано: {file_path}")
    try:
        backup = make_backup(file_path)
        print(f"Резервна копія: {backup}")
    except Exception as e:
        print(f"Помилка при створенні резервної копії: {e}")
        return
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            src = f.read()
    except Exception as e:
        print(f"Помилка читання файлу: {e}")
        return
    processed, count = process_text(src)
    if processed.strip() == src.strip():
        print("Змін не виявлено. Файл не перезаписано.")
        try:
            os.remove(backup)
        except Exception:
            pass
        return
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(processed)
        print(f"Готово. Вставлено тегів: {count}")
    except Exception as e:
        print(f"Помилка при перезаписі файлу: {e}")
        print(f"Оригінал збережено у: {backup}")

# ---------- CLI приклад швидкого запуску #GPT
if __name__ == "__main__":
    print("SFX Auto-markup — старт")
    print(f"YAML конфіг: {DEFAULT_YAML_FILENAME} (створюється автоматично, якщо відсутній)")
    process_file_dialog()