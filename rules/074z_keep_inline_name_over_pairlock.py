# 074z_keep_inline_name_over_pairlock.py
# -*- coding: utf-8 -*-
"""
Гард після pair-lock: якщо в репліці є інлайн-атрибуція «— … — сказала/Ім'я …»,
повертаємо мовця за цим ім'ям (щоб вокатив не перебив).
"""
import re

PHASE, PRIORITY, SCOPE, NAME = 74, 99, "fulltext", "keep_inline_name_over_pairlock"

NBSP = "\u00A0"
TAG  = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
DASH = "-\u2012\u2013\u2014\u2015"
ENDP = r"[\.!\?…\"”»]"
IS_DLG = re.compile(r"^\s*(?:[" + re.escape(DASH) + r"]|[«\"„“”'’])")

VERBS_M = r"(?:сказав|відповів|спитав|запитав|крикнув|вигукнув|прошепотів|буркнув|мовив|промовив|пояснив|гукнув|відказав)"
VERBS_F = r"(?:сказала|відповіла|спитала|запитала|крикнула|вигукнула|прошепотіла|буркнула|промовила|пояснила|гукнула|відказала|закричала)"
VERBS_N = r"(?:каже|говорить|питає|запитує|кричить|вигукує|шепоче|бурчить|мовить|промовляє|пояснює|гукає|відказує|додає|зазначає|просить|велить|нагадує)"
VERB_ANY = rf"(?:{VERBS_M}|{VERBS_F}|{VERBS_N})"

def _nrm(s:str)->str: 
    return (s or "").replace("\u00A0"," ").strip()

def _legend_alias_map(ctx):
    amap = (getattr(ctx,"metadata",{}) or {}).get("legend") or {}
    return {(k or "").strip().casefold(): v for k, v in amap.items()}

def _roles_gender(ctx):
    return (getattr(ctx,"metadata",{}) or {}).get("roles_gender") or {}

def _candidate_names(amap, rg):
    s = set(amap.keys())
    for _,rec in rg.items():
        for nm in (rec.get("names") or []): 
            if nm: s.add(_nrm(nm).casefold())
        for al in (rec.get("aliases") or []):
            if al: s.add(_nrm(al).casefold())
    return {c for c in s if "(" not in c and ")" not in c and 1 < len(c) <= 50}

def _name_rx(cands):
    if not cands:
        return re.compile(r"(?P<name>[A-ZА-ЯЇІЄҐ][\w’'\-]+(?:\s+[A-ZА-ЯЇІЄҐ][\w’'\-]+)?)", re.IGNORECASE)
    alt = "|".join(re.escape(c) for c in sorted(cands, key=len, reverse=True))
    return re.compile(rf"(?P<name>{alt})", re.IGNORECASE)

def _gid_by_name(name_txt, amap, rg):
    key = _nrm(name_txt).casefold()
    gid = amap.get(key)
    if gid: return gid
    for g, rec in rg.items():
        pool = set()
        pool.update(_nrm(x).casefold() for x in (rec.get("names") or []))
        pool.update(_nrm(x).casefold() for x in (rec.get("aliases") or []))
        if key in pool: return g
    return None

def apply(text: str, ctx):
    amap = _legend_alias_map(ctx); rg = _roles_gender(ctx)
    name_rx = _name_rx(_candidate_names(amap, rg))

    INLINE_NAME_ATTR1 = re.compile(
        r"" + ENDP + r"\s*[" + re.escape(DASH) + r"]\s*" + VERB_ANY + r"\s+" + name_rx.pattern + r"\s*[,:\-]?",
        re.IGNORECASE | re.DOTALL
    )
    INLINE_NAME_ATTR2 = re.compile(
        r"" + ENDP + r"\s*[" + re.escape(DASH) + r"]\s*" + name_rx.pattern + r"\s*(?:,\s*)?" + VERB_ANY + r"\s*[,:\-]?",
        re.IGNORECASE | re.DOTALL
    )
    # Кома-вставка: дві ОКРЕМІ маски, щоб уникнути дублю іменованої групи
    INLINE_NAME_ATTR3a = re.compile(
        r",\s*[" + re.escape(DASH) + r"]\s*" + VERB_ANY + r"\s+" + name_rx.pattern + r"\s*[,:\-]?",
        re.IGNORECASE | re.DOTALL
    )
    INLINE_NAME_ATTR3b = re.compile(
        r",\s*[" + re.escape(DASH) + r"]\s*" + name_rx.pattern + r"\s*,?\s*" + VERB_ANY + r"\s*[,:\-]?",
        re.IGNORECASE | re.DOTALL
    )

    lines = text.splitlines(keepends=True)
    fixed = 0

    for i, ln in enumerate(lines):
        m = TAG.match(ln)
        if not m: 
            continue
        ind, gid_s, body = m.groups()
        if gid_s == "1": 
            continue

        b = _nrm(body)
        mm = (INLINE_NAME_ATTR1.search(b) or INLINE_NAME_ATTR2.search(b) or
              INLINE_NAME_ATTR3a.search(b) or INLINE_NAME_ATTR3b.search(b))
        if not mm:
            continue

        name_txt = mm.group("name")
        gid_target = _gid_by_name(name_txt, amap, rg)
        if not gid_target or gid_target == f"#g{gid_s}":
            continue

        lines[i] = f"{ind}{gid_target}: {body}"
        fixed += 1

    try:
        ctx.logs.append(f"[074z keep_inline_name] restored:{fixed}")
    except Exception:
        pass

    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
