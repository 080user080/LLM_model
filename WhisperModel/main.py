# main.py
"""Головний файл запуску з покращеним розпізнаванням"""
import os
import sys
import time
from pathlib import Path
from colorama import Fore, Back, Style, init
import threading

# Ініціалізувати colorama
init(autoreset=True)

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
import torch
import requests

# Імпорт модулів
from functions.logic_core import FunctionRegistry
from functions.logic_commands import VoiceAssistant
from functions.logic_audio import (
    should_ignore_command, correct_whisper_text, 
    check_volume, check_activation_word, remove_activation_word,
    text_similarity
)
from functions.logic_audio_filtering import get_audio_filter
from functions.logic_continuous_listener import create_continuous_listener
from functions.logic_tts import TTSEngine
from functions.config import (
    SAMPLE_RATE, LISTEN_DURATION, VOLUME_THRESHOLD,
    ACTIVATION_WORD, ACTIVATION_LISTEN_DURATION, COMMAND_LISTEN_DURATION, 
    MICROPHONE_DEVICE_ID, CONTINUOUS_MODE,
    ASSISTANT_NAME, ASSISTANT_EMOJI, ASSISTANT_DISPLAY_NAME,
    TTS_ENABLED, TTS_DEVICE, TTS_CACHE_DIR, TTS_MODEL_DIR, TTS_VOICES_DIR,
    TTS_DEFAULT_VOICE, TTS_SPEECH_RATE, TTS_VOLUME, TTS_SPEAK_PREFIXES
)

# Вивід інформації про мікрофони
print("\n" + "="*60)
print("🎤 ДОСТУПНІ МІКРОФОНИ:")
print("="*60)
print(sd.query_devices())
print("="*60 + "\n")

if MICROPHONE_DEVICE_ID is not None:
    print(f"{Fore.YELLOW}🎤 Вибрано мікрофон #{MICROPHONE_DEVICE_ID}")
    device_info = sd.query_devices(MICROPHONE_DEVICE_ID)
    print(f"   Назва: {device_info['name']}")
    print(f"   Канали: {device_info['max_input_channels']}")
else:
    print(f"{Fore.YELLOW}🎤 Використовується системний мікрофон за замовчуванням")
    default_input = sd.query_devices(kind='input')
    print(f"   Назва: {default_input['name']}")
print()

