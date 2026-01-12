import requests
import json
from colorama import Fore

class StreamingHandler:
    """Обробник стрімінгу відповідей від LLM"""
    
    def __init__(self, api_url):
        self.api_url = api_url
    
    def stream_response(self, messages):
        """Отримати відповідь у стрімінг режимі"""
        try:
            response = requests.post(
                self.api_url,
                json={
                    "messages": messages,
                    "temperature": 0.1,
                    "max_tokens": 8000,
                    "stream": True
                },
                stream=True,
                timeout=60
            )
            
            full_text = ""
            print(f"{Fore.GREEN} [МАРК]: {Fore.WHITE}", end="", flush=True)
            
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == '[DONE]':
                            break
                        try:
                            json_data = json.loads(data)
                            delta = json_data['choices'][0]['delta']
                            if 'content' in delta:
                                content = delta['content']
                                print(content, end="", flush=True)
                                full_text += content
                        except:
                            pass
            
            print()  # Новий рядок після стрімінгу
            return full_text
            
        except Exception as e:
            return f"❌ Помилка стрімінгу: {str(e)}"

def init():
    """Ініціалізація модуля"""
    pass