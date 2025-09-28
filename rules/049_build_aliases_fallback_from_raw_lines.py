# -*- coding: utf-8 -*-
"""
049_build_aliases_fallback_from_raw_lines.py
Будує meta.legend (alias -> #gX), якщо її ще НЕ збудовано правилом 050.
Джерело - "сира" легенда у вигляді #gN -> "Назва (attrs, ...)"
або alias -> #gN, де alias = "Назва (attrs, ...)".
Також заповнює hints.first_person_gid за міткою "Головний герой".
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 49, 0, "fulltext", "build_aliases_fallback_from_raw_lines"

# латиниця, схожа на кирилицю
_LAT2CYR = str.maketrans("aceopxyiACEOPXYI", "асеорхуіАСЕОРХУІ")

PAREN = re.compile(r"\((?P<attrs>.*?)\)\s*$")

def _nrm(s: str) -> str:
    return s.translate(_LAT2CYR).strip()

def _split_name_attrs(text: str):
    """'Правнучка (F, дівчинка, дитина, онучка, сонечко)' -> (['Правнучка'], 'F, дівчинка, ...')"""
    m = PAREN.search(text)
    attrs = m.group("attrs") if m else ""
    name = text[:m.start()].strip() if m else text.strip()
    names = [n.strip() for n in name.split("/") if n.strip()]
    return names, attrs

def _auto_aliases(names, attrs_lower):
    """
    Мінімальні автододавання:
    - якщо в attrs є форми звертання, беремо їх як alias (розділені комами)
    - спец-випадки: 'дідо' -> 'діду', 'мати/мама' -> 'мамо'
    """
    out = set(names)
    # витягнути "м'які" alias з атрибутів (через кому)
    for token in [t.strip() for t in attrs_lower.split(",")]:
        if not token:
            continue
        # відсікаємо службові теги типу 'F', 'M', 'дитина' тощо — лишаємо потенційні звертання / прізвиська
        if len(token) >= 3 and token.isalpha():
            out.add(token)
    # спец-випадки
    low_names = {n.lower() for n in names}
    if any(n in ("дідо",) for n in low_names) or "дід" in attrs_lower:
        out.add("діду")
    if "мати" in attrs_lower or "мама" in attrs_lower:
        out.add("мамо")
    return out

def apply(text, ctx):
    meta = getattr(ctx, "metadata", {}) or {}
    if meta.get("legend"):  # вже збудовано правилом 050
        return text

    # спроби дістати "сиру" легенду з різних місць контексту
    raw_map = {}
    # варіант 1: у когось буває ctx.legend як #gN -> line
    raw_legend = getattr(ctx, "legend", None)
    if isinstance(raw_legend, dict):
        # якщо ключі виглядають як #gN — це точно #g -> line
        if all(isinstance(k, str) and k.strip().startswith("#g") for k in raw_legend.keys()):
            raw_map = {k.strip(): str(v) for k, v in raw_legend.items()}
        else:
            # інакше, можливо alias->#g, де alias = "Назва (attrs...)"
            # Повернемо до #g->line, щоб парсити єдиним шляхом
            tmp = {}
            for alias, gid in raw_legend.items():
                alias = str(alias)
                gid = str(gid).strip()
                # у цьому випадку як "line" візьмемо alias-рядок
                tmp.setdefault(gid, alias)
            raw_map = tmp

    # варіант 2: деякі GUI кладуть легенду у meta.legend_text (цілий блок тексту)
    if not raw_map:
        legend_text = (meta.get("legend_text") or "").strip()
        if legend_text:
            for ln in legend_text.splitlines():
                ln = ln.strip()
                if not ln or not ln.startswith("#g"):
                    continue
                # очікуємо: #gN - Назва (attrs,…)
                try:
                    gid, rest = ln.split("-", 1)
                    raw_map[gid.strip()] = rest.strip()
                except ValueError:
                    pass

    if not raw_map:
        # нічого не змогли витягнути — віддаємо керування далі
        return text

    # Будуємо meta.legend: alias -> #gN
    alias2gid = {}
    first_person_gid = None

    for gid, line in raw_map.items():
        line = _nrm(str(line))
        names, attrs = _split_name_attrs(line)
        attrs_lower = attrs.lower()

        # підказка для first_person_gid
        if "головний герой" in attrs_lower and not first_person_gid:
            first_person_gid = gid

        aliases = _auto_aliases(names, attrs_lower)
        for a in aliases:
            a = _nrm(a)
            if not a:
                continue
            # нормалізуємо пробіли, нижній регістр для надійних порівнянь
            a_key = a.casefold()
            # не перезаписуємо, якщо уже є (перша згадка важливіша)
            alias2gid.setdefault(a_key, gid)

    # Записуємо у meta.legend у вигляді "оригінальний_alias -> #g"
    # (інші правила все одно нормалізують до lower/casefold при пошуку)
    meta["legend"] = {k: v for k, v in alias2gid.items()}
    if first_person_gid:
        (meta.setdefault("hints", {}))["first_person_gid"] = first_person_gid
    setattr(ctx, "metadata", meta)

    return text

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
