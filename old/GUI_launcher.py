import tkinter as tk
from tkinter import messagebox
import pkgutil
import importlib
import traceback
import os
import sys
import logging

# Налаштування логів
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Якщо папка GUI знаходиться в корені репозиторію поруч з цим файлом,
# переконаємось, що вона в sys.path як пакет
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

PLUGINS_PACKAGE = "GUI"  # назва папки-пакету з плагінами

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LLM_model — GUI (plugin loader)")
        self.geometry("600x400")

        # Верхня панель для кнопок, можна змінити під ваш UI
        self.buttons_frame = tk.Frame(self)
        self.buttons_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

        # Місце для логів / віджети які додають плагіни
        self.content_frame = tk.Frame(self)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Завантажуємо і реєструємо плагіни
        self.load_plugins()

    def load_plugins(self):
        # Просканувати пакет PLUGINS_PACKAGE і імпортувати модулі
        try:
            package = importlib.import_module(PLUGINS_PACKAGE)
        except Exception as e:
            logger.warning("Не вдалося імпортувати пакет %s: %s", PLUGINS_PACKAGE, e)
            return

        pkg_path = getattr(package, "__path__", None)
        if not pkg_path:
            logger.info("Пакет %s не має __path__ — нема плагінів", PLUGINS_PACKAGE)
            return

        for finder, name, ispkg in pkgutil.iter_modules(pkg_path):
            # ігноруємо __init__ та приватні модулі (починаються з _)
            if name.startswith("_"):
                continue
            full_name = f"{PLUGINS_PACKAGE}.{name}"
            try:
                module = importlib.import_module(full_name)
                logger.info("Імпортовано плагін: %s", full_name)
            except Exception:
                logger.error("Помилка при імпорті плагіну %s:\n%s", full_name, traceback.format_exc())
                continue

            # Підтримуємо два варіанти API: register(root, buttons_frame, content_frame)
            # або get_buttons() -> список структур
            try:
                if hasattr(module, "register"):
                    # register може приймати (app, buttons_frame, content_frame)
                    try:
                        module.register(self, self.buttons_frame, self.content_frame)
                        logger.info("Зареєстровано плагін через register(): %s", full_name)
                    except TypeError:
                        # менш явний виклик register(buttons_frame)
                        module.register(self.buttons_frame)
                        logger.info("Зареєстровано плагін через register(buttons_frame): %s", full_name)
                elif hasattr(module, "get_buttons"):
                    btns = module.get_buttons()
                    self._install_buttons_from_list(btns)
                    logger.info("Зареєстровано плагін через get_buttons(): %s", full_name)
                else:
                    logger.info("Плагін %s не містить register/get_buttons — пропуск", full_name)
            except Exception:
                logger.error("Помилка при реєстрації плагіна %s:\n%s", full_name, traceback.format_exc())

    def _install_buttons_from_list(self, buttons):
        # Очікуємо список dict {'label': str, 'callback': callable, 'tooltip': str (opt)}
        for b in buttons:
            label = b.get("label", "Unnamed")
            callback = b.get("callback")
            if not callable(callback):
                logger.warning("Callback для кнопки %s не callable — пропуск", label)
                continue
            btn = tk.Button(self.buttons_frame, text=label, command=lambda cb=callback: self._safe_call(cb))
            btn.pack(side=tk.LEFT, padx=4)
            # tooltip можна реалізувати окремо при потребі

    def _safe_call(self, cb):
        try:
            cb(self)  # передаємо app (або нічого — як в плагіні)
        except TypeError:
            try:
                cb()
            except Exception:
                logger.error("Помилка у callback:\n%s", traceback.format_exc())
        except Exception:
            logger.error("Помилка у callback:\n%s", traceback.format_exc())
            messagebox.showerror("Error", "Помилка під час виконання операції. Подивіться лог.")

if __name__ == "__main__":
    app = App()
    app.mainloop()