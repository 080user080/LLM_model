# Швидка обгортка: якщо у вас вже є GUI_launcher.py — використаємо його.
# Якщо ви ще не мерджили зміни, цей файл залишає старий вміст неторканим,
# але при запуску буде намагатися використовувати GUI_launcher.
try:
    # Переважаючий шлях — використати новий лаунчер
    from GUI_launcher import main as gui_main  # type: ignore
except Exception:
    gui_main = None

if __name__ == "__main__":
    if gui_main:
        gui_main()
    else:
        # Fall back: старий monolithic GUI (якщо ви тимчасово не хочете відразу міняти)
        try:
            # Якщо в репозиторії є клас DialogGUI у цьому файлі — запустити його.
            # Старий файл вже містить цей клас, тому імпорт/виклик спрацює.
            from GUI import DialogGUI  # noqa: F401
            app = DialogGUI()
            app.mainloop()
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise