"""
Пошук і завантаження плагінів в пакеті GUI.plugins.
Плагін — модуль, що експортує одну з:
  - register(app, buttons_frame, content_frame)
  - get_buttons() -> list[dict(label, callback, tooltip?)]
"""
import pkgutil
import importlib
import traceback
import logging

logger = logging.getLogger(__name__)

PLUGINS_PACKAGE = "GUI.plugins"

def discover_plugins():
    try:
        pkg = importlib.import_module(PLUGINS_PACKAGE)
    except Exception:
        logger.debug("Пакет %s не знайдено", PLUGINS_PACKAGE)
        return []

    pkg_path = getattr(pkg, "__path__", None)
    if not pkg_path:
        return []

    modules = []
    for finder, name, ispkg in pkgutil.iter_modules(pkg_path):
        if name.startswith("_"):
            continue
        full = f"{PLUGINS_PACKAGE}.{name}"
        try:
            m = importlib.import_module(full)
            modules.append(m)
            logger.info("Імпорт плагіна: %s", full)
        except Exception:
            logger.error("Помилка імпорту плагіна %s:\n%s", full, traceback.format_exc())
    return modules

def register_all(app, buttons_frame, content_frame):
    for m in discover_plugins():
        try:
            if hasattr(m, "register"):
                m.register(app, buttons_frame, content_frame)
            elif hasattr(m, "get_buttons"):
                for b in m.get_buttons():
                    install_button(app, buttons_frame, b)
            else:
                logger.debug("Плагін %s не має entrypoint register/get_buttons", getattr(m, "__name__", "<unknown>"))
        except Exception:
            logger.error("Помилка реєстрації плагіна %s:\n%s", getattr(m, "__name__", "<unknown>"), traceback.format_exc())

from functools import partial
def install_button(app, frame, b):
    # b: dict with 'label' and 'callback'
    label = b.get("label", "Unnamed")
    cb = b.get("callback")
    import tkinter as tk
    from tkinter import ttk
    if not callable(cb):
        logger.warning("Callback %s not callable", label)
        return
    btn = ttk.Button(frame, text=label, command=lambda cb=cb: safe_call(app, cb))
    btn.pack(fill="x", pady=4)
    return btn

def safe_call(app, cb):
    try:
        cb(app)
    except TypeError:
        cb()
    except Exception:
        logger.exception("Error in plugin callback")