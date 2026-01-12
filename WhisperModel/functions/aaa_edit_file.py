import os
import shutil
from datetime import datetime

def llm_function(name, description, parameters):
    """Декоратор для реєстрації функцій"""
    def decorator(func):
        func._is_llm_function = True
        func._function_name = name
        func._description = description
        func._parameters = parameters
        return func
    return decorator

@llm_function(
    name="edit_file",
    description="редагування txt або py файлів з автоматичним бекапом",
    parameters={
        "filepath": "повний шлях до файлу або назва файлу на робочому столі",
        "new_content": "новий вміст файлу (повністю замінить старий)"
    }
)
def edit_file(filepath, new_content):
    """Редагувати файл з бекапом"""
    try:
        # Якщо вказано тільки ім'я файлу, шукати на робочому столі
        if not os.path.isabs(filepath):
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            filepath = os.path.join(desktop, filepath)
        
        # Перевірити чи файл існує
        if not os.path.exists(filepath):
            return f"❌ Файл не знайдено: {filepath}"
        
        # Перевірити розширення
        if not filepath.endswith(('.txt', '.py')):
            return f"❌ Можна редагувати тільки .txt або .py файли"
        
        # Створити бекап
        backup_dir = os.path.join(os.path.dirname(filepath), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.basename(filepath)
        backup_path = os.path.join(backup_dir, f"{filename}.backup_{timestamp}")
        
        shutil.copy2(filepath, backup_path)
        
        # Записати новий вміст
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return f"✅ Файл відредаговано: {filename}\n📦 Бекап збережено: {os.path.basename(backup_path)}"
    
    except Exception as e:
        return f"❌ Помилка редагування: {str(e)}"