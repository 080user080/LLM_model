def hello_callback(app=None):
    # Тут можна використовувати `app` (він може бути None або екземпляр Tk)
    if app:
        try:
            from tkinter import messagebox
            messagebox.showinfo("Hello", "Кнопка з плагіну натиснута!")
            return
        except Exception:
            pass
    print("Hello from sample_button plugin!")

def register(app, buttons_frame=None, content_frame=None):
    # Простий варіант: додаємо одну кнопку в buttons_frame
    # Ми не імпортуємо tkinter тут прямо — краще робити це у вашому середовищі
    try:
        import tkinter as tk
    except Exception:
        # fallback: якщо викликають без GUI, нічого не робимо
        return

    if buttons_frame is not None:
        btn = tk.Button(buttons_frame, text="Say Hello (plugin)", command=lambda: hello_callback(app))
        btn.pack(side=tk.LEFT, padx=4)