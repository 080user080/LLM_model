# functions/aaa_execute_python.py
"""Виконання Python коду в безпечній пісочниці"""
import os
import sys
import subprocess
import tempfile
import time
from pathlib import Path
from datetime import datetime
from colorama import Fore

def llm_function(name, description, parameters):
    """Декоратор для реєстрації функцій"""
    def decorator(func):
        func._is_llm_function = True
        func._function_name = name
        func._description = description
        func._parameters = parameters
        return func
    return decorator

# Пісочниця
SANDBOX_DIR = Path("D:/Python/MARK/sandbox")
SCRIPTS_DIR = SANDBOX_DIR / "scripts"
OUTPUT_DIR = SANDBOX_DIR / "output"
LOGS_DIR = SANDBOX_DIR / "logs"
TEMP_DIR = SANDBOX_DIR / "temp"

# Створити директорії
for dir_path in [SANDBOX_DIR, SCRIPTS_DIR, OUTPUT_DIR, LOGS_DIR, TEMP_DIR]:
    dir_path.mkdir(exist_ok=True, parents=True)

class PythonSandbox:
    """Безпечна пісочниця для Python коду"""
    
    def __init__(self):
        self.timeout = 30  # секунд
        self.max_memory = 512  # MB (не використовується на Windows, але для інформації)
        
        # Заборонені модулі/функції
        self.forbidden = [
            #'os.system', 'os.remove', 'os.rmdir', 'shutil.rmtree',
            #'subprocess.call', 'eval', 'exec', '__import__',
            #'open(', 'file(', 'input(', 'raw_input(',
        ]
    
    def validate_code(self, code):
        """Перевірити код на безпеку"""
        code_lower = code.lower()
        
        for forbidden in self.forbidden:
            if forbidden.lower() in code_lower:
                return False, f"Заборонено використання: {forbidden}"
        
        # Додаткові перевірки
        dangerous_patterns = [
            #'import os',
            #'import subprocess',
            #'import shutil',
            #'from os import',
            #'__builtins__',
            #'globals()',
            #'locals()',
        ]
        
        for pattern in dangerous_patterns:
            if pattern in code_lower:
                return False, f"Заборонений патерн: {pattern}"
        
        return True, "OK"
    
    def execute(self, code, script_name=None):
        """Виконати код в пісочниці"""
        print(f"{Fore.CYAN}🔒 Виконання в пісочниці...")
        
        # Валідація
        is_safe, message = self.validate_code(code)
        if not is_safe:
            return {
                'success': False,
                'error': f"⛔ Код не пройшов перевірку безпеки: {message}",
                'output': '',
                'stderr': ''
            }
        
        # Створити тимчасовий скрипт
        if script_name is None:
            script_name = f"script_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
        
        script_path = SCRIPTS_DIR / script_name
        log_path = LOGS_DIR / f"{script_name}.log"
        
        # Записати код
        try:
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(code)
        except Exception as e:
            return {
                'success': False,
                'error': f"❌ Помилка запису скрипта: {e}",
                'output': '',
                'stderr': ''
            }
        
        print(f"{Fore.CYAN}   📝 Скрипт: {script_name}")
        
        # Виконати
        try:
            start_time = time.time()
            
            # Запустити Python subprocess
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                cwd=str(SANDBOX_DIR)  # Робоча директорія = пісочниця
            )
            
            # Чекати з timeout
            try:
                stdout, stderr = process.communicate(timeout=self.timeout)
                returncode = process.returncode
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                return {
                    'success': False,
                    'error': f"⏱️ Timeout: виконання перевищило {self.timeout}с",
                    'output': stdout,
                    'stderr': stderr
                }
            
            execution_time = time.time() - start_time
            
            # Записати лог
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(f"=== Виконання: {datetime.now()} ===\n")
                f.write(f"Час: {execution_time:.2f}с\n")
                f.write(f"Return code: {returncode}\n")
                f.write(f"\n=== STDOUT ===\n{stdout}\n")
                f.write(f"\n=== STDERR ===\n{stderr}\n")
            
            # Результат
            success = returncode == 0
            
            if success:
                print(f"{Fore.GREEN}   ✅ Виконано за {execution_time:.2f}с")
                return {
                    'success': True,
                    'output': stdout.strip(),
                    'stderr': stderr.strip(),
                    'execution_time': execution_time,
                    'script_path': str(script_path),
                    'log_path': str(log_path)
                }
            else:
                print(f"{Fore.RED}   ❌ Помилка (код {returncode})")
                return {
                    'success': False,
                    'error': f"Код завершився з помилкою (return code {returncode})",
                    'output': stdout.strip(),
                    'stderr': stderr.strip(),
                    'execution_time': execution_time
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': f"❌ Помилка виконання: {e}",
                'output': '',
                'stderr': str(e)
            }

# Глобальний екземпляр
_sandbox = PythonSandbox()

@llm_function(
    name="execute_python",
    description="Виконати Python код в безпечній пісочниці",
    parameters={
        "code": "Python код для виконання",
        "script_name": "(опціонально) назва скрипта"
    }
)
def execute_python(code, script_name=None):
    """Виконати Python код"""
    result = _sandbox.execute(code, script_name)
    
    if result['success']:
        output = result['output']
        time_str = f"{result['execution_time']:.2f}с"
        
        if output:
            return f"✅ Виконано ({time_str}):\n{output}"
        else:
            return f"✅ Виконано ({time_str}). Вивід порожній."
    else:
        error_msg = result['error']
        stderr = result.get('stderr', '')
        
        if stderr:
            return f"❌ Помилка:\n{error_msg}\n\nДеталі:\n{stderr}"
        else:
            return f"❌ {error_msg}"

@llm_function(
    name="execute_python_code",
    description="Виконати Python код в безпечній пісочниці (alias для execute_python)",
    parameters={
        "code": "Python код для виконання",
        "script_name": "(опціонально) назва скрипта"
    }
)
def execute_python_code(code, script_name=None):
    """Alias для execute_python для сумісності з LLM"""
    return execute_python(code, script_name)

@llm_function(
    name="execute_python_file",
    description="Виконати Python файл з пісочниці",
    parameters={
        "filename": "Назва файлу в D:/Python/MARK/sandbox/scripts/"
    }
)
def execute_python_file(filename):
    """Виконати існуючий Python файл"""
    script_path = SCRIPTS_DIR / filename
    
    if not script_path.exists():
        return f"❌ Файл не знайдено: {filename}"
    
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        return execute_python(code, filename)
    
    except Exception as e:
        return f"❌ Помилка читання файлу: {e}"

@llm_function(
    name="list_sandbox_scripts",
    description="Показати список скриптів в пісочниці",
    parameters={}
)
def list_sandbox_scripts():
    """Список скриптів"""
    scripts = list(SCRIPTS_DIR.glob("*.py"))
    
    if not scripts:
        return "📂 Пісочниця порожня"
    
    result = f"📂 Скриптів в пісочниці: {len(scripts)}\n\n"
    
    for script in sorted(scripts):
        size = script.stat().st_size
        mtime = datetime.fromtimestamp(script.stat().st_mtime)
        result += f"📄 {script.name} ({size} байт, {mtime.strftime('%Y-%m-%d %H:%M')})\n"
    
    return result.strip()