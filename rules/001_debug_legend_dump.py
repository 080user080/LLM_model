# -*- coding: utf-8 -*-
"""
001_debug_legend_dump.py — діагностика легенди
Пише у лог:
  • скільки alias і для яких #gN вони є,
  • чи є 'сонечко' в aliases і до якого #g воно прив'язане,
  • конфлікти alias→кілька #g,
  • латинські lookalike-символи у aliases,
  • hints (first_person_gid), relations (якщо є).

Не змінює текст.
"""

PHASE, PRIORITY, SCOPE, NAME = 52, -1, "fulltext", "debug_legend_dump"

# латинські символи, що візуально схожі на кирилицю
_LAT2CYR = str.maketrans("aceopxyiACEOPXYI", "асеорхуіАСЕОРХУІ")

def _log(ctx, msg: str):
    try:
        ctx.logs.append(msg)
    except Exception:
        try: print(msg)
        except Exception: pass

def _nrm_lookalike(s: str) -> str:
    # нормалізуємо регістр + замінюємо латиницю на кирилицю
    return s.translate(_LAT2CYR).strip().casefold()

def apply(text: str, ctx):
    meta = getattr(ctx, "metadata", {}) or {}
    # alias->#gX (основне сховище)
    amap = (meta.get("legend") or {}) or getattr(ctx, "legend", {}) or {}
    hints = meta.get("hints") or {}
    relations = meta.get("relations") or []
    constraints = meta.get("constraints") or {}

    _log(ctx, "=== LEGEND DEBUG ===")
    _log(ctx, f"aliases_total={len(amap)}")

    # інвертуємо у #g -> [aliases]
    gid2aliases = {}
    for alias, gid in amap.items():
        gid2aliases.setdefault(gid, []).append(alias)

    for gid in sorted(gid2aliases.keys()):
        aliases = sorted(gid2aliases[gid], key=lambda s: _nrm_lookalike(s))
        preview = ", ".join(aliases[:12]) + (" …" if len(aliases) > 12 else "")
        _log(ctx, f"{gid}: {len(aliases)} aliases → {preview}")

    # перевірка 'сонечко'
    target = "сонечко"
    target_hits = [(a, g) for a, g in amap.items()
                   if _nrm_lookalike(a) == _nrm_lookalike(target)]
    if target_hits:
        lst = ", ".join([f"'{a}'→{g}" for a, g in target_hits])
        _log(ctx, f"CHECK alias '{target}': FOUND → {lst}")
    else:
        _log(ctx, f"CHECK alias '{target}': NOT FOUND in legend aliases")

    # конфлікти alias→кілька #g
    conflicts = {}
    for a, g in amap.items():
        k = _nrm_lookalike(a)
        conflicts.setdefault(k, set()).add(g)
    conflicts = {k: v for k, v in conflicts.items() if len(v) > 1}
    if conflicts:
        _log(ctx, f"ALIAS CONFLICTS ({len(conflicts)}):")
        for k, gs in conflicts.items():
            _log(ctx, f"  '{k}' → {sorted(gs)}")
    else:
        _log(ctx, "ALIAS CONFLICTS: none")

    # попередження про латиницю у aliases
    lookalike_warn = []
    for a in amap.keys():
        if a != a.translate(_LAT2CYR):  # була латиниця
            lookalike_warn.append(a)
    if lookalike_warn:
        _log(ctx, f"LATIN LOOKALIKES in aliases ({len(lookalike_warn)}): "
                  + ", ".join(sorted(lookalike_warn, key=_nrm_lookalike)))
    else:
        _log(ctx, "LATIN LOOKALIKES: none")

    # hints / relations / constraints (якщо існують)
    if hints:
        _log(ctx, f"hints: {hints}")
    if relations:
        _log(ctx, f"relations: {relations}")
    if constraints:
        _log(ctx, f"constraints: {constraints}")

    _log(ctx, "=== LEGEND DEBUG END ===")
    return text

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
