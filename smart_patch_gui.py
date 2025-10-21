#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smart_patch_gui.py — GUI для спрощених diff і генерації unified diff.
Спрощений diff:
  - старий рядок
  + новий рядок
"""

from __future__ import annotations
import os, re, sys, shutil
from dataclasses import dataclass
from difflib import SequenceMatcher, unified_diff
from typing import List, Tuple, Optional
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Правила ігнорування рядків у цільовому файлі під час пошуку відповідностей
# Рядки, що збігаються з цими шаблонами, не створюють розбіжностей і можуть
# бути пропущені між рядками старого та нового блоків, якщо diff цього не вимагає.
IGNORE_LINE_PATTERNS = [r"^\\s*#\\s*не\\s*спамимо\\s*тут.*$"]
_IGNORE_RE = re.compile("|".join(IGNORE_LINE_PATTERNS), re.IGNORECASE)

def _is_ignored_line(ln: str) -> bool:
    return bool(_IGNORE_RE.search(ln))

# Моделі
@dataclass
class Rule:
    find: str
    replace: str
    idx: int

@dataclass
class ApplyStats:
    replaced: int = 0
    fuzzy_replaced: int = 0
    missing: int = 0

# I/O
def _detect_newline_style(raw: bytes) -> str:
    return "\r\n" if b"\r\n" in raw else "\n"

def _try_read_text(path: str, forced_encoding: Optional[str] = None) -> Tuple[str, str, bool, str]:
    with open(path, "rb") as f:
        raw = f.read()
    newline = _detect_newline_style(raw)
    candidates = [forced_encoding] if forced_encoding else ["utf-8-sig", "utf-8", "cp1251", "latin1"]
    last_err = None
    for enc in candidates:
        try:
            txt = raw.decode(enc)
            had_bom = enc == "utf-8-sig"
            return txt.replace("\r\n", "\n"), ("utf-8" if had_bom else enc), had_bom, newline
        except UnicodeDecodeError as e:
            last_err = e
    raise UnicodeDecodeError("decode", b"", 0, 0, f"Cannot decode {path}: {last_err}")

def _write_text_preserve(path: str, text_unix: str, encoding: str, had_bom: bool, newline_style: str) -> None:
    data = text_unix.replace("\n", newline_style)
    if had_bom and encoding.lower().startswith("utf-8"):
        with open(path, "wb") as f:
            f.write(b"\xef\xbb\xbf"); f.write(data.encode("utf-8"))
    else:
        with open(path, "w", encoding=encoding, newline="") as f:
            f.write(data)

# Утиліта: прибрати BOM з початку рядка/блоку
def _strip_bom(s: str) -> str:
    return s.lstrip("\ufeff")

# Парсер diff
def parse_simple_diff(diff_path: str) -> List[Rule]:
    try:
        with open(diff_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except UnicodeDecodeError:
        with open(diff_path, "r", encoding="cp1251") as f:
            lines = f.read().splitlines()

    def is_hdr(s: str) -> bool:
        # Підтримуємо unified і context diff заголовки
        return s.startswith((
            "diff --git", "--- ", "+++ ",
            "*** ", "***************",      # context diff
            "Index:", "rename from ", "rename to "
        ))

    rules: List[Rule] = []
    i, idx = 0, 1
    while i < len(lines):
        s = lines[i]

        # Ханк з контекстом
        if s.startswith("@@"):
            i += 1
            old_buf: List[str] = []
            new_buf: List[str] = []
            while i < len(lines) and not lines[i].startswith("@@") and not is_hdr(lines[i]):
                t = lines[i]
                if t.startswith(" "):
                    p = t[1:]
                    old_buf.append(p); new_buf.append(p); i += 1; continue
                if t.startswith("-") and not t.startswith("---"):
                    pm = t[1:]
                    # злиття однакових -/+ у контекст
                    if i + 1 < len(lines) and lines[i+1].startswith("+") and lines[i+1][1:] == pm:
                        old_buf.append(pm); new_buf.append(pm); i += 2; continue
                    old_buf.append(pm); i += 1; continue
                if t.startswith("+") and not t.startswith("+++"):
                    new_buf.append(t[1:]); i += 1; continue
                # службові рядки типу "\ No newline at end of file"
                i += 1
            old_txt = _strip_bom("\n".join(old_buf))
            new_txt = _strip_bom("\n".join(new_buf))
            rules.append(Rule(find=old_txt, replace=new_txt, idx=idx))
            idx += 1
            continue

        # Заголовки
        if is_hdr(s):
            i += 1
            continue

        # Фолбек: група '-' [контекст] '+'
        if s.startswith("-") and not s.startswith("---"):
            old_block: List[str] = []
            while i < len(lines) and lines[i].startswith("-") and not lines[i].startswith("---"):
                old_block.append(lines[i][1:]); i += 1
            k = i
            while k < len(lines) and lines[k].startswith(" ") and not lines[k].startswith(("---", "+++", "@@")):
                k += 1
            new_block: List[str] = []
            while k < len(lines) and lines[k].startswith("+") and not lines[k].startswith("+++"):
                new_block.append(lines[k][1:]); k += 1
            old_txt = _strip_bom("\n".join(old_block))
            new_txt = _strip_bom("\n".join(new_block))
            rules.append(Rule(find=old_txt, replace=new_txt, idx=idx))
            idx += 1
            i = k
            continue

        # Чисті вставки без якоря
        if s.startswith("+") and not s.startswith("+++"):
            new_block: List[str] = []
            while i < len(lines) and lines[i].startswith("+") and not lines[i].startswith("+++"):
                new_block.append(lines[i][1:]); i += 1
            rules.append(Rule(find="", replace=_strip_bom("\n".join(new_block)), idx=idx))
            idx += 1
            continue

        i += 1

    if not rules:
        raise ValueError("Diff-файл не містить застосовних правил.")
    return rules

# Застосування правил
def _normalize(s: str, case_insensitive: bool, normalize_ws: bool) -> str:
    if normalize_ws:
        s = re.sub(r"\s+", " ", s)
    return s.lower() if case_insensitive else s

def _ws_tolerant_pattern(s: str) -> str:
    esc = re.escape(s)
    # Спершу зберігаємо межі рядків як обов'язковий перенос з опційними відступами
    esc = re.sub(r"(?:\\r\\n|\\n|\\r)", r"[ \t]*\r?\n[ \t]*", esc)
    # Усередині рядка дозволяємо групи пробілів/табів
    esc = re.sub(r"(?:\\t)+", r"[ \t]+", esc)
    esc = re.sub(r"(?:\\ )+", r"[ \t]+", esc)
    return esc

def _block_pattern_allow_ignored(s: str) -> str:
    """Побудувати regex, що дозволяє довільну кількість "ігнорованих" рядків
    між рядками шаблону s. Не видаляє їх з файлу. Застосовується лише для пошуку.
    """
    parts = s.splitlines()
    if not parts:
        return ""
    esc = [re.escape(p) for p in parts]
    # Роздільник між рядками: перенос рядка з опційними відступами та нуль/багато
    # ігнорованих рядків між ними
    sep = r"[ \t]*\r?\n(?:[ \t]*|(?:" + _IGNORE_RE.pattern + r")\r?\n[ \t]*)*"
    return sep.join(esc)

def _find_block_indices_with_ignored(lines: List[str], old_lines: List[str]) -> Optional[Tuple[int, int, List[int]]]:
    """
    Знаходимо послідовність old_lines у lines, дозволяючи довільну кількість
    ігнорованих рядків між ними. Повертаємо:
      (start_idx, end_idx, matched_idxs)
    де matched_idxs — індекси саме співпадінь для "неігнорованих" рядків old_lines.
    """
    if not old_lines:
        return None
    n = len(lines)
    j = 0  # індекс у old_lines
    matched = []
    start_idx = -1
    for i in range(n):
        ln = lines[i]
        if _is_ignored_line(ln):
            continue
        if j < len(old_lines) and ln == old_lines[j]:
            matched.append(i)
            if start_idx == -1:
                start_idx = i
            j += 1
            if j == len(old_lines):
                end_idx = i
                return start_idx, end_idx, matched
    return None

def _replace_block_preserving_ignored(text: str, old: str, new: str) -> Tuple[str, int]:
    """
    Локалізуємо блок old у тексті по-рядково, дозволяючи ігноровані рядки між
    відповідностями, і замінюємо ТІЛЬКИ знайдені "неігноровані" рядки old на new.
    Всі рядки, що відповідають _is_ignored_line, залишаються на місці.
    """
    lines = text.splitlines()
    old_lines = old.splitlines()
    res = _find_block_indices_with_ignored(lines, old_lines)
    if not res:
        return text, 0
    s, e, matched_idxs = res
    # Збираємо ігноровані рядки всередині діапазону [s, e], щоб зберегти їх позиції
    inner_ignored: List[Tuple[int, str]] = []
    for i in range(s, e + 1):
        if _is_ignored_line(lines[i]) and i not in matched_idxs:
            inner_ignored.append((i, lines[i]))
    # Видаляємо лише matched_idxs (старі неігноровані рядки)
    to_delete = set(matched_idxs)
    kept_segment = [ln for i, ln in enumerate(lines[s:e+1]) if (s + i) not in to_delete]
    # Нова вставка: new + збережені ігноровані рядки у їх первинних позиціях відносно s
    new_block_lines = new.splitlines()
    # Базово вставляємо new у позицію першого збігу
    merged_segment = new_block_lines[:]
    # Після цього повертаємо ігноровані рядки у їх вихідні місця, зсув рахуємо від s
    # Якщо позиція більша за довжину merged_segment — додаємо в кінець.
    for i, ln in inner_ignored:
        rel = i - s
        if 0 <= rel <= len(merged_segment):
            merged_segment.insert(rel, ln)
        else:
            merged_segment.append(ln)
    new_lines = lines[:s] + merged_segment + lines[e+1:]
    return "\n".join(new_lines), 1

def _block_find_and_replace(txt: str, old: str, new: str,
                            case_insensitive: bool, normalize_ws: bool) -> Tuple[str, int]:
    if not old:
        return txt, 0
    # 1) Точний збіг
    i = txt.find(old)
    if i != -1:
        return txt[:i] + new + txt[i + len(old):], 1
    # 2) Пробіло-толерантний шаблон (fallback навіть коли normalize_ws=False)
    pat = _ws_tolerant_pattern(old)
    flags = re.DOTALL | re.MULTILINE | (re.IGNORECASE if case_insensitive else 0)
    m = re.search(pat, txt, flags)
    if m:
        return txt[:m.start()] + new + txt[m.end():], 1
    # 3) Дозволити "ігноровані" рядки між рядками блоку, зберігаючи їх під час заміни
    txt_pres, n_pres = _replace_block_preserving_ignored(txt, old, new)
    if n_pres:
        return txt_pres, n_pres
    # 3) Ще одна спроба: case-insensitive exact (коли просять)
    if case_insensitive:
        low_txt, low_old = txt.lower(), old.lower()
        j = low_txt.find(low_old)
        if j != -1:
            return txt[:j] + new + txt[j + len(old):], 1
    return txt, 0

def apply_rules_to_text(
    text_unix: str,
    rules: List[Rule],
    mode: str,
    case_insensitive: bool = False,
    normalize_ws: bool = False,
    fuzzy_threshold: float = 0.82,
) -> Tuple[str, ApplyStats, List[str]]:
    logs: List[str] = []
    stats = ApplyStats()

    def prep(s: str) -> str:
        return _normalize(s, case_insensitive, normalize_ws)

    # ---- Швидке індексування рядків для exact/fuzzy(line) ----
    # Оновлюється після кожної успішної заміни.
    def make_line_views(t: str):
        ls = t.splitlines()
        pls = [prep(x) for x in ls]
        idx_map = {}
        for i, key in enumerate(pls):
            # перше входження достатньо для наших одноразових замін
            if key not in idx_map:
                idx_map[key] = i
        return ls, pls, idx_map

    lines_cache = None  # tuple: (lines, prepped_lines, index_map)
    def ensure_cache():
        nonlocal lines_cache
        if lines_cache is None:
            lines_cache = make_line_views(txt)

    if mode == "regex":
        txt = text_unix
        total = 0
        for r in rules:
            if not r.find:
                logs.append(f"[#{r.idx}] regex: порожній шаблон — пропущено")
                stats.missing += 1
                continue
            flags = (re.IGNORECASE | re.DOTALL) if case_insensitive else re.DOTALL
            try:
                pat = re.compile(r.find, flags)
            except re.error as e:
                logs.append(f"[#{r.idx}] regex помилка: {e}")
                stats.missing += 1
                continue
            txt_new, n = pat.subn(r.replace, txt, count=1)
            if n:
                logs.append(f"[#{r.idx}] regex: замінено 1 блок")
                total += 1
                txt = txt_new
            else:
                logs.append(f"[#{r.idx}] regex: збігів немає")
                stats.missing += 1
        stats.replaced += total
        return txt, stats, logs

    txt = text_unix
    for r in rules:
        # Блок
        if ("\n" in r.find) or ("\n" in r.replace) or r.find:
            if r.find:
                txt_new, n = _block_find_and_replace(txt, r.find, r.replace, case_insensitive, normalize_ws)
                if n:
                    txt = txt_new
                    stats.replaced += 1
                    logs.append(f"[#{r.idx}] exact(block): замінено 1 блок")
                else:
                    # Додатковий fallback: пробіло-толерантний пошук навіть якщо normalize_ws=False
                    txt_new2, n2 = _block_find_and_replace(txt, r.find, r.replace, case_insensitive, True)
                    if n2:
                        txt = txt_new2
                        stats.replaced += 1
                        logs.append(f"[#{r.idx}] exact(block-ws): замінено 1 блок")
                    else:
                        stats.missing += 1
                        logs.append(f"[#{r.idx}] exact(block): збігів немає")
            else:
                stats.missing += 1
                logs.append(f"[#{r.idx}] вставка без якоря: пропущено")
            continue

        # Рядок, замінюємо лише перше входження
        lines = txt.splitlines()
        old_cmp = prep(r.find)
        replaced_here = 0
        for k, ln in enumerate(lines):
            if _is_ignored_line(ln):
                continue
            if prep(ln) == old_cmp:
                # якщо у підстановці кілька рядків — розгортаємо їх у список
                if "\n" in r.replace:
                    new_lines = r.replace.splitlines()
                    lines = lines[:k] + new_lines + lines[k+1:]
                else:
                    lines[k] = r.replace
                replaced_here = 1
                break
        if replaced_here:
            txt = "\n".join(lines)
            stats.replaced += 1
            logs.append(f"[#{r.idx}] exact(line): замінено 1 рядок")
        else:
            if mode == "fuzzy":
                best_k, best_ratio = -1, 0.0
                for k, ln in enumerate(lines):
                    if _is_ignored_line(ln):
                        continue
                    ratio = SequenceMatcher(None, old_cmp, prep(ln)).ratio()
                    if ratio > best_ratio:
                        best_ratio, best_k = ratio, k
                if best_k >= 0 and best_ratio >= fuzzy_threshold:
                    lines[best_k] = r.replace
                    txt = "\n".join(lines)
                    stats.fuzzy_replaced += 1
                    logs.append(f"[#{r.idx}] fuzzy(line): рядок {best_k+1}, ratio={best_ratio:.2f}")
                else:
                    stats.missing += 1
                    logs.append(f"[#{r.idx}] fuzzy(line): не знайдено (max={best_ratio:.2f})")

    return txt, stats, logs

# Unified diff
def build_unified_diff(before_text_unix: str, after_text_unix: str, fromfile: str, tofile: str, context: int = 3) -> str:
    a = before_text_unix.splitlines()
    b = after_text_unix.splitlines()
    lines = list(unified_diff(a, b, fromfile=fromfile, tofile=tofile, n=context, lineterm=""))
    return "\n".join(lines) + ("\n" if lines else "")

# GUI
class SmartPatchGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Smart Patch GUI")
        self.geometry("820x640")
        self.minsize(780, 560)

        self.diff_path = tk.StringVar()
        self.target_path = tk.StringVar()
        self.write_enabled = tk.BooleanVar(value=False)
        self.dry_run = tk.BooleanVar(value=True)
        self.backup = tk.BooleanVar(value=False)
        self.log_to_file = tk.BooleanVar(value=False)
        self.log_path = tk.StringVar(value="")
        self.search_mode = tk.StringVar(value="fuzzy")
        self.case_insensitive = tk.BooleanVar(value=False)
        self.normalize_ws = tk.BooleanVar(value=False)
        self.fuzzy_threshold = tk.DoubleVar(value=0.82)

        self._unified_diff_cache: str = ""
        self._last_stats: Optional[ApplyStats] = None

        self._build_ui()
        self._bind_events()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 6}

        frm_files = ttk.LabelFrame(self, text="Файли")
        frm_files.pack(fill="x", **pad)
        row = ttk.Frame(frm_files); row.pack(fill="x", padx=8, pady=6)
        ttk.Label(row, text="Diff:").pack(side="left")
        ttk.Entry(row, textvariable=self.diff_path, width=70).pack(side="left", padx=6)
        ttk.Button(row, text="Обрати…", command=self._choose_diff).pack(side="left")

        row2 = ttk.Frame(frm_files); row2.pack(fill="x", padx=8, pady=6)
        ttk.Label(row2, text="Цільовий файл:").pack(side="left")
        ttk.Entry(row2, textvariable=self.target_path, width=64).pack(side="left", padx=6)
        ttk.Button(row2, text="Обрати…", command=self._choose_target).pack(side="left")

        frm_opts = ttk.LabelFrame(self, text="Опції")
        frm_opts.pack(fill="x", **pad)
        opt1 = ttk.Frame(frm_opts); opt1.pack(fill="x", padx=8, pady=4)
        self.chk_write = ttk.Checkbutton(opt1, text="Запис", variable=self.write_enabled); self.chk_write.pack(side="left")
        ttk.Checkbutton(opt1, text="Перевірка без запису (dry-run)", variable=self.dry_run, command=self._on_toggle_dryrun).pack(side="left", padx=12)
        self.chk_backup = ttk.Checkbutton(opt1, text="Бекап (*.bak)", variable=self.backup); self.chk_backup.pack(side="left", padx=12)

        opt2 = ttk.Frame(frm_opts); opt2.pack(fill="x", padx=8, pady=4)
        ttk.Checkbutton(opt2, text="Запис логу у файл", variable=self.log_to_file, command=self._on_toggle_logfile).pack(side="left")
        ttk.Entry(opt2, textvariable=self.log_path, width=48).pack(side="left", padx=6)
        self.btn_choose_log = ttk.Button(opt2, text="Обрати лог…", command=self._choose_log); self.btn_choose_log.pack(side="left")

        opt3 = ttk.Frame(frm_opts); opt3.pack(fill="x", padx=8, pady=4)
        ttk.Label(opt3, text="Режим пошуку:").pack(side="left")
        for val, label in (
            ("exact", "Exact (точна)"),
            ("regex", "Regex (регулярний вираз)"),
            ("fuzzy", "Fuzzy (нечітка)"),
        ):
            ttk.Radiobutton(opt3, text=label, value=val, variable=self.search_mode).pack(side="left", padx=8)

        opt4 = ttk.Frame(frm_opts); opt4.pack(fill="x", padx=8, pady=4)
        ttk.Checkbutton(opt4, text="Ігнорувати регістр", variable=self.case_insensitive).pack(side="left")
        ttk.Checkbutton(opt4, text="Нормалізувати пробіли", variable=self.normalize_ws).pack(side="left")
        ttk.Label(opt4, text="Поріг fuzzy:").pack(side="left", padx=(16,4))
        ttk.Spinbox(opt4, from_=0.5, to=0.99, increment=0.01, textvariable=self.fuzzy_threshold, width=6).pack(side="left")

        frm_actions = ttk.Frame(self)
        frm_actions.pack(fill="x", **pad)
        self.btn_apply = ttk.Button(frm_actions, text="Застосувати", command=self._apply, state="disabled"); self.btn_apply.pack(side="left")
        self.btn_save_udiff = ttk.Button(frm_actions, text="Зберегти unified diff…", command=self._save_unified_diff, state="disabled"); self.btn_save_udiff.pack(side="left", padx=8)

        frm_out = ttk.LabelFrame(self, text="Вивід")
        frm_out.pack(fill="both", expand=True, **pad)
        self.txt_log = tk.Text(frm_out, wrap="none", height=18)
        self.txt_log.pack(fill="both", expand=True, padx=6, pady=6)
        yscroll = ttk.Scrollbar(self.txt_log.master, orient="vertical", command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=yscroll.set); yscroll.place(relx=1.0, rely=0, relheight=1.0, anchor="ne")
        self.txt_log.bind("<Control-c>", lambda e: self.txt_log.event_generate("<<Copy>>"))
        self.txt_log.bind("<ButtonRelease-1>", self._auto_copy_selected)
        self.txt_log.bind("<KeyRelease>", self._auto_copy_selected)

        self.status = tk.StringVar(value="Готово")
        frm_status = ttk.Frame(self)
        frm_status.pack(fill="x")
        ttk.Label(frm_status, textvariable=self.status, anchor="w").pack(fill="x", padx=8, pady=4)

        self._on_toggle_dryrun()
        self._on_toggle_logfile()
        self._refresh_apply_state()

    def _bind_events(self):
        self.diff_path.trace_add("write", lambda *_: self._refresh_apply_state())
        self.target_path.trace_add("write", lambda *_: self._refresh_apply_state())

    # Діалоги
    def _choose_diff(self):
        path = filedialog.askopenfilename(title="Обрати diff-файл", filetypes=[("Diff files","*.diff *.patch *.txt"), ("All files","*.*")])
        if path:
            self.diff_path.set(path)

    def _choose_target(self):
        path = filedialog.askopenfilename(title="Обрати цільовий файл", filetypes=[("Text files","*.py *.txt *.cfg *.ini *.*"), ("All files","*.*")])
        if path:
            self.target_path.set(path)
            if not self.log_path.get():
                self.log_path.set(path + ".patch.log.txt")

    def _choose_log(self):
        path = filedialog.asksaveasfilename(title="Куди зберегти лог", defaultextension=".txt", filetypes=[("Text log","*.txt"), ("All files","*.*")])
        if path:
            self.log_path.set(path)

    # Стан UI
    def _refresh_apply_state(self):
        ok = bool(self.diff_path.get().strip()) and bool(self.target_path.get().strip())
        self.btn_apply.config(state="normal" if ok else "disabled")

    def _on_toggle_dryrun(self):
        if self.dry_run.get():
            self.chk_write.state(["disabled"])
            self.chk_backup.state(["disabled"])
        else:
            self.chk_write.state(["!disabled"])
            self.chk_backup.state(["!disabled"])

    def _on_toggle_logfile(self):
        self.btn_choose_log.config(state=("normal" if self.log_to_file.get() else "disabled"))

    # Лог
    def _log(self, line: str):
        ts = datetime.now().isoformat(timespec="seconds")
        self.txt_log.insert("end", f"[{ts}] {line}\n")
        self.txt_log.see("end")

    def _auto_copy_selected(self, _evt=None):
        try:
            if self.txt_log.tag_ranges("sel"):
                sel = self.txt_log.get("sel.first", "sel.last")
                if sel:
                    self.clipboard_clear()
                    self.clipboard_append(sel)
        except tk.TclError:
            pass

    # Основна дія
    def _apply(self):
        diff_path = self.diff_path.get().strip()
        target_path = self.target_path.get().strip()
        if not os.path.isfile(diff_path):
            messagebox.showerror("Помилка", "Diff-файл не знайдено.")
            return
        if not os.path.isfile(target_path):
            messagebox.showerror("Помилка", "Цільовий файл не знайдено.")
            return

        self.txt_log.delete("1.0", "end")
        self.status.set("Працюю…")
        self._unified_diff_cache = ""
        self._last_stats = None

        try:
            text0, enc, had_bom, nl = _try_read_text(target_path, forced_encoding=None)
            rules = parse_simple_diff(diff_path)
        except Exception as e:
            self._log(f"ПОМИЛКА: {e}")
            self.status.set("Помилка")
            messagebox.showerror("Помилка", str(e))
            return

        mode = self.search_mode.get()
        case_ins = self.case_insensitive.get()
        norm_ws = self.normalize_ws.get()
        fuzzy_thr = float(self.fuzzy_threshold.get())

        text1, stats, logs = apply_rules_to_text(
            text_unix=text0, rules=rules, mode=mode,
            case_insensitive=case_ins, normalize_ws=norm_ws, fuzzy_threshold=fuzzy_thr,
        )

        for ln in logs:
            self._log(ln)
        self._log(f"Σ exact/regex: {stats.replaced}, fuzzy: {stats.fuzzy_replaced}, missing: {stats.missing}")

        udiff = build_unified_diff(text0, text1, fromfile=target_path, tofile=target_path)
        self._unified_diff_cache = udiff
        self.btn_save_udiff.config(state=("normal" if udiff.strip() else "disabled"))
        self._log("Unified diff згенеровано." if udiff.strip() else "Unified diff порожній (змін немає).")

        if not self.dry_run.get() and self.write_enabled.get():
            try:
                if self.backup.get():
                    shutil.copyfile(target_path, target_path + ".bak")
                    self._log(f"Backup створено → {target_path}.bak")
                _write_text_preserve(target_path, text1, enc, had_bom, nl)
                self._log(f"Файл оновлено → {target_path}")
                self.status.set("Файл оновлено")
            except Exception as e:
                self._log(f"ПОМИЛКА запису: {e}")
                self.status.set("Помилка запису")
                messagebox.showerror("Помилка запису", str(e))
                return
        else:
            self.status.set("Dry-run завершено")

        if self.log_to_file.get():
            try:
                log_path = self.log_path.get().strip() or (target_path + ".patch.log.txt")
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write(self.txt_log.get("1.0", "end"))
                self._log(f"Лог збережено → {log_path}")
            except Exception as e:
                self._log(f"ПОМИЛКА запису логу: {e}")

        self._last_stats = stats

    # Збереження unified diff
    def _save_unified_diff(self):
        if not self._unified_diff_cache:
            messagebox.showinfo("Інфо", "Немає diff для збереження.")
            return
        path = filedialog.asksaveasfilename(title="Зберегти unified diff", defaultextension=".patch",
                                            filetypes=[("Patch/Diff","*.patch *.diff"), ("All files","*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._unified_diff_cache)
            self._log(f"Unified diff збережено → {path}")
        except Exception as e:
            self._log(f"ПОМИЛКА збереження unified diff: {e}")
            messagebox.showerror("Помилка", str(e))

if __name__ == "__main__":
    app = SmartPatchGUI()
    app.mainloop()
