def test_action(app=None):
    print("test_action called")
    if app:
        try:
            from tkinter import messagebox
            messagebox.showinfo("Plugin", "test_action виконаний")
        except Exception:
            pass

def get_buttons():
    return [
        {"label": "Test Action", "callback": test_action, "tooltip": "Це тестова кнопка"}
    ]