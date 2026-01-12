import os
from datetime import datetime

DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")

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
    name="create_file",
    description="створення txt файлу на робочому столі",
    parameters={
        "filename": "назва файлу (можна без .txt)",
        "content": "текстовий вміст файлу"
    }
)
def create_file(filename, content):
    """Створити txt файл на робочому столі"""
    try:
        if not filename.endswith('.txt'):
            filename += '.txt'
        
        filepath = os.path.join(DESKTOP_PATH, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return f"✅ Файл створено: {filename} на робочому столі"
    except Exception as e:
        return f"❌ Помилка створення файлу: {str(e)}"