# -*- coding: utf-8 -*-
"""
#GPT: Ukrainian vocatives + opposite speaker fill
Розпізнає звертання у відмінках/синонімах (на основі легенди + дужок),
виправляє самозвертання (-> #g?) і ставить протилежного мовця в двоосібному контексті.

phase=73 (перед two-party), priority=12, scope=fulltext.
"""
from __future__ import annotations
import re
import unicodedata
from typing import Dict, List, Set, Tuple, Optional

phase = 73
priority = 12
scope = "fulltext"
name = "vocative_uk_morph"

TAG = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
IS_DIALOG = re.compile(r"^\s*(?:[-–—]|[«\"„“”'’])")
TRIM = ".,:;!?»«”“’'—–-()[]{}"

# --- нормалізація/ключі ---
def _strip_acc(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if not unicodedata.combining(ch))

def _key(s: str) -> str:
    return _strip_acc(s).casefold().strip(TRIM + " ")

# --- словничок родинних звертань (базові форми) ---
KIN_BASE = {
    "дід": {"дід","діду","дідом","діде","діда","дідоню","дідусю","дідусь","дідуся","дідусем"},
    "баба": {"баба","бабо","бабу","бабусю","бабусе","бабуню","бабцю","бабце"},
    "тато": {"тато","тату","тата","татусю","татусе","татусем"},
    "мама": {"мама","мамо","маму","матусю","матусе","матусю","мамусю","мамусе"},
    "сину": {"сину","сине","сина","сином","синочку","синочек"},
    "доня": {"доню","доня","донюню","донечко","донечко","донечці","донечкою"},
}

def _morph_expand_token(tok: str) -> Set[str]:
    """Дешеві морф. варіанти для імен/прізвиськ."""
    t = _key(tok)
    out = {t}
    # -о -> -у / -е (Дідо -> Діду/Діде; Лоло -> Лолу/Лоле)
    if t.endswith("о") and len(t) >= 3:
        out.add(t[:-1] + "у")
        out.add(t[:-1] + "е")
    # -а/-я -> можливе кличне -о/-е (Мама->мамо; Таша->ташо/таше (рідко), лишимо мамо)
    if t.endswith("а"):
        out.add(t[:-1] + "о")
    if t in KIN_BASE:
        out |= {_key(x) for x in KIN_BASE[t]}
    return out

def _aliases_from_legend(ctx) -> Dict[str, Set[str]]:
    """
    Повертає:
      alias_key -> {#gN,...}
      й паралельно будує #gN -> {alias_key,...} для швидкої перевірки самозвертання
    Враховує:
      • основні імена (ліворуч від дужок/тире),
      • слова в дужках після імені як синоніми (через кому).
    """
    legend = getattr(ctx, "legend", {}) or {}
    amap: Dict[str, Set[str]] = {}
    for raw, gid in legend.items():
        base = re.split(r"[—–]|[(]", raw, 1)[0].strip() or raw
        inside = ""
        m = re.search(r"\(([^)]*)\)", raw)
        if m:
            inside = m.group(1)
        cands = {base.strip(), raw.strip()}
        for ch in inside.split(","):
            ch = ch.strip()
            if ch:
                cands.add(ch)
        for c in cands:
            if not c:
                continue
            # токени по словах
            for tok in re.split(r"[/\\;|]", c):
                tok = tok.strip()
                if not tok:
                    continue
                for variant in _morph_expand_token(tok):
                    amap.setdefault(variant, set()).add(gid)
    return amap

def _gid2names(amap: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    g2n: Dict[str, Set[str]] = {}
    for alias, gids in amap.items():
        for gid in gids:
            g2n.setdefault(gid, set()).add(alias)
    return g2n

def _find_vocative_gid(text: str, amap: Dict[str, Set[str]]) -> Optional[str]:
    """Шукає у перших ~90 символів звертання; віддає #gN якщо однозначно."""
    s = _strip_acc(text).lstrip()
    win = s[:90]
    # спершу: слово + пунктуація як маркер кличної форми
    m = re.search(r"\b([A-ZА-ЯЇІЄҐ][\w’'\-]+)\s*[,!:—]", win)
    if m:
        cand = _key(m.group(1))
        gids = amap.get(cand)
        if gids and len(gids) == 1:
            return next(iter(gids))
    # запасний: пошук будь-якого з alias усередині вікна (по спаданню довжини)
    tokens = sorted(amap.keys(), key=len, reverse=True)
    hits: Set[str] = set()
    for tk in tokens:
        if re.search(rf"\b{re.escape(tk)}\b", win, flags=re.IGNORECASE):
            for g in amap[tk]:
                hits.add(g)
    if len(hits) == 1:
        return next(iter(hits))
    return None

def apply(text: str, ctx) -> str:
    lines = text.splitlines(keepends=True)
    amap = _aliases_from_legend(ctx)
    g2n = _gid2names(amap)
    narrator = getattr(ctx, "narrator_tag", "#g1")

    # Розпарсимо рядки з тегами для доступу до сусідів
    items: List[dict] = []
    for i, ln in enumerate(lines):
        m = TAG.match(ln)
        if not m:
            items.append({"i": i, "kind": "raw", "line": ln})
            continue
        indent, gid, rest = m.group(1), m.group(2), m.group(3)
        tag = f"#g{gid}"
        items.append({"i": i, "kind": "tag", "indent": indent, "tag": tag, "rest": rest, "is_dialog": bool(IS_DIALOG.match(rest.lstrip()))})

    # Допоміжне: зібрати явні співрозмовники у вікні навколо i
    def window_speakers(center: int, radius: int = 4) -> List[str]:
        s: List[str] = []
        for j in range(max(0, center - radius), min(len(items), center + radius + 1)):
            if j == center: continue
            it = items[j]
            if it.get("kind") != "tag": continue
            tg = it.get("tag")
            if tg and tg not in {"#g?", narrator}:
                s.append(tg)
        # стабільний список у порядку появи, без дублікатів
        seen = set(); out = []
        for t in s:
            if t not in seen:
                seen.add(t); out.append(t)
        return out

    # Прохід: самозвертання → #g?; #g? з звертанням → протилежний мовець (якщо однозначно)
    for idx, it in enumerate(items):
        if it.get("kind") != "tag": continue
        tag = it["tag"]; rest = it["rest"]
        if not it["is_dialog"]: continue

        gid_voc = _find_vocative_gid(rest, amap)
        if not gid_voc:
            continue

        # 1) Самозвертання: якщо тег відповідає тому ж герою — прибираємо тег
        if tag == gid_voc:
            it["tag"] = "#g?"
            continue

        # 2) Якщо тег невідомий, спробуємо поставити «протилежного» співрозмовника
        if tag == "#g?":
            neigh = window_speakers(idx, radius=5)
            # якщо у вікні є хтось один, і це НЕ той, до кого звертаються — берeмо його
            cand = [g for g in neigh if g != gid_voc]
            if len(set(cand)) == 1:
                it["tag"] = cand[0]
                continue
            # якщо двоє і один з них = адресат, беремо іншого
            if len(set(neigh)) == 2 and gid_voc in neigh:
                other = [g for g in neigh if g != gid_voc][0]
                it["tag"] = other
                continue
        # інакше лишаємо як є

    # Збірка
    out: List[str] = []
    for it in items:
        if it.get("kind") != "tag":
            out.append(it["line"]); continue
        out.append(f"{it['indent']}{it['tag']}: {it['rest']}")
    return "".join(out)

apply.phase, apply.priority, apply.scope, apply.name = phase, priority, scope, name
