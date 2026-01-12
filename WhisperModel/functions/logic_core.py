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
        """Згенерувати Voice-First system prompt"""
        from .config import ASSISTANT_NAME, ASSISTANT_MODES, ACTIVE_MODE
        
        mode = ASSISTANT_MODES[ACTIVE_MODE]
        
        prompt = f"""ТИ: Голосовий асистент {ASSISTANT_NAME}

МОВА: Українська, розмовна
СТИЛЬ: {mode['style']}
РЕЖИМ: {ACTIVE_MODE} (максимум {mode['max_words']} слів, {mode['max_sentences']} речення)

ПРАВИЛА ГОЛОСОВОЇ ВЗАЄМОДІЇ:
1. Відповідь = {mode['max_sentences']} речення максимум
2. Дія → виконай → підтверди одним словом
3. БЕЗ вступів: "Звичайно", "З радістю", "Дозвольте"
4. БЕЗ пояснень: "Я зробив X тому що Y"
5. ТІЛЬКИ факти та результати
6. ОБОВЯЗКОВО в кінці кожного речення крапка чи інший розділовий знак закінчення речення.

ПРИКЛАДИ ВІДПОВІДЕЙ ({ACTIVE_MODE} режим):
"""
        
        for example in mode['examples']:
            prompt += f"• {example}\n"
        
        prompt += """
ВИЗНАЧ НАМІР:
1. КОМАНДА - є дієслово (відкрий, закрий, знайди...) → ВИКОНАЙ
2. ПИТАННЯ - є питальне слово (що, де, коли...) → ВІДПОВІДЬ
3. НОВИНА/ШУМ - довгий текст БЕЗ запиту → {"response":"Слухаю."}
4. НЕЗРОЗУМІЛО - нечітко → {"response":"Не зрозумів."}

ФОРМАТ (одне з двох):
1. ДІЯ: {"action":"функція","параметр":"значення"}
2. ВІДПОВІДЬ: {"response":"текст"}

НІКОЛИ:
• Текст поза JSON
• Токени <|start|>, <|end|>, commentary
• Кілька JSON об'єктів
• Пояснення чому ти щось робиш

ПРІОРИТЕТИ:
1. ШВИДКІСТЬ > точність (краще помилитись швидко)
2. ДІЯ > розмова (завжди спробуй виконати)
3. СТИСЛІСТЬ > повнота (1 слово > 10 слів)

ЗАБОРОНЕНІ ФРАЗИ:
"Звичайно", "Я допоможу", "Дозвольте", "З радістю", "Будь ласка", "Один момент"

ДОЗВОЛЕНІ ВІДПОВІДІ:
"Готово", "Відкрив", "Не знайдено", "Помилка", "Слухаю", "Так", "Ні"

"""
        
        if not self.functions:
            return prompt + "\n\nФункції недоступні."
        
        prompt += "\nДОСТУПНІ ФУНКЦІЇ:\n"
        
        for func_name, func_info in self.functions.items():
            prompt += f"\n🔧 {func_info['name']}\n"
            prompt += f"   Опис: {func_info['description']}\n"
            
            if func_info['parameters']:
                prompt += "   Параметри:\n"
                for param_name, param_desc in func_info['parameters'].items():
                    prompt += f"   • {param_name}: {param_desc}\n"
        
        prompt += """
ПРИКЛАДИ ВИКОНАННЯ:

Користувач: "відкрий блокнот"
Ти: {"action":"open_program","program_name":"notepad"}

Користувач: "який час"
Ти: {"response":"Пятнадцята година тридцять хвилин."}

Користувач: [довгий текст новини без питання]
Ти: {"response":"Слухаю."}

Користувач: "абракадабра шум"
Ти: {"response":"Не зрозумів."}

ПАМ'ЯТАЙ: Ти голосовий асистент. Люди чують твої відповіді. Будь стислим!
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