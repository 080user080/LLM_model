# 077_fix_dialog_flip.py
# -*- coding: utf-8 -*-
"""
Анти-«зубець»: виправляє зламане чергування всередині діалогового блоку.
Додає жорсткий кейс A B ? B → ? := A перед загальною логікою.
"""

import re
from collections import Counter

PHASE, PRIORITY, SCOPE, NAME = 77, 0, "fulltext", "fix_dialog_flip"

NBSP = "\u00A0"
TAG = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)

# Тире/дефіси для позначення діалогів
DASHES_CHARS = "-\u2012\u2013\u2014\u2015"
IS_DIALOG_BODY = re.compile(rf"^\s*(?:[{re.escape(DASHES_CHARS)}]|[«\"„“”'’])")

# Явна атрибуція «… . — Ім'я, …» або «… , — Ім'я …» — такі рядки не перетеглюємо
ENDING_PUNCT = r"[\.!\?…\"”»]"
INLINE_NAME_ATTR = re.compile(
    IS_DIALOG_BODY.pattern + r".*?" + ENDING_PUNCT + r"?\s*[" + re.escape(DASHES_CHARS) + r"]\s*[A-ZА-ЯЇІЄҐ][\w’'\-]+",
    re.DOTALL
)

def _is_dialog_line(line: str) -> bool:
    m = TAG.match(line)
    if not m:
        return False
    gid, body = m.group(2), m.group(3)
    if gid == "1":
        return False
    b = (body or "").replace(NBSP, " ").lstrip()
    return bool(IS_DIALOG_BODY.match(b))

def _blocks_from_meta(ctx, lines):
    meta = getattr(ctx, "metadata", {}) or {}
    spans = meta.get("dialog_blocks")
    if spans:
        return [{"start": s["start"], "end": s["end"]} for s in spans]
    # fallback: як у 042_detect_dialog_blocks
    blocks, in_blk, start = [], False, None
    for i, ln in enumerate(lines):
        is_d = _is_dialog_line(ln)
        if is_d and not in_blk:
            in_blk, start = True, i
        if (not is_d) and in_blk:
            blocks.append({"start": start, "end": i - 1})
            in_blk, start = False, None
    if in_blk:
        blocks.append({"start": start, "end": len(lines) - 1})
    return blocks

def _scene_of_line(i, meta):
    for sp in (meta.get("scene_spans") or []):
        if sp["start"] <= i <= sp["end"]:
            return (sp["label"] or "").lower()
    return (meta.get("scene") or "").lower()

def _is_forbidden(gid_full, i, meta):
    """Перевіряє allow/forbid для сцени; True = не можна призначати gid_full у цьому рядку."""
    c = (meta.get("constraints") or {}).get(gid_full) or {}
    scene = _scene_of_line(i, meta)
    allow = [x.lower() for x in (c.get("allowed_scenes") or [])]
    forbid = [x.lower() for x in (c.get("forbidden_scenes") or [])]
    if scene:
        if allow and scene not in allow:
            return True
        if forbid and scene in forbid:
            return True
    return False

def _dominant_pair(gids_seq):
    """Повертає 2 найчастотніші #gN (без #g?/#g1) і лічильники."""
    cnt = Counter(g for g in gids_seq if g not in {None, "#g1", "#g?"})
    if len(cnt) < 2:
        return None, None, cnt
    top2 = cnt.most_common(2)
    return top2[0][0], top2[1][0], cnt

def _expected(prev_gid, A, B):
    if prev_gid == A:
        return B
    if prev_gid == B:
        return A
    return None

