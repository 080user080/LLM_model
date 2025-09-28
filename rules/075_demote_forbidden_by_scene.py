# 075_demote_forbidden_by_scene.py — після пар/вокативів знімати заборонених мовців до #g?
# -*- coding: utf-8 -*-

import re
PHASE, PRIORITY, SCOPE, NAME = 75, 99, "fulltext", "demote_forbidden_by_scene"

TAG = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)

def _scene_of_line(i, meta):
    spans = meta.get("scene_spans") or []
    for sp in spans:
        if sp["start"] <= i <= sp["end"]:
            return sp["label"]
    return meta.get("scene")

def apply(text, ctx):
    meta = getattr(ctx, "metadata", {}) or {}
    constraints = meta.get("constraints") or {}
    rg = meta.get("roles_gender") or {}

    # fallback: якщо constraints нема, демотуємо “діда” поза Прологом
    pro_span = None
    for sp in (meta.get("scene_spans") or []):
        if (sp["label"] or "").lower().startswith("пролог"):
            pro_span = (sp["start"], sp["end"])
            break
    grandpas = {gid for gid, rec in rg.items()
                if any(k in " ".join(rec.get("roles") or []).lower() for k in ("дід", "дідо", "дідус"))}

    lines = text.splitlines(keepends=True)
    out, demoted = [], 0

    for i, ln in enumerate(lines):
        m = TAG.match(ln)
        if not m:
            out.append(ln); continue
        ind, gid_s, body = m.groups()
        if gid_s in ("?", "1"):
            out.append(ln); continue

        gid = f"#g{gid_s}"
        scene = _scene_of_line(i, meta) or ""

        c = constraints.get(gid) or {}
        allow = [x.lower() for x in (c.get("allowed_scenes") or [])]
        forbid = [x.lower() for x in (c.get("forbidden_scenes") or [])]
        deny = False
        if scene:
            sl = scene.lower()
            if allow and sl not in allow: deny = True
            if forbid and sl in forbid:   deny = True

        # fallback “дідо поза Прологом”, якщо constraints не задані
        if not allow and not forbid and pro_span and gid in grandpas:
            s, e = pro_span
            if not (s <= i <= e):
                deny = True

        if deny:
            out.append(f"{ind}#g?: {body}")
            demoted += 1
        else:
            out.append(ln)

    try:
        ctx.logs.append(f"[075 demote_forbidden_by_scene] demoted:{demoted}")
    except Exception:
        pass
    return "".join(out)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
