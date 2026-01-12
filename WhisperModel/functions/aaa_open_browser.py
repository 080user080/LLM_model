import webbrowser

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
    name="open_browser",
    description="відкрити сайт у браузері",
    parameters={
        "url": "адреса сайту (наприклад: https://google.com або просто google.com)"
    }
)
def open_browser(url):
    """Відкрити URL у браузері"""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    webbrowser.open(url)
    return f"✅ Відкрито: {url}"