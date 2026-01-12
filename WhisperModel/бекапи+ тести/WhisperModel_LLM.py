import os
import sys

# Додати шляхи до CUDA бібліотек
venv_path = sys.prefix
nvidia_paths = [
    os.path.join(venv_path, 'Lib', 'site-packages', 'nvidia', 'cublas', 'bin'),
    os.path.join(venv_path, 'Lib', 'site-packages', 'nvidia', 'cudnn', 'bin'),
    os.path.join(venv_path, 'Lib', 'site-packages', 'nvidia', 'cuda_runtime', 'bin'),
]

for path in nvidia_paths:
    if os.path.exists(path):
        os.environ['PATH'] = path + os.pathsep + os.environ['PATH']
        try:
            os.add_dll_directory(path)
        except:
            pass

import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import requests
import json
import re
from datetime import datetime

# Налаштування
SAMPLE_RATE = 16000
DURATION = 5  # секунд запису
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"

# Шлях до робочого столу
DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")

def create_file_on_desktop(filename, content):
    """Створити txt файл на робочому столі"""
    try:
        # Якщо не вказано розширення, додати .txt
        if not filename.endswith('.txt'):
            filename += '.txt'
            
        filepath = os.path.join(DESKTOP_PATH, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"✅ Файл створено: {filename}"
    except Exception as e:
        return f"❌ Помилка створення файлу: {str(e)}"

def extract_json_from_text(text):
    """Витягти JSON з тексту, навіть якщо він в markdown блоках"""
    # Спробувати знайти JSON в markdown блоках
    json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()
    
    # Спробувати знайти JSON в звичайних блоках
    json_match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()
    
    # Спробувати знайти JSON без блоків
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        return json_match.group(0).strip()
    
    return text.strip()

def ask_llm(user_message, conversation_history):
    """Відправити запит до LM Studio з функціями"""
    try:
        # Системний промпт з інструкціями для LLM
        system_prompt = """Ти корисний асистент з доступом до функцій. Відповідай українською мовою коротко і по суті.

ДОСТУПНІ ФУНКЦІЇ:
1. create_file - створення txt файлу на робочому столі
   Параметри:
   - filename: назва файлу (можна без розширення, .txt додасться автоматично)
   - content: текстовий вміст файлу

Коли користувач просить створити файл, відповідай ТІЛЬКИ JSON (без markdown блоків):
{
  "action": "create_file",
  "filename": "назва_файлу",
  "content": "текст для файлу"
}

Якщо це звичайна розмова, просто відповідай текстом."""

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})
        
        response = requests.post(LM_STUDIO_URL, 
            json={
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 512,
                "stream": False
            },
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"Помилка: {response.status_code}"
    except requests.exceptions.ConnectionError:
        return "❌ Не можу з'єднатися з LM Studio. Переконайся, що сервер запущений!"
    except Exception as e:
        return f"❌ Помилка: {str(e)}"

def process_llm_response(response_text):
    """Обробити відповідь LLM і виконати функції якщо потрібно"""
    # Витягти JSON з тексту
    json_text = extract_json_from_text(response_text)
    
    try:
        # Спробувати розпарсити як JSON
        response_json = json.loads(json_text)
        
        if response_json.get("action") == "create_file":
            filename = response_json.get("filename", f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            content = response_json.get("content", "")
            result = create_file_on_desktop(filename, content)
            return result
    except json.JSONDecodeError as e:
        # Якщо не JSON, повернути як звичайний текст
        print(f"[Debug] Не вдалося розпарсити JSON: {e}")
        print(f"[Debug] Текст: {json_text[:100]}...")
        pass
    
    return response_text

print("Завантаження Whisper моделі...")
whisper_model = WhisperModel(
    "medium",
    device="cuda",
    compute_type="float16"
)

print("Перевірка з'єднання з LM Studio...")
try:
    test_response = requests.get("http://localhost:1234/v1/models", timeout=5)
    if test_response.status_code == 200:
        models = test_response.json()
        print(f"✅ LM Studio підключено! Модель: {models['data'][0]['id']}")
    else:
        print("⚠️  LM Studio працює, але є проблеми з API")
except:
    print("❌ LM Studio не запущений! Запусти сервер в LM Studio.")
    exit()

print(f"📁 Робочий стіл: {DESKTOP_PATH}")
print("\n=== Готово! ===\n")

# Історія розмови
conversation_history = []

while True:
    print("Натисни Enter щоб почати запис (або 'q' для виходу)...")
    user_input = input()
    
    if user_input.lower() == 'q':
        print("Вихід...")
        break
    
    print(f"🎤 Говори ({DURATION} секунд)...")
    
    # Запис аудіо
    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype=np.float32
    )
    sd.wait()
    
    audio = np.squeeze(audio)
    
    # Розпізнавання мовлення
    print("🔍 Розпізнаю...")
    segments, info = whisper_model.transcribe(
        audio,
        language="uk"
    )
    
    recognized_text = ""
    for seg in segments:
        recognized_text += seg.text
    
    if not recognized_text.strip():
        print("Нічого не розпізнано. Спробуй ще раз.\n")
        continue
    
    print(f"\n💬 [Ти сказав]: {recognized_text}")
    
    # Додати до історії
    conversation_history.append({"role": "user", "content": recognized_text})
    
    # Відправка до LLM
    print("🤔 [LLM думає...]")
    
    answer = ask_llm(recognized_text, conversation_history)
    
    print(f"\n[Debug] Сира відповідь LLM: {answer}\n")
    
    # Обробити відповідь (виконати функції якщо потрібно)
    final_answer = process_llm_response(answer)
    
    # Додати до історії
    conversation_history.append({"role": "assistant", "content": answer})
    
    print(f"\n🤖 [Відповідь]: {final_answer}\n")
    print("-" * 60 + "\n")
    
    # Обмежити історію до 10 останніх повідомлень
    if len(conversation_history) > 10:
        conversation_history = conversation_history[-10:]