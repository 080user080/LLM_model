# functions/aaa_programs.py
"""Функції для керування програмами через SafetySandbox"""
import os
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
    description="Відкрити програму на комп'ютері (notepad, calculator, chrome, paint, explorer, code). Можна також вказати файл для відкриття.",
    parameters={
        "program_name": "Назва програми (наприклад: notepad, chrome, калькулятор)",
        "file_path": "(опціонально) шлях до файлу, який потрібно відкрити в програмі"
    }
)
def open_program(program_name, file_path=None):
    """Відкрити програму через SafetySandbox (з можливістю передати файл)"""
    try:
        from .core_safety_sandbox import get_sandbox
        sandbox = get_sandbox()

        # Отримуємо шлях до програми з whitelist
        program_name_lower = program_name.lower()
        if program_name_lower not in sandbox.allowed_programs:
            # Спробуємо знайти частковий збіг
            matches = [name for name in sandbox.allowed_programs if program_name_lower in name]
            if matches:
                program_name_lower = matches[0]
            else:
                available = ", ".join(list(sandbox.allowed_programs.keys())[:10])
                return f"❌ Програму '{program_name}' не знайдено в дозволених.\n💡 Доступні: {available}..."

        program_path = sandbox.allowed_programs[program_name_lower]

        # Перевіряємо існування файлу програми
        if not os.path.exists(program_path):
            # Для стандартних програм Windows пробуємо знайти в PATH
            if program_path in ["notepad.exe", "calc.exe", "mspaint.exe", "explorer.exe"]:
                import shutil
                found = shutil.which(program_path)
                if found:
                    program_path = found
                else:
                    # Стандартні шляхи
                    if program_path == "notepad.exe":
                        program_path = r"C:\Windows\System32\notepad.exe"
                    elif program_path == "calc.exe":
                        program_path = r"C:\Windows\System32\calc.exe"
                    elif program_path == "mspaint.exe":
                        program_path = r"C:\Windows\System32\mspaint.exe"
                    elif program_path == "explorer.exe":
                        program_path = r"C:\Windows\explorer.exe"

        if not os.path.exists(program_path):
            return f"❌ Виконуваний файл не знайдено: {program_path}"

        # Формуємо команду запуску
        cmd = [program_path]
        if file_path:
            if os.path.exists(file_path):
                cmd.append(file_path)
            else:
                return f"❌ Файл не існує: {file_path}"

        # Використовуємо логіку SafetySandbox для логування та підтвердження
        print(f"{Fore.CYAN}🔒 Відкриття через SafetySandbox: {cmd}")
        success, message = sandbox.execute_safe_program(program_name_lower)

        if success:
            # Якщо треба відкрити з файлом, робимо це окремо (бо execute_safe_program не підтримує аргументи)
            if file_path:
                subprocess.Popen(cmd)
                message = f"Відкрито {program_name} з файлом {os.path.basename(file_path)}"
                sandbox._log_action("open_program", program_name, True, message)
            return f"✅ {message}"
        else:
            return f"⚠️ {message}"

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
        from .core_safety_sandbox import get_sandbox
        sandbox = get_sandbox()
        success, message = sandbox.close_safe_program(process_name)
        return message  # Вже містить префікс або чистий текст
    except Exception as e:
        return f"Помилка: {str(e)}"

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
            return f"✅ Програму додано в whitelist: {program_name}"
        else:
            return f"❌ Не вдалося додати програму."
    except Exception as e:
        return f"❌ Помилка: {str(e)}"

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
        return "Статус виведено в консоль."
    except Exception as e:
        return f"Помилка: {str(e)}"

@llm_function(
    name="enable_auto_confirm",
    description="Увімкнути автопідтвердження для безпечних програм (notepad, calculator, paint)",
    parameters={}
)
def enable_auto_confirm():
    try:
        from .core_safety_sandbox import get_sandbox
        sandbox = get_sandbox()
        sandbox.enable_auto_confirm()
        return "✅ Автопідтвердження увімкнено для безпечних програм."
    except Exception as e:
        return f"❌ Помилка: {str(e)}"

@llm_function(
    name="disable_auto_confirm",
    description="Вимкнути автопідтвердження (питати підтвердження для всіх дій)",
    parameters={}
)
def disable_auto_confirm():
    try:
        from .core_safety_sandbox import get_sandbox
        sandbox = get_sandbox()
        sandbox.disable_auto_confirm()
        return "✅ Автопідтвердження вимкнено. Підтвердження потрібне для всіх дій."
    except Exception as e:
        return f"❌ Помилка: {str(e)}"