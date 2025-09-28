#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
legend_final_code.py — Генератор легенди тегів для українських текстів.

GUI за замовчуванням:
  python legend_final_code.py

CLI:
  python legend_final_code.py --cli --in Dialog_test.txt --out legend.yaml --out-txt legend.txt \
      --min-freq 1 --top 30 --preview 20 --hints legend_hints.yaml --seed legend_seed.txt
"""
import re
import argparse
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Set
from datetime import datetime
import json
import os

UKR_APOST = "’'"

# Дієслова мовлення
SPEECH_VERBS = r"(сказ(ав|ала|али)|відпов(ів|іла|іли)|крикн(ув|ула|ули)|прошепот(ів|іла|іли)|вигукн(ув|ула|ули)|мов(ив|ила|или)|промов(ив|ила|или)|запит(ав|ала|али)|спит(ав|ала|али)|буркн(ув|нула|нули)|процед(ив|ила|или)|відказ(ав|ала|али)|зазнач(ив|ила|или)|погод(ився|илась|илися))"

# Великі службові токени
STOP_CAP = {
    "Він","Вона","Воно","Вони","Я","Ми","Ви","Тут","Там","Це","Усе","Все","Той","Та","Такий","Так","Також","Або","А",
    "На","По","З","І","Як","Якщо","Тому","Але","Бо","Хоч","Із","До","Після","Перед","Між","Аж","Лише","Що","Коли",
    "Січня","Лютого","Березня","Квітня","Травня","Червня","Липня","Серпня","Вересня","Жовтня","Листопада","Грудня",
    "Понеділок","Вівторок","Середа","Четвер","Пʼятниця","Субота","Неділя"
}
# Нижній регістр шум
STOP_WORDS = {
    "так","ні","добре","звичайно","навіть","може","напевно","ну","значить","йо-хо","а-а",
    "показуй","покажи","бий","буду","потрібно","їм","йди","стій","чекай","дивись","слухай",
    "я","ми","ви","він","вона","воно","вони","хтось","ніхто","кожен"
}

NAME_TOKEN = r"[A-ZА-ЯЇІЄҐ][A-Za-zА-Яа-яЁёЇїІіЄєҐґ" + UKR_APOST + r"\-]+"

def is_stop_token(tok: str) -> bool:
    t = tok.strip(".,!?—–-:;«»\"()[]{}").casefold()
    return (t in STOP_WORDS) or (tok in STOP_CAP) or (t in {s.casefold() for s in STOP_CAP})

# ---------- Нормалізація форм імен ----------
def normalize_name_form(name: str, candidates: Set[str]) -> str:
    n = name.strip().strip(",.?!:;\"«»“”()").replace("`", "’")
    if not n:
        return name
    n = n.replace("'", "’")
    low = n.lower()
    if n in candidates:
        return n
    if low.endswith("е") and len(n) > 3:
        base = n[:-1]
        if base in candidates: return base
    if low.endswith("о") and len(n) > 3:
        base = n[:-1] + "а"
        if base in candidates: return base
    if low.endswith("і") and len(n) > 3:
        base_a = n[:-1] + "а"; base_ya = n[:-1] + "я"
        if base_a in candidates: return base_a
        if base_ya in candidates: return base_ya
    if low.endswith("ю") and len(n) > 3:
        base = n[:-1] + "я"
        if base in candidates: return base
    if low.endswith("у") and len(n) > 3:
        base = n[:-1] + "а"
        if base in candidates: return base
    return n

# ---------- Пошук кандидатів ----------
def find_name_candidates(text: str) -> Tuple[Counter, Dict[str, Counter]]:
    total = Counter()
    ctx = defaultdict(Counter)
    verb_pat = re.compile(rf"{SPEECH_VERBS}\s+(?P<name>{NAME_TOKEN})", flags=re.IGNORECASE|re.UNICODE)
    for m in verb_pat.finditer(text):
        nm = m.group("name")
        if nm in STOP_CAP: continue
        total[nm] += 1; ctx[nm]["verb"] += 1
    voc_pat = re.compile(rf"[—–\-,:;!\?]\s*(?P<name>{NAME_TOKEN})\s*[,!?\-]", flags=re.UNICODE)
    for m in voc_pat.finditer(text):
        nm = m.group("name")
        if nm in STOP_CAP: continue
        total[nm] += 1; ctx[nm]["voc"] += 1
    quote_pat = re.compile(rf"[«\"“”](.*?)([»\"“”])", flags=re.DOTALL|re.UNICODE)
    for qm in quote_pat.finditer(text):
        seg = qm.group(0)
        around = seg + " "
        for m in verb_pat.finditer(around):
            nm = m.group("name")
            if nm in STOP_CAP: continue
            total[nm] += 1; ctx[nm]["verb_quote"] += 1
        mv = re.findall(rf"(^|[—–\-])\s*(?P<name>{NAME_TOKEN})\s*[,!?\-]", seg)
        for tup in mv:
            nm = tup[1]
            if nm and nm not in STOP_CAP:
                total[nm] += 1; ctx[nm]["voc_quote"] += 1
    return total, ctx

def score_candidate(ctx: dict) -> int:
    return ctx.get("verb",0)*2 + ctx.get("verb_quote",0)*2 + ctx.get("voc",0) + ctx.get("voc_quote",0)

def filter_candidates(total: Counter, contexts: Dict[str, Counter]) -> Counter:
    keep = Counter()
    for n, cnt in total.items():
        if is_stop_token(n): continue
        if contexts.get(n, {}).get("verb",0) + contexts.get(n, {}).get("verb_quote",0) >= 1 or \
           contexts.get(n, {}).get("voc",0) + contexts.get(n, {}).get("voc_quote",0) >= 2:
            keep[n] = cnt + score_candidate(contexts.get(n, {}))  # невелика вага за контекст
    return keep

# ---------- Групування аліасів ----------
def build_alias_groups(total: Counter) -> Dict[str, Set[str]]:
    forms = set(total.keys())
    norm_map = {n: normalize_name_form(n, forms) for n in forms}
    groups = defaultdict(set)
    for n, canon in norm_map.items():
        groups[canon].add(n)
    def stem(s: str) -> str:
        return re.sub(rf"[{UKR_APOST}’'\-]", "", s.lower())[:6]
    by_stem = defaultdict(list)
    for canon in list(groups.keys()):
        by_stem[stem(canon)].append(canon)
    for bucket in by_stem.values():
        if len(bucket) < 2: continue
        best = max(bucket, key=lambda c: sum(total[f] for f in groups[c]))
        merged = set()
        for c in bucket:
            if c == best: continue
            merged |= groups[c]; del groups[c]
        groups[best] |= merged
    return dict(groups)

# ---------- Присвоєння тегів ----------
def assign_tags(groups: Dict[str, Set[str]], total: Counter, top: int, min_freq: int) -> List[Tuple[str, int, Set[str]]]:
    ranked = []
    for canon, forms in groups.items():
        freq = sum(total.get(f,0) for f in forms)
        if freq >= min_freq: ranked.append((canon, freq, forms))
    ranked.sort(key=lambda t: (-t[1], t[0]))
    return ranked[:top]

# ---------- HINTS ----------
def load_hints(path: str):
    if not path or not os.path.exists(path): return {}
    # YAML
    if path.lower().endswith((".yml",".yaml")):
        try:
            import yaml
            data = yaml.safe_load(open(path, "r", encoding="utf-8")) or {}
            out = {}
            for name, info in data.items():
                out[str(name)] = {
                    "gender": str(info.get("gender","?")),
                    "role": str(info.get("role","?")),
                    "aliases": list(info.get("aliases", []))
                }
            return out
        except Exception:
            pass
    # TXT "Name (M, ролі, …)"
    out = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"): continue
            if "(" in s and s.endswith(")"):
                name, attrs = s.split("(", 1)
                name = name.strip(" #-\t")
                attrs = [a.strip() for a in attrs[:-1].split(",") if a.strip()]
                gender = "?"
                role_parts = []
                for a in attrs:
                    if a in ("M","F","NB"): gender = a
                    else: role_parts.append(a)
                out[name] = {"gender": gender, "role": ", ".join(role_parts) if role_parts else "?", "aliases": []}
            else:
                name = s.strip(" #-\t")
                out[name] = {"gender": "?", "role": "?", "aliases": []}
    return out

# ---------- SEED: попередня розмітка #gN ----------
def load_seed(path: str):
    """
    Рядок формату: #gN - Ім'я (M/F/NB, ролі, …)
    Підтримує кілька імен у полі Ім'я через "/" -> створить aliases.
    """
    if not path or not os.path.exists(path): return []
    seed = []
    pat = re.compile(r"^\s*#g?(\d+)\s*-\s*(.+?)(?:\s*\((.+)\))?\s*$")
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            m = pat.match(line.strip())
            if not m: continue
            n = int(m.group(1))
            name_field = m.group(2).strip()
            names = [p.strip() for p in name_field.split("/") if p.strip()]
            name = names[0]
            aliases = names[1:]
            gender = "?"
            role = "?"
            if m.group(3):
                parts = [p.strip() for p in m.group(3).split(",") if p.strip()]
                roles = []
                for p2 in parts:
                    if p2 in ("M","F","NB"): gender = p2
                    else: roles.append(p2)
                if roles: role = ", ".join(roles)
            seed.append({"g": f"g{n}", "name": name, "gender": gender, "role": role, "aliases": aliases})
    seed.sort(key=lambda r: int(r["g"][1:]))
    return seed

# ---------- Побудова записів ----------
def build_records(tag_entries: List[Tuple[str, int, Set[str]]],
                  total: Counter,
                  hints: Dict[str, dict],
                  seed: List[dict]) -> List[dict]:
    # map: canon -> freq, forms
    canon_map = {canon: {"freq": freq, "forms": forms} for canon, freq, forms in tag_entries}

    # Start with g0, then seed (preserve their numbers), then auto, then g98,g99
    records: List[dict] = []
    used_canons = set()

    # g0
    records.append({"g": "g0", "name": "Невідомий", "gender": "?", "role": "fallback",
                    "aliases": [], "voice": "#voice_g0", "freq": 0})

    # seed
    canon_cf = {c.casefold(): c for c in canon_map.keys()}
    for r in seed:
        canon_key = canon_cf.get(r["name"].casefold())
        freq = 0
        aliases_auto = []
        if canon_key:
            freq = canon_map[canon_key]["freq"]
            aliases_auto = sorted(set(canon_map[canon_key]["forms"]) - {canon_key})
            used_canons.add(canon_key)
            name_final = canon_key
        else:
            name_final = r["name"]
        # merge hints
        h = hints.get(name_final, hints.get(r["name"], {}))
        gender = r["gender"] if r["gender"] != "?" else h.get("gender","?")
        role = r["role"] if r["role"] != "?" else h.get("role","?")
        aliases = sorted(set(r.get("aliases", [])) | set(h.get("aliases", [])) | set(aliases_auto))
        records.append({
            "g": r["g"], "name": name_final, "gender": gender, "role": role,
            "aliases": aliases, "voice": f"#voice_{r['g']}", "freq": freq
        })

    # auto-assigned starting after max existing g
    max_g = max([0] + [int(r["g"][1:]) for r in records])
    next_g = max_g + 1
    for canon, info in canon_map.items():
        if canon in used_canons: continue
        h = hints.get(canon, {})
        records.append({
            "g": f"g{next_g}", "name": canon,
            "gender": h.get("gender","?"),
            "role": h.get("role","?"),
            "aliases": sorted(set(info["forms"]) - {canon} | set(h.get("aliases", []))),
            "voice": f"#voice_g{next_g}",
            "freq": info["freq"]
        })
        next_g += 1

    # g1 narrator seed override handling:
    # якщо у seed вже був g1 — нічого не додаємо оповідача,
    # інакше додаємо за замовчуванням оповідача як g1 перед seed.
    if not any(r["g"] == "g1" for r in records):
        records.insert(1, {"g": "g1", "name": "Оповідач", "gender": "?",
                           "role": "наратив", "aliases": [], "voice": "#voice_g1", "freq": 0})

    # g98, g99
    records.append({"g": "g98", "name": "Авторські вставки", "gender": "?", "role": "meta",
                    "aliases": [], "voice": "#voice_g98", "freq": 0})
    records.append({"g": "g99", "name": "Натовп", "gender": "?", "role": "group",
                    "aliases": [], "voice": "#voice_g99", "freq": 0})

    # унікальні та відсортовані за номером
    uniq = {}
    for r in records:
        uniq[r["g"]] = r
    records = [uniq[k] for k in sorted(uniq.keys(), key=lambda g: int(g[1:]))]
    return records

# ---------- Формування YAML ----------
def to_yaml(records: List[dict], version: int = 1) -> str:
    def y(s: str) -> str: return '"' + str(s).replace('"', '\\"') + '"'
    lines = []
    for r in records:
        if r["g"] in ("g0", "g98", "g99") or (r["g"]=="g1" and r["name"]=="Оповідач"):
            lines.append(f'{r["g"]}: {{name: {y(r["name"])}, role: {y(r["role"])}, aliases: []}}')
        else:
            aliases_yaml = "[" + ", ".join(y(a) for a in r["aliases"]) + "]"
            lines += [
                f'{r["g"]}:',
                f'  name: {y(r["name"])}',
                f'  gender: {y(r["gender"])}',
                f'  role: {y(r["role"])}',
                f'  aliases: {aliases_yaml}',
                f'  voice: {y(r["voice"])}',
                f'  freq: {r.get("freq",0)}',
            ]
    lines.append(f"version: {version}")
    lines.append(f'generated_at: "{datetime.utcnow().isoformat()}Z"')
    return "\n".join(lines)

# ---------- Формування TXT ----------
def to_txt(records: List[dict]) -> str:
    out = []
    for r in records:
        n = r["g"][1:]
        name = r["name"]
        attrs = []
        if r["gender"] and r["gender"] != "?": attrs.append(r["gender"])
        if r["role"] and r["role"] != "?": attrs.append(r["role"])
        if r.get("aliases"): attrs.extend(r["aliases"])
        line = f"#g{n} - {name}" + (f" ({', '.join(attrs)})" if attrs else "")
        out.append(line)
    # секція частот
    out.append("")
    out.append("## Частоти згадок")
    for r in records:
        out.append(f"#g{r['g'][1:]} - {r.get('freq',0)}")
    return "\n".join(out)

# ---------- Превʼю ----------
def tag_preview(text: str, names: List[str], limit_lines: int = 20) -> List[str]:
    unknown = []
    lines = text.splitlines()[:limit_lines]
    known = set(names)
    voc_pat = re.compile(rf"[—–\-,:;!\?]\s*(?P<name>{NAME_TOKEN})\s*[,!?\-]", flags=re.UNICODE)
    for line in lines:
        for m in voc_pat.finditer(line):
            nm = m.group("name")
            if nm not in known: unknown.append(nm)
    return unknown

# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(description="Генератор легенди тегів для текстів (UA).")
    ap.add_argument("--in", dest="inp", default="Dialog_test.txt")
    ap.add_argument("--out", dest="out_yaml", default="legend.yaml")
    ap.add_argument("--out-txt", dest="out_txt", default=None, help="Шлях до TXT. Якщо не вказано, буде <out>.txt")
    ap.add_argument("--min-freq", type=int, default=1)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--preview", type=int, default=20)
    ap.add_argument("--hints", dest="hints", default=None, help="YAML/TXT з підказками статі/ролей/аліасів")
    ap.add_argument("--seed", dest="seed", default=None, help="TXT з фіксованим порядком #gN - Ім'я (атрибути)")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--cli", action="store_true", help="Примусовий CLI-режим")
    args = ap.parse_args()

    if args.test:
        run_tests(); return

    text = open(args.inp, "r", encoding="utf-8").read()
    total_raw, contexts = find_name_candidates(text)
    total = filter_candidates(total_raw, contexts)

    groups = build_alias_groups(total)
    ranked = assign_tags(groups, total, top=args.top, min_freq=args.min_freq)

    hints = load_hints(args.hints)
    seed = load_seed(args.seed)

    records = build_records(ranked, total, hints, seed)

    yaml_str = to_yaml(records, version=1)
    open(args.out_yaml, "w", encoding="utf-8").write(yaml_str)

    out_txt_path = args.out_txt or os.path.splitext(args.out_yaml)[0] + ".txt"
    txt_str = to_txt(records)
    open(out_txt_path, "w", encoding="utf-8").write(txt_str)

    preview_unknown = tag_preview(text, [r["name"] for r in records if r["g"].startswith("g")], limit_lines=args.preview)
    summary = {
        "found_forms_raw": len(total_raw),
        "found_forms_after_filter": len(total),
        "groups": len(groups),
        "emitted_tags": sum(1 for r in records if r["g"].startswith("g") and r["g"] not in ("g0","g98","g99")),
        "unknown_preview": preview_unknown[:20],
        "yaml": args.out_yaml,
        "txt": out_txt_path
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

# ---------- Тести ----------
def run_tests():
    t1 = "— Лоло, не бігай! — крикнула Таша."
    total, _ = find_name_candidates(t1); assert total["Лоло"] >= 1; assert total["Таша"] >= 1
    t2 = "«Привіт», — сказав Василь. — Іване, ходімо!"
    total, _ = find_name_candidates(t2); assert total["Василь"] >= 1; assert "Іване" in total
    groups = build_alias_groups(Counter({"Таша": 2, "Ташо": 1}))
    assert any(k == "Таша" for k in groups.keys()); assert "Ташо" in next(v for k,v in groups.items() if k.startswith("Таш"))
    c = Counter({"Лоло": 5, "Таша": 3, "Василь": 1})
    groups = build_alias_groups(c); ranked = assign_tags(groups, c, top=2, min_freq=1)
    assert ranked[0][0] == "Лоло" and len(ranked) == 2
    recs = build_records(ranked, c, {}, [])
    txt = to_txt(recs); assert "#g2" in txt
    print("OK: tests passed.")

# ====================== GUI (Tkinter) ======================
def run_gui():
    import threading
    import tkinter as tk
    from tkinter import filedialog, messagebox

    BG = "#1e1e1e"; FG = "#e6e6e6"; ACCENT = "#3a96dd"; ENTRY_BG = "#2b2b2b"

    root = tk.Tk(); root.title("Генератор легенди тегів"); root.configure(bg=BG)

    def lbl(r, t, row): tk.Label(r, text=t, bg=BG, fg=FG, anchor="w").grid(row=row, column=0, sticky="w")
    def entry(var, row):
        e = tk.Entry(frm, textvariable=var, bg=ENTRY_BG, fg=FG, insertbackground=FG, width=60)
        e.grid(row=row, column=1, sticky="we", padx=6); return e
    def browse_file(var, row, save=False, exts=() ):
        def _():
            p = filedialog.asksaveasfilename if save else filedialog.askopenfilename
            ft = [("All","*.*")]
            if exts: ft = [(ext.upper(), f"*.{ext}") for ext in exts]
            path = p(title="Файл", defaultextension=f".{exts[0]}" if save and exts else None, filetypes=ft)
            if path: var.set(path)
        tk.Button(frm, text="…", command=_, bg=ACCENT, fg="white").grid(row=row, column=2, sticky="we")

    frm = tk.Frame(root, bg=BG); frm.pack(fill="both", expand=True, padx=12, pady=12)
    frm.grid_columnconfigure(1, weight=1)

    in_var = tk.StringVar(value="Dialog_test.txt")
    outy_var = tk.StringVar(value="legend.yaml")
    outt_var = tk.StringVar(value="legend.txt")
    hints_var = tk.StringVar(value="")
    seed_var = tk.StringVar(value="")
    minf_var = tk.IntVar(value=1)
    top_var = tk.IntVar(value=30)
    prev_var = tk.IntVar(value=20)

    lbl(frm, "Вхідний TXT:", 0); entry(in_var,0); browse_file(in_var,0,save=False, exts=("txt","md","log"))
    lbl(frm, "Вихід YAML:", 1); entry(outy_var,1); browse_file(outy_var,1,save=True, exts=("yaml","yml"))
    lbl(frm, "Вихід TXT:", 2); entry(outt_var,2); browse_file(outt_var,2,save=True, exts=("txt",))
    lbl(frm, "Hints (YAML/TXT):", 3); entry(hints_var,3); browse_file(hints_var,3,save=False, exts=("yaml","yml","txt"))
    lbl(frm, "Seed (TXT):", 4); entry(seed_var,4); browse_file(seed_var,4,save=False, exts=("txt",))

    tk.Label(frm, text="Мін. частота:", bg=BG, fg=FG).grid(row=5, column=0, sticky="w")
    tk.Spinbox(frm, from_=1, to=999, textvariable=minf_var, width=6, bg=ENTRY_BG, fg=FG, insertbackground=FG).grid(row=5, column=1, sticky="w", padx=6)
    tk.Label(frm, text="TOP:", bg=BG, fg=FG).grid(row=6, column=0, sticky="w")
    tk.Spinbox(frm, from_=1, to=300, textvariable=top_var, width=6, bg=ENTRY_BG, fg=FG, insertbackground=FG).grid(row=6, column=1, sticky="w", padx=6)
    tk.Label(frm, text="Превʼю рядків:", bg=BG, fg=FG).grid(row=7, column=0, sticky="w")
    tk.Spinbox(frm, from_=0, to=500, textvariable=prev_var, width=6, bg=ENTRY_BG, fg=FG, insertbackground=FG).grid(row=7, column=1, sticky="w", padx=6)

    log = tk.Text(frm, height=12, bg="#111", fg="#ddd", insertbackground=FG); log.grid(row=8, column=0, columnspan=3, sticky="nsew", pady=(6,0))
    frm.grid_rowconfigure(8, weight=1)
    def logln(s): log.insert("end", s + "\n"); log.see("end")

    def job():
        try:
            text = open(in_var.get(), "r", encoding="utf-8").read()
            total_raw, contexts = find_name_candidates(text)
            total = filter_candidates(total_raw, contexts)
            groups = build_alias_groups(total)
            ranked = assign_tags(groups, total, top=top_var.get(), min_freq=minf_var.get())
            hints = load_hints(hints_var.get() or None)
            seed = load_seed(seed_var.get() or None)
            records = build_records(ranked, total, hints, seed)
            open(outy_var.get(), "w", encoding="utf-8").write(to_yaml(records))
            open(outt_var.get(), "w", encoding="utf-8").write(to_txt(records))
            logln("Готово."); logln(json.dumps({"tags": len([r for r in records if r['g'].startswith('g')]), "yaml": outy_var.get(), "txt": outt_var.get()}, ensure_ascii=False, indent=2))
            messagebox.showinfo("Готово", "Легенду збережено.")
        except Exception as e:
            logln(f"Помилка: {e}"); messagebox.showerror("Помилка", str(e))

    tk.Button(root, text="Згенерувати", command=lambda: __import__("threading").Thread(target=job, daemon=True).start(),
              bg=ACCENT, fg="white").pack(padx=12, pady=(0,12), anchor="e")
    root.mainloop()

# ---------- Точка входу ----------
if __name__ == "__main__":
    # GUI за замовчуванням, CLI якщо явно --cli або присутні CLI-прапори
    cli_flags = {"--in","--out","--out-txt","--min-freq","--top","--preview","--hints","--seed","--test","--cli"}
    if ("--cli" in sys.argv) or any(flag in sys.argv for flag in cli_flags):
        # прибрати службовий --cli
        if "--cli" in sys.argv: sys.argv.remove("--cli")
        main()
    else:
        run_gui()
