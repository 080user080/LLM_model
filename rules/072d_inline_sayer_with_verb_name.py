# 072d_inline_sayer_with_verb_name.py
# -*- coding: utf-8 -*-
import re

PHASE, PRIORITY, SCOPE, NAME = 72, 11, "fulltext", "inline_sayer_with_verb_name"

NBSP = "\u00A0"
TAG = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
DASHES = "-\u2012\u2013\u2014\u2015"
ENDP = r"[\.!\?…\"”»]"
IS_DLG = re.compile(r"^\s*(?:[" + re.escape(DASHES) + r"]|[«\"„“”'’])")

VERBS_M = r"(?:сказав|відповів|спитав|запитав|крикнув|вигукнув|прошепотів|буркнув|мовив|промовив|пояснив|гукнув|відказав)"
VERBS_F = r"(?:сказала|відповіла|спитала|запитала|крикнула|вигукнула|прошепотіла|буркнула|промовила|пояснила|гукнула|відказала|закричала)"
VERBS_N = r"(?:каже|говорить|питає|запитує|кричить|вигукує|шепоче|бурчить|мовить|промовляє|пояснює|гукає|відказує|додає|зазначає|просить|велить|нагадує)"
VERB_ANY = rf"(?:{VERBS_M}|{VERBS_F}|{VERBS_N})"

_LAT2CYR = str.maketrans("aceopxyiACEOPXYI","асеорхуіАСЕОРХУІ")
def _nrm(s:str)->str: return (s or "").translate(_LAT2CYR)

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
    key = _nrm(name_txt).strip().casefold()
    gid = amap.get(key)
    if gid: return gid
    for g,rec in rg.items():
        pool = set()
        pool.update(_nrm(x).strip().casefold() for x in (rec.get("names") or []))
        pool.update(_nrm(x).strip().casefold() for x in (rec.get("aliases") or []))
        if key in pool: return g
    return None

def _patterns(name_rx):
    # «… . — сказала Ім'я, …»
    p_verb_name = re.compile(
        rf"{ENDP}\s*[{re.escape(DASHES)}]\s*{VERB_ANY}\s+{name_rx.pattern}\s*[,:\-]?",
        re.IGNORECASE | re.DOTALL
    )
    # «… . — Ім'я сказала, …»
    p_name_verb = re.compile(
        rf"{ENDP}\s*[{re.escape(DASHES)}]\s*{name_rx.pattern}\s*(?:,\s*)?{VERB_ANY}\s*[,:\-]?",
        re.IGNORECASE | re.DOTALL
    )
    # Кома-вставка: дві ОКРЕМІ маски, щоб не дублювати (?P<name>) в одному патерні
    p_comma_vn = re.compile(
        rf",\s*[{re.escape(DASHES)}]\s*{VERB_ANY}\s+{name_rx.pattern}\s*[,:\-]?",
        re.IGNORECASE | re.DOTALL
    )
    p_comma_nv = re.compile(
        rf",\s*[{re.escape(DASHES)}]\s*{name_rx.pattern}\s*,?\s*{VERB_ANY}\s*[,:\-]?",
        re.IGNORECASE | re.DOTALL
    )
    return p_verb_name, p_name_verb, p_comma_vn, p_comma_nv

def apply(text:str, ctx):
    amap = _legend_alias_map(ctx); rg = _roles_gender(ctx)
    name_rx = _name_rx(_candidate_names(amap, rg))
    p1, p2, p3a, p3b = _patterns(name_rx)

    lines = text.splitlines(keepends=True)
    changed = 0

    for i, ln in enumerate(lines):
        m = TAG.match(ln)
        if not m: continue
        indent, gid_s, body = m.groups()
        if gid_s == "1": continue

        bnorm = _nrm(body)
        mm = None
        for pat in (p1, p2, p3a, p3b):
            mm = pat.search(bnorm)
            if mm: break
        if not mm: 
            continue

        name_txt = mm.group("name")
        gid_target = _gid_by_name(name_txt, amap, rg)
        if not gid_target or gid_target == f"#g{gid_s}":
            continue

        lines[i] = f"{indent}{gid_target}: {body}"
        changed += 1

    try:
        ctx.logs.append(f"[072d inline_verb_name] retagged:{changed}")
    except Exception:
        pass

    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
