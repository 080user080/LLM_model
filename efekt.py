# efekt.py
# -*- coding: utf-8 -*-
"""
Модуль для роботи з тегами звукових ефектів.
Читає sfx.yaml (секція sounds) і дозволяє вставляти теги у текст.
"""

import os
import re
from typing import Tuple, List, Dict

import yaml  # потрібен пакет pyyaml

TAG_RX = re.compile(r"#([A-Za-z]+[0-9]*)")

def load_sounds(yaml_path: str) -> Dict[str, Dict]:
    """Завантажує словник sounds з YAML."""
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"Файл {yaml_path} не знайдено")
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    sounds = data.get("sounds", {})
    return sounds

def validate_tags(text: str, sounds: Dict[str, Dict]) -> List[str]:
    """Перевіряє, які теги у тексті відсутні у конфігу."""
    known = set(sounds.keys())
    unknown: List[str] = []
    for m in TAG_RX.findall(text):
        base = re.match(r"([A-Za-z]+)", m).group(1)  # #v12 → v
        if base not in known and m not in known:
            unknown.append(m)
    return unknown

def insert_effect_tag(text: str, tag: str) -> Tuple[str, str]:
    """
    Вставляє тег у кінець тексту (окремим рядком).
    Повертає (новий_текст, повідомлення_логу).
    """
    if not tag.startswith("#"):
        tag = "#" + tag
    if not text.endswith("\n"):
        text += "\n"
    new_text = text + tag + "\n"
    return new_text, f"Вставлено тег {tag}"