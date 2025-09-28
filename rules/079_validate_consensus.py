# 079_validate_consensus.py — валідація узгодженості рішень (консенсус + заборони сцени + рід дієслова)
# -*- coding: utf-8 -*-
"""
Мета: після усіх правил перевірити, що призначений мовець узгоджується з явними сигналами.
Якщо ні — або міняємо на консенсусного кандидата, або демотуємо до #g?.

Джерела сигналів (з «вагами»):
  • inline-атрибуція без дієслова «… . — Ім'я, …»          → вага 3
  • lead-in у попередніх рядках «Ім'я … каже/сказала:»      → вага 2
  • займенник «він/вона» + попередній мовець того ж роду    → вага 1

Додаткові жорсткі перевірки:
  • заборона героя в поточній сцені (allow/forbid з 053) → демотувати або замінити на best, якщо він дозволений;
  • рід дієслова в рядку («сказав/сказала») vs. рід героя → якщо конфлікт і є best без конфлікту → замінити, інакше демотувати.

Порядок: пізно, після 074/077, перед 098 (щоб прибрати службові маркери вже після валідації).
"""

import re
from collections import defaultdict

PHASE, PRIORITY, SCOPE, NAME = 79, 0, "fulltext", "validate_consensus"  #GPT

# ---------------- Basics ----------------
NBSP = "\u00A0"
TAG = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
DASHES = r"\-\u2012\u2013\u2014\u2015"
IS_DIALOG_BODY = re.compile(rf"^\s*(?:[{DASHES}]|[«\"„“”'’])")

# legend / roles_gender
def _meta(ctx):          return getattr(ctx, "metadata", {}) or {}
def _legend(ctx):        return (_meta(ctx).get("legend") or {})
def _roles_gender(ctx):  return (_meta(ctx).get("roles_gender") or {})
def _constraints(ctx):   return (_meta(ctx).get("constraints") or {})
def _block_by_line(ctx): return (_meta(ctx).get("dialog_block_id_by_line") or {})

# нормалізація «схожих» лат/кир
_LAT2CYR = str.maketrans("aceopxyiACEOPXYI", "асеорхуіАСЕОРХУІ")
def _nrm(s): return (s or "").translate(_LAT2CYR).strip()

# ---------------- Inline «— … . — Ім'я, …» ----------------
ENDPUNCT_OR_COMMA = r"[\.!\?…\"”»«„“”,]"
NAME_FALLBACK_RX = re.compile(r"(?P<name>[A-ZА-ЯЇІЄҐ][\w’'\-]+(?:\s+[A-ZА-ЯЇІЄҐ][\w’'\-]+)?)", re.IGNORECASE)
def _cand_names(amap, rg):
    s = set(k.casefold() for k in amap.keys())
    for rec in rg.values():
        for nm in (rec.get("names") or []):
            if nm: s.add(_nrm(nm).casefold())
        for al in (rec.get("aliases") or []):
            if al: s.add(_nrm(al).casefold())
    return {c for c in s if "(" not in c and ")" not in c and 1 < len(c) <= 50}

def _name_rx(cands):
    if not cands: return NAME_FALLBACK_RX
    alt = "|".join(re.escape(c) for c in sorted(cands, key=len, reverse=True))
    return re.compile(rf"(?P<name>{alt})", re.IGNORECASE)

def _inline_patterns(name_rx):
    p_main = re.compile(rf"{ENDPUNCT_OR_COMMA}\s*[{DASHES}]\s*{name_rx.pattern}\s*([,:]|[{DASHES}])",
                        re.IGNORECASE | re.DOTALL)
    p_comma = re.compile(rf",\s*[{DASHES}]\s*{name_rx.pattern}\s*([,:]|[{DASHES}])",
                         re.IGNORECASE | re.DOTALL)
    return p_main, p_comma

# ---------------- Lead-in «Ім'я … каже/сказала:» ----------------
VERBS_M = "сказав|відповів|спитав|запитав|крикнув|вигукнув|прошепотів|буркнув|мовив|промовив|пояснив|гукнув|відказав"
VERBS_F = "сказала|відповіла|спитала|запитала|крикнула|вигукнула|прошепотіла|буркнула|промовила|пояснила|гукнула|відказала"
VERBS_N = "каже|говорить|питає|запитує|кричить|вигукує|шепоче|бурчить|мовить|промовляє|пояснює|гукає|відказує|додає|зазначає|просить|велить|нагадує"
VERB_ANY = re.compile(rf"\b(?:{VERBS_M}|{VERBS_F}|{VERBS_N})\b", re.IGNORECASE)
def _verb_gender(tok):
    t = (tok or "").lower()
    if re.fullmatch(VERBS_F, t): return "F"
    if re.fullmatch(VERBS_M, t): return "M"
    return None

def _leadin_match(text, name_rx):
    """Повертає (name, verb) або (None,None) з попереднього наративу."""
    if not text: return None, None
    m_name = name_rx.search(_nrm(text))
    m_verb = VERB_ANY.search(_nrm(text))
    if m_name and m_verb:
        return _nrm(m_name.group("name")), _nrm(m_verb.group(0))
    return None, None

# ---------------- Pronoun coref ----------------
P_M = r"(?:він|йому|ним|ньому|нього|цей|цього|цьому|цим|той|того|тому|тим)"
P_F = r"(?:вона|її|їй|неї|нею|ця|цієї|цій|цією|цю|та)"
PRON_M = re.compile(rf"\b{P_M}\b", re.IGNORECASE)
PRON_F = re.compile(rf"\b{P_F}\b", re.IGNORECASE)

def _want_gender_from_pron(text):
    low = (text or "").lower()
    if PRON_F.search(low): return "F"
    if PRON_M.search(low): return "M"
    return None

def _nearest_prev_same_gender(lines, i, want, rg, block_by_line):
    blk = block_by_line.get(i)
    for j in range(i - 1, max(-1, i - 7), -1):
        if block_by_line.get(j) != blk:
            break
        m = TAG.match(lines[j])
        if not m: continue
        gid_s = m.group(2)
        if gid_s in ("?", "1"): continue
        gid_full = f"#g{gid_s}"
        if (rg.get(gid_full) or {}).get("gender") == want:
            return gid_full
    return None

# ---------------- Constraints & helpers ----------------
def _is_dialog_line(line):
    m = TAG.match(line)
    if not m: return False
    gid, body = m.group(2), m.group(3)
    if gid == "1": return False
    return bool(IS_DIALOG_BODY.match((body or "").replace(NBSP, " ").lstrip()))

def _scene_of_line(i, meta):
    for sp in (meta.get("scene_spans") or []):
        if sp["start"] <= i <= sp["end"]:
            return (sp["label"] or "").lower()
    return (meta.get("scene") or "").lower()

def _is_forbidden(gid_full, i, meta):
    c = (meta.get("constraints") or {}).get(gid_full) or {}
    scene = _scene_of_line(i, meta)
    allow = [x.lower() for x in (c.get("allowed_scenes") or [])]
    forbid = [x.lower() for x in (c.get("forbidden_scenes") or [])]
    if scene:
        if allow and scene not in allow: return True
        if forbid and scene in forbid:   return True
    return False

def _map_name_to_gid(name_txt, amap, rg):
    key = _nrm(name_txt).casefold()
    gid = amap.get(key)
    if gid: return gid
    for g, rec in rg.items():
        pool = set()
        pool.update(_nrm(x).casefold() for x in (rec.get("names") or []))
        pool.update(_nrm(x).casefold() for x in (rec.get("aliases") or []))
        if key in pool: return g
    return None

