import os
import sys
import subprocess
import time
import ctypes

def llm_function(name, description, parameters):
    def decorator(func):
        func._is_llm_function = True
        func._function_name = name
        func._description = description
        func._parameters = parameters
        return func
    return decorator

@llm_function(
    name="close_program",
    description="закрити програму за її назвою (наприклад: notepad, CalculatorApp)",
    parameters={
        "process_name": "назва процесу без .exe"
    }
)
def close_program(process_name):
    """Закриває процес у Windows за допомогою taskkill"""
    try:
        # Додаємо .exe якщо користувач забув
        if not process_name.lower().endswith(".exe"):
            exec_name = process_name + ".exe"
        else:
            exec_name = process_name

        # Виконуємо системну команду Windows
        # /F - примусово, /IM - за іменем образу
        result = subprocess.run(
            ["taskkill", "/F", "/IM", exec_name], 
            capture_output=True, 
            text=True, 
            encoding='cp866' # Кодування консолі Windows
        )
        
        if result.returncode == 0:
            return f"✅ Процес {exec_name} успішно закрито"
        else:
            return f"ℹ️ Не вдалося закрити {exec_name} (можливо, він не запущений)"
            
    except Exception as e:
        return f"❌ Помилка у новій навичці: {str(e)}"