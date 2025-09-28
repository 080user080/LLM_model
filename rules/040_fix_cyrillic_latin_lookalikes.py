# rules/040_fix_cyrillic_latin_lookalikes.py  #GPT
PHASE, PRIORITY, SCOPE, NAME = 40, 0, "fulltext", "fix_cyr_lat_lookalikes"
MAP = str.maketrans("aceopxyiACEOPXYI", "асеорхуіАСЕОРХУІ")
def apply(text, ctx): return text.translate(MAP)
apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