# Тестовий запис
print("🧪 Тестовий запис 2 секунди...")
test_audio = sd.rec(
    int(2 * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype=np.float32,
    device=MICROPHONE_DEVICE_ID,
    blocking=True
)
volume = np.abs(test_audio).mean()
print(f"   Середня гучність: {volume:.6f}")
print(f"   Поріг: {VOLUME_THRESHOLD}")

if volume < 0.01:
    print(f"{Fore.RED}   ⚠️  ДУЖЕ ТИХО! Гучність {volume:.6f} < 0.01")
    print(f"{Fore.YELLOW}   💡 Підвищте гучність мікрофона в Windows:")
    print(f"{Fore.YELLOW}      1. Правий клік на звук → Налаштування")
    print(f"{Fore.YELLOW}      2. Введення → USB2.0 Camera → Властивості")
    print(f"{Fore.YELLOW}      3. Рівні → Мікрофон 100% + Підсилення +20dB")
elif volume > VOLUME_THRESHOLD:
    print(f"   ✅ Мікрофон працює!")
else:
    print(f"   ❌ Занадто тихо")
print()

from functions.logic_stt import get_stt_engine

def load_stt_model():
    """Завантажити STT двигун"""
    try:
        stt_engine = get_stt_engine()
        available_models = stt_engine.get_available_models()
        
        if not available_models:
            print(f"{Fore.RED}   ❌ Немає доступних моделей STT")
            raise Exception("Не вдалося завантажити жодну модель STT")
        
        print(f"   ✅ Моделі завантажені: {', '.join(available_models)}")
        print(f"   🎯 Пристрій: {stt_engine.device}")
        
        return stt_engine
        
    except Exception as e:
        print(f"   ❌ Помилка завантаження моделей STT: {e}")
        raise

def transcribe_audio(audio, stt_engine, audio_filter):
    """Транскрибувати аудіо через STT двигун"""
    try:
        print(f"{Fore.CYAN}🔧 Початкова довжина: {len(audio)/SAMPLE_RATE:.1f}с")
        print(f"{Fore.YELLOW}🔥 ТЕСТ: фільтрація ВИМКНЕНА")
        
        # 🔥 ТЕСТ: Повністю без фільтрації!
        # audio = audio_filter.process_audio(...)
        
        print(f"{Fore.CYAN}🔧 Після фільтрації: {len(audio)/SAMPLE_RATE:.1f}с")
        
        # Перевірка гучності
        volume = np.abs(audio).mean()
        print(f"{Fore.CYAN}🔊 Середня гучність ДО підсилення: {volume:.6f}")
        
        # 🔥 КРИТИЧНО: Підсилення аудіо якщо занадто тихо!
        if volume < 0.01:  # Якщо тихіше ніж 1%
            boost_factor = 0.05 / (volume + 1e-8)  # Підсилити до 5%
            boost_factor = min(boost_factor, 50.0)  # Максимум x50
            audio = audio * boost_factor
            new_volume = np.abs(audio).mean()
            print(f"{Fore.YELLOW}🔊 ПІДСИЛЕНО x{boost_factor:.1f} → гучність: {new_volume:.6f}")
        
        # Нормалізація до [-1, 1]
        max_val = np.max(np.abs(audio))
        if max_val > 1.0:
            audio = audio / max_val
            print(f"{Fore.YELLOW}🔧 Нормалізовано (було {max_val:.2f})")
        
        # Мінімальна перевірка довжини
        if len(audio) < SAMPLE_RATE * 0.3:
            print(f"{Fore.YELLOW}⚠️  Занадто короткий запис")
            return ""
        
        # Виклик STT двигуна
        text = stt_engine.transcribe(audio)
        
        print(f"{Fore.GREEN}✅ Розпізнано: '{text}'")
        
        return text.strip()
        
    except Exception as e:
        print(f"{Fore.RED}   ❌ Помилка транскрипції: {e}")
        import traceback
        traceback.print_exc()
        return ""

def record_audio_with_countdown(duration, sample_rate, label="Запис"):
    """Записати аудіо з зворотнім відліком"""
    print(f"{Fore.CYAN}🎤 {label}: ", end="", flush=True)
    
    audio_data = []
    
    def callback(indata, frames, time_info, status):
        audio_data.append(indata.copy())
    
    stream = sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype=np.float32,
        device=MICROPHONE_DEVICE_ID,
        callback=callback
    )
    
    stream.start()
    
    # Зворотній відлік
    for i in range(duration, 0, -1):
        print(f"{Fore.YELLOW}{i}", end="", flush=True)
        time.sleep(1)
        if i > 1:
            print(f"{Fore.LIGHTBLACK_EX}...", end="", flush=True)
    
    stream.stop()
    stream.close()
    
    print(f" {Fore.GREEN}✓")
    
    if audio_data:
        audio = np.concatenate(audio_data, axis=0)
        return np.squeeze(audio)
    else:
        return np.array([])

