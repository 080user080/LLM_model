# 038_detect_scenes.py — детектор меж сцен (Пролог / Глава N / Розділ N / Частина N / Епілог)
# -*- coding: utf-8 -*-
"""
Визначає межі сцен і заносить у ctx.metadata:
  meta["scenes"] = [{"label": "Пролог", "line": 0}, {"label": "Глава 1", "line": 123}, ...]
  meta["scene"]  = поточна сцена (остання знайдена під час проходу)
  meta["scene_index_by_line"] = { <line_idx>: <index_in_meta["scenes"]>, ... }
  meta["scene_spans"] = [{"label": "...", "start": i, "end": j}, ...]  # кінець включно

Підтримує заголовки як ОКРЕМІ рядки без #g, або як #g1: ... :
  • Пролог / Епілог
  • Глава 7 / Розділ 3 / Частина 2  (дозволяє також римські числа: Глава IV)
  • Кінець прологу → ставить межу (мітка "Кінець прологу"), але не змінює попередню сцену

Нічого в тексті не змінює. Працює ДО правил, що потребують поточної сцени (напр. 053_*).
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 38, 0, "fulltext", "detect_scenes"  # запускаємо до 041/050+

# Рядок з тегом #gN:
TAG_ANY = re.compile(r"^\s*#g(\d+|\?)\s*:\s*(.*)$")

# Прості заголовки без тегів (#g) — лише сам рядок
PLAIN_SCENE_RX = re.compile(
    r"""^\s*(?:
            (?P<solo>(пролог|епілог))                                   # Пролог / Епілог
            |
            (?P<head>(глава|розділ|частина))\s+
            (?P<num>(\d+|[IVXLCDM]+))                                   # арабські або римські
        )\.?\s*$""",
    re.IGNORECASE | re.VERBOSE
)

# Те саме усередині наративного рядка #g1:
G1_SCENE_RX = re.compile(
    r"""^\s*(?:
            (?P<solo>(пролог|епілог))
            |
            (?P<head>(глава|розділ|частина))\s+
            (?P<num>(\d+|[IVXLCDM]+))
        )\.?\s*$""",
    re.IGNORECASE | re.VERBOSE
)

# Кінець прологу — маркер «розрізу» поточної сцени (не створює нову сцену)
END_PROLOGUE_RX = re.compile(r"^\s*(?:#g1\s*:\s*)?кінець\s+прологу\.?\s*$", re.IGNORECASE)

def _label_from_match(m):
    solo = m.group("solo") if m else None
    head = m.group("head") if m else None
    num  = m.group("num")  if m else None
    if solo:
        return solo.strip().capitalize()
    if head and num:
        return f"{head.strip().capitalize()} {num.strip()}"
    return None

def apply(text: str, ctx):
    lines = text.splitlines(keepends=True)

    scenes = []                  # [{"label":..., "line": idx}, ...]
    scene_index_by_line = {}     # line_idx -> index in scenes
    scene_spans = []             # [{"label":..., "start": i, "end": j}, ...]
    boundary_lines = []          # індекси рядків-«розрізів» (Кінець прологу)
    current_idx = None

    for i, raw in enumerate(lines):
        line = raw.rstrip("\n")

        # 1) plain заголовок без тегів
        m_plain = PLAIN_SCENE_RX.match(line)
        if m_plain:
            label = _label_from_match(m_plain)
            scenes.append({"label": label, "line": i})
            current_idx = len(scenes) - 1
            scene_index_by_line[i] = current_idx
            continue

        # 2) #g1: заголовок
        m_tag = TAG_ANY.match(line)
        if m_tag:
            gid, body = m_tag.groups()
            if gid == "1":
                # #g1: Пролог / Глава N ...
                m_g1 = G1_SCENE_RX.match(body.strip())
                if m_g1:
                    label = _label_from_match(m_g1)
                    scenes.append({"label": label, "line": i})
                    current_idx = len(scenes) - 1
                    scene_index_by_line[i] = current_idx
                    continue

        # 3) кінець прологу — маркер межі: не створюємо сцену, а лише запам'ятовуємо "розріз"
        if END_PROLOGUE_RX.match(line):
            boundary_lines.append(i)
            continue

        # маркуємо приналежність поточній сцені (якщо вже є)
        if current_idx is not None:
            scene_index_by_line[i] = current_idx

    # Побудова spans (start/end) — кінець включно, з урахуванням "розрізів" boundary_lines
    if scenes:
        # Базові межі від заголовків сцен
        base_spans = []
        for idx, item in enumerate(scenes):
            start = item["line"]
            end = (scenes[idx + 1]["line"] - 1) if idx + 1 < len(scenes) else (len(lines) - 1)
            base_spans.append({"label": item["label"], "start": start, "end": end})
        # Розрізаємо базові інтервали на boundary_lines, не змінюючи label
        cuts = sorted(set(boundary_lines))
        for span in base_spans:
            cur_start, cur_end, label = span["start"], span["end"], span["label"]
            # усі boundary всередині цього інтервалу
            inner = [b for b in cuts if cur_start <= b <= cur_end]
            if not inner:
                scene_spans.append(span)
                continue
            prev = cur_start
            for b in inner:
                if prev <= b - 1:
                    scene_spans.append({"label": label, "start": prev, "end": b - 1})
                prev = b + 1  # boundary-рядок не належить жодній сцені
            if prev <= cur_end:
                scene_spans.append({"label": label, "start": prev, "end": cur_end})

    # Запис у метадані
    meta = getattr(ctx, "metadata", {}) or {}
    meta["scenes"] = scenes
    meta["scene_index_by_line"] = scene_index_by_line
    if scenes:
        # поточна сцена = остання реальна сцена, не boundary
        meta["scene"] = scenes[-1]["label"]
    meta["scene_spans"] = scene_spans
    if boundary_lines:
        meta["scene_boundaries"] = [{"label": "Кінець прологу", "line": i} for i in boundary_lines]
    setattr(ctx, "metadata", meta)

    # Лог
    try:
        ctx.logs.append(f"[038 scenes] found:{len(scenes)} spans:{len(scene_spans)} current:{meta.get('scene')}")
    except Exception:
        pass

    return text

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
