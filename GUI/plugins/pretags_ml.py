# Плагін: пре-тегування + (спрощений) виклик ML, перенесено з GUI.py
import os
import re
import tempfile
import json
import sys

DASHES = "-\u2012\u2013\u2014\u2015"
IS_DLG_LINE = re.compile(rf"^\s*(?:[{re.escape(DASHES)}]|[«\"„“”'’])")

def _pretag_transform(text: str) -> str:
    out = []
    for ln in text.splitlines():
        if not ln.strip():
            out.append("")
            continue
        if IS_DLG_LINE.match(ln):
            out.append(f"#g?: {ln.strip()}")
        else:
            out.append(f"#g1: {ln.rstrip()}")
    return "\n".join(out)

def _run_zeroshot_like_original(app, out_path, legend_text):
    try:
        parsed = None
        try:
            parsed = json.loads(legend_text)
        except Exception:
            parsed = None
        lf = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".json")
        with lf:
            json.dump(parsed if parsed is not None else {}, lf, ensure_ascii=False, indent=2)
        legend_path = lf.name
    except Exception as e:
        app._log_q_put(f"Помилка підготовки легенди: {e}")
        app.after(0, lambda: app._set_status("Помилка"))
        return

    ok = False
    try:
        import zeroshot_speaker_models as zsf  # type: ignore
    except Exception:
        zsf = None
    if zsf and hasattr(zsf, "process_file"):
        try:
            zsf.process_file(input_path=out_path, legend_path=legend_path, output_path=out_path, only_unknown=True)
            ok = True
            app._log_q_put("ML_model: модульний виклик успішний (plugin)")
        except Exception as e:
            app._log_q_put(f"ML plugin call failed: {e}")

    if not ok:
        py = sys.executable or "python"
        cmd = [py, "-u", "zeroshot_speaker_models.py", "--in", out_path, "--out", out_path, "--legend", legend_path]
        try:
            import subprocess
            app._log_q_put("Запуск ML (процес) plugin: " + " ".join(cmd))
            cp = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
            if cp.returncode == 0:
                ok = True
                if cp.stdout:
                    app._log_q_put(cp.stdout.strip())
        except Exception as e:
            app._log_q_put(f"ML process failed: {e}")

    if ok:
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                new_text = f.read()
            summary = app._build_summary(new_text, legend_text, logs=None)
            app.after(0, lambda: app._set_output_text(new_text))
            app.after(0, lambda: app._set_log_summary(summary))
            app.after(0, lambda: app._set_status("Завершено (ML_model, plugin)"))
            app._log_q_put("ML_model: готово (plugin)")
        except Exception as e:
            app._log_q_put(f"Помилка читання результату: {e}")
            app.after(0, lambda: app._set_status("Помилка"))
    try:
        os.unlink(legend_path)
    except Exception:
        pass

def _pretag_then_zeroshot(app):
    try:
        in_path = (app.in_path.get() or "").strip()
        out_path = (app.out_path.get() or "").strip() or "Dialog_dialogues.txt"
        legend = app.txt_legend.get("1.0", "end-1c").strip()
        if not in_path or not os.path.isfile(in_path):
            try:
                from tkinter import messagebox
                messagebox.showerror("Помилка", "Оберіть існуючий вхідний .txt файл.")
            except Exception:
                pass
            return
        if not legend:
            try:
                from tkinter import messagebox
                messagebox.showerror("Помилка", "Легенда порожня. Вставте або завантажте легенду.")
            except Exception:
                pass
            return
        app._log_q_put("Пре-тег: старт (plugin)")
        try:
            with open(in_path, "r", encoding="utf-8") as f:
                raw = f.read()
        except Exception as e:
            app._log_q_put(f"Помилка читання: {e}")
            app._set_status("Помилка")
            return
        pre = _pretag_transform(raw)
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(pre)
            app._log_q_put(f"Записано: {out_path}")
        except Exception as e:
            app._log_q_put(f"Помилка запису: {e}")
            app._set_status("Помилка")
            return
        summary = app._build_summary(pre, legend or "", logs=None)
        app.after(0, lambda: app._set_output_text(pre))
        app.after(0, lambda: app._set_log_summary(summary))
        app.after(0, lambda: app._set_status("Пре-тег завершено (plugin)"))
        _run_zeroshot_like_original(app, out_path, legend)
    except Exception as e:
        app._log_q_put(f"Plugin error: {e}")

def register(app, buttons_frame, content_frame):
    try:
        from tkinter import ttk
        btn = ttk.Button(buttons_frame, text="Пре-тег #g1/#g? + ML (plugin)", command=lambda: _pretag_then_zeroshot(app))
        btn.pack(fill="x", pady=4)
    except Exception:
        pass