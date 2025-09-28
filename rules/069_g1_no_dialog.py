# rules/069_g1_no_dialog.py
# -*- coding: utf-8 -*-
#GPT: #g1 не може мати діалог. Переназначаємо такі рядки на #g2 (1-ша особа) або #g? (невідомий),
# а також враховуємо підказку "долинає чоловічий/жіночий голос".

from __future__ import annotations
import re
PHASE, PRIORITY, SCOPE, NAME = 25, 10, "fulltext", "g1_no_dialog_strict"  # запускаємо РАНО

TAG_G1 = re.compile(r"^(\s*)#g1\s*:\s*(.*)$", re.DOTALL)

# Усі типи тире/лапок + нормалізація
DASH_CLASS = r"\-\u2012\u2013\u2014\u2015"
DIALOG_START = re.compile(rf"^\s*(?:[{DASH_CLASS}]|[«\"„“”'’])")
NBSP = u"\u00A0"  # не-розривний пробіл

I_PRON = re.compile(r"\bя\b", re.IGNORECASE)
I_VERB = re.compile(r"\b(кажу|говорю|відповідаю|питаю|прошу|дякую|зізнаюся|шепочу|бурмочу|вигукую|кричу)\b",
                    re.IGNORECASE)

# Підказки з попереднього наративу
VOICE_GENDER = re.compile(r"\bдолинає\s+(?:\w+\s+)?(чоловічий|жіночий)\s+голос\b", re.IGNORECASE)
VOICE_NAME = re.compile(r"\bголос\s+([A-ZА-ЯЇІЄҐ][\w’'\-]+)", re.IGNORECASE)
TRIM = ".,:;!?»«”“’'—–-()[]{}"

def _alias_map(ctx):
    legend = getattr(ctx, "metadata", {}).get("legend", {}) or {}
    amap = {}
    for k, gid in legend.items():
        base = re.split(r"[—–]|\(|,", k, maxsplit=1)[0].strip() or k
        first = base.split()[0]
        for c in {k.strip(), base, first}:
            if c:
                amap.setdefault(c.casefold(), gid)
    return amap

def _guess_from_prev(lines, idx, amap):
    seen = 0
    gender_hint = False
    for k in range(idx - 1, -1, -1):
        s = lines[k].replace(NBSP, " ").strip()
        if not s:
            continue
        seen += 1
        if VOICE_GENDER.search(s):
            gender_hint = True
        m = VOICE_NAME.search(s)
        if m:
            nm = m.group(1).strip(TRIM)
            gid = amap.get(nm.casefold())
            if gid and re.fullmatch(r"#g\d{1,2}", gid):
                return gid
        if seen >= 3:
            break
    return "#g?" if gender_hint else None

def apply(text, ctx):
    lines = text.splitlines(keepends=True)
    amap = _alias_map(ctx)
    child = "#g2"

    for i, ln in enumerate(lines):
        m = TAG_G1.match(ln)
        if not m:
            continue
        indent, body = m.group(1), m.group(2)
        body_norm = body.replace(NBSP, " ").lstrip()

        # Якщо не діалог — лишаємо як є (це наратив #g1)
        if not DIALOG_START.match(body_norm):
            continue

        # Діалог під #g1 → переназначити
        tgt = None
        if I_VERB.search(body_norm) or I_PRON.search(body_norm):
            tgt = child  # «я/кажу/відповідаю…» → #g2
        if tgt is None:
            tgt = _guess_from_prev(lines, i, amap)  # «долинає … голос», «голос <Ім’я>»
        if tgt is None:
            tgt = "#g?"

        lines[i] = f"{indent}{tgt}: {body}"
    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
