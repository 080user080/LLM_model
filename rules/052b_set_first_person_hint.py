# 052b_set_first_person_hint.py — встановлює hints.first_person_gid з легенди/ролей
# -*- coding: utf-8 -*-
PHASE, PRIORITY, SCOPE, NAME = 52, 1, "fulltext", "set_first_person_hint"

def apply(text, ctx):
    meta = getattr(ctx, "metadata", {}) or {}
    rg   = meta.get("roles_gender") or {}
    hints = meta.get("hints") or {}

    if not hints.get("first_person_gid"):
        cand = None
        # 1) явна роль «Головний герой»
        for gid, rec in rg.items():
            roles = " ".join(rec.get("roles") or []).lower()
            if "головн" in roles and "геро" in roles:
                cand = gid; break
        # 2) запасний: якщо є #g2 — вважаємо його «я»
        if not cand and "#g2" in rg:
            cand = "#g2"
        if cand:
            hints["first_person_gid"] = cand

    meta["hints"] = hints
    setattr(ctx, "metadata", meta)
    return text

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
