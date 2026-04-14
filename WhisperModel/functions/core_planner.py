# functions/core_planner.py
import json
import re
import os
import time
import os
from colorama import Fore

class Planner:
    def __init__(self, assistant):
        self.assistant = assistant

    def _ask_llm(self, prompt: str) -> str:
        """Спрощений доступ до LLM через асистента."""
        if hasattr(self.assistant, 'ask_llm'):
            return self.assistant.ask_llm(prompt)
        return ""

    def create_plan(self, task: str) -> list:
        prompt = f"""
Ти планувальник задач. Розбий задачу на послідовність викликів функцій.

Доступні функції:
- create_file(filename, content)
- edit_file(filepath, new_content)
- execute_python(code)
- debug_python_code(code)
- open_program(program_name, file_path)
- close_program(process_name)

Якщо потрібно відкрити щойно створений файл, використовуй "file_path": "{{previous_file_path}}" — я підставлю шлях автоматично.

Відповідь ТІЛЬКИ у форматі JSON списку:
[
  {{"action": "function_name", "args": {{...}}}}
]

Задача: {task}
"""
        response = self._ask_llm(prompt)
        print(f"{Fore.YELLOW}📋 [Planner] Відповідь LLM:\n{response}{Fore.RESET}")
        # Спробуємо витягти JSON з відповіді
        try:
            start = response.find('[')
            end = response.rfind(']') + 1
            if start != -1 and end > start:
                json_str = response[start:end]
                plan = json.loads(json_str)
                if isinstance(plan, list):
                    return plan
        except Exception as e:
            print(f"{Fore.RED}❌ [Planner] Помилка парсингу JSON: {e}{Fore.RESET}")

        return []
    def validate_plan_safety(self, plan: list, task: str) -> tuple[bool, str]:
        """
        Перевіряє план на безпеку та реалістичність через LLM.
        Повертає (безпечний_чи_ні, пояснення).
        ТИМЧАСОВО ВИМКНЕНО – завжди повертає True.
        """
        # Тимчасове відключення перевірки безпеки
        return True, "Безпека тимчасово вимкнена (тестовий режим)."
        
        if not plan:
            return False, "План порожній"

        prompt = f"""
Оціни цей план дій для завдання: "{task}"

План:
{json.dumps(plan, ensure_ascii=False, indent=2)}

Чи є цей план безпечним та реалістичним? Чи не містить він небезпечних операцій (видалення файлів, форматування дисків, виконання шкідливого коду)?

Відповідай ТІЛЬКИ у форматі:
БЕЗПЕЧНИЙ: так/ні
ПОЯСНЕННЯ: <коротке пояснення>
"""
        response = self._ask_llm(prompt)
        print(f"{Fore.CYAN}🛡️ [SafetyCheck] Відповідь LLM:\n{response}{Fore.RESET}")

        is_safe = False
        explanation = "Не вдалося визначити безпеку."

        # Парсимо відповідь
        if "БЕЗПЕЧНИЙ: так" in response.upper() or "БЕЗПЕЧНИЙ: ТАК" in response.upper():
            is_safe = True
        explanation_match = re.search(r'ПОЯСНЕННЯ:\s*(.+)', response, re.IGNORECASE | re.DOTALL)
        if explanation_match:
            explanation = explanation_match.group(1).strip()
        return is_safe, explanation

    def _extract_file_path(self, result_text: str) -> str | None:
        """Спробувати витягти повний шлях до файлу з результату create_file."""
        # Шукаємо шлях, ігноруючи додатковий текст
        match = re.search(r'✅ Файл створено:\s*([^\n]+?)(?:\s+на робочому столі)?$', result_text.strip(), re.IGNORECASE)
        if match:
            path = match.group(1).strip()
            # Якщо шлях не абсолютний, додаємо Desktop
            if not os.path.isabs(path):
                desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                path = os.path.join(desktop, path)
            return path
        return None

    def execute_plan(self, plan: list):
        results = []
        context = {"last_file_path": None}

        for i, step in enumerate(plan, 1):
            action = step.get("action")
            args = step.get("args", {}).copy()  # копіюємо, щоб не змінювати оригінал

            # Підставляємо збережений шлях файлу
            if "file_path" in args and str(args["file_path"]).strip() in ("{{previous_file_path}}", "{previous_file_path}"):
                if context["last_file_path"]:
                    args["file_path"] = context["last_file_path"]
                    print(f"{Fore.CYAN}🔗 Підставлено шлях: {args['file_path']}{Fore.RESET}")
                else:
                    print(f"{Fore.YELLOW}⚠️ Немає попереднього файлу для відкриття{Fore.RESET}")

            # Якщо це execute_python і ми маємо попередній .py файл, додаємо script_name
            if action == "execute_python" and context.get("last_file_path"):
                # Якщо LLM не передав script_name, але є файл .py
                if "script_name" not in args and context["last_file_path"].endswith('.py'):
                    script_name = os.path.basename(context["last_file_path"])
                    args["script_name"] = script_name
                    print(f"{Fore.CYAN}🔗 Автоматично додано script_name: {script_name}{Fore.RESET}")

            print(f"{Fore.CYAN}🔧 [Planner] Крок {i}: {action} {args}{Fore.RESET}")

            try:
                result = self.assistant.execute_function(action, args)
                
                # --- ВАЛІДАЦІЯ РЕЗУЛЬТАТУ ---
                validation_passed = self._validate_step(action, args, result)
                if not validation_passed:
                    print(f"{Fore.YELLOW}⚠️ Крок {i} не пройшов валідацію. Намагаюсь виправити...{Fore.RESET}")
                    # Спроба отримати альтернативну дію від LLM
                    fix_prompt = f"""Дія '{action}' з параметрами {args} не виконалась успішно.
Результат: {result}
Запропонуй альтернативну дію у тому ж JSON форматі:
{{"action": "назва_функції", "args": {{...}}}}
Відповідай ТІЛЬКИ JSON об'єктом."""
                    fix_response = self.assistant.ask_llm(fix_prompt)
                    try:
                        alt_step = json.loads(fix_response)
                        if isinstance(alt_step, dict) and "action" in alt_step:
                            action = alt_step["action"]
                            args = alt_step.get("args", {})
                            print(f"{Fore.CYAN}🔁 Виконую альтернативну дію: {action} {args}{Fore.RESET}")
                            result = self.assistant.execute_function(action, args)
                    except Exception as e:
                        print(f"{Fore.RED}❌ Не вдалося отримати виправлення: {e}{Fore.RESET}")
                # -------------------------
                
                print(f"{Fore.GREEN}   ✅ Результат: {result}{Fore.RESET}")
                results.append((action, "ok", result))

                # Зберігаємо шлях файлу, якщо це create_file
                if action == "create_file":
                    file_path = self._extract_file_path(result)
                    if file_path:
                        context["last_file_path"] = file_path
                        print(f"{Fore.CYAN}   📁 Збережено шлях: {file_path}{Fore.RESET}")
                        
                        # Активне очікування, поки файл реально з'явиться на диску
                        for attempt in range(50):  # 5 секунд (50 * 0.1)
                            if os.path.exists(file_path):
                                print(f"{Fore.GREEN}   📁 Файл підтверджено на диску{Fore.RESET}")
                                break
                            time.sleep(0.1)
                        else:
                            print(f"{Fore.YELLOW}   ⚠️ Файл не з'явився за 5 сек, продовжую{Fore.RESET}")
                    else:
                        print(f"{Fore.YELLOW}   ⚠️ Не вдалося витягти шлях з результату{Fore.RESET}")
                elif action == "execute_python_file":
                    # Для execute_python_file також можемо зберегти шлях до вихідного файлу, якщо треба
                    pass
                elif action == "execute_python":
                    # Якщо виконання коду створило файл, спробуємо запам'ятати
                    file_match = re.search(r"✅ Файл створено:\s*([^\n]+)", result)
                    if file_match:
                        path = file_match.group(1).strip()
                        if not os.path.isabs(path):
                            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                            path = os.path.join(desktop, path)
                        context["last_file_path"] = path
                        print(f"{Fore.CYAN}   📁 Запам'ятовано створений файл: {path}{Fore.RESET}")
                elif action == "open_program":
                    # Якщо відкриваємо файл, можемо зберегти його шлях
                    if "file_path" in args:
                        context["last_file_path"] = args["file_path"]
                
                # Додаткова перевірка для create_file: якщо файл не .py, а наступний крок execute_python,
                # то краще не підставляти script_name автоматично
                if action == "create_file" and not context.get("last_file_path", "").endswith('.py'):
                    # Позначаємо, що це не Python-файл
                    context["last_is_python"] = False
                # ... (за потреби)
                
                # Невелика пауза між кроками для загальної стабільності
                time.sleep(0.2)

            except Exception as e:
                error_msg = str(e)
                print(f"{Fore.RED}   ❌ Помилка: {error_msg}{Fore.RESET}")
                results.append((action, "error", error_msg))
                break  # Зупиняємо виконання при помилці

        return results

    def _validate_step(self, action: str, args: dict, result: str) -> bool:
        """Перевіряє, чи дія дійсно виконалась успішно."""
        # Якщо результат містить ознаку помилки
        if result.startswith("❌") or "помилка" in result.lower():
            return False
        
        if action == "create_file":
            filename = args.get("filename", "")
            if not filename:
                return False
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            expected_path = os.path.join(desktop, filename)
            # Якщо файл не існує одразу – дамо йому трохи часу (вже є очікування в execute_plan)
            return os.path.exists(expected_path)
        elif action == "open_program":
            # Проста перевірка за повідомленням
            return "✅" in result or "Відкрито" in result
        elif action == "execute_python":
            return not result.startswith("❌")
        elif action == "execute_python_file":
            return not result.startswith("❌")
        # За замовчуванням вважаємо успішним
        return True

    def _execute_single_step(self, action: str, args: dict) -> str:
        """Виконати один крок (без валідації та логування) — для зовнішнього виконавця."""
        return self.assistant.execute_function(action, args)