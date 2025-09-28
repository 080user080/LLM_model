# -*- coding: utf-8 -*-
"""
051_enrich_aliases_from_parenthetical.py
Збагачує meta.legend (alias -> #gX) за рахунок дужкових атрибутів у "сирих" alias-рядках.
Працює ПІСЛЯ 050-го правила. Безпечно: не перезаписує існуючі ключі, конфлікти лише логуються.

Приклад:
  '#g5: Правнучка (F, дівчинка, дитина, онучка, сонечко)'
  якщо в meta.legend залишився сирий ключ 'Правнучка (F, дівчинка, дитина, онучка, сонечко)' → витягне
  'Правнучка', 'онучка', 'сонечко' і додасть як окремі alias → #g5.

Також додає кілька корисних кличних форм зі спец-евристик:
  - якщо є 'дід/дідо' → додати 'діду'
  - якщо є 'мати/мама' → додати 'мамо'
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 51, 0, "fulltext", "enrich_aliases_from_parenthetical"

# латиниця, схожа на кирилицю (lookalikes)
_LAT2CYR = str.maketrans("aceopxyiACEOPXYI", "асеорхуіАСЕОРХУІ")

PAREN = re.compile(r"\((?P<attrs>.*?)\)\s*$")

def _nrm(s: str) -> str:
    # нормалізація: прибрати зайві пробіли, уніфікувати лат/кир, нижній регістр для ключа
    return s.translate(_LAT2CYR).strip()

def _split_name_attrs(text: str):
    """
    'Правнучка (F, дівчинка, дитина, онучка, сонечко)' -> (['Правнучка'], 'F, дівчинка, дитина, онучка, сонечко')
    'Той / Той-Спис (M, ватажок)' -> (['Той','Той-Спис'], 'M, ватажок')
    """
    m = PAREN.search(text)
    attrs = m.group("attrs") if m else ""
    name = text[:m.start()].strip() if m else text.strip()
    names = [n.strip() for n in name.split("/") if n.strip()]
    return names, attrs

def _token_candidates(attrs_lower: str):
    """
    З дужкових атрибутів дістаємо слова-кандидати (через кому).
    Відсікаємо службові маркери (F/M/дитина/жінка/чоловік/головний герой тощо) — залишаємо
    лише текстові лейбли, які потенційно можуть бути звертаннями/прізвиськами.
    """
    out = []
    for tok in [t.strip() for t in attrs_lower.split(",")]:
        if not tok or len(tok) < 2:
            continue
        # відсікання очевидних службових/загальних міток
        if tok in {"f", "m", "жінка", "чоловік", "дитина", "оповідач", "наратив", "сучасні сцени",
                   "сучасний співрозмовник", "головний герой"}:
            continue
        # лишаємо прості словесні/складені з дефісом форми
        if re.fullmatch(r"[A-Za-zА-Яа-яЁёЄєІіЇїҐґ'’\- ]{2,}", tok):
            out.append(tok)
    return out

def _add_vocative_specials(names, attrs_lower, out_set):
    """
    Кілька корисних “кличних” автододавань для частих випадків.
    """
    low_names = {n.lower() for n in names}
    if any(n in ("дідо",) for n in low_names) or "дід" in attrs_lower:
        out_set.add("діду")
    if "мати" in attrs_lower or "мама" in attrs_lower:
        out_set.add("мамо")

def apply(text: str, ctx):
    meta = getattr(ctx, "metadata", {}) or {}
    amap = (meta.get("legend") or {})  # alias->#g

    if not amap:
        return text  # нічого збагачувати

    # зворотне: #g -> [alias-рядки]
    gid2aliases = {}
    for alias, gid in amap.items():
        gid2aliases.setdefault(gid, []).append(alias)

    # евристика: визначаємо, чи варто збагачувати (коли лишилися “сирі” ключі з дужками)
    raw_like = 0
    for gid, alist in gid2aliases.items():
        if any(("(" in a and ")" in a) for a in alist):
            raw_like += 1
    if raw_like == 0:
        return text  # нема сирих рядків — усе вже розкладено 050-м правилом

    added, conflicts = 0, 0
    for gid, alist in gid2aliases.items():
        # беремо ПЕРШИЙ alias цього gid із дужками як “джерело” (якщо є)
        base = next((a for a in alist if "(" in a and ")" in a), None)
        if not base:
            continue

        base_nrm = _nrm(base)
        names, attrs = _split_name_attrs(base_nrm)
        attrs_lower = attrs.lower()

        # кандидати: самі імена + токени з дужок
        cand = set(names)
        cand.update(_token_candidates(attrs_lower))
        _add_vocative_specials(names, attrs_lower, cand)

        for a in cand:
            key = _nrm(a)
            if not key:
                continue
            key_cf = key.casefold()

            # Якщо такий ключ уже є і мапиться на цей самий gid — пропускаємо.
            # Якщо є, але на інший gid — вважаємо конфліктом і не чіпаємо.
            if key_cf in amap:
                if amap[key_cf] != gid:
                    conflicts += 1
                continue

            amap[key_cf] = gid
            added += 1

    meta["legend"] = amap
    setattr(ctx, "metadata", meta)

    try:
        ctx.logs.append(f"[051 enrich] added:{added} conflicts:{conflicts} raw_gids:{raw_like}")
    except Exception:
        pass

    return text

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
