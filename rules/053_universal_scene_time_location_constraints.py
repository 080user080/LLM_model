# 053_universal_scene_time_location_constraints.py — універсальні обмеження за сценою/часом/локацією (fixed)
# -*- coding: utf-8 -*-
import re

PHASE, PRIORITY, SCOPE, NAME = 53, 0, "fulltext", "universal_scene_time_location_constraints"

TAG_ANY = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)
_LAT2CYR = str.maketrans("aceopxyiACEOPXYI", "асеорхуіАСЕОРХУІ")
def _nrm(s: str) -> str: return (s or "").translate(_LAT2CYR).strip()

def _roles_gender(ctx): return (getattr(ctx, "metadata", {}) or {}).get("roles_gender") or {}
def _legend_alias_map(ctx):
    meta = getattr(ctx, "metadata", {}) or {}
    amap = meta.get("legend") or {}
    return {(k or "").strip().casefold(): v for k, v in amap.items()}

def _raw_legend_from_ctx(ctx):
    raw = {}
    raw_leg = getattr(ctx, "legend", None)
    if isinstance(raw_leg, dict) and all(isinstance(k,str) and k.strip().startswith("#g") for k in raw_leg):
        return {k.strip(): str(v) for k,v in raw_leg.items()}
    meta = getattr(ctx, "metadata", {}) or {}
    leg_text = (meta.get("legend_text") or "").strip()
    if leg_text:
        for ln in leg_text.splitlines():
            ln = ln.strip()
            if not ln or not ln.startswith("#g"): continue
            try:
                gid, rest = ln.split("-", 1)
                raw[gid.strip()] = rest.strip()
            except ValueError:
                pass
    return raw or None

def _split_name_attrs(text: str):
    m = re.search(r"\((?P<attrs>.*?)\)\s*$", text or "")
    attrs = m.group("attrs") if m else ""
    name = text[:m.start()].strip() if m else (text or "").strip()
    names = [n.strip() for n in name.split("/") if n.strip()]
    return names, attrs

def _parse_scene_tokens(attrs: str):
    allowed, forbidden, time_tags, locations = set(), set(), set(), set()
    for raw in (a.strip() for a in (attrs or "").split(",")):
        if not raw: continue
        t = _nrm(raw); low = t.casefold()
        if low.startswith("allow:"):
            allowed.add(_nrm(t.split(":",1)[1]))
        elif low.startswith("forbid:"):
            forbidden.add(_nrm(t.split(":",1)[1]))
        elif low.startswith(("сцена:", "scene:")):
            allowed.add(_nrm(t.split(":",1)[1]))
        elif low.startswith(("час:", "time:")):
            time_tags.add(_nrm(t.split(":",1)[1]))
        elif low.startswith(("локація:", "loc:", "location:")):
            locations.add(_nrm(t.split(":",1)[1]))
        else:
            if "сучасні" in low and "сцени" in low: time_tags.add("сучасні")
    return {
        "allowed_scenes": sorted(allowed) if allowed else None,
        "forbidden_scenes": sorted(forbidden) if forbidden else None,
        "time_tags": sorted(time_tags) if time_tags else None,
        "locations": sorted(locations) if locations else None,
    }

def _build_constraints(ctx):
    meta = getattr(ctx, "metadata", {}) or {}
    rg = _roles_gender(ctx)
    raw_map = _raw_legend_from_ctx(ctx)
    constraints = {}
    for gid, rg_rec in rg.items():
        base_line = None
        if raw_map and gid in raw_map:
            base_line = _nrm(raw_map[gid])
        else:
            for a, g in (meta.get("legend") or {}).items():
                if g == gid and "(" in a and ")" in a:
                    base_line = _nrm(a); break
        names, attrs = _split_name_attrs(base_line or " ".join(rg_rec.get("names") or []))
        parsed = _parse_scene_tokens(attrs or "")
        roles = (rg_rec.get("roles") or [])
        if not parsed["time_tags"]:
            if any("сучасні сцени" in r.casefold() for r in roles):
                parsed["time_tags"] = ["сучасні"]
        constraints[gid] = parsed
    meta["constraints"] = constraints
    setattr(ctx, "metadata", meta)
    return constraints

def _label_from_text(txt: str):
    if not txt: return None
    t = txt.strip()
    m = re.match(r"^\s*(пролог|епілог)\.?\s*$", t, flags=re.IGNORECASE)
    if m: return m.group(1).strip().capitalize()
    m = re.match(r"^\s*(глава|розділ|частина)\s+(?:\d+|[IVXLCDM]+)\.?\s*$", t, flags=re.IGNORECASE)
    if m: return f"{m.group(1).strip().capitalize()} " + re.findall(r"(?:\d+|[IVXLCDM]+)", t, flags=re.IGNORECASE)[0]
    return None

def _detect_scene(line: str):
    label = _label_from_text(line)
    if label: return label
    m = TAG_ANY.match(line)
    if m and m.group(2) == "1":
        return _label_from_text(m.group(3))
    return None

def apply(text: str, ctx):
    meta = getattr(ctx, "metadata", {}) or {}
    constraints = meta.get("constraints") or _build_constraints(ctx)

    lines = text.splitlines(keepends=True)
    out = []
    current_scene = meta.get("scene")
    demoted = 0; scene_switched = 0

    for ln in lines:
        label = _detect_scene(ln.strip())
        if label:
            current_scene = label
            scene_switched += 1
            out.append(ln); continue

        m = TAG_ANY.match(ln)
        if not m: out.append(ln); continue

        indent, gid_short, body = m.groups()
        if gid_short in ("?", "1"): out.append(ln); continue
        gid_full = f"#g{gid_short}"

        c = constraints.get(gid_full) or {}
        allow = c.get("allowed_scenes") or []
        forbid = c.get("forbidden_scenes") or []

        if current_scene:
            sl = current_scene.lower()
            deny = False
            if allow and all(sl != x.lower() for x in allow): deny = True
            if forbid and any(sl == x.lower() for x in forbid): deny = True
            if deny:
                out.append(f"{indent}#g?: {body}")
                demoted += 1
                continue

        out.append(ln)

    meta["scene"] = current_scene
    setattr(ctx, "metadata", meta)
    try: ctx.logs.append(f"[053 constraints] demoted:{demoted} scene_switches:{scene_switched}")
    except Exception: pass
    return "".join(out)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
