# functions/aaa_programs.py
"""Функції для керування програмами (з SafetySandbox)"""
import subprocess
from colorama import Fore

def llm_function(name, description, parameters):
    """Декоратор для реєстрації функцій в LLM"""
    def decorator(func):
        func._is_llm_function = True
        func._function_name = name
        func._description = description
        func._parameters = parameters
        return func
    return decorator

@llm_function(
    name="open_program",
    description="Відкрити програму на комп'ютері",
    parameters={
        "program_name": "Назва програми (notepad, calculator, chrome, paint, explorer, code)"
    }
)
def open_program(program_name):
    """Відкрити програму через SafetySandbox"""
    try:
        # Отримати sandbox
        from .core_safety_sandbox import get_sandbox
        sandbox = get_sandbox()
        
        # Виконати через sandbox
        success, message = sandbox.execute_safe_program(program_name)
        
        if success:
            return f"⚡ МАРК: {message}"
        else:
            return f"⚡ МАРК: {message}"
            
    except Exception as e:
        return f"⚡ МАРК: Помилка: {str(e)}"

@llm_function(
    name="close_program",
    description="Закрити запущену програму",
    parameters={
        "process_name": "Назва процесу (notepad.exe, chrome.exe, calc.exe)"
    }
)
def close_program(process_name):
    """Закрити програму через SafetySandbox"""
    try:
        # Отримати sandbox
        from .core_safety_sandbox import get_sandbox
        sandbox = get_sandbox()
        
        # Виконати через sandbox
        success, message = sandbox.close_safe_program(process_name)
        
        if success:
            return f"⚡ МАРК: {message}"
        else:
            return f"⚡ МАРК: {message}"
            
    except Exception as e:
        return f"⚡ МАРК: Помилка: {str(e)}"

@llm_function(
    name="add_allowed_program",
    description="Додати програму в whitelist (тільки якщо користувач явно попросив)",
    parameters={
        "program_name": "Назва програми",
        "program_path": "Повний шлях до executable"
    }
)
def add_allowed_program(program_name, program_path):
    """Додати програму в whitelist"""
    try:
        from .core_safety_sandbox import get_sandbox
        sandbox = get_sandbox()
        
        success = sandbox.add_allowed_program(program_name, program_path)
        
        if success:
            return f"⚡ МАРК: Програму додано в whitelist: {program_name}"
        else:
            return f"⚡ МАРК: Не вдалося додати програму."
            
    except Exception as e:
        return f"⚡ МАРК: Помилка: {str(e)}"

@llm_function(
    name="show_sandbox_status",
    description="Показати статус SafetySandbox (дозволені програми, захищені директорії, лог)",
    parameters={}
)
def show_sandbox_status():
    """Показати статус sandbox"""
    try:
        from .core_safety_sandbox import get_sandbox
        sandbox = get_sandbox()
        
        sandbox.print_status()
        
        return f"⚡ МАРК: Статус виведено в консоль."
        
    except Exception as e:
        return f"⚡ МАРК: Помилка: {str(e)}"

@llm_function(
    name="enable_auto_confirm",
    description="Увімкнути автопідтвердження для безпечних програм (notepad, calculator, paint)",
    parameters={}
)
def enable_auto_confirm():
    """Увімкнути автопідтвердження"""
    try:
        from .core_safety_sandbox import get_sandbox
        sandbox = get_sandbox()
        
        sandbox.enable_auto_confirm()
        
        return f"⚡ МАРК: Автопідтвердження увімкнено для безпечних програм."
        
    except Exception as e:
        return f"⚡ МАРК: Помилка: {str(e)}"

@llm_function(
    name="disable_auto_confirm",
    description="Вимкнути автопідтвердження (питати підтвердження для всіх дій)",
    parameters={}
)
def disable_auto_confirm():
    """Вимкнути автопідтвердження"""
    try:
        from .core_safety_sandbox import get_sandbox
        sandbox = get_sandbox()
        
        sandbox.disable_auto_confirm()
        
        return f"⚡ МАРК: Автопідтвердження вимкнено. Підтвердження потрібне для всіх дій."
        
    except Exception as e:
        return f"⚡ МАРК: Помилка: {str(e)}"