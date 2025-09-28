# gui.py
#GPT: Темна GUI-оболонка для розстановки діалогів. Логіка у logic.py
#GPT: Зведений лог без фризів. Виправлено: додано _clear_legend/_paste_legend/_load_legend_file.

import os
import threading
import queue
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Спроба підключити зовнішню логіку.
# На початку намагаємося завантажити удосконалену версію `improved_logic`.
# Якщо вона відсутня або викликає помилку – використовуємо штатний `logic`.
# Використовуємо абсолютний імпорт, щоб працювало як при запуску всередині пакету,
# так і при прямому запуску файлу GUI.py. Relative imports (.improved_logic) не
# працюють, якщо __package__ дорівнює None.
try:
    import improved_logic as logic  # type: ignore
    LOGIC_AVAILABLE = True
except Exception:
    try:
        import logic as logic  # noqa: F401
        LOGIC_AVAILABLE = True
    except Exception:
        logic = None  # type: ignore
        LOGIC_AVAILABLE = False

# --------------------- Константи оформлення --------------------- #GPT
BG = "#1e1e1e"
PANEL = "#252526"
FG = "#e6e6e6"
ACCENT = "#3a96dd"
ENTRY_BG = "#2b2b2b"
ENTRY_FG = FG
FONT = ("Segoe UI", 10)

# Файли за замовчуванням (мають узгоджуватися з logic.py)
DEF_INPUT = "Dialog_test.txt"
DEF_OUTPUT = "Dialog_dialogues.txt"
DEF_LEGEND = "Legenda_test.txt"

