# functions/aaa_confirmation.py
"""Система підтвердження дій"""
import time
import threading
from colorama import Fore

# Глобальна змінна для GUI
_gui_instance = None

def set_gui_instance(gui):
    """Встановити екземпляр GUI"""
    global _gui_instance
    _gui_instance = gui

def llm_function(name, description, parameters):
    def decorator(func):
        func._is_llm_function = True
        func._function_name = name
        func._description = description
        func._parameters = parameters
        return func
    return decorator

@llm_function(
    name="confirm_action",
    description="Запитати підтвердження дії у користувача",
    parameters={
        "action": "Дія яку потрібно підтвердити",
        "question": "Питання для користувача"
    }
)
def confirm_action(action, question):
    """Система голосового підтвердження через GUI"""
    try:
        global _gui_instance
        
        if not _gui_instance:
            # Якщо GUI немає, використовуємо консоль
            print(f"{Fore.YELLOW}⚠️  {question}")
            print(f"{Fore.YELLOW}   💡 Скажіть 'так' або 'ні' (10 секунд)...")
            
            # Імітуємо очікування
            time.sleep(10)
            return {"status": "timeout", "action": action}
        
        # Створюємо подію для GUI
        result = {"confirmed": None}
        event = threading.Event()
        
        def callback(response):
            result["confirmed"] = response
            event.set()
        
        # Показуємо підтвердження в GUI
        _gui_instance.queue_message('show_confirmation', (question, callback))
        
        # Чекаємо відповіді
        event.wait(timeout=30)
        
        if result["confirmed"] is None:
            return {"status": "timeout", "action": action}
        
        return {
            "status": "confirmed" if result["confirmed"] else "cancelled",
            "action": action,
            "confirmed": result["confirmed"]
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}