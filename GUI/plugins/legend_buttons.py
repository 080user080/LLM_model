# Плагін: кнопки для роботи з легендою (переніс логіки з GUI.py)
def _clear_legend(app):
    try:
        app.txt_legend.delete("1.0", "end")
        try:
            app._set_status("Легенду очищено")
        except Exception:
            pass
        try:
            app._rebuild_tags()
        except Exception:
            pass
    except Exception:
        pass

def _paste_legend(app):
    try:
        text = app.clipboard_get()
    except Exception:
        text = ""
    if text:
        try:
            app.txt_legend.delete("1.0", "end")
            app.txt_legend.insert("1.0", text)
            try:
                app._set_status("Легенду вставлено")
            except Exception:
                pass
            try:
                app._rebuild_tags()
            except Exception:
                pass
        except Exception:
            pass

def _load_legend_file(app):
    try:
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(title="Обрати файл легенди", filetypes=[("Текстові файли", "*.txt"), ("Усі файли", "*.*")])
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        app.txt_legend.delete("1.0", "end")
        app.txt_legend.insert("1.0", text)
        try:
            app._set_status(f"Легенда завантажена: {path.split('/')[-1]}")
        except Exception:
            pass
        try:
            app._rebuild_tags()
        except Exception:
            pass
    except Exception as e:
        try:
            from tkinter import messagebox
            messagebox.showerror("Помилка читання", str(e))
        except Exception:
            pass

def register(app, buttons_frame, content_frame):
    try:
        from tkinter import ttk
        for label, cb in [
            ("Очистити легенду", _clear_legend),
            ("Вставити легенду", _paste_legend),
            ("Завантажити легенду з файлу", _load_legend_file),
        ]:
            btn = ttk.Button(buttons_frame, text=label, command=lambda cb=cb: cb(app))
            btn.pack(fill="x", pady=4)
    except Exception:
        # якщо UI недоступний — пропускаємо
        pass