# --------------------- Головний клас GUI ------------------------ #GPT
class DialogGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Розпізнавання діалогів → підготовка до TTS")
        self.geometry("1200x820")
        self.configure(bg=BG)
        self.minsize(960, 700)

        # Черга коротких лог-подій для статусу
        self.log_q = queue.Queue()
        self._working = False  # індикатор тривалого завдання
        self._status_tick = 0

        self._build_style()
        self._build_layout()
        self._bind_shortcuts()

        # Таймер періодичного зчитування коротких подій
        self.after(120, self._drain_logs)

        # Завжди підтягуємо дефолтні файли (перемикач видалено)
        self._load_defaults()

    # ----------------- Стиль ----------------- #GPT
    def _build_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=FG, font=FONT)
        style.configure("Small.TLabel", background=BG, foreground="#bbbbbb", font=("Segoe UI", 9))
        style.configure("TButton", font=FONT, padding=6)
        style.map("TButton", background=[("active", ACCENT)], foreground=[("active", "#ffffff")])
        style.configure("TEntry", fieldbackground=ENTRY_BG, foreground=ENTRY_FG)
        style.configure("TLabelframe", background=BG, foreground=FG, font=("Segoe UI Semibold", 10))
        style.configure("TLabelframe.Label", background=BG, foreground=FG)

    # ----------------- Розмітка ----------------- #GPT
    def _build_layout(self):
        top = ttk.Frame(self, style="Panel.TFrame")
        top.pack(fill="x", padx=10, pady=10)

        # Вхідний файл
        ttk.Label(top, text="Вхідний .txt:").grid(row=0, column=0, padx=8, pady=8, sticky="w")
        self.in_path = tk.StringVar()
        self.e_in = ttk.Entry(top, textvariable=self.in_path, width=90)
        self._paint_entry(self.e_in)
        self.e_in.grid(row=0, column=1, padx=8, pady=8, sticky="we")
        ttk.Button(top, text="Обрати…", command=self._choose_input).grid(row=0, column=2, padx=8, pady=8)

        # Вихідний файл
        ttk.Label(top, text="Вивід (.txt):").grid(row=1, column=0, padx=8, pady=8, sticky="w")
        self.out_path = tk.StringVar()
        self.e_out = ttk.Entry(top, textvariable=self.out_path, width=90)
        self._paint_entry(self.e_out)
        self.e_out.grid(row=1, column=1, padx=8, pady=8, sticky="we")
        ttk.Button(top, text="Зберегти як…", command=self._choose_output).grid(row=1, column=2, padx=8, pady=8)

        top.columnconfigure(1, weight=1)

        # Середня зона: Легенда + Кнопки
        mid = ttk.Frame(self)
        mid.pack(fill="x", padx=10, pady=(0, 10))

        legend_frame = ttk.Labelframe(mid, text="Легенда #g1…#g30")
        legend_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.txt_legend = self._make_text(legend_frame, height=10)
        self.txt_legend.pack(fill="both", expand=True, padx=8, pady=8)

        btns = ttk.Frame(mid)
        btns.pack(side="left", fill="y")
        self.btn_run = ttk.Button(btns, text="▶ Запустити обробку", command=self._run_processing)
        self.btn_run.pack(fill="x", pady=(0, 8))
        self.btn_clear_legend = ttk.Button(btns, text="Очистити легенду", command=self._clear_legend)
        self.btn_clear_legend.pack(fill="x", pady=4)
        self.btn_paste_legend = ttk.Button(btns, text="Вставити легенду", command=self._paste_legend)
        self.btn_paste_legend.pack(fill="x", pady=4)
        self.btn_load_legend = ttk.Button(btns, text="Завантажити легенду з файлу", command=self._load_legend_file)
        self.btn_load_legend.pack(fill="x", pady=4)

        # Нижня зона: Зведений лог та Вихідний текст
        bottom = ttk.Frame(self)
        bottom.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        log_frame = ttk.Labelframe(bottom, text="Зведений лог")
        out_frame = ttk.Labelframe(bottom, text="Оброблений текст")
        log_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        out_frame.pack(side="left", fill="both", expand=True)

        self.txt_log = self._make_text(log_frame, height=18, undo=False, wrap_mode="word")
        self.txt_log.pack(fill="both", expand=True, padx=8, pady=8)

        self.txt_output = self._make_text(out_frame, height=18, undo=False, wrap_mode="word")
        self.txt_output.pack(fill="both", expand=True, padx=8, pady=8)

        # Статусбар
        self.status = ttk.Label(self, text="Готово", style="Small.TLabel", anchor="w")
        self.status.pack(fill="x", padx=12, pady=(0, 8))

    # ----------------- Віджети-помічники ----------------- #GPT
    def _make_text(self, parent, height=10, undo=True, wrap_mode="word"):
        txt = tk.Text(parent, height=height, bg=ENTRY_BG, fg=ENTRY_FG,
                      insertbackground=FG, undo=undo, maxundo=-1,
                      wrap=wrap_mode, font=FONT, relief="flat")
        y = ttk.Scrollbar(parent, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=y.set)
        y.pack(side="right", fill="y")

        txt.bind("<Control-c>", lambda e: self._ctrl(e, "copy"))
        txt.bind("<Control-v>", lambda e: self._ctrl(e, "paste"))
        txt.bind("<Control-x>", lambda e: self._ctrl(e, "cut"))
        txt.bind("<Control-a>", lambda e: self._ctrl(e, "selall"))

        self._add_context_menu(txt)
        return txt

    def _paint_entry(self, entry: ttk.Entry):
        entry.bind("<Control-a>", lambda e: (entry.select_range(0, "end"), "break"))
        self._add_context_menu(entry, is_entry=True)

    def _add_context_menu(self, widget, is_entry=False):
        menu = tk.Menu(widget, tearoff=0, bg=PANEL, fg=FG,
                       activebackground=ACCENT, activeforeground="white")
        menu.add_command(label="Копіювати", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="Вставити", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_command(label="Вирізати", command=lambda: widget.event_generate("<<Cut>>"))
        menu.add_separator()
        if is_entry:
            menu.add_command(label="Виділити все", command=lambda: widget.select_range(0, "end"))
        else:
            menu.add_command(label="Виділити все", command=lambda: widget.tag_add("sel", "1.0", "end-1c"))

        def popup(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        widget.bind("<Button-3>", popup)

    # ----------------- Події та дії ----------------- #GPT
    def _choose_input(self):
        path = filedialog.askopenfilename(
            title="Обрати вхідний TXT",
            filetypes=[("Текстові файли", "*.txt"), ("Усі файли", "*.*")]
        )
        if path:
            self.in_path.set(path)
            base = os.path.splitext(os.path.basename(path))[0]
            if not self.out_path.get() or self.out_path.get() in ("", DEF_OUTPUT):
                self.out_path.set(f"{base}_dialogues.txt")

    def _choose_output(self):
        path = filedialog.asksaveasfilename(
            title="Куди зберегти результат",
            defaultextension=".txt",
            initialfile=self.out_path.get() or DEF_OUTPUT,
            filetypes=[("Текстові файли", ".txt")]
        )
        if path:
            self.out_path.set(path)

    def _run_processing(self):
        # Автоматично: максимум мінус один процес
        auto_workers = max(1, (os.cpu_count() or 2) - 1)

        in_path = (self.in_path.get() or "").strip()
        out_path = (self.out_path.get() or "").strip()
        legend = self.txt_legend.get("1.0", "end-1c")

        # Підставляємо дефолти, якщо порожньо
        if not in_path and os.path.exists(DEF_INPUT):
            in_path = DEF_INPUT
            self.in_path.set(in_path)
        if not out_path:
            out_path = DEF_OUTPUT
            self.out_path.set(out_path)
        if not legend and os.path.exists(DEF_LEGEND):
            try:
                with open(DEF_LEGEND, "r", encoding="utf-8") as f:
                    legend = f.read()
                    self.txt_legend.delete("1.0", "end")
                    self.txt_legend.insert("1.0", legend)
            except Exception:
                pass

        if not in_path or not os.path.isfile(in_path):
            messagebox.showerror("Помилка", "Оберіть існуючий вхідний .txt файл або покладіть DEF_INPUT поряд.")
            return
        if not out_path:
            messagebox.showerror("Помилка", "Вкажіть ім'я вихідного файлу.")
            return

        # Короткі події у лог-чергу
        self._log_q_put("Запуск")

        if not LOGIC_AVAILABLE:
            self._log_q_put("logic.py відсутній: імітація обробки…")
            self._start_worker(self._mock_process, args=(in_path, legend, out_path))
            return

        self._start_worker(self._real_process, args=(in_path, legend, out_path, auto_workers))

    def _real_process(self, in_path, legend, out_path, workers):
        # Працює у фоні
        self._log_q_put(f"Працює | процесів: {workers}")
        try:
            output_text, logs = logic.process_dialogs(in_path, legend, workers=workers)

            # Запис результату у файл
            try:
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(output_text or "")
                self._log_q_put(f"Записано: {out_path}")
            except Exception as e:
                self._log_q_put(f"Помилка запису: {e}")

            # Побудувати зведений лог і оновити UI у головному потоці
            summary = self._build_summary(output_text or "", legend or "", logs)
            self.after(0, lambda: self._set_log_summary(summary))
            self.after(0, lambda: self._set_output_text(output_text or ""))
            self.after(0, lambda: self._set_status("Завершено"))
            self._log_q_put("Завершено")
        except Exception as e:
            self._log_q_put(f"Помилка: {e}")
            self.after(0, lambda: self._set_status("Помилка"))

    def _mock_process(self, in_path, legend, out_path):
        # Демо-дані
        demo = (
            "#g2: Розповідач каже щось.\n"
            "#g3: Привіт.\n"
            "#g?: Нерозпізнано.\n"
            "#g2: Продовження.\n"
        )
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(demo)
            self._log_q_put(f"Записано: {out_path}")
        except Exception as e:
            self._log_q_put(f"Помилка запису: {e}")

        summary = self._build_summary(demo, legend or "", logs=None)
        self.after(0, lambda: self._set_log_summary(summary))
        self.after(0, lambda: self._set_output_text(demo))
        self.after(0, lambda: self._set_status("Завершено (демо)"))
        self._log_q_put("Завершено")

    # ----------------- Зведення ----------------- #GPT
    def _build_summary(self, output_text: str, legend_text: str, logs):
        # 1) Розбір легенди
        narrator_tag, narrator_name, mains = self._parse_legend(legend_text)

        # 2) Підрахунки за обробленим текстом
        lines = [ln for ln in output_text.splitlines() if ln.strip()]
        total_dialogs = 0
        unknown_dialogs = 0
        per_group = {}

        dlg_pat = re.compile(r"^\s*(#g\d+|#g\?)\s*:")
        grp_pat = re.compile(r"^\s*(#g\d+)\s*:")

        for ln in lines:
            m = dlg_pat.match(ln)
            if not m:
                continue
            total_dialogs += 1
            if m.group(1) == "#g?":
                unknown_dialogs += 1
            else:
                g = grp_pat.match(ln)
                if g:
                    tag = g.group(1)
                    per_group[tag] = per_group.get(tag, 0) + 1

        narrator_count = per_group.get(narrator_tag, 0) if narrator_tag else 0

        # 3) Підрахунок спрацювань правил за сирими логами (якщо є)
        rule_counts = {}
        raw = ""
        if isinstance(logs, str):
            raw = logs
        elif isinstance(logs, (list, tuple)):
            try:
                raw = "\n".join(str(x) for x in logs)
            except Exception:
                raw = ""
        if raw:
            # Підтримуємо кілька форматів: [RULE] name, rule=name, Rule name, Правило name
            patterns = [
                re.compile(r"\[(?:RULE|Rule|rule)\]\s*([\wА-Яа-я_\-]+)"),
                re.compile(r"\brule\s*[=:]\s*([\w_\-]+)", re.IGNORECASE),
                re.compile(r"\b(?:Rule|Правило)\s*[:\-]?\s*([\wА-Яа-я_\-]+)")
            ]
            for p in patterns:
                for name in p.findall(raw):
                    rule_counts[name] = rule_counts.get(name, 0) + 1

        # 4) Рендер зведення
        lines_out = []
        if narrator_tag:
            lines_out.append(f"Оповідач: {narrator_tag} — {narrator_name}")
        if mains:
            pretty = ", ".join([f"{t} — {n}" for t, n in mains])
            lines_out.append(f"Головні герої: {pretty}")

        lines_out.append(f"Кількість діалогів: {total_dialogs}")
        if narrator_tag:
            lines_out.append(f"Пряма мова оповідача ({narrator_tag}): {narrator_count}")
        lines_out.append(f"Нерозпізнаних (#g?): {unknown_dialogs}")

        if per_group:
            lines_out.append("Присвоєні голоси:")
            for tag, cnt in sorted(per_group.items(), key=lambda kv: (-kv[1], kv[0])):
                lines_out.append(f"  {tag} — {cnt}")

        if rule_counts:
            lines_out.append("Спрацювання правил:")
            for name, cnt in sorted(rule_counts.items(), key=lambda kv: (-kv[1], kv[0])):
                lines_out.append(f"  {name} — {cnt}")

        return "\n".join(lines_out) if lines_out else "Немає даних для зведення. Перевірте легенду та вихідний текст."

    def _parse_legend(self, legend_text: str):
        narrator_keywords = ("оповідач", "наратор", "диктор", "narrator", "voiceover")
        main_keywords = ("головн", "[main]", "(головн", "main")
        grp_line = re.compile(r"^\s*(#g\d+)\s*[:\-]\s*(.+?)\s*$", re.IGNORECASE)

        narrator_tag = None
        narrator_name = None
        mains = []  # list[(tag, name)]

        for raw in legend_text.splitlines():
            m = grp_line.match(raw)
            if not m:
                continue
            tag, name = m.group(1), m.group(2)
            low = name.lower()
            if any(k in low for k in narrator_keywords) and not narrator_tag:
                narrator_tag, narrator_name = tag, name.strip()
            if any(k in low for k in main_keywords):
                mains.append((tag, name.strip()))

        # Якщо оповідача явно не знайдено, спробуємо #g2 як звичну умовність
        if narrator_tag is None:
            for raw in legend_text.splitlines():
                m = grp_line.match(raw)
                if m and m.group(1) == "#g2":
                    narrator_tag, narrator_name = m.group(1), m.group(2).strip()
                    break

        return narrator_tag, narrator_name, mains

    # ----------------- Оновлення UI ----------------- #GPT
    def _set_log_summary(self, text: str):
        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.insert("1.0", text)
        self.txt_log.see("1.0")
        self.txt_log.configure(state="normal")

    def _start_worker(self, target, args=()):
        self.btn_run.config(state="disabled")
        self._set_busy(True)
        t = threading.Thread(target=self._wrap_worker, args=(target, args), daemon=True)
        t.start()

    def _wrap_worker(self, target, args):
        try:
            self._working = True
            target(*args)
        finally:
            self._working = False
            self.after(0, lambda: (self.btn_run.config(state="normal"), self._set_busy(False)))

    # ----------------- Кнопки легенди ----------------- #GPT
    def _clear_legend(self):
        self.txt_legend.delete("1.0", "end")
        self._set_status("Легенду очищено")

    def _paste_legend(self):
        try:
            text = self.clipboard_get()
        except Exception:
            text = ""
        if text:
            self.txt_legend.delete("1.0", "end")
            self.txt_legend.insert("1.0", text)
            self._set_status("Легенду вставлено")

    def _load_legend_file(self):
        path = filedialog.askopenfilename(
            title="Обрати файл легенди",
            filetypes=[("Текстові файли", "*.txt"), ("Усі файли", "*.*")]
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                self.txt_legend.delete("1.0", "end")
                self.txt_legend.insert("1.0", text)
                self._set_status(f"Легенда завантажена: {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("Помилка читання", str(e))

    # ----------------- Короткі події ----------------- #GPT
    def _append_log(self, line: str):
        self.txt_log.insert("end", line.rstrip() + "\n")
        self.txt_log.see("end")

    def _log_q_put(self, line: str):
        self.log_q.put(line)

    def _drain_logs(self):
        try:
            burst = []
            for _ in range(20):  # до 20 коротких повідомлень за тик
                burst.append(self.log_q.get_nowait())
        except queue.Empty:
            pass
        if burst:
            self._append_log("\n".join(burst))
        # Пульс стану під час роботи
        if self._working:
            self._status_tick = (self._status_tick + 1) % 20
            dots = (self._status_tick // 5) + 1
            self._set_status("Працює" + "." * dots)
        self.after(120, self._drain_logs)

    def _set_output_text(self, text: str):
        self.txt_output.delete("1.0", "end")
        self.txt_output.insert("1.0", text)
        self.txt_output.see("1.0")

    def _set_status(self, s: str):
        self.status.config(text=s)

    def _set_busy(self, is_busy: bool):
        try:
            self.configure(cursor="watch" if is_busy else "")
        except Exception:
            pass

    def _ctrl(self, event, what):
        w = event.widget
        try:
            if what == "copy":
                w.event_generate("<<Copy>>")
            elif what == "paste":
                w.event_generate("<<Paste>>")
            elif what == "cut":
                w.event_generate("<<Cut>>")
            elif what == "selall":
                if isinstance(w, tk.Text):
                    w.tag_add("sel", "1.0", "end-1c")
                elif isinstance(w, ttk.Entry):
                    w.select_range(0, "end")
        except Exception:
            pass
        return "break"

    def _bind_shortcuts(self):
        self.bind("<Control-s>", self._save_output_shortcut)
        self.bind("<F5>", lambda _e: self._run_processing())

    def _save_output_shortcut(self, _evt=None):
        path = self.out_path.get().strip() or DEF_OUTPUT
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.txt_output.get("1.0", "end-1c"))
            self._append_log(f"Збережено: {path}")
            self._set_status("Збережено")
        except Exception as e:
            messagebox.showerror("Помилка запису", str(e))
            self._set_status("Помилка запису")

    # ----------------- Дефолтні файли ----------------- #GPT
    def _load_defaults(self):
        if os.path.exists(DEF_INPUT):
            self.in_path.set(DEF_INPUT)
        else:
            self.in_path.set("")
        self.out_path.set(DEF_OUTPUT)
        if os.path.exists(DEF_LEGEND):
            try:
                with open(DEF_LEGEND, "r", encoding="utf-8") as f:
                    text = f.read()
                self.txt_legend.delete("1.0", "end")
                self.txt_legend.insert("1.0", text)
            except Exception:
                pass

# --------------------- Точка входу --------------------- #GPT
if __name__ == "__main__":
    app = DialogGUI()
    app.mainloop()
