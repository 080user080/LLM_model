# 077b_enforce_two_speaker_alternation.py — підчищення «пари» (ABAB) у блоці діалогу, допускає 1 пустий рядок
# -*- coding: utf-8 -*-
import re

PHASE, PRIORITY, SCOPE, NAME = 77, 1, "fulltext", "enforce_two_speaker_alternation"

NBSP = "\u00A0"
TAG  = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
DASHES = "-\u2012\u2013\u2014\u2015"
IS_DLG = re.compile(r"^\s*(?:[" + re.escape(DASHES) + r"]|[«\"„“”'’])")
ENDP   = r"[\.!\?…\"”»]"

# явна інлайн-атрибуція типу «…» — сказала/Ім'я …
VERBS_ANY = r"(?:сказав|сказала|каже|відповів|відповіла|говорить|питає|запитав|запитала|крикнув|крикнула|закричала|вигукнув|вигукнула|прошепотів|прошепотіла|буркнув|буркнула|промовив|промовила|пояснив|пояснила|гукнув|гукнула|відказав|відказала|додав|додала|зазначив|зазначила|просить|велить|нагадує)"
INLINE_NAME_ATTR = re.compile(
    r"" + ENDP + r"\s*[" + re.escape(DASHES) + r"]\s*(?:" + VERBS_ANY + r"\s+[A-ZА-ЯЇІЄҐ][\w’'\-]+|[A-ZА-ЯЇІЄҐ][\w’'\-]+\s*(?:,\s*)?" + VERBS_ANY + r")",
    re.IGNORECASE | re.DOTALL
)

def _nrm(s:str)->str: return (s or "").replace(NBSP," ").strip()

def _legend_map(ctx):
    amap = (getattr(ctx,"metadata",{}) or {}).get("legend") or {}
    # key: alias lower → gid
    return {(k or "").strip().casefold(): v for k,v in amap.items()}

def _roles_gender(ctx):
    return (getattr(ctx,"metadata",{}) or {}).get("roles_gender") or {}

def _aliases_for_gid(gid, amap, rg):
    out = set()
    for k,v in amap.items():
        if v == gid: out.add(k)
    rec = rg.get(gid) or {}
    for x in (rec.get("names") or []):   out.add(_nrm(x).casefold())
    for x in (rec.get("aliases") or []): out.add(_nrm(x).casefold())
    # фільтр: без дужок, помірна довжина
    return {a for a in out if "(" not in a and ")" not in a and 1 < len(a) <= 50}

def _has_any_alias(text, aliases):
    t = _nrm(text).casefold()
    for a in aliases:
        if a and a in t:
            return True
    return False

def _is_dialog_line(ln:str)->bool:
    m = TAG.match(ln)
    if not m: return False
    gid, body = m.group(2), m.group(3)
    if gid == "1": return False
    return bool(IS_DLG.match((body or "").lstrip()))

def apply(text: str, ctx):
    amap = _legend_map(ctx); rg = _roles_gender(ctx)

    lines = text.splitlines(keepends=True)
    n = len(lines)
    changed = 0
    i = 0

    while i < n:
        # Знаходимо блок послідовних діалогових рядків (#gN/#g?), допускаючи 1 пустий рядок між ними
        blk_idx = []
        j = i
        blanks = 0
        while j < n:
            line = lines[j]
            if not line.strip():
                blanks += 1
                if blanks > 1:
                    break
                # допускаємо один пустий рядок як частину блоку, але НЕ додаємо його у blk_idx
                j += 1
                continue
            m = TAG.match(line)
            # кінець блоку, якщо рядок не тегований або це наратив (#g1)
            if not m or (m and m.group(2) == "1"):
                break
            # перевірка, чи це справді діалогова репліка (припускаємо, що треба)
            if not _is_dialog_line(line):
                break
            blk_idx.append(j)
            j += 1

        # якщо блок короткий — пропускаємо
        if len(blk_idx) < 4:
            i = max(j, i+1)
            continue

        # Витяг тегів і тіл
        gids = []
        bodies = []
        for k in blk_idx:
            m = TAG.match(lines[k])
            _, gid_s, body = m.groups()
            gids.append(f"#g{gid_s}")
            bodies.append(body)

        # Унікальні спікери (ігноруємо #g? і #g1)
        uniq = []
        for g in gids:
            if g not in ("#g1", "#g?") and g not in uniq:
                uniq.append(g)
        if len(uniq) != 2:
            i = max(j, i+1)
            continue  # працюємо лише для чітких «пар»

        a, b = uniq[0], uniq[1]

        # Підготовка alias для охоронців
        a_alias = _aliases_for_gid(a, amap, rg)
        b_alias = _aliases_for_gid(b, amap, rg)

        # очікувана альтернація починається з першого неневідомого тега у блоці
        start_tag = None
        for g in gids:
            if g != "#g?":
                start_tag = g; break
        if not start_tag:
            start_tag = a
        expected = start_tag

        # Проходимо блок і лагідно виправляємо тільки #g? і явні «зубці» A A A/B
        for pos, k in enumerate(blk_idx):
            cur = gids[pos]
            body = bodies[pos]
            if INLINE_NAME_ATTR.search(body or ""):
                expected = b if expected == a else a
                continue
            # не міняти, якщо в тілі є чіткий вказівник на конкретного героя
            if _has_any_alias(body, _aliases_for_gid(cur, amap, rg)):
                expected = b if expected == a else a
                continue

            # 1) якщо невідомий → ставимо очікуваного
            if cur == "#g?":
                if expected in (a,b):
                    ind = TAG.match(lines[k]).group(1)
                    lines[k] = f"{ind}{expected}: {body}"
                    changed += 1
                expected = b if expected == a else a
                continue

            # 2) якщо стоїть «не той» і сусіди підказують чітку ABAB
            prev_cur = gids[pos-1] if pos-1 >= 0 else None
            next_cur = gids[pos+1] if pos+1 < len(gids) else None
            if cur != expected and cur in (a,b):
                if next_cur == expected and (prev_cur in (None, cur, "#g?")):
                    ind = TAG.match(lines[k]).group(1)
                    lines[k] = f"{ind}{expected}: {body}"
                    gids[pos] = expected
                    changed += 1
                    expected = b if expected == a else a
                    continue

            # оновлюємо очікування
            expected = b if expected == a else a

        i = j  # наступний блок

    try:
        ctx.logs.append(f"[077b enforce_two_speaker_alternation] fixed:{changed}")
    except Exception:
        pass

    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