def check_lm_studio():
    """Перевірити та автоматично завантажити потрібну модель"""
    import subprocess
    import os
    
    DESIRED_MODEL = "openai/gpt-oss-20b"
    # Правильний шлях до lms
    LMS_PATH = os.path.expanduser(r"~\.lmstudio\bin\lms.exe")
    BASE_URL = "http://localhost:1234"
    
    def get_current_model():
        try:
            response = requests.get(f"{BASE_URL}/v1/models", timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get('data') and len(data['data']) > 0:
                    return data['data'][0]['id']
        except:
            pass
        return None
    
    print(f"{Fore.CYAN}🔌 Перевірка LM Studio...")
    
    # Перевірка поточної моделі
    current_model = get_current_model()
    
    if current_model == DESIRED_MODEL:
        print(f"{Fore.GREEN}✅ Підключено до LM Studio")
        print(f"{Fore.YELLOW}   📝 Модель: {current_model}")
        return True
    
    if current_model:
        print(f"{Fore.YELLOW}⚠️  Поточна модель: {current_model}")
        print(f"{Fore.YELLOW}   Потрібна: {DESIRED_MODEL}")
    else:
        print(f"{Fore.YELLOW}⚠️  Жодної моделі не завантажено")
    
    # Автозавантаження через lms
    print(f"{Fore.CYAN}🤖 Автоматичне завантаження моделі...")
    
    try:
        process = subprocess.Popen(
            [LMS_PATH, "load", DESIRED_MODEL],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print(f"{Fore.CYAN}⏳ Очікування завантаження (до 20с)...")
        
        # Очікування з перевіркою
        for i in range(20):
            time.sleep(1)
            
            current = get_current_model()
            if current == DESIRED_MODEL:
                print(f"{Fore.GREEN}✅ Модель завантажена за {i+1}с!")
                return True
            
            if i % 3 == 0:
                print(f"{Fore.LIGHTBLACK_EX}   {i}с...")
        
        # Фінальна перевірка
        current = get_current_model()
        if current == DESIRED_MODEL:
            print(f"{Fore.GREEN}✅ Модель завантажена!")
            return True
        
        print(f"{Fore.YELLOW}⚠️  Завантаження триває довше")
        return True  # Дати шанс продовжити
        
    except Exception as e:
        print(f"{Fore.RED}❌ Помилка автозавантаження: {e}")
        print(f"{Fore.YELLOW}💡 Завантажте модель вручну")
        return False

def main():
    """Головна функція запуску"""
    print(f"{Back.BLUE}{Fore.WHITE}{'='*60}")
    print(f"{Back.BLUE}{Fore.WHITE}{ASSISTANT_EMOJI} {ASSISTANT_NAME} - Голосовий Асистент {Style.RESET_ALL}")
    print(f"{Back.BLUE}{Fore.WHITE}{'='*60}{Style.RESET_ALL}")
    
    print(f"\n{Fore.CYAN}🔧 Завантаження модулів...")
    start_time = time.time()
    registry = FunctionRegistry()
    load_time = time.time() - start_time
    print(f"{Fore.LIGHTBLACK_EX}⏱️  {load_time:.2f}с")
    
    print(f"\n{Fore.CYAN}🔊 Завантаження STT моделей...")
    start_time = time.time()
    
    try:
        stt_engine = load_stt_model()
        stt_time = time.time() - start_time
        print(f"{Fore.LIGHTBLACK_EX}⏱️  {stt_time:.2f}с")
            
    except Exception as e:
        print(f"{Fore.RED}❌ Не вдалося завантажити модель розпізнавання мови")
        print(f"{Fore.RED}   Деталі: {e}")
        return
    
    # 🎛️ Ініціалізація аудіо фільтра
    print(f"\n{Fore.CYAN}🎛️  Ініціалізація аудіо фільтрів...")
    start_time = time.time()
    audio_filter = get_audio_filter(SAMPLE_RATE)
    filter_time = time.time() - start_time
    print(f"{Fore.LIGHTBLACK_EX}⏱️  {filter_time:.2f}с")
    
    # 🔊 Ініціалізація TTS двигуна (ЯКЩО УВІМКНЕНО)
    tts_engine = None
    if TTS_ENABLED:
        print(f"\n{Fore.CYAN}🔊 Ініціалізація TTS двигуна...")
        start_time = time.time()
        try:
            tts_engine = TTSEngine()
            tts_time = time.time() - start_time
            if tts_engine.is_ready:
                print(f"{Fore.GREEN}✅ TTS двигун готовий")
                print(f"{Fore.CYAN}   Голоси: {', '.join(tts_engine.get_voices())}")
                print(f"{Fore.CYAN}   Швидкість: {tts_engine.speech_rate}")
                print(f"{Fore.CYAN}   Гучність: {tts_engine.volume}")
                print(f"{Fore.CYAN}   Пристрій: {tts_engine.device}")
                print(f"{Fore.LIGHTBLACK_EX}⏱️  {tts_time:.2f}с")
            else:
                print(f"{Fore.RED}❌ TTS двигун не готовий")
                tts_engine = None
        except Exception as e:
            print(f"{Fore.RED}❌ Помилка ініціалізації TTS: {e}")
            import traceback
            traceback.print_exc()
            tts_engine = None
    else:
        print(f"\n{Fore.YELLOW}⚠️  TTS вимкнено в налаштуваннях")
    
    print(f"\n{Fore.CYAN}🔌 Підключення до LM Studio...")
    if not check_lm_studio():
        return
    
    print(f"\n{Fore.YELLOW}{'='*60}")
    print(f"{Fore.YELLOW}📦 Функцій: {Fore.WHITE}{len(registry.functions)}")
    for func_name in registry.functions.keys():
        print(f"{Fore.CYAN}   • {func_name}")
    print(f"{Fore.YELLOW}{'='*60}{Style.RESET_ALL}")
    
    system_prompt = registry.get_system_prompt()
    
    # 🔥 НОВИЙ: Створити listener перед assistant, щоб передати його
    print(f"\n{Fore.CYAN}🎧 Створення безперервного слухача...")
    listener = create_continuous_listener(
        SAMPLE_RATE, 
        audio_filter, 
        MICROPHONE_DEVICE_ID,
        CONTINUOUS_MODE
    )
    
    if not listener:
        print(f"{Fore.RED}❌ Не вдалося створити слухача")
        return
    
    # 🔥 ОНОВЛЕНО: Передаємо stt_engine замість w2v_model
    assistant = VoiceAssistant(stt_engine, registry, system_prompt, listener=listener)
    
    # 🔥 ОНОВЛЕНО: Передаємо listener в TTS двигун (якщо він існує)
    if tts_engine and listener:
        tts_engine.listener = listener
    
    # Встановити TTS двигун в асистента
    if tts_engine:
        assistant.set_tts_engine(tts_engine)
    
    # Передати асистента в voice_input модуль
    try:
        from functions.aaa_voice_input import set_assistant
        set_assistant(assistant)
        print(f"{Fore.GREEN}✅ Асистент встановлено для voice_input")
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️  Не вдалося передати асистента: {e}")
    
    print(f"{Fore.GREEN}✅ Асистент переданий в voice_input")
    
    # Створити функцію транскрипції для continuous listener
    def transcribe_wrapper(audio):
        """Обгортка для transcribe_audio"""
        return transcribe_audio(audio, stt_engine, audio_filter)
    
    print(f"\n{Back.CYAN}{Fore.BLACK} 🎧 РЕЖИМ БЕЗПЕРЕРВНОГО ПРОСЛУХОВУВАННЯ {Style.RESET_ALL}")
    print(f"{Fore.YELLOW}💡 Говоріть природньо, асистент завжди слухає")
    
    # 🔥 Додаємо інформацію про TTS
    if tts_engine and tts_engine.is_ready:
        print(f"{Fore.CYAN}💬 TTS активовано: відповіді озвучуватимуться")
        print(f"{Fore.CYAN}   Запис буде автоматично призупинятися під час озвучення")
    
    print(f"{Fore.LIGHTBLACK_EX}💡 Ctrl+C для виходу\n")
    
    try:
        # Запустити безперервне прослуховування
        listener.start(transcribe_wrapper, assistant)
        
        # Тримати основний потік активним
        while listener.is_listening:
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}👋 Вимикаюся...")
        listener.stop()
        assistant.is_listening = False
        # 🔥 ОНОВЛЕНО: Зупинити TTS при виході
        if tts_engine:
            tts_engine.stop()

if __name__ == "__main__":
    main()