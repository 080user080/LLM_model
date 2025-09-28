# -*- coding: utf-8 -*-
"""1-ша особа + звертання до матері (#g3 з легенди) → спікер first_person_gid (#g2 за замовч.)."""
import re

PHASE, PRIORITY, SCOPE, NAME = 74, 5, "fulltext", "firstperson_to_child_when_addressing_mother"

NBSP = "\u00A0"
DASH = r"\-\u2012\u2013\u2014\u2015"
DIALOG = re.compile(rf"^\s*(?:[{DASH}]|[«\"„“”'’])")
TAG_ANY = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)

I_PRON = re.compile(r"\b(я|мені|мене|мною|мій|моє|мої|в мені|у мені)\b", re.IGNORECASE)
I_VERB = re.compile(r"\b(кажу|говорю|відповідаю|питаю|прошу|дякую|зізнаюся|шепочу|бурмочу|вигукую|кричу|показую|звертаюся|стримуюсь|охаю)\b", re.IGNORECASE)

TRIM = ".,:;!?»«”“’'—–-()[]{}"

def _norm(s: str) -> str:
    return s.replace(NBSP, " ").strip(TRIM + " ").lower()

def _alias_map(ctx):
    legend = getattr(ctx, "metadata", {}).get("legend", {}) or {}
    amap = {}
    for raw, gid in legend.items():
        base = str(raw).split(" ")[0]
        amap[base.lower()] = str(gid)
    return amap

def _addresses_mother(text: str, amap: dict) -> bool:
    low = _norm(text)
    for name, gid in amap.items():
        if gid == "#g3":
            if re.search(rf"(?:^|[\s«\"'—–-]){re.escape(name)}\s*[,!?:]", low):
                return True
    return False

def apply(text, ctx):
    lines = text.splitlines(keepends=True)
    meta  = getattr(ctx, "metadata", {}) or {}
    first_person_gid = (meta.get('hints') or {}).get('first_person_gid', '#g2')
    amap  = _alias_map(ctx)

    for i, ln in enumerate(lines):
        m = TAG_ANY.match(ln)
        if not m:
            continue
        indent, gid, body = m.groups()

        # ПРАЦЮЄМО ЛИШЕ З НЕВИЗНАЧЕНИМИ (#g?)
        if gid != '?':
            continue

        body_norm = body.replace(NBSP, " ").lstrip()
        if not DIALOG.match(body_norm):
            continue

        low = body_norm.lower()
        if (I_PRON.search(low) or I_VERB.search(low)) and _addresses_mother(body_norm, amap):
            lines[i] = f"{indent}{first_person_gid}: {body}"

    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