def apply(text: str, ctx):
    meta = getattr(ctx, "metadata", {}) or {}
    lines = text.splitlines(keepends=True)

    blocks = _blocks_from_meta(ctx, lines)
    total_fixed_q = total_flip = skipped_attr = skipped_forbid = 0

    for blk in blocks:
        s, e = blk["start"], blk["end"]

        # Збираємо діалогові лінії блоку
        idxs, gids = [], []
        for i in range(s, e + 1):
            m = TAG.match(lines[i])
            if not m:
                continue
            gid_s = m.group(2)
            if not _is_dialog_line(lines[i]):
                continue
            idxs.append(i)
            gids.append(f"#g{gid_s}" if gid_s not in {"?", "1"} else f"#g{gid_s}")

        if len(idxs) < 3:
            continue

        A, B, cnt = _dominant_pair(gids)
        if not A or not B:
            continue

        # Переконаємось, що A/B домінують (>=70% відомих у блоці)
        known = [g for g in gids if g not in {"#g?", "#g1"}]
        if known:
            share = sum(1 for g in known if g in {A, B}) / max(1, len(known))
            if share < 0.7:
                continue

        # Прохід по блоці
        for k, i in enumerate(idxs):
            m = TAG.match(lines[i])
            ind, gid_s, body = m.groups()
            cur = f"#g{gid_s}" if gid_s not in {"?", "1"} else f"#g{gid_s}"

            # знайти попереднього відомого (A/B)
            prev = None
            for t in range(k - 1, -1, -1):
                gprev = gids[t]
                if gprev in {A, B}:
                    prev = gprev
                    break
            exp = _expected(prev, A, B) if prev else None

            # --- ЖОРСТКИЙ ЛОКАЛЬНИЙ КЕЙС: A B ? B → ? := A ---
            if cur == "#g?":
                prev_known = None
                twoback = None
                next_known = None

                # найближчий відомий зліва
                for t in range(k - 1, -1, -1):
                    if gids[t] not in {"#g?", "#g1"}:
                        prev_known = gids[t]
                        break
                # відомий на два кроки ліворуч
                if k - 2 >= 0 and gids[k - 2] not in {"#g?", "#g1"}:
                    twoback = gids[k - 2]
                # найближчий відомий справа
                for t in range(k + 1, len(idxs)):
                    if gids[t] not in {"#g?", "#g1"}:
                        next_known = gids[t]
                        break

                if twoback and prev_known and next_known and prev_known == next_known and twoback != prev_known:
                    exp_local = twoback  # очікуваний A
                    if INLINE_NAME_ATTR.search(body or "") is None and not _is_forbidden(exp_local, i, meta):
                        lines[i] = f"{ind}{exp_local}: {body}"
                        gids[k] = exp_local
                        total_fixed_q += 1
                        continue  # до наступного рядка

            # 1) Звичайний кейс: #g? → очікуваний за попереднім чергуванням
            if cur == "#g?" and exp:
                if INLINE_NAME_ATTR.search(body or ""):
                    skipped_attr += 1
                    continue
                if _is_forbidden(exp, i, meta):
                    skipped_forbid += 1
                    continue
                lines[i] = f"{ind}{exp}: {body}"
                gids[k] = exp
                total_fixed_q += 1
                continue

            # 2) Поодинокий «вставний» X між A і B: A X B або B X A → X := очікуваний
            if cur not in {"#g?", "#g1"} and cur not in {A, B} and exp:
                occurrences = sum(1 for g in gids if g == cur)
                if occurrences == 1:
                    nxt = None
                    for t in range(k + 1, len(idxs)):
                        gnext = gids[t]
                        if gnext in {A, B}:
                            nxt = gnext
                            break
                    if nxt and nxt != prev and INLINE_NAME_ATTR.search(body or "") is None:
                        if _is_forbidden(exp, i, meta):
                            skipped_forbid += 1
                        else:
                            lines[i] = f"{ind}{exp}: {body}"
                            gids[k] = exp
                            total_flip += 1
                        continue

    try:
        ctx.logs.append(f"[077 fix_flip] fixed_q:{total_fixed_q} flips:{total_flip} skip_attr:{skipped_attr} skip_forbid:{skipped_forbid}")
    except Exception:
        pass

    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
