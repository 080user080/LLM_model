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

# Налаштування
SAMPLE_RATE = 16000
DURATION = 3  # секунд запису
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"

def ask_llm(user_message):
    """Відправити запит до LM Studio"""
    try:
        response = requests.post(LM_STUDIO_URL, 
            json={
                "messages": [
                    {"role": "system", "content": "Ти корисний асистент. Відповідай українською мовою коротко і по суті."},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.2,
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

print("Завантаження Whisper моделі...")
whisper_model = WhisperModel(
    "medium",
    device="cuda",
    compute_type="float16"
)

print("Перевірка з'єднання з LM Studio...")
try:
    test_response = requests.get("http://localhost:1234/v1/models", timeout=1)
    if test_response.status_code == 200:
        models = test_response.json()
        print(f"✅ LM Studio підключено! Модель: {models['data'][0]['id']}")
    else:
        print("⚠️  LM Studio працює, але є проблеми з API")
except:
    print("❌ LM Studio не запущений! Запусти сервер в LM Studio.")
    exit()

print("\n=== Готово! ===\n")

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
    
    # Відправка до LLM
    print("🤔 [LLM думає...]")
    
    answer = ask_llm(recognized_text)
    
    print(f"\n🤖 [Відповідь]: {answer}\n")
    print("-" * 60 + "\n")