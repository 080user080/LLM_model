import re
from colorama import Fore

class Dispatcher:
    """Диспетчер швидких команд (regex router)"""
    
    def __init__(self, registry):
        self.registry = registry
        self.quick_routes = self._build_routes()
    
    def _build_routes(self):
        """Створити швидкі маршрути для частих команд"""
        return [
            # Відкриття програм
            {
                'pattern': r'відкрий\s+(блокнот|notepad)',
                'action': 'open_program',
                'params': {'program_name': 'notepad'}
            },
            {
                'pattern': r'відкрий\s+(калькулятор|calculator)',
                'action': 'open_program',
                'params': {'program_name': 'calculator'}
            },
            {
                'pattern': r'відкрий\s+(paint|пейнт)',
                'action': 'open_program',
                'params': {'program_name': 'paint'}
            },
            {
                'pattern': r'відкрий\s+(провідник|explorer)',
                'action': 'open_program',
                'params': {'program_name': 'explorer'}
            },
            {
                'pattern': r'відкрий\s+(chrome|хром)',
                'action': 'open_program',
                'params': {'program_name': 'chrome'}
            },
            
            # Відкриття сайтів
            {
                'pattern': r'відкрий\s+(?:сайт\s+)?google',
                'action': 'open_browser',
                'params': {'url': 'google.com'}
            },
            {
                'pattern': r'відкрий\s+(?:сайт\s+)?youtube',
                'action': 'open_browser',
                'params': {'url': 'youtube.com'}
            },
            
            # Математика
            {
                'pattern': r'порахуй\s+(\d+)\s*\+\s*(\d+)',
                'action': 'calculate',
                'params_from_groups': lambda m: {'expression': f'{m.group(1)}+{m.group(2)}'}
            },
            {
                'pattern': r'порахуй\s+(\d+)\s*[\-−]\s*(\d+)',
                'action': 'calculate',
                'params_from_groups': lambda m: {'expression': f'{m.group(1)}-{m.group(2)}'}
            },
            {
                'pattern': r'порахуй\s+(\d+)\s*[×*]\s*(\d+)',
                'action': 'calculate',
                'params_from_groups': lambda m: {'expression': f'{m.group(1)}*{m.group(2)}'}
            },
            
            # Час і дата
            {
                'pattern': r'який\s+(?:зараз\s+)?час',
                'action': 'get_time',
                'params': {}
            },
            {
                'pattern': r'яка\s+(?:сьогодні\s+)?дата',
                'action': 'get_date',
                'params': {}
            },
        ]
    
    def try_quick_route(self, command):
        """Спробувати знайти швидкий маршрут для команди"""
        command_lower = command.lower().strip()
        
        for route in self.quick_routes:
            match = re.search(route['pattern'], command_lower, re.IGNORECASE)
            if match:
                action = route['action']
                
                # Отримати параметри
                if 'params_from_groups' in route:
                    params = route['params_from_groups'](match)
                else:
                    params = route.get('params', {})
                
                # Виконати функцію
                if action in self.registry.functions:
                    try:
                        result = self.registry.execute_function(action, params)
                        return result
                    except:
                        return None
                
                # Спеціальні функції
                if action == 'get_time':
                    from datetime import datetime
                    return f"⏰ Зараз {datetime.now().strftime('%H:%M:%S')}"
                
                if action == 'get_date':
                    from datetime import datetime
                    return f"📅 Сьогодні {datetime.now().strftime('%d.%m.%Y')}"
        
        return None