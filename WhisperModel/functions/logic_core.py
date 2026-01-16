# functions/logic_core.py
"""Ядро асистента - реєстр функцій та VoiceAssistant"""
import os
import sys
import importlib
import inspect
from pathlib import Path
import time
from colorama import Fore, Back, Style

# Глобальне посилання на реєстр, щоб aaa_architect міг його оновити
global_registry = None

class FunctionRegistry:
    """Реєстр функцій з автоматичним завантаженням"""
    
    def __init__(self):
        global global_registry
        self.functions = {}
        self.core_modules = {}
        self.load_all_modules()
        global_registry = self  # Зберігаємо посилання на себе
    
    def refresh(self):
        """Перезавантажити всі функції без перезапуску програми"""
        print(f"{Fore.CYAN}♻️  Оновлення реєстру навичок...")
        
        # Очистити поточні функції
        self.functions.clear()
        
        # Примусово очистити кеш модулів aaa_*, щоб Python перечитав файли
        keys_to_remove = [k for k in sys.modules if k.startswith('functions.aaa_')]
        for k in keys_to_remove:
            del sys.modules[k]
            
        # Завантажити заново
        self.load_all_modules()
        print(f"{Fore.GREEN}✅ Реєстр оновлено. Доступно навичок: {len(self.functions)}")

    def load_all_modules(self):
        """Автоматично завантажити всі модулі з папки functions"""
        functions_dir = Path(__file__).parent
        
        if not functions_dir.exists():
            print(f"{Fore.YELLOW}⚠️  Папка functions не знайдена")
            return
        
        # Спочатку завантажити CORE модулі (core_*.py)
        print(f"{Fore.CYAN}📦 Завантаження core модулів...")
        core_files = sorted(functions_dir.glob("core_*.py"))
        
        for file_path in core_files:
            module_name = file_path.stem
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                self.core_modules[module_name] = module
                print(f"{Fore.MAGENTA}⚡ Core: {Fore.CYAN}{module_name}")
                
                if hasattr(module, 'init'):
                    module.init()
                    
            except Exception as e:
                print(f"{Fore.RED}❌ Помилка завантаження {module_name}: {e}")
        
        # Завантажити звичайні функції (aaa_*.py)
        print(f"\n{Fore.CYAN}📦 Завантаження функцій...")
        for file_path in sorted(functions_dir.glob("aaa_*.py")):
            module_name = file_path.stem
            try:
                # Важливо: використовуємо ім'я пакета functions.aaa_... для коректного імпорту
                spec = importlib.util.spec_from_file_location(f"functions.{module_name}", file_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"functions.{module_name}"] = module # Реєструємо в sys.modules
                spec.loader.exec_module(module)
                
                for name, obj in inspect.getmembers(module):
                    if inspect.isfunction(obj) and hasattr(obj, '_is_llm_function'):
                        func_info = {
                            'function': obj,
                            'name': obj._function_name,
                            'description': obj._description,
                            'parameters': obj._parameters
                        }
                        self.functions[obj._function_name] = func_info
                        print(f"{Fore.GREEN}✅ {Fore.CYAN}{obj._function_name}")
            
            except Exception as e:
                print(f"{Fore.RED}❌ Помилка завантаження {module_name}: {e}")
    
    def get_core_module(self, name):
        """Отримати core модуль за назвою"""
        for module_name, module in self.core_modules.items():
            if name in module_name:
                return module
        return None
    
    def get_system_prompt(self):
        """Згенерувати Voice-First system prompt для Code Assistant"""
        from .config import ASSISTANT_NAME, ASSISTANT_MODES, ACTIVE_MODE
        
        mode = ASSISTANT_MODES[ACTIVE_MODE]
        
        prompt = f"""ТИ: Голосовий асистент {ASSISTANT_NAME} для написання коду

МОВА: Українська, розмовна
СТИЛЬ: {mode['style']}
РЕЖИМ: {ACTIVE_MODE} (максимум {mode['max_words']} слів, {mode['max_sentences']} речення)

КРИТИЧНІ ПРАВИЛА:
1. ВИКОНАЙ ДІЮ, не пояснюй її
2. Відповідь = результат, не коментар
3. Якщо код - просто код, без "ось код:"
4. Якщо помилка - скажи "Помилка: [причина]"
5. Якщо не зрозумів - скажи "Не зрозумів. Повторіть?"

ПРИКЛАДИ КОДОВИХ КОМАНД:
• "Марк, запусти код: print('hello')" → {{"action":"execute_python_code","code":"print('hello')","confirm":false}}
• "Марк, досліди Flask" → {{"action":"research_topic","topic":"Flask hello world","confirm":false}}
• "Марк, встанови flask" → {{"action":"shell_execute","command":"pip install flask","confirm":true,"risk":"package_install"}}
• "Марк, відкрий блокнот" → {{"action":"open_program","program_name":"notepad","confirm":false}}

ПРИКЛАДИ ВІДПОВІДЕЙ:
• Коли виконав: "Готово."
• Коли помилка: "Помилка: файл не знайдено."
• Коли не впевнений: "Не зрозумів. Повторіть?"
• Коли ризик: "Це видалить файли. Підтверджуєте?"

ЗАБОРОНЕНІ ФРАЗИ:
"Звичайно", "Я допоможу", "Дозвольте", "З радістю", 
"Ось ваш код", "Я може допомогти", "Один момент"

ДОЗВОЛЕНІ ФРАЗИ:
"Готово", "Відкрив", "Помилка", "Не зрозумів", "Слухаю", 
"Виконую", "Підтверджую", "Скасовано"
"""
        
        if not self.functions:
            return prompt + "\n\n⚠️ Функції недоступні."
        
        prompt += "\n\nДОСТУПНІ ФУНКЦІЇ:\n"
        
        for func_name, func_info in self.functions.items():
            prompt += f"\n🔧 {func_info['name']}\n"
            prompt += f"   Опис: {func_info['description']}\n"
            
            if func_info['parameters']:
                prompt += "   Параметри:\n"
                for param_name, param_desc in func_info['parameters'].items():
                    prompt += f"   • {param_name}: {param_desc}\n"
        
        prompt += """
ПРАВИЛА ВИБОРУ ФУНКЦІЇ:
1. Якщо користувач говорить код → execute_python_code
2. Якщо "досліди", "знайди інформацію" → research_topic
3. Якщо "встанови", "pip install" → shell_execute
4. Якщо "відкрий", "закрий" → open_program/close_program
5. Якщо математика → calculate

ВИЗНАЧ НАМІР БЕЗ ПОЯСНЕНЬ!
"""
        
        return prompt
    
    def execute_function(self, action, params):
        """Виконати функцію за назвою"""
        if action not in self.functions:
            return f"{Fore.RED}❌ Функція {action} не знайдена"
        
        try:
            func = self.functions[action]['function']
            result = func(**params)
            return result
        except Exception as e:
            return f"{Fore.RED}❌ Помилка виконання {action}: {str(e)}"