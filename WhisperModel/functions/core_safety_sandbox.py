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
        #self.audit_log_path = Path(__file__).parent / "audit_log.json"
        
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
    
    def _log_action(self, action_type, program_name, success, message):
        """Записати дію в audit log"""
        # Тимчасово відключено для уникнення помилки
        pass
    
    def is_safe_program(self, program_name):
        """Перевірити чи програма безпечна (auto-confirm)"""
        return program_name.lower() in self.safe_programs
    
    def _get_process_executable_name(self, process_name):
        """Отримати ім'я виконуваного файла процеса"""
        # Якщо вже .exe, повертаємо як є
        if process_name.lower().endswith('.exe'):
            return process_name.lower()
        
        # Перевіряємо мапінг
        process_name_lower = process_name.lower()
        if process_name_lower in self.process_name_map:
            return self.process_name_map[process_name_lower]
        
        # Додаємо .exe
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
            # Отримуємо PID процесу
            pids = self._get_process_pids(process_name)
            
            if not pids:
                return False, "Процес не знайдено", 0
            
            # Завантажуємо функції WinAPI
            EnumWindows = ctypes.windll.user32.EnumWindows
            GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId
            SendMessage = ctypes.windll.user32.SendMessageW
            
            closed_windows = set()
            
            # Callback функція для перебору вікон
            def enum_windows_callback(hwnd, lParam):
                pid = ctypes.c_ulong()
                GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                
                if pid.value in pids:
                    # WM_CLOSE = 0x0010 - нормальне закриття (збереження даних)
                    SendMessage(hwnd, 0x0010, 0, 0)
                    closed_windows.add(pid.value)
                return True  # Продовжити перебір
            
            # Тип callback функції
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
            
            # Перебираємо всі вікна
            EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
            
            if closed_windows:
                return True, f"Відправлено команду закриття для {len(closed_windows)} вікон процесу {process_name}", len(closed_windows)
            else:
                return False, "Не знайдено вікон для закриття", 0
            
        except Exception as e:
            return False, f"Помилка WinAPI: {str(e)}", 0
    
    def _force_close_program(self, process_name):
        """Примусове закриття програми (тільки для критичних випадків)"""
        try:
            exec_name = self._get_process_executable_name(process_name)
            
            # Використовуємо taskkill для примусового закриття
            result = subprocess.run(
                ["taskkill", "/F", "/IM", exec_name], 
                capture_output=True, 
                text=True, 
                encoding='cp866'
            )
            
            if result.returncode == 0:
                return True, f"Програма {process_name} примусово закрита (втрата незбережених даних)"
            else:
                # Спробуємо через psutil якщо встановлено
                try:
                    import psutil
                    for proc in psutil.process_iter(['pid', 'name']):
                        if proc.info['name'] and proc.info['name'].lower() == exec_name:
                            proc.terminate()
                            time.sleep(0.5)
                            if proc.is_running():
                                proc.kill()
                            return True, f"Програма {process_name} примусово закрита (терміновано)"
                    
                    return False, f"Процес {process_name} не знайдено для закриття"
                except ImportError:
                    return False, f"Не вдалося закрити {process_name}: {result.stderr}"
                
        except Exception as e:
            return False, f"Помилка примусового закриття: {str(e)}"
    
    def close_safe_program(self, process_name, require_confirmation=False):
        """Закрити програму безпечно"""
        try:
            print(f"{Fore.CYAN}🔒 Спроба коректного закриття {process_name}...")
            
            # 1. Спочатку спробуємо нормально закрити через WinAPI
            success, message, window_count = self._close_window_by_process_name(process_name)
            
            if not success:
                return False, f"Не вдалося знайти або закрити {process_name}: {message}"
            
            # 2. Чекаємо 3 секунди на нормальне закриття
            print(f"{Fore.YELLOW}   ⏳ Чекаю 3 секунди на нормальне закриття...")
            time.sleep(3)
            
            # 3. Перевіряємо чи процес ще існує
            pids = self._get_process_pids(process_name)
            
            if not pids:
                # Процес закрився успішно
                self._log_action("close_program", process_name, True, "Нормальне закриття (WM_CLOSE)")
                return True, f"Програма {process_name} успішно закрита (збережені дані)"
            
            # 4. Процес ще запущений - обробляємо в залежності від налаштувань
            print(f"{Fore.YELLOW}   ⚠️  {process_name} ще запущений після команди закриття")
            
            if self.is_safe_program(process_name):
                # Для безпечних програм - закриваємо примусово
                print(f"{Fore.YELLOW}   🔧 Безпечна програма - закриваю примусово...")
                force_success, force_message = self._force_close_program(process_name)
                
                if force_success:
                    self._log_action("close_program", process_name, True, f"Примусове закриття для безпечної програми")
                    return True, f"Програма {process_name} закрита (безпечна програма)"
                else:
                    self._log_action("close_program", process_name, False, f"Не вдалося примусово закрити безпечну програму")
                    return False, f"Не вдалося закрити {process_name}: {force_message}"
            
            elif require_confirmation:
                # Потрібне підтвердження користувача
                self._log_action("close_program", process_name, False, 
                               f"Потребує підтвердження для примусового закриття")
                return False, f"ПОТРІБНЕ_ПІДТВЕРДЖЕННЯ:{process_name} не відповідає на команду закриття. Скажіть 'так' щоб закрити примусово або 'ні' щоб залишити відкритим."
            
            else:
                # Без підтвердження - залишаємо відкритим
                self._log_action("close_program", process_name, False, 
                               f"Залишено відкритим - потребує підтвердження")
                return False, f"Програма {process_name} не закрита. Скажіть 'закрий примусово {process_name}' щоб закрити."
            
        except Exception as e:
            message = f"Помилка закриття: {str(e)}"
            self._log_action("close_program", process_name, False, message)
            return False, message
    
    def execute_safe_program(self, program_name):
        """Виконати програму безпечно"""
        program_name_lower = program_name.lower()
        
        # Перевірити чи програма в whitelist
        if program_name_lower not in self.allowed_programs:
            message = f"Програма '{program_name}' не в whitelist"
            self._log_action("open_program", program_name, False, message)
            return False, message
        
        program_path = self.allowed_programs[program_name_lower]
        
        # Перевірити чи потрібне підтвердження
        if not self.auto_confirm_enabled or not self.is_safe_program(program_name_lower):
            # TODO: Додати голосове підтвердження
            print(f"{Fore.YELLOW}⚠️  Підтвердження потрібне для: {program_name}")
        
        # Знайти програму
        if not os.path.exists(program_path):
            # Спробувати стандартні шляхи Windows
            if program_path == "notepad.exe":
                program_path = r"C:\Windows\System32\notepad.exe"
            elif program_path == "calc.exe":
                program_path = r"C:\Windows\System32\calc.exe"
            elif program_path == "mspaint.exe":
                program_path = r"C:\Windows\System32\mspaint.exe"
            elif program_path == "explorer.exe":
                program_path = r"C:\Windows\explorer.exe"
        
        # Перевірити чи існує
        if not os.path.exists(program_path):
            message = f"Програму не знайдено: {program_path}"
            self._log_action("open_program", program_name, False, message)
            return False, message
        
        try:
            # Запустити програму
            subprocess.Popen([program_path])
            message = f"Відкрив {program_name}"
            self._log_action("open_program", program_name, True, message)
            return True, message
        
        except Exception as e:
            message = f"Помилка запуску: {str(e)}"
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