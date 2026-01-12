# functions/logic_continuous_listener.py
"""Безперервне прослуховування з динамічною детекцією по паузах"""
import numpy as np
import sounddevice as sd
import threading
import queue
import time
from colorama import Fore, Style
from collections import deque

class ContinuousListener:
    """Слухач з детекцією по паузах (як Whisper)"""
    
    def __init__(self, sample_rate, audio_filter, vad_model=None, vad_utils=None, device_id=None, config=None):
        self.sample_rate = sample_rate
        self.audio_filter = audio_filter
        self.device_id = device_id
        
        # Налаштування
        if config is None:
            config = {}
        
        # Детекція по паузах
        self.sound_threshold = config.get('sound_threshold', 0.025)
        self.silence_threshold = config.get('silence_threshold', 0.015)
        self.pause_duration = config.get('pause_duration', 1.0)
        self.min_speech_duration = config.get('min_speech_duration', 0.5)
        self.max_speech_duration = config.get('max_speech_duration', 10.0)
        self.command_cooldown = config.get('command_cooldown', 1.0)
        
        # Буфери
        self.audio_queue = queue.Queue()
        max_buffer = int(sample_rate * self.max_speech_duration)
        self.recording_buffer = deque(maxlen=max_buffer)
        
        # Стан
        self.is_listening = False
        self.is_recording = False  # Чи зараз записується мовлення
        self.is_paused = False     # 🔥 НОВИЙ: прапор паузи запису
        self.last_sound_time = 0
        self.recording_start_time = 0
        self.last_command_time = 0
        
        # Індикатор
        self.last_indicator_update = 0
        self.indicator_interval = 0.2
        self.silence_message_count = 0
        self.max_silence_messages = 3
        
        # Ключові слова (не використовуються - все через LLM)
        self.command_triggers = []
        
        # Звертання
        from .config import ASSISTANT_NAME
        self.address_words = [ASSISTANT_NAME.lower(), 'марк', 'mark']
        
        print(f"{Fore.GREEN}✅ ContinuousListener (динамічна детекція по паузах)")
        print(f"{Fore.YELLOW}🔊 Звук > {self.sound_threshold} | Тиша < {self.silence_threshold}")
        print(f"{Fore.YELLOW}⏸️  Пауза {self.pause_duration}с = кінець фрази")
    
    def audio_callback(self, indata, frames, time_info, status):
        """Callback для запису"""
        if status:
            print(f"{Fore.YELLOW}⚠️  {status}")
        
        # 🔥 Пропускаємо аудіо, якщо режим паузи
        if self.is_paused:
            return
        
        # Легке підсилення x5
        boosted = indata * 5.0
        self.audio_queue.put(boosted)
    
    def pause_listening(self):
        """Призупинити запис з мікрофону"""
        if self.is_listening and not self.is_paused:
            self.is_paused = True
            print(f"{Fore.YELLOW}⏸️  Запис призупинено (TTS відтворення)")
            return True
        return False
    
    def resume_listening(self):
        """Відновити запис з мікрофону"""
        if self.is_listening and self.is_paused:
            self.is_paused = False
            # Очистити чергу від даних, що накопичилися під час паузи
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break
            print(f"{Fore.YELLOW}▶️  Запис відновлено")
            return True
        return False
    
    def show_activity_indicator(self, volume, is_sound):
        """Показати індикатор"""
        current_time = time.time()
        
        if current_time - self.last_indicator_update < self.indicator_interval:
            return
        
        self.last_indicator_update = current_time
        
        # Візуальний індикатор
        volume_bar_length = 20
        volume_level = min(int(volume * 20), volume_bar_length)
        volume_bar = "█" * volume_level + "░" * (volume_bar_length - volume_level)
        
        # Статус
        if is_sound:
            status = f"{Fore.GREEN}🔊 Звук"
            if self.is_recording:
                status += f" {Fore.YELLOW}[ЗАПИС]"
        else:
            status = f"{Fore.LIGHTBLACK_EX}⚪ Тиша"
        
        # Додати індикатор паузи
        if self.is_paused:
            status = f"{Fore.MAGENTA}⏸️  ПАУЗА (TTS)"
        
        print(f"\r{Fore.CYAN}🎤 [{volume_bar}] {volume:.4f} {status}  ", end="", flush=True)
    
    def process_speech(self, transcribe_func, assistant):
        """Обробити записане мовлення"""
        if len(self.recording_buffer) < self.sample_rate * self.min_speech_duration:
            if self.silence_message_count < self.max_silence_messages:
                print(f" | {Fore.LIGHTBLACK_EX}⭕ Занадто коротко")
                self.silence_message_count += 1
            return
        
        # Скинути лічильник
        self.silence_message_count = 0
        
        # Конвертувати
        audio_data = np.array(list(self.recording_buffer), dtype=np.float32).flatten()
        duration = len(audio_data) / self.sample_rate
        
        print(f"\n{Fore.CYAN}🔊 Обробка {duration:.1f}с мовлення...")
        
        # Розпізнати
        text = transcribe_func(audio_data)
        
        if not text or len(text) < 3:
            print(f"{Fore.LIGHTBLACK_EX}⭕ Пусто або надто коротко")
            return
        
        # Виправлення
        from .config import WHISPER_CORRECTIONS
        text_corrected = text
        for wrong, correct in WHISPER_CORRECTIONS.items():
            text_corrected = text_corrected.replace(wrong, correct)
        
        if text_corrected != text:
            print(f"{Fore.CYAN}✏️  Виправлено: {Fore.WHITE}{text_corrected}")
            text = text_corrected
        
        # Cooldown
        current_time = time.time()
        if current_time - self.last_command_time < self.command_cooldown:
            print(f"{Fore.LIGHTBLACK_EX}⭕ Cooldown активний")
            return
        
        self.last_command_time = current_time
        
        # Передати до LLM
        assistant.process_command(text)
        print(f"\n{Fore.CYAN}🎧 Продовжую слухати...\n")
    
    def listening_loop(self, transcribe_func, assistant):
        """Основний цикл - детекція по паузах"""
        print(f"{Fore.GREEN}🎧 Слухаю безперервно (детекція по паузах)...\n")
        
        while self.is_listening:
            try:
                # 🔥 Пропускаємо обробку, якщо режим паузи
                if self.is_paused:
                    time.sleep(0.1)
                    continue
                
                # Отримати аудіо чанк (100мс)
                audio_chunk = self.audio_queue.get(timeout=1.0)
                
                # Обчислити гучність
                volume = np.abs(audio_chunk).mean()
                
                # Визначити чи це звук
                is_sound = volume > self.sound_threshold
                
                # Показати індикатор
                self.show_activity_indicator(volume, is_sound)
                
                current_time = time.time()
                
                if is_sound:
                    # Є звук
                    self.last_sound_time = current_time
                    
                    if not self.is_recording:
                        # Початок запису
                        self.is_recording = True
                        self.recording_start_time = current_time
                        self.recording_buffer.clear()
                        print(f"\n{Fore.GREEN}▶️  Початок запису...")
                    
                    # Додати в буфер
                    self.recording_buffer.extend(audio_chunk.flatten())
                    
                    # Захист від зависання (максимальна тривалість)
                    if current_time - self.recording_start_time > self.max_speech_duration:
                        print(f"\n{Fore.YELLOW}⏱️  Максимальна тривалість досягнута")
                        self.is_recording = False
                        self.process_speech(transcribe_func, assistant)
                        self.recording_buffer.clear()
                
                else:
                    # Тиша
                    if self.is_recording:
                        # Додавати тишу в буфер (можуть бути паузи між словами)
                        self.recording_buffer.extend(audio_chunk.flatten())
                        
                        # Перевірити тривалість паузи
                        silence_duration = current_time - self.last_sound_time
                        
                        if silence_duration >= self.pause_duration:
                            # Пауза достатньо довга - кінець фрази
                            print(f"\n{Fore.CYAN}⏸️  Пауза {silence_duration:.1f}с - кінець фрази")
                            self.is_recording = False
                            self.process_speech(transcribe_func, assistant)
                            self.recording_buffer.clear()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"\n{Fore.RED}❌ Помилка: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.1)
    
    def start(self, transcribe_func, assistant):
        """Запустити"""
        self.is_listening = True
        self.is_paused = False
        
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.float32,
            device=self.device_id,
            callback=self.audio_callback,
            blocksize=int(self.sample_rate * 0.1)  # 100мс чанки
        )
        
        self.stream.start()
        print(f"{Fore.GREEN}✅ Аудіо стрім запущено")
        
        self.processing_thread = threading.Thread(
            target=self.listening_loop,
            args=(transcribe_func, assistant),
            daemon=True
        )
        self.processing_thread.start()
        print(f"{Fore.GREEN}✅ Потік обробки запущено\n")
    
    def stop(self):
        """Зупинити"""
        print(f"\n{Fore.YELLOW}🛑 Зупиняю слухача...")
        self.is_listening = False
        self.is_paused = False
        
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
        
        if hasattr(self, 'processing_thread'):
            self.processing_thread.join(timeout=2.0)
        
        print(f"{Fore.GREEN}✅ Слухач зупинено")


def create_continuous_listener(sample_rate, audio_filter, microphone_id=None, config=None):
    """Створити listener з динамічною детекцією"""
    try:
        listener = ContinuousListener(
            sample_rate=sample_rate,
            audio_filter=audio_filter,
            vad_model=None,
            vad_utils=None,
            device_id=microphone_id,
            config=config
        )
        
        return listener
        
    except Exception as e:
        print(f"{Fore.RED}❌ Помилка: {e}")
        import traceback
        traceback.print_exc()
        return None