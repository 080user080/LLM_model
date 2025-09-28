# 073_leadin_sayer_gender_checked.py — lead-in «Ім'я … каже/сказала: — …», +gender, +prev-line
# -*- coding: utf-8 -*-

import re
PHASE, PRIORITY, SCOPE, NAME = 73, 8, "fulltext", "leadin_sayer_gender_checked"

# Родові
VERBS_M = "сказав|відповів|спитав|запитав|крикнув|вигукнув|прошепотів|буркнув|мовив|промовив|пояснив|гукнув|відказав"
VERBS_F = "сказала|відповіла|спитала|запитала|крикнула|вигукнула|прошепотіла|буркнула|промовила|пояснила|гукнула|відказала"
# Нейтральні (теп. час)
VERBS_N = "каже|говорить|питає|запитує|кричить|вигукує|шепоче|бурчить|мовить|промовляє|пояснює|гукає|відказує|додає|зазначає|просить|велить|нагадує"
VERBS_ANY = rf"(?:{VERBS_M}|{VERBS_F}|{VERBS_N})"

TAG_ANY = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
_LAT2CYR = str.maketrans("aceopxyiACEOPXYI", "асеорхуіАСЕОРХУІ")
PREV_LOOKBACK = 2  # скільки рядків назад дивитись

# Узагальнений «галас натовпу» перед реплікою → не атрибутуємо конкретному мовцю (#GPT)
GROUP_NOISE = re.compile(
    r"\b(інші|усі|всі|вони|люди|решта|натовп)\b.*\b("
    r"кричать|гукають|вигукують|волають|свистять|співають|регочуть|галасують"
    r")\b.*:?$",
    re.IGNORECASE
)

def _nrm(s: str) -> str:
    return (s or "").translate(_LAT2CYR).strip()

def _roles_gender(ctx):
    return (getattr(ctx, "metadata", {}) or {}).get("roles_gender") or {}

def _legend_alias_map(ctx):
    amap = (getattr(ctx, "metadata", {}) or {}).get("legend") or {}
    return {(k or "").strip().casefold(): v for k, v in amap.items()}

def _guess_gender_by_name(name: str):
    n = (name or "").lower()
    if n.endswith(("а","я","ія","ея")): return "F"
    if n.endswith(("о","ій","ий","ко","енко")): return "M"
    return None

def _verb_gender(tok: str):
    t = (tok or "").lower()
    if re.fullmatch(VERBS_F, t): return "F"
    if re.fullmatch(VERBS_M, t): return "M"
    return None  # нейтральні

def _compile_name_regex(alias_keys):
    keys = [k for k in alias_keys if 1 < len(k) <= 40]
    keys.sort(key=len, reverse=True)
    if not keys:
        return re.compile(r"(?P<name>[A-ZА-ЯЇІЄҐ][\w’'\-]+(?:\s+[A-ZА-ЯЇІЄҐ][\w’'\-]+)?)", re.IGNORECASE)
    alt = "|".join(re.escape(k) for k in keys)
    return re.compile(rf"(?P<name>{alt})", re.IGNORECASE)

def _make_leadin_pattern(name_rx):
    # Дозволяємо довільну «прослойку» до 180 символів між ім'ям і дієсловом (щоб зловити «дивиться з докором і каже»)
    return re.compile(rf"^\s*{name_rx.pattern}\s+.{{0,180}}?\b(?P<verb>{VERBS_ANY})\b.*?$",
                      re.IGNORECASE | re.DOTALL)

def _match_leadin(text, name_rx, amap, rg):
    if not text: return None, None, None
    mm = _make_leadin_pattern(name_rx).search(_nrm(text))
    if not mm: return None, None, None
    name_txt = _nrm(mm.group("name")); verb_txt = _nrm(mm.group("verb"))
    gid_cand = amap.get(name_txt.casefold())
    if not gid_cand or gid_cand == "#g1":
        return None, None, None
    vgen = _verb_gender(verb_txt)
    rgen = (rg.get(gid_cand) or {}).get("gender") or _guess_gender_by_name(name_txt)
    if vgen and rgen and vgen != rgen:
        return None, None, None
    return gid_cand, verb_txt, vgen

def _prev_narrative_lines(lines, i):
    res = []
    for j in range(i - 1, max(-1, i - PREV_LOOKBACK - 1), -1):
        if TAG_ANY.match(lines[j]):  # якщо це вже #g-рядок — стоп
            break
        core = lines[j].rstrip("\n")
        if core.strip():
            res.append(core)
    return res

def apply(text: str, ctx):
    rg = _roles_gender(ctx)
    amap = _legend_alias_map(ctx)
    name_rx = _compile_name_regex(list(amap.keys()))

    lines = text.splitlines(keepends=True)
    resolved_prev = resolved_inline = 0

    for i, ln in enumerate(lines):
        m = TAG_ANY.match(ln)
        if not m: 
            continue
        indent, gid, body = m.groups()
        if gid != "?":
            continue

        # 0) Якщо прямо перед реплікою(ами) описано «інші/усі/вони … кричать:» — пропускаємо атрибуцію (#GPT)
        prev_core = (lines[i-1].rstrip("\n") if i-1 >= 0 else "")
        if prev_core and GROUP_NOISE.search(prev_core):
            continue

        # 1) lead-in у попередніх наративних рядках
        done = False
        for prev in _prev_narrative_lines(lines, i):
            # Якщо будь-який із переглянутих наративів — груповий «галас», зупиняємо пошук (#GPT)
            if GROUP_NOISE.search(prev):
                done = True
                break
            gid_cand, verb_txt, _ = _match_leadin(prev, name_rx, amap, rg)
            if gid_cand:
                lines[i] = f"{indent}{gid_cand}: {body}"
                resolved_prev += 1
                done = True
                break
        if done:
            continue

        # 2) lead-in у цьому ж рядку (префейс до першого «—/лапок/двокрапки»)
        preface = re.split(r"[—\-«\"„“”'’:]\s*", (body or ""), maxsplit=1)[0]
        # Якщо префейс виглядає як «інші/усі/вони … кричать:» — не атрибутуємо (#GPT)
        if GROUP_NOISE.search(preface):
            continue
        gid_cand, verb_txt, _ = _match_leadin(preface, name_rx, amap, rg)
        if gid_cand:
            lines[i] = f"{indent}{gid_cand}: {body}"
            resolved_inline += 1

    try:
        ctx.logs.append(f"[073 leadin+gender] resolved_prev:{resolved_prev} resolved_inline:{resolved_inline}")
    except Exception:
        pass

    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
