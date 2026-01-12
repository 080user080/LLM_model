# functions/logic_tts.py
"""Модуль TTS на базі StyleTTS2 Ukrainian (patriotyk)"""
import os
import sys
import time
import hashlib
import threading
import subprocess
from pathlib import Path
from colorama import Fore
import numpy as np
import sounddevice as sd
import soundfile as sf
import torch

class TTSEngine:
    """Двигун TTS для синтезу мовлення"""
    
    def __init__(self, config=None, listener=None):
        """Ініціалізація TTS двигуна"""
        from .config import (
            TTS_ENABLED, TTS_DEVICE, TTS_CACHE_DIR, TTS_VOICES_DIR,
            TTS_DEFAULT_VOICE, TTS_SPEECH_RATE, TTS_VOLUME
        )
        
        self.enabled = TTS_ENABLED
        if not self.enabled:
            print(f"{Fore.YELLOW}⚠️  TTS вимкнено")
            self.is_ready = False
            return
        
        self.listener = listener
        self.is_ready = False
        self.is_playing = False
        
        # Налаштування
        self.device = TTS_DEVICE
        self.cache_dir = Path(TTS_CACHE_DIR)
        self.voices_dir = Path(TTS_VOICES_DIR)
        self.default_voice = TTS_DEFAULT_VOICE
        self.speech_rate = TTS_SPEECH_RATE
        self.volume = TTS_VOLUME
        
        # Створення директорій
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self.voices_dir.mkdir(exist_ok=True, parents=True)
        
        # Модель та голоси
        self.model = None
        self.available_voices = {}
        self.style_vectors = {}
        
        print(f"{Fore.CYAN}🔊 Ініціалізація TTS (StyleTTS2 Ukrainian)...")
        print(f"{Fore.CYAN}   Пристрій: {self.device}")
        
        try:
            self._install_dependencies()
            self._discover_voices()
            self._load_model()
            self.is_ready = True
            print(f"{Fore.GREEN}✅ TTS готовий")
        except Exception as e:
            print(f"{Fore.RED}❌ Помилка TTS: {e}")
            import traceback
            traceback.print_exc()
            self.is_ready = False
    
    def _install_dependencies(self):
        """Встановити залежності"""
        print(f"{Fore.CYAN}📦 Перевірка залежностей...")
        
        deps = [
            "styletts2-inference",
            "ukrainian-word-stress",
            "ipa-uk",
            "unicodedata2"
        ]
        
        for dep in deps:
            try:
                if dep == "styletts2-inference":
                    from styletts2_inference.models import StyleTTS2
                elif dep == "ukrainian-word-stress":
                    from ukrainian_word_stress import Stressifier
                elif dep == "ipa-uk":
                    from ipa_uk import ipa
                else:
                    __import__(dep.replace("-", "_"))
            except ImportError:
                print(f"{Fore.YELLOW}   Встановлення {dep}...")
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", dep
                ])
        
        print(f"{Fore.GREEN}✅ Залежності готові")
    
    def _discover_voices(self):
        """Знайти голоси (.pt файли)"""
        self.available_voices.clear()
        
        if not self.voices_dir.exists():
            print(f"{Fore.YELLOW}⚠️  Папка голосів не знайдена: {self.voices_dir}")
            return
        
        # Шукаємо .pt файли
        pt_files = list(self.voices_dir.glob("*.pt"))
        
        for pt_file in pt_files:
            voice_name = pt_file.stem
            self.available_voices[voice_name] = pt_file
            print(f"{Fore.CYAN}   🎵 Голос: {voice_name}")
        
        if not self.available_voices:
            print(f"{Fore.YELLOW}⚠️  Голоси не знайдено")
            print(f"{Fore.YELLOW}   💡 Помістіть .pt файли в {self.voices_dir}")
        else:
            print(f"{Fore.GREEN}✅ Знайдено голосів: {len(self.available_voices)}")
            if self.default_voice not in self.available_voices:
                self.default_voice = list(self.available_voices.keys())[0]
    
    def _load_model(self):
        """Завантажити модель StyleTTS2"""
        print(f"{Fore.CYAN}🔧 Завантаження моделі...")
        
        try:
            from styletts2_inference.models import StyleTTS2
            
            # Використовуємо MULTISPEAKER модель
            print(f"{Fore.CYAN}   Завантаження multispeaker моделі...")
            self.model = StyleTTS2(
                hf_path='patriotyk/styletts2_ukrainian_multispeaker',
                device=self.device
            )
            
            print(f"{Fore.GREEN}✅ Модель завантажена")
            
            # Завантажити стилі
            self._load_style_vectors()
            
        except Exception as e:
            print(f"{Fore.RED}❌ Помилка завантаження: {e}")
            raise
    
    def _load_style_vectors(self):
        """Завантажити стилі голосів"""
        if not self.available_voices:
            print(f"{Fore.YELLOW}⚠️  Немає голосів для завантаження")
            return
        
        print(f"{Fore.CYAN}📂 Завантаження стилів...")
        
        for voice_name, pt_path in self.available_voices.items():
            try:
                style_vector = torch.load(pt_path, map_location=self.device)
                self.style_vectors[voice_name] = style_vector
                print(f"{Fore.GREEN}   ✅ {voice_name}")
            except Exception as e:
                print(f"{Fore.RED}   ❌ {voice_name}: {e}")
        
        print(f"{Fore.GREEN}✅ Стилів завантажено: {len(self.style_vectors)}")
    
    def _preprocess_text(self, text):
        """Підготувати текст (наголоси + IPA)"""
        try:
            from ukrainian_word_stress import Stressifier, StressSymbol
            from ipa_uk import ipa
            from unicodedata import normalize
            import re
            
            # Очистити
            text = text.strip().replace('"', '')
            if not text:
                return ""
            
            # Наголоси
            stressify = Stressifier()
            text = text.replace('+', StressSymbol.CombiningAcuteAccent)
            text = normalize('NFKC', text)
            
            # Тире
            text = re.sub(r'[᠆‐‑‒–—―⁻₋−⸺⸻]', '-', text)
            text = re.sub(r' - ', ': ', text)
            
            # IPA фонетика
            phonetic = ipa(stressify(text))
            
            return phonetic
            
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  Помилка препроцесингу: {e}")
            return text
    
    def _split_to_parts(self, text):
        """Розбити текст на частини"""
        split_symbols = '.?!:'
        parts = ['']
        index = 0
        
        for s in text:
            parts[index] += s
            if s in split_symbols and len(parts[index]) > 150:
                index += 1
                parts.append('')
        
        return [p.strip() for p in parts if p.strip()]
    
    def _get_cache_key(self, text, voice_name, rate):
        """Ключ кешу"""
        key_string = f"{text}|{voice_name}|{rate:.2f}"
        key_hash = hashlib.md5(key_string.encode('utf-8')).hexdigest()
        
        cache_subdir = self.cache_dir / key_hash[:2]
        cache_subdir.mkdir(exist_ok=True)
        
        return cache_subdir / f"{key_hash}.wav"
    
    def _pause_recording(self):
        """Призупинити запис"""
        if self.listener and hasattr(self.listener, 'pause_listening'):
            return self.listener.pause_listening()
        return False
    
    def _resume_recording(self):
        """Відновити запис"""
        if self.listener and hasattr(self.listener, 'resume_listening'):
            return self.listener.resume_listening()
        return False
    
    def synthesize(self, text, voice_name=None, rate=None):
        """Синтезувати текст"""
        if not self.is_ready or not self.model:
            print(f"{Fore.RED}❌ TTS не готовий")
            return None
        
        if voice_name is None:
            voice_name = self.default_voice
        if rate is None:
            rate = self.speech_rate
        
        # Перевірити кеш
        cache_path = self._get_cache_key(text, voice_name, rate)
        if cache_path.exists():
            print(f"{Fore.GREEN}♻️  Кеш")
            return cache_path
        
        print(f"{Fore.CYAN}🔊 Синтез: '{text[:50]}...' [{voice_name}]")
        
        try:
            # Отримати стиль
            if voice_name not in self.style_vectors:
                print(f"{Fore.RED}❌ Голос не знайдено: {voice_name}")
                return None
            
            style = self.style_vectors[voice_name]
            
            # Розбити на частини
            parts = self._split_to_parts(text)
            
            result_wav = []
            
            for part in parts:
                # Підготувати текст
                phonetic = self._preprocess_text(part)
                
                if not phonetic:
                    continue
                
                # Токенізувати
                tokens = self.model.tokenizer.encode(phonetic)
                
                # Синтез
                wav = self.model(tokens, speed=rate, s_prev=style)
                result_wav.append(wav)
            
            if not result_wav:
                print(f"{Fore.RED}❌ Порожній результат")
                return None
            
            # Об'єднати
            audio = torch.concatenate(result_wav).cpu().numpy()
            
            # Зберегти
            sf.write(str(cache_path), audio, 24000)
            print(f"{Fore.GREEN}✅ Синтезовано")
            
            return cache_path
            
        except Exception as e:
            print(f"{Fore.RED}❌ Помилка синтезу: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def speak(self, text, voice_name=None, rate=None, wait=True):
        """Озвучити текст"""
        if not self.enabled or not self.is_ready:
            return False
        
        if not text or len(text.strip()) == 0:
            return False
        
        # Призупинити запис
        was_recording = self._pause_recording()
        
        try:
            # Синтезувати
            audio_path = self.synthesize(text, voice_name, rate)
            if not audio_path or not audio_path.exists():
                return False
            
            # Завантажити
            audio_data, sample_rate = sf.read(str(audio_path), dtype='float32')
            audio_data = audio_data * self.volume
            
            # Відтворити
            duration = len(audio_data) / sample_rate
            print(f"{Fore.CYAN}🔊 Відтворення ({duration:.1f}с)...")
            self.is_playing = True
            
            if wait:
                sd.play(audio_data, sample_rate)
                sd.wait()
                self.is_playing = False
            else:
                def play_async():
                    sd.play(audio_data, sample_rate)
                    sd.wait()
                    self.is_playing = False
                
                thread = threading.Thread(target=play_async, daemon=True)
                thread.start()
            
            return True
            
        except Exception as e:
            print(f"{Fore.RED}❌ Помилка відтворення: {e}")
            return False
            
        finally:
            if was_recording:
                self._resume_recording()
    
    def stop(self):
        """Зупинити відтворення"""
        if self.is_playing:
            sd.stop()
            self.is_playing = False
    
    def get_voices(self):
        """Список голосів"""
        return list(self.available_voices.keys())
    
    def set_voice(self, voice_name):
        """Встановити голос"""
        if voice_name in self.available_voices:
            self.default_voice = voice_name
            return True
        return False
    
    def set_rate(self, rate):
        """Встановити швидкість"""
        if 0.5 <= rate <= 2.0:
            self.speech_rate = rate
            return True
        return False
    
    def set_volume(self, volume):
        """Встановити гучність"""
        if 0.0 <= volume <= 1.0:
            self.volume = volume
            return True
        return False


# Глобальний екземпляр
_tts_engine = None

def get_tts_engine(listener=None):
    """Отримати TTS engine"""
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = TTSEngine(listener=listener)
    return _tts_engine

def init_tts(listener=None):
    """Ініціалізувати TTS"""
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = TTSEngine(listener=listener)
    return _tts_engine