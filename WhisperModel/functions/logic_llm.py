# functions/logic_llm.py
"""Робота з LLM"""
import re
import json
import requests
from colorama import Fore
from .config import LM_STUDIO_URL

def extract_json_from_text(text):
    """Витягти JSON з тексту"""
    # Видалити всі токени LM Studio
    clean_text = re.sub(r'<\|[^|]+\|>', '', text)
    
    # Видалити службові слова та коментарі
    clean_text = re.sub(r'assistant|channel|commentary|constrain|message|to=functions\.\w+', '', clean_text, flags=re.IGNORECASE)
    
    # Видалити все після останньої закриваючої дужки
    if '}' in clean_text:
        clean_text = clean_text[:clean_text.rfind('}') + 1]
    
    # Видалити все перед першою відкриваючою дужкою
    if '{' in clean_text:
        clean_text = clean_text[clean_text.find('{'):]
    
    clean_text = clean_text.strip()
    
    # Якщо це JSON в блоках ```json ... ```
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', clean_text, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()
    
    # Якщо це JSON в блоках ``` ... ```
    json_match = re.search(r'```\s*(\{.*?\})\s*```', clean_text, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()
    
    # Якщо є тільки JSON об'єкт
    json_match = re.search(r'(\{.*?\})', clean_text, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()
    
    # Якщо нічого не знайдено, повертаємо як response
    return json.dumps({"response": text.strip()})

def ask_llm(user_message, conversation_history, system_prompt):
    """Відправити запит до LM Studio"""
    try:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})
        
        # 🔥 ВИПРАВЛЕННЯ: Додано поле "model", яке вимагає API
        response = requests.post(LM_STUDIO_URL, 
            json={
                "model": "local-model",  # Це поле обов'язкове для сумісності з OpenAI API
                "messages": messages,
                "temperature": 0.0,
                "max_tokens": 1024,
                "stream": False
            },
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            # 🔥 ВИПРАВЛЕННЯ: Виводимо текст помилки від сервера
            error_msg = f"Помилка API {response.status_code}: {response.text}"
            print(f"{Fore.RED}{error_msg}")
            return f"Помилка: {response.status_code}"
            
    except Exception as e:
        return f"{Fore.RED}❌ Помилка з'єднання: {str(e)}"

def process_llm_response(response_text, registry):
    """Обробити відповідь LLM і виконати функції"""
    # Спершу спробувати отримати чистий JSON
    json_text = extract_json_from_text(response_text)
    
    print(f"{Fore.LIGHTBLACK_EX}📦 [Спроба парсингу]: {json_text[:200]}...")
    
    try:
        response_json = json.loads(json_text)
        
        # Якщо це відповідь
        if "response" in response_json:
            return response_json["response"]
        
        # Якщо це команда з явним action
        if "action" in response_json:
            action = response_json.pop("action")
            
            # Логування перед виконанням
            print(f"{Fore.MAGENTA}⚡ [Виконую]: {action} з параметрами {response_json}")
            
            result = registry.execute_function(action, response_json)
            return result
        
        # Якщо немає action, але є program_name, то це, ймовірно, відкриття програми
        if "program_name" in response_json:
            print(f"{Fore.MAGENTA}⚡ [Виконую open_program, оскільки знайдено program_name]")
            result = registry.execute_function("open_program", response_json)
            return result
        
        # Якщо невідомий формат
        return f"❌ Невідомий формат команди: {response_json}"
        
    except json.JSONDecodeError as e:
        print(f"{Fore.YELLOW}⚠️ [JSON помилка]: {e}")
        print(f"{Fore.YELLOW}⚠️ [Оригінал]: {response_text}")
        
        # Якщо не вдалося розпарсити, спробуємо витягти JSON з токенів вручну
        if "to=functions.open_program" in response_text:
            json_match = re.search(r'<\|message\|>(\{.*?\})', response_text)
            if json_match:
                try:
                    json_str = json_match.group(1)
                    response_json = json.loads(json_str)
                    if "program_name" in response_json:
                        print(f"{Fore.MAGENTA}⚡ [Знайдено через токени]: open_program")
                        result = registry.execute_function("open_program", response_json)
                        return result
                except:
                    pass
        
        return response_text
    except Exception as e:
        return f"{Fore.RED}❌ Помилка обробки: {str(e)}"