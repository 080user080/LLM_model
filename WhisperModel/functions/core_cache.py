import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from colorama import Fore

class CacheManager:
    """Менеджер кешування команд з автоматичним виконанням дій"""
    
    def __init__(self, registry, cache_duration_hours=24):
        self.cache_file = Path(__file__).parent / "cache_data.json"
        self.cache_duration = timedelta(hours=cache_duration_hours)
        self.registry = registry
        self.cache = self._load_cache()
        
        print(f"{Fore.MAGENTA}💾 Кеш: {len(self.cache)} записів")
    
    def _load_cache(self):
        """Завантажити кеш з файлу"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    
                    # Очистити прострочені записи при завантаженні
                    cleaned_cache = {}
                    now = datetime.now()
                    
                    for key, entry in cache_data.items():
                        timestamp = datetime.fromisoformat(entry['timestamp'])
                        if now - timestamp < self.cache_duration:
                            cleaned_cache[key] = entry
                    
                    # Зберегти очищений кеш
                    if len(cleaned_cache) != len(cache_data):
                        cache_data = cleaned_cache
                        with open(self.cache_file, 'w', encoding='utf-8') as f:
                            json.dump(cache_data, f, ensure_ascii=False, indent=2)
                    
                    return cache_data
            except Exception as e:
                print(f"{Fore.RED}❌ Помилка завантаження кешу: {e}")
                return {}
        return {}
    
    def _save_cache(self):
        """Зберегти кеш"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"{Fore.RED}❌ Помилка кешу: {e}")
    
    def _extract_action_info(self, command_text, response):
        """Визначити, яку дію потрібно виконати на основі команди та відповіді"""
        command_lower = command_text.lower()
        response_lower = response.lower()
        
        # Словники для відображення команд на дії
        action_patterns = [
            {
                'patterns': ['відкрий', 'відкрити', 'запусти', 'запустіть', 'open', 'start', 'run'],
                'action': 'open_program',
                'param_key': 'program_name',
                'extract_from_response': True
            },
            {
                'patterns': ['закрий', 'закрити', 'вимкни', 'виключи', 'close', 'kill', 'terminate'],
                'action': 'close_program',
                'param_key': 'process_name',
                'extract_from_response': True
            },
            {
                'patterns': ['порахуй', 'обчисли', 'скільки', 'calculate', 'compute'],
                'action': 'calculate',
                'param_key': 'expression',
                'extract_from_response': False
            }
        ]
        
        # Знайти програму в команді
        known_programs = {
            'блокнот': 'notepad',
            'notepad': 'notepad',
            'хром': 'chrome',
            'chrome': 'chrome',
            'браузер': 'chrome',
            'провідник': 'explorer',
            'explorer': 'explorer'
        }
        
        for pattern_info in action_patterns:
            for pattern in pattern_info['patterns']:
                if pattern in command_lower:
                    # Знайти назву програми в команді
                    program_name = None
                    
                    # Шукаємо програму в команді
                    for prog_ua, prog_en in known_programs.items():
                        if prog_ua in command_lower or prog_en in command_lower:
                            program_name = prog_en
                            break
                    
                    # Якщо не знайшли в команді, спробуємо витягти з відповіді
                    if not program_name and pattern_info['extract_from_response']:
                        for prog_ua, prog_en in known_programs.items():
                            if prog_ua in response_lower or prog_en in response_lower:
                                program_name = prog_en
                                break
                    
                    if program_name:
                        return {
                            'action': pattern_info['action'],
                            'params': {pattern_info['param_key']: program_name}
                        }
        
        return None
    
    def get(self, command_text):
        """Отримати з кешу відповідь та інформацію про дію"""
        key = command_text.lower().strip()
        
        if key in self.cache:
            entry = self.cache[key]
            timestamp = datetime.fromisoformat(entry['timestamp'])
            
            if datetime.now() - timestamp < self.cache_duration:
                # Оновити лічильник використань
                entry['hits'] = entry.get('hits', 0) + 1
                self._save_cache()
                
                # Повернути відповідь та інформацію про дію
                response = entry['response']
                action_info = entry.get('action_info')
                
                return response, action_info
            
            else:
                # Видалити прострочений запис
                del self.cache[key]
                self._save_cache()
        
        return None, None
    
    def set(self, command_text, response):
        """Додати в кеш разом з інформацією про дію"""
        key = command_text.lower().strip()
        
        # Визначити інформацію про дію
        action_info = self._extract_action_info(command_text, response)
        
        self.cache[key] = {
            'response': response,
            'action_info': action_info,
            'timestamp': datetime.now().isoformat(),
            'hits': 0
        }
        self._save_cache()
    
    def execute_cached_action(self, action_info):
        """Виконати дію з кешованої інформації"""
        if not action_info:
            return None
        
        try:
            action = action_info.get('action')
            params = action_info.get('params', {})
            
            if action and action in self.registry.functions:
                print(f"{Fore.MAGENTA}⚡ [Виконую з кешу]: {action} з параметрами {params}")
                result = self.registry.execute_function(action, params)
                return result
            else:
                print(f"{Fore.YELLOW}⚠️  Дія {action} не знайдена в реєстрі")
                return None
        except Exception as e:
            print(f"{Fore.RED}❌ Помилка виконання з кешу: {e}")
            return None