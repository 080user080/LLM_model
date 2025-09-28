# -*- coding: utf-8 -*-
"""
050_build_metadata_from_legend.py
Будує:
  ctx.metadata.legend      : { "аліас/клична" -> "#gX" }
  ctx.metadata.hints       : { "first_person_gid": "#gY" }  (якщо можна визначити)
  ctx.metadata.relations   : [("mother", "#gA", "#gB"), ...]  з фраз типу "мати <Ім'я>"

УНІВЕРСАЛЬНО:
- НЕ має хардкоду на #g2.
- first_person_gid обирається за атрибутом "Головний герой".
  Якщо кандидатів кілька — рейтингує:
    +2 за "дитина/хлопчик/дівчинка/підліток/юнак/дівчина"
    +2 якщо є відношення mother(parent)->child(this)
    +1 за "герой/Головний герой" (сам факт)
  Тай-брейк — найменший номер #gN.
- Якщо "Головний герой" відсутній — first_person_gid не виставляється (залишається None).
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 50, 0, "fulltext", "build_metadata_from_legend"

LINE = re.compile(r"^\s*#g(?P<num>\d+)\s*-\s*(?P<body>.+?)\s*$")
PAREN = re.compile(r"\((?P<attrs>.*?)\)\s*$")
HDR   = re.compile(r"^\s*Легенда\s*:?\s*$", re.IGNORECASE)

# --- helpers -----------------------------------------------------------------

def _split_name_attrs(body: str):
    m = PAREN.search(body)
    attrs = m.group("attrs") if m else ""
    name_part = body[:m.start()].strip() if m else body.strip()
    names = [n.strip() for n in name_part.split("/") if n.strip()]
    return names, attrs

def _auto_aliases(names, attrs_lower):
    out = set(n for n in names)
    if "дід" in attrs_lower or any(n.lower() == "дідо" for n in names):
        out.add("діду")
    if "мати" in attrs_lower or "мама" in attrs_lower:
        out.add("мамо")
    if any(k in attrs_lower for k in ("онучка","правнучка","дівчинка")):
        out.add("сонечко")
    return out

def _legend_lines_from(text, ctx):
    meta = getattr(ctx, "metadata", {}) or {}
    raw = meta.get("legend_text")
    if raw:
        return raw.splitlines()
    # блок після "Легенда"
    lines = text.splitlines()
    block, take = [], False
    for ln in lines:
        if HDR.match(ln):
            take = True; continue
        if take:
            s = ln.strip()
            if not s:
                continue
            if s.startswith("#g") and LINE.match(s):
                block.append(s)
                continue
            # інший текст → кінець блоку легенди
            break
    if block:
        return block
    # будь-де
    return [ln for ln in lines if LINE.match(ln)]

def _gid_num(gid: str) -> int:
    m = re.match(r"#g(\d+)$", gid or "")
    return int(m.group(1)) if m else 10**9

# --- main --------------------------------------------------------------------

def apply(text, ctx):
    legend_map, relations = {}, []
    name_to_gid = {}
    rows = _legend_lines_from(text, ctx)

    # первинний парс
    parsed = []  # (gid, names[], attrs, attrs_lower)
    for raw in rows:
        m = LINE.match(raw)
        if not m:
            continue
        gid = f"#g{m.group('num')}"
        names, attrs = _split_name_attrs(m.group("body"))
        attrs_l = attrs.lower()

        if names:
            name_to_gid.setdefault(names[0], gid)

        for a in _auto_aliases(names, attrs_l):
            legend_map[a] = gid

        parsed.append((gid, names, attrs, attrs_l))

    # relations mother -> child
    for gid_a, names, attrs, attrs_l in parsed:
        mm = re.search(r"(мати|мама)\s+([A-ZА-ЯЇІЄҐ][\w’'\-]+)", attrs, flags=re.IGNORECASE)
        if mm:
            child = mm.group(2)
            gid_b = name_to_gid.get(child)
            if gid_b:
                relations.append(("mother", gid_a, gid_b))

    # обрати first_person_gid універсально серед "Головний герой"
    candidates = []
    for gid, names, attrs, attrs_l in parsed:
        if "головний герой" in attrs_l:
            score = 0
            if any(k in attrs_l for k in ("дитина","хлопчик","дівчинка","підліток","юнак","дівчина")):
                score += 2
            # якщо цей gid є "child" у зв'язці mother(parent)->child(this)
            if any(r == ("mother", p, gid) for r in relations for p in [r[1]] if r[0] == "mother" and r[2] == gid):
                score += 2
            score += 1  # сам факт "Головний герой"
            candidates.append((score, _gid_num(gid), gid))

    first_person_gid = None
    if candidates:
        candidates.sort(key=lambda t: (-t[0], t[1]))
        first_person_gid = candidates[0][2]

    # записати в ctx.metadata
    meta = getattr(ctx, "metadata", {}) or {}
    meta.setdefault("legend", {})
    meta["legend"].update(legend_map)
    meta.setdefault("hints", {})
    if first_person_gid:
        meta["hints"]["first_person_gid"] = first_person_gid
    # якщо не визначили — не ставимо нічого; правила мають вміти працювати з відсутнім hint
    if relations:
        meta["relations"] = relations
    ctx.metadata = meta
    return text

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
