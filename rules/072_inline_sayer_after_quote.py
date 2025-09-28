# -*- coding: utf-8 -*-
"""
072_inline_sayer_after_quote.py
Визначає мовця у ТІЙ Ж САМИЙ ЛІНІЇ діалогу за пост-атрибуцією типу:
  — ... — сказала Таша.      → #g(Таша)
  «...» — сказав Нієр.       → #g(Нієр)
  — ... — сказав я.          → first_person_gid (з легенди hints)

Консервативно: працює лише коли знайдено ІМ'Я з легенди або "я".
Займенники "він/вона" пропускаємо (краще лишити #g?).
"""
import re, unicodedata

PHASE, PRIORITY, SCOPE, NAME = 72, 9, "fulltext", "inline_sayer_after_quote"

NBSP = "\u00A0"
TRIM = ".,:;!?»«”“’'—–-()[]{}"
DASH = r"\-\u2012\u2013\u2014\u2015"
DIALOG = re.compile(rf"^\s*(?:[{DASH}]|[«\"„“”'’])")
TAG_ANY = re.compile(r"^(\s*)#g(\d+|\?)\s*:\s*(.*)$", re.DOTALL)

# Дієслова мовлення (можеш доповнювати за потреби)
#
# Окремо поділяємо на чоловічі (masculine) та жіночі (feminine) форми, щоб
# виявляти морфологічну невідповідність між дієсловом та іменем. Це
# дозволяє пропускати випадки на кшталт «сказав Ольга» – тут дієслово
# чоловічого роду не узгоджується з жіночим ім'ям, тому така атрибуція
# вважається ненадійною. При необхідності, список можна розширити.
SAY_VERBS = (
    r"сказав|сказала|кажу|каже|відповів|відповіла|спитав|спитала|"
    r"крикнув|крикнула|вигукнув|вигукнула|прошепотів|прошепотіла|"
    r"буркнув|буркнула|мовив|промовила|пояснив|пояснила|гукнув|гукнула"
)

# Виділяємо окремо множини маскулінних та фемінних форм. Використовуємо
# нормалізовану форму (без наголосів, у нижньому регістрі) для порівняння.
MASC_VERBS = {
    "сказав", "кажу", "каже", "відповів", "спитав",
    "крикнув", "вигукнув", "прошепотів", "буркнув", "мовив",
    "пояснив", "гукнув"
}
FEM_VERBS = {
    "сказала", "відповіла", "спитала",
    "крикнула", "вигукнула", "прошепотіла", "буркнула",
    "промовила", "пояснила", "гукнула"
}

# Патерни типу:   — … — сказав Нієр   /   — … — Нієр сказав
# Патерни типу:   — … — сказав Нієр   /   — … — Нієр сказав
# Додатково захоплюємо дієслово мовлення як окрему групу «verb», щоб
# перевіряти рід. Обидва патерни працюють без регістрової чутливості.
AFTER_QUOTE_VERB_NAME = re.compile(
    rf"[{DASH}]\s*[,»\"“”'’]*\s*(?:—\s*)?(?:,?\s*)?(?P<verb>{SAY_VERBS})\s+(?P<who>[A-ZА-ЯЇІЄҐ][\w’'\-]+|я)\b",
    re.IGNORECASE
)
AFTER_QUOTE_NAME_VERB = re.compile(
    rf"[{DASH}]\s*[,»\"“”'’]*\s*(?:—\s*)?(?P<who>[A-ZА-ЯЇІЄҐ][\w’'\-]+)\s+(?P<verb>{SAY_VERBS})\b",
    re.IGNORECASE
)

def _nfd_strip(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if not unicodedata.combining(ch))

def _norm(s: str) -> str:
    return _nfd_strip(s).casefold().strip(TRIM + " ")

def _alias_map(ctx):
    """З легенди будуємо мапу нормалізованих імен/аліасів → #gX"""
    legend = getattr(ctx, "metadata", {}).get("legend", {}) or {}
    amap = {}
    for raw, gid in legend.items():
        base = re.split(r"[—–]|[\(,]", str(raw), 1)[0].strip() or str(raw)
        for cand in {str(raw).strip(), base, base.split()[0]}:
            if cand:
                amap.setdefault(_norm(cand), str(gid))
    return amap

def _dialog_of(line: str):
    m = TAG_ANY.match(line)
    if not m: return None, None, None
    indent, gid, body = m.groups()
    body_norm = body.replace(NBSP, " ").lstrip()
    if not DIALOG.match(body_norm): return None, None, None
    return indent, f"#g{gid}", body

def apply(text, ctx):
    lines = text.splitlines(keepends=True)
    meta  = getattr(ctx, "metadata", {}) or {}
    amap  = _alias_map(ctx)
    first_person_gid = (meta.get('hints') or {}).get('first_person_gid', '#g2')

    for i, ln in enumerate(lines):
        ind, gid, body = _dialog_of(ln)
        if gid != "#g?":
            continue

        s = body.replace(NBSP, " ")
        m = AFTER_QUOTE_VERB_NAME.search(s) or AFTER_QUOTE_NAME_VERB.search(s)
        if not m:
            continue

        who_raw = m.group("who")
        who_n = _norm(who_raw)
        verb_raw = m.groupdict().get("verb")

        # Якщо з дієслова можна визначити рід, перевіряємо узгодженість із ім'ям.
        # Пропускаємо випадки, де рід дієслова та ім'я суперечать одне одному.
        if verb_raw:
            verb_norm = _norm(verb_raw)
            # Визначаємо рід дієслова
            if verb_norm in MASC_VERBS:
                verb_gender = 'm'
            elif verb_norm in FEM_VERBS:
                verb_gender = 'f'
            else:
                verb_gender = None

            # Евристика для визначення роду імені: більшість українських жіночих
            # імен закінчуються на «а» або «я». Це проста перевірка без
            # повноцінного морфаналізу; у сумнівних випадках повертаємо None.
            name_gender = None
            if who_n != 'я':
                # беремо останню літеру нормалізованого імені
                last_ch = who_n[-1] if who_n else ''
                if last_ch in {'а', 'я', 'е', 'ь', 'я', 'ю'}:
                    name_gender = 'f'
                elif last_ch in {'о', 'й', 'р', 'н', 'д', 'т', 'л', 'с', 'м', 'к', 'б', 'г', 'п', 'щ', 'ч', 'ц'}:
                    name_gender = 'm'

            # Якщо і рід дієслова, і рід імені визначені та не співпадають —
            # не атрибутуємо спікера цією евристикою (залишаємо #g?).
            if verb_gender and name_gender and verb_gender != name_gender:
                continue

        # "я" → first_person_gid
        if who_n == "я":
            lines[i] = f"{ind}{first_person_gid}: {body}"
            continue

        # ІМ'Я з легенди → той самий #gX (але не #g1 як спікер)
        gid_found = amap.get(who_n)
        if gid_found and gid_found != "#g1":
            lines[i] = f"{ind}{gid_found}: {body}"
            continue

        # Інакше (він/вона/не з легенди) — не чіпаємо, хай вирішать інші правила
        # залишаємо #g?
    return "".join(lines)

apply.phase, apply.priority, apply.scope, apply.name = PHASE, PRIORITY, SCOPE, NAME
