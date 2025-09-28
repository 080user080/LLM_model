# 072c_inline_sayer_no_verb.py — «— … . — Ім'я, …» без дієслова → призначення мовця (з fallback на roles_gender)
# -*- coding: utf-8 -*-

import re

PHASE, PRIORITY, SCOPE, NAME = 72, 10, "fulltext", "inline_sayer_no_verb"

TAG_ANY = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
DASH = r"\-\u2012\u2013\u2014\u2015"
ENDPUNCT = r"[\.!\?…\"”»]"

_LAT2CYR = str.maketrans("aceopxyiACEOPXYI", "асеорхуіАСЕОРХУІ")
def _nrm(s: str) -> str:
    return (s or "").translate(_LAT2CYR).strip()

def _legend_alias_map(ctx):
    amap = (getattr(ctx, "metadata", {}) or {}).get("legend") or {}
    return {(k or "").strip().casefold(): v for k, v in amap.items()}

def _roles_gender(ctx):
    return (getattr(ctx, "metadata", {}) or {}).get("roles_gender") or {}

def _candidate_names(amap, rg):
    """Узгоджений список імен/аліасів із legend + roles_gender.names/aliases."""
    cand = set(amap.keys())
    for gid, rec in rg.items():
        for nm in (rec.get("names") or []):
            if nm: cand.add(_nrm(nm).casefold())
        for al in (rec.get("aliases") or []):
            if al: cand.add(_nrm(al).casefold())
    # викидаємо явно «сирі» рядки з дужками
    return {c for c in cand if "(" not in c and ")" not in c and len(c) <= 50}

def _build_name_rx(cands):
    if not cands:
        # універсальний fallback: Ім'я (може бути складене)
        return re.compile(r"(?P<name>[A-ZА-ЯЇІЄҐ][\w’'\-]+(?:\s+[A-ZА-ЯЇІЄҐ][\w’'\-]+)?)", re.IGNORECASE)
    alt = "|".join(re.escape(c) for c in sorted(cands, key=len, reverse=True))
    return re.compile(rf"(?P<name>{alt})", re.IGNORECASE)

def _patterns(name_rx):
    # 1) … <крапка/оклик/знак/еліпсис/лапки> <тире> Ім'я , …
    p1 = re.compile(rf"^\s*[{DASH}].+?{ENDPUNCT}\s*[{DASH}]\s*{name_rx.pattern}\s*[,:]\s*.*$",
                    re.IGNORECASE | re.DOTALL)
    # 2) … , <тире> Ім'я , …
    p2 = re.compile(rf"^\s*[{DASH}].+?,\s*[{DASH}]\s*{name_rx.pattern}\s*[,:]\s*.*$",
                    re.IGNORECASE | re.DOTALL)
    return p1, p2

def _gid_by_name(name_txt, amap, rg):
    key = _nrm(name_txt).casefold()
    gid = amap.get(key)
    if gid: return gid
    # fallback: пошук у roles_gender.names/aliases
    for g, rec in rg.items():
        if key in { _nrm(x).casefold() for x in (rec.get("names") or []) + (rec.get("aliases") or []) }:
            return g
    return None

def apply(text: str, ctx):
    amap = _legend_alias_map(ctx)
    rg = _roles_gender(ctx)
    name_rx = _build_name_rx(_candidate_names(amap, rg))
    p1, p2 = _patterns(name_rx)

    lines = text.splitlines(keepends=True)
    resolved = 0

    for i, ln in enumerate(lines):
        m = TAG_ANY.match(ln)
        if not m: continue
        indent, gid, body = m.groups()
        if gid != "?": continue

        b = _nrm(body)
        mm = p1.match(b) or p2.match(b)
        if not mm: continue

        name_txt = _nrm(mm.group("name"))
        gid_cand = _gid_by_name(name_txt, amap, rg)
        if not gid_cand or gid_cand == "#g1":
            continue

        lines[i] = f"{indent}{gid_cand}: {body}"
        resolved += 1

    try:
        ctx.logs.append(f"[072c inline_no_verb] resolved:{resolved}")
    except Exception:
        pass

    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