# ---------------- Main ----------------
def apply(text, ctx):
    meta = _meta(ctx)
    amap = { (k or "").strip().casefold(): v for k, v in _legend(ctx).items() }
    rg = _roles_gender(ctx)
    block_by = _block_by_line(ctx)

    name_rx = _name_rx(_cand_names(amap, rg))
    p_inline, p_inline2 = _inline_patterns(name_rx)

    lines = text.splitlines(keepends=True)
    switched = demoted = kept = conflicts = 0
    audit = []

    for i, ln in enumerate(lines):
        m = TAG.match(ln)
        if not m: continue
        indent, gid_s, body = m.groups()

        # аналізуємо лише діалогові рядки з відомим мовцем
        if gid_s in ("1", "?"): 
            continue
        if not _is_dialog_line(ln):
            continue

        assigned = f"#g{gid_s}"

        # 0) Жорстка сцена-заборона
        if _is_forbidden(assigned, i, meta):
            # спробуємо знайти best по консенсусу; якщо нема — демотувати
            best_gid, best_w, votes = _consensus_for_line(i, lines, body, name_rx, p_inline, p_inline2, amap, rg, block_by)
            if best_gid and not _is_forbidden(best_gid, i, meta):
                lines[i] = f"{indent}{best_gid}: {body}"
                switched += 1
                audit.append((i, assigned, best_gid, "forbidden->best"))
            else:
                lines[i] = f"{indent}#g?: {body}"
                demoted += 1
                audit.append((i, assigned, "#g?", "forbidden->demote"))
            continue

        # 1) М'яка валідація консенсусом
        best_gid, best_w, votes = _consensus_for_line(i, lines, body, name_rx, p_inline, p_inline2, amap, rg, block_by)

        # 2) Перевірка роду дієслова (якщо є) проти assigned і best
        verb_match = VERB_ANY.search(_nrm(body))
        if verb_match:
            vgen = _verb_gender(verb_match.group(0))
            if vgen:
                as_gen = (rg.get(assigned) or {}).get("gender")
                if as_gen and as_gen != vgen:
                    # assigned суперечить дієслову; якщо best погоджується — перемкнемо
                    best_gen = (rg.get(best_gid) or {}).get("gender") if best_gid else None
                    if best_gid and best_gen == vgen and not _is_forbidden(best_gid, i, meta):
                        lines[i] = f"{indent}{best_gid}: {body}"
                        switched += 1
                        audit.append((i, assigned, best_gid, "verb_gender_conflict->best"))
                        continue
                    else:
                        lines[i] = f"{indent}#g?: {body}"
                        demoted += 1
                        audit.append((i, assigned, "#g?", "verb_gender_conflict->demote"))
                        continue

        # 3) Якщо є альтернативний консенсус і його вага явно вища — перемкнути
        cur_w = votes.get(assigned, 0)
        if best_gid and best_gid != assigned and best_w >= cur_w + 2 and not _is_forbidden(best_gid, i, meta):
            lines[i] = f"{indent}{best_gid}: {body}"
            switched += 1
            audit.append((i, assigned, best_gid, f"consensus {best_w}>{cur_w}+2"))
        else:
            kept += 1

    # Зберегти аудит у метадані
    meta.setdefault("validation_audit", [])
    for rec in audit:
        meta["validation_audit"].append({"line": rec[0], "from": rec[1], "to": rec[2], "reason": rec[3]})
    setattr(ctx, "metadata", meta)

    try:
        ctx.logs.append(f"[079 validate_consensus] kept:{kept} switched:{switched} demoted:{demoted}")
    except Exception:
        pass

    return "".join(lines)

# ---------------- Helpers: consensus per line ----------------
def _consensus_for_line(i, lines, body, name_rx, p_inline, p_inline2, amap, rg, block_by):
    votes = defaultdict(int)

    bnorm = _nrm(body)

    # A) Inline «… . — Ім'я, …»
    mm = p_inline.search(bnorm) or p_inline2.search(bnorm)
    if mm:
        name = _nrm(mm.group("name"))
        gid = _map_name_to_gid(name, amap, rg)
        if gid:
            votes[gid] += 3

    # B) Lead-in у попередніх наративних рядках (до 2 рядків вгору)
    for j in range(i - 1, max(-1, i - 3), -1):
        mprev = TAG.match(lines[j])
        if mprev:  # натрапили на #g-рядок — зупиняємось (це вже не префейс)
            break
        name, verb = _leadin_match(lines[j], name_rx)
        if name and verb:
            gid = _map_name_to_gid(name, amap, rg)
            vgen = _verb_gender(verb)
            # якщо дієслово має рід — перевіримо його з гендером героя
            if gid and vgen:
                rgen = (rg.get(gid) or {}).get("gender")
                if rgen and rgen != vgen:
                    continue  # не голосує проти роду
            if gid:
                votes[gid] += 2
                break

    # C) Займенники «він/вона» в самому рядку
    want = _want_gender_from_pron(body)
    if want:
        gid_prev = _nearest_prev_same_gender(lines, i, want, rg, block_by)
        if gid_prev:
            votes[gid_prev] += 1

    # best
    if not votes:
        return None, 0, votes
    best_gid = max(votes.items(), key=lambda kv: kv[1])[0]
    return best_gid, votes[best_gid], votes

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME  #GPT
