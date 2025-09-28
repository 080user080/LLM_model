# 052_extract_roles_gender.py — витяг гендеру та ролей з легенди у ctx.metadata
# -*- coding: utf-8 -*-
"""
Створює ctx.metadata["roles_gender"] для правил:
{
  "#g5": {"gender":"F","roles":["правнучка","дитина","онучка","сонечко"],
          "names":["Правнучка"], "aliases":[...], "first_person": False},
  ...
}
Працює після 050/051: використовує meta.legend (alias->#g) і, за можливості,
“сирі” рядки легенди (#gN - Назва (атрибути,...)) з ctx.legend або meta.legend_text.
"""

import re

PHASE, PRIORITY, SCOPE, NAME = 52, 0, "fulltext", "extract_roles_gender"  #GPT

# латиниця-схожа-на-кирилицю
_LAT2CYR = str.maketrans("aceopxyiACEOPXYI", "асеорхуіАСЕОРХУІ")
PAREN = re.compile(r"\((?P<attrs>.*?)\)\s*$")

# службові токени, які не заносимо у roles
SERVICE_TOKENS = {
    "m","f","оповідач","наратив","сучасні сцени","сучасний співрозмовник","головний герой"
}

# евристики визначення гендеру зі слів у дужках
F_STEMS = ("жін", "дів", "мати", "мам", "баб", "правнуч", "донь")
M_STEMS = ("чолов", "хлоп", "дід", "дідо", "дідус", "старійшин", "ватаж")

def _nrm(s: str) -> str:
    return s.translate(_LAT2CYR).strip()

def _split_name_attrs(text: str):
    """
    'Правнучка (F, дівчинка, дитина, онучка, сонечко)'
      -> names=['Правнучка'], attrs='F, дівчинка, дитина, онучка, сонечко'
    'Той / Той-Спис (M, ватажок)'
      -> names=['Той','Той-Спис'], attrs='M, ватажок'
    """
    m = PAREN.search(text)
    attrs = m.group("attrs") if m else ""
    name = text[:m.start()].strip() if m else text.strip()
    names = [n.strip() for n in name.split("/") if n.strip()]
    return names, attrs

def _tokenize_attrs(attrs: str):
    toks = []
    for t in (x.strip() for x in attrs.split(",")):
        if not t: 
            continue
        # брати тільки буквено-апострофні токени
        if re.fullmatch(r"[A-Za-zА-Яа-яЁёЄєІіЇїҐґ'’\- ]{1,}", t):
            toks.append(t)
    return toks

def _guess_gender(attrs_lower: str):
    # явні позначки M/F
    if re.search(r"(^|[,;\s])f($|[,;\s])", attrs_lower): 
        return "F"
    if re.search(r"(^|[,;\s])m($|[,;\s])", attrs_lower): 
        return "M"
    # стем-евристики
    if any(st in attrs_lower for st in F_STEMS): 
        return "F"
    if any(st in attrs_lower for st in M_STEMS): 
        return "M"
    return None

def _raw_legend_map_from_ctx(ctx):
    """
    Повертає {#gN: 'Назва (атрибути,...)'} якщо є в ctx.legend або meta.legend_text.
    """
    # варіант 1: ctx.legend як #g -> line
    raw = {}
    raw_leg = getattr(ctx, "legend", None)
    if isinstance(raw_leg, dict) and all(isinstance(k,str) and k.strip().startswith("#g") for k in raw_leg):
        return {k.strip(): str(v) for k,v in raw_leg.items()}

    # варіант 2: meta.legend_text
    meta = getattr(ctx, "metadata", {}) or {}
    leg_text = (meta.get("legend_text") or "").strip()
    if leg_text:
        for ln in leg_text.splitlines():
            ln = ln.strip()
            if not ln or not ln.startswith("#g"):
                continue
            try:
                gid, rest = ln.split("-", 1)
                raw[gid.strip()] = rest.strip()
            except ValueError:
                pass
    return raw or None

def apply(text: str, ctx):
    meta = getattr(ctx, "metadata", {}) or {}
    amap = (meta.get("legend") or {})  # alias->#g
    if not amap:
        return text

    # готуємо alias-и та кандидати “сирих” рядків для кожного gid
    gid2aliases = {}
    for alias, gid in amap.items():
        gid2aliases.setdefault(gid, []).append(alias)

    raw_map = _raw_legend_map_from_ctx(ctx)

    roles_gender = {}
    added = 0

    for gid, aliases in gid2aliases.items():
        # базовий рядок для імен/ролей беремо з:
        # 1) сирої легенди (#g -> "Назва (attrs)")
        base_line = None
        if raw_map and gid in raw_map:
            base_line = _nrm(raw_map[gid])
        else:
            # 2) або з alias, який містить дужки
            base_line = next(( _nrm(a) for a in aliases if "(" in a and ")" in a ), None)
        # якщо ні — візьмемо перший alias як ім'я без атрибутів
        if not base_line and aliases:
            base_line = _nrm(aliases[0])

        names, attrs = _split_name_attrs(base_line)
        attrs_lower = attrs.lower()

        # гендер
        gender = _guess_gender(attrs_lower)

        # ролі: усі токени з дужок, що не службові
        roles = []
        for tok in _tokenize_attrs(attrs):
            t = _nrm(tok)
            tcf = t.casefold()
            if tcf in SERVICE_TOKENS:
                continue
            # відкидаємо одинарні літери на кшталт m/f
            if tcf in {"m","f"}:
                continue
            if t:
                roles.append(t)

        # очищені aliases (lower/casefold) для зручності подальших правил
        norm_aliases = sorted({ _nrm(a).casefold() for a in aliases })

        # first-person підказка
        first_person = False
        if meta.get("hints") and meta["hints"].get("first_person_gid") == gid:
            first_person = True

        roles_gender[gid] = {
            "gender": gender,
            "roles": roles,
            "names": names,
            "aliases": norm_aliases,
            "first_person": first_person,
        }
        added += 1

    meta["roles_gender"] = roles_gender
    setattr(ctx, "metadata", meta)

    try:
        ctx.logs.append(f"[052 roles_gender] gids:{len(roles_gender)} (updated:{added})")
    except Exception:
        pass

    return text

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME  #GPT
