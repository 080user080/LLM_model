# functions/aaa_open_program.py - виправлена версія
import os
import subprocess
import json
from pathlib import Path
import shutil  # Додаємо для пошуку в PATH

def llm_function(name, description, parameters):
    """Декоратор для реєстрації функцій"""
    def decorator(func):
        func._is_llm_function = True
        func._function_name = name
        func._description = description
        func._parameters = parameters
        return func
    return decorator

PROGRAMS_FILE = Path(__file__).parent / "programs_list.json"

def find_in_path(program_name):
    """Знайти програму в системному PATH"""
    return shutil.which(program_name)

def safe_load_programs():
    """Безпечне завантаження програм"""
    default_programs = {
        "notepad": "notepad.exe",
        "блокнот": "notepad.exe",
        "калькулятор": "calculatorApp.exe",
        "paint": "mspaint.exe",
        "explorer": "explorer.exe",
        "провідник": "explorer.exe",
        "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    }
    
    if not PROGRAMS_FILE.exists():
        with open(PROGRAMS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_programs, f, indent=2, ensure_ascii=False)
        return default_programs
    
    try:
        with open(PROGRAMS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return default_programs

@llm_function(
    name="open_program",
    description="відкрити будь-яку програму за назвою (notepad, chrome, calculator, vscode тощо)",
    parameters={
        "program_name": "назва програми (наприклад: notepad, chrome, калькулятор)",
        "file_path": "(опціонально) файл який відкрити в програмі"
    }
)
def open_program(program_name, file_path=None):
    """Відкрити програму"""
    from colorama import Fore
    
    try:
        programs = safe_load_programs()
        program_name_lower = program_name.lower()
        
        if program_name_lower not in programs:
            matches = [name for name in programs.keys() if program_name_lower in name]
            if matches:
                program_name_lower = matches[0]
            else:
                available = ", ".join(list(programs.keys())[:10])
                return f"❌ Програму '{program_name}' не знайдено.\n💡 Доступні: {available}..."
        
        program_path = programs[program_name_lower]
        
        # Для стандартних програм Windows шукаємо в PATH
        standard_programs = ["notepad.exe", "calculatorApp.exe", "mspaint.exe", "explorer.exe"]
        
        if program_path in standard_programs:
            # Шукаємо програму в системному PATH
            full_path = find_in_path(program_path)
            if not full_path:
                # Якщо не знайшли в PATH, пробуємо стандартні шляхи
                if program_path == "notepad.exe":
                    full_path = r"C:\Windows\System32\notepad.exe"
                elif program_path == "calc.exe":
                    full_path = r"C:\Windows\System32\calculatorApp.exe"
                elif program_path == "mspaint.exe":
                    full_path = r"C:\Windows\System32\mspaint.exe"
                elif program_path == "explorer.exe":
                    full_path = r"C:\Windows\explorer.exe"
                else:
                    return f"❌ Не вдалося знайти {program_path} у системі"
            program_path = full_path
        
        # Перевіряємо чи файл існує
        if not os.path.exists(program_path):
            return f"❌ Файл не знайдено: {program_path}"
        
        # Запускаємо програму
        if file_path:
            if os.path.exists(file_path):
                subprocess.Popen([program_path, file_path])
                return f"✅ Відкрито {program_name} з файлом {file_path}"
            else:
                return f"❌ Файл не існує: {file_path}"
        else:
            subprocess.Popen([program_path])
            return f"✅ Відкрито {program_name}"
    
    except Exception as e:
        return f"❌ Помилка відкриття '{program_name}': {str(e)}"