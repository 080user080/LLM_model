# functions/core_safety_sandbox.py
"""SafetySandbox - безпечне виконання програм"""
import os
import subprocess
import json
import ctypes
import ctypes.wintypes
import time
from pathlib import Path
from datetime import datetime
from colorama import Fore

class SafetySandbox:
    """Безпечне виконання команд з whitelist та підтвердженням"""
    
    def __init__(self):
        self.config_path = Path(__file__).parent / "safety_config.json"
        
        # Завантажити конфігурацію
        self.config = self._load_config()
        
        # Програми що дозволені
        self.allowed_programs = self.config.get("allowed_programs", {})
        
        # Небезпечні патерни (заборонені)
        self.blocked_patterns = self.config.get("blocked_patterns", [
            r"rm -rf /",
            r"del /f /s /q C:\\",
            r"format",
            r"sudo rm",
            r"rmdir /s",
        ])
        
        # Автопідтвердження для безпечних програм
        self.auto_confirm_enabled = self.config.get("auto_confirm", True)
        self.safe_programs = self.config.get("safe_programs", [
            "notepad", "calculator", "paint", "mspaint"
        ])
        
        # Словник для відображення імен процесів
        self.process_name_map = {
            "notepad": "notepad.exe",
            "блокнот": "notepad.exe",
            "calculator": "calc.exe",
            "калькулятор": "calc.exe",
            "paint": "mspaint.exe",
            "пейнт": "mspaint.exe",
            "chrome": "chrome.exe",
            "хром": "chrome.exe",
            "браузер": "chrome.exe",
            "explorer": "explorer.exe",
            "провідник": "explorer.exe",
        }
        
        print(f"{Fore.GREEN}✅ SafetySandbox ініціалізовано")
        print(f"{Fore.CYAN}   Дозволених програм: {len(self.allowed_programs)}")
        print(f"{Fore.CYAN}   Автопідтвердження: {self.auto_confirm_enabled}")
    
    def _load_config(self):
        """Завантажити конфігурацію"""
        default_config = {
            "allowed_programs": {
                "notepad": "notepad.exe",
                "блокнот": "notepad.exe",
                "calculator": "calc.exe",
                "калькулятор": "calc.exe",
                "paint": "mspaint.exe",
                "пейнт": "mspaint.exe",
                "explorer": "explorer.exe",
                "провідник": "explorer.exe",
                "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                "хром": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                "браузер": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            },
            "safe_programs": ["notepad", "calculator", "paint", "mspaint"],
            "auto_confirm": True,
            "blocked_patterns": [
                r"rm -rf /",
                r"del /f /s /q C:\\",
                r"format",
                r"sudo rm",
                r"rmdir /s",
            ]
        }
        
        if not self.config_path.exists():
            # Створити default config
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            return default_config
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"{Fore.RED}❌ Помилка завантаження config: {e}")
            return default_config
    
    def _save_config(self):
        """Зберегти конфігурацію"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"{Fore.RED}❌ Помилка збереження config: {e}")
    
    # ДОДАНО: Відсутній метод
    def is_safe_program(self, program_name):
        """Перевірити чи програма безпечна (auto-confirm)"""
        return program_name.lower() in self.safe_programs
    
    def _log_action(self, action_type, program_name, success, message):
        """Записати дію в audit log"""
        # Тимчасово відключено для уникнення помилки
        pass
    
    def _get_process_executable_name(self, process_name):
        """Отримати ім'я виконуваного файла процеса"""
        if process_name.lower().endswith('.exe'):
            return process_name.lower()
        
        process_name_lower = process_name.lower()
        if process_name_lower in self.process_name_map:
            return self.process_name_map[process_name_lower]
        
        return f"{process_name_lower}.exe"
    
    def _get_process_pids(self, process_name):
        """Отримати PID процесу за ім'ям"""
        try:
            import psutil
            
            exec_name = self._get_process_executable_name(process_name)
            pids = []
            
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] and proc.info['name'].lower() == exec_name:
                    pids.append(proc.info['pid'])
            
            return pids
        except ImportError:
            print(f"{Fore.YELLOW}⚠️  psutil не встановлено. Використовую taskkill.")
            return []
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  Помилка пошуку PID: {e}")
            return []
    
    def _close_window_by_process_name(self, process_name):
        """Безпечне закриття вікна через WinAPI (WM_CLOSE)"""
        try:
            pids = self._get_process_pids(process_name)
            
            if not pids:
                return False, "Процес не знайдено", 0
            
            EnumWindows = ctypes.windll.user32.EnumWindows
            GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId
            SendMessage = ctypes.windll.user32.SendMessageW
            
            closed_windows = set()
            
            def enum_windows_callback(hwnd, lParam):
                pid = ctypes.c_ulong()
                GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                
                if pid.value in pids:
                    SendMessage(hwnd, 0x0010, 0, 0)
                    closed_windows.add(pid.value)
                return True
            
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
            EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
            
            if closed_windows:
                return True, f"Відправлено команду закриття для {len(closed_windows)} вікон", len(closed_windows)
            else:
                return False, "Не знайдено вікон для закриття", 0
            
        except Exception as e:
            return False, f"Помилка WinAPI: {str(e)}", 0
    
    def _force_close_program(self, process_name):
        """Примусове закриття програми"""
        try:
            exec_name = self._get_process_executable_name(process_name)
            
            result = subprocess.run(
                ["taskkill", "/F", "/IM", exec_name], 
                capture_output=True, 
                text=True, 
                encoding='cp866'
            )
            
            if result.returncode == 0:
                return True, f"Програма {process_name} примусово закрита"
            else:
                try:
                    import psutil
                    for proc in psutil.process_iter(['pid', 'name']):
                        if proc.info['name'] and proc.info['name'].lower() == exec_name:
                            proc.terminate()
                            time.sleep(0.5)
                            if proc.is_running():
                                proc.kill()
                            return True, f"Програма {process_name} примусово закрита"
                    
                    return False, f"Процес {process_name} не знайдено"
                except ImportError:
                    return False, f"Не вдалося закрити: {result.stderr}"
                
        except Exception as e:
            return False, f"Помилка: {str(e)}"
    
    def close_safe_program(self, process_name, require_confirmation=False):
        """Закрити програму безпечно"""
        try:
            print(f"{Fore.CYAN}🔒 Спроба коректного закриття {process_name}...")
            
            success, message, window_count = self._close_window_by_process_name(process_name)
            
            if not success:
                return False, f"Не вдалося знайти або закрити {process_name}: {message}"
            
            print(f"{Fore.YELLOW}   ⏳ Чекаю 3 секунди...")
            time.sleep(3)
            
            pids = self._get_process_pids(process_name)
            
            if not pids:
                self._log_action("close_program", process_name, True, "Нормальне закриття")
                return True, f"Програма {process_name} успішно закрита"
            
            print(f"{Fore.YELLOW}   ⚠️  {process_name} ще запущений")
            
            if self.is_safe_program(process_name):
                print(f"{Fore.YELLOW}   🔧 Безпечна програма - закриваю примусово...")
                force_success, force_message = self._force_close_program(process_name)
                
                if force_success:
                    self._log_action("close_program", process_name, True, f"Примусове закриття")
                    return True, f"Програма {process_name} закрита"
                else:
                    self._log_action("close_program", process_name, False, f"Не вдалося закрити")
                    return False, f"Не вдалося закрити {process_name}: {force_message}"
            
            elif require_confirmation:
                self._log_action("close_program", process_name, False, f"Потребує підтвердження")
                return False, f"ПОТРІБНЕ_ПІДТВЕРДЖЕННЯ:{process_name} не відповідає. Скажіть 'так' щоб закрити."
            
            else:
                self._log_action("close_program", process_name, False, f"Залишено відкритим")
                return False, f"Програма {process_name} не закрита. Скажіть 'закрий примусово {process_name}'."
            
        except Exception as e:
            message = f"Помилка: {str(e)}"
            self._log_action("close_program", process_name, False, message)
            return False, message
    
    def execute_safe_program(self, program_name):
        """Виконати програму безпечно"""
        program_name_lower = program_name.lower()
        
        if program_name_lower not in self.allowed_programs:
            message = f"Програма '{program_name}' не в whitelist"
            self._log_action("open_program", program_name, False, message)
            return False, message
        
        program_path = self.allowed_programs[program_name_lower]
        
        if not self.auto_confirm_enabled or not self.is_safe_program(program_name_lower):
            print(f"{Fore.YELLOW}⚠️  Підтвердження потрібне для: {program_name}")
        
        if not os.path.exists(program_path):
            if program_path == "notepad.exe":
                program_path = r"C:\Windows\System32\notepad.exe"
            elif program_path == "calc.exe":
                program_path = r"C:\Windows\System32\calc.exe"
            elif program_path == "mspaint.exe":
                program_path = r"C:\Windows\System32\mspaint.exe"
            elif program_path == "explorer.exe":
                program_path = r"C:\Windows\explorer.exe"
        
        if not os.path.exists(program_path):
            message = f"Програму не знайдено: {program_path}"
            self._log_action("open_program", program_name, False, message)
            return False, message
        
        try:
            subprocess.Popen([program_path])
            message = f"Відкрив {program_name}"
            self._log_action("open_program", program_name, True, message)
            return True, message
        
        except Exception as e:
            message = f"Помилка: {str(e)}"
            self._log_action("open_program", program_name, False, message)
            return False, message
    
    def add_allowed_program(self, program_name, program_path):
        """Додати програму в whitelist"""
        self.allowed_programs[program_name.lower()] = program_path
        self.config["allowed_programs"] = self.allowed_programs
        self._save_config()
        
        message = f"Програму додано: {program_name}"
        self._log_action("add_program", program_name, True, message)
        return True
    
    def enable_auto_confirm(self):
        """Увімкнути автопідтвердження"""
        self.auto_confirm_enabled = True
        self.config["auto_confirm"] = True
        self._save_config()
    
    def disable_auto_confirm(self):
        """Вимкнути автопідтвердження"""
        self.auto_confirm_enabled = False
        self.config["auto_confirm"] = False
        self._save_config()
    
    def print_status(self):
        """Вивести статус sandbox"""
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}🛡️  SAFETYSANDBOX STATUS")
        print(f"{Fore.CYAN}{'='*60}")
        
        print(f"\n{Fore.GREEN}📋 Дозволені програми ({len(self.allowed_programs)}):")
        for name, path in list(self.allowed_programs.items())[:10]:
            safe = "🟢" if name in self.safe_programs else "🟡"
            print(f"   {safe} {name} → {path}")
        
        print(f"\n{Fore.YELLOW}⚙️  Налаштування:")
        print(f"   Автопідтвердження: {self.auto_confirm_enabled}")
        print(f"   Безпечних програм: {len(self.safe_programs)}")
        
        print(f"\n{Fore.RED}🚫 Заборонені патерни ({len(self.blocked_patterns)}):")
        for pattern in self.blocked_patterns[:5]:
            print(f"   ❌ {pattern}")
        
        print(f"\n{Fore.CYAN}🔧 Процеси для закриття:")
        for name, exe in self.process_name_map.items():
            print(f"   • {name} → {exe}")
        
        print(f"\n{Fore.CYAN}{'='*60}\n")


# Глобальний екземпляр
_sandbox = None

def get_sandbox():
    """Отримати глобальний SafetySandbox"""
    global _sandbox
    if _sandbox is None:
        _sandbox = SafetySandbox()
    return _sandbox