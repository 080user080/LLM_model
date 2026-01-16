# functions/logic_audio_filtering.py
"""GPU-прискорена фільтрація аудіо з AGC та fallback шумодавом"""
import numpy as np
import torch
from colorama import Fore

class AudioFilter:
    """Система фільтрації аудіо з AGC та fallback"""
    
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        # AGC параметри
        self.target_volume = 0.05  # Цільова середня гучність
        self.current_gain = 1.0    # Поточний коефіцієнт підсилення
        self.max_gain = 50.0       # Максимальне підсилення
        self.min_gain = 0.1        # Мінімальне підсилення
        self.agc_attack_time = 0.05 # Швидкість реакції (50ms)
        
        # Noise reducer (fallback)
        self.noise_reducer = None
        self._init_noise_reducer()
        
        print(f"{Fore.GREEN}✅ AudioFilter ініціалізовано на {self.device}")
        print(f"{Fore.CYAN}   AGC: {'УВІМКНЕНО'} | Noise reducer: {'УВІМКНЕНО' if self.noise_reducer else 'ВИМКНЕНО'}")
    
    def _init_noise_reducer(self):
        """Ініціалізація шумодаву (fallback)"""
        try:
            # Спроба 1: RNNoise (найкраще, але не завжди доступне)
            import rnnnoise
            self.noise_reducer = rnnnoise.RNNoise()
            self.noise_type = "rnnoise"
            print(f"{Fore.GREEN}✅ RNNoise готовий")
        except ImportError:
            try:
                # Спроба 2: Noisereduce (чистий Python)
                import noisereduce as nr
                self.noise_reducer = nr
                self.noise_type = "noisereduce"
                print(f"{Fore.GREEN}✅ NoiseReduce готовий")
            except ImportError:
                # Спроба 3: Немає шумодаву (тільки AGC)
                self.noise_reducer = None
                self.noise_type = "none"
                print(f"{Fore.YELLOW}⚠️  Шумодав недоступний. Встановіть: pip install noisereduce")
    
    def apply_agc(self, audio):
        """Застосувати Automatic Gain Control"""
        if len(audio) == 0:
            return audio
            
        # Обчислити поточну гучність
        current_volume = np.abs(audio).mean()
        
        if current_volume > 0.0001:  # Уникаємо ділення на нуль
            # Розрахувати бажане підсилення
            desired_gain = self.target_volume / current_volume
            
            # Обмежити діапазон
            desired_gain = min(desired_gain, self.max_gain)
            desired_gain = max(desired_gain, self.min_gain)
            
            # Плавний перехід
            max_change = self.agc_attack_time * self.sample_rate / len(audio)
            if desired_gain > self.current_gain:
                gain_change = min(desired_gain / self.current_gain, 1.0 + max_change)
            else:
                gain_change = max(desired_gain / self.current_gain, 1.0 - max_change)
            
            self.current_gain *= gain_change
            
            # Застосувати
            boosted = audio * self.current_gain
            
            # Запобігти clipping
            boosted = np.clip(boosted, -1.0, 1.0)
            
            return boosted
        
        return audio
    
    def apply_noise_reduction(self, audio):
        """Застосувати шумодав (fallback)"""
        if not self.noise_reducer:
            return audio
        
        try:
            if self.noise_type == "rnnoise":
                # RNNoise
                return self.noise_reducer.process(audio, sample_rate=self.sample_rate)
            
            elif self.noise_type == "noisereduce":
                # NoiseReduce (безшумний профіль - перші 0.5 сек)
                if len(audio) < self.sample_rate * 0.5:
                    return audio
                
                noise_profile = audio[:int(self.sample_rate * 0.5)]
                reduced = self.noise_reducer.reduce_noise(
                    y=audio,
                    sr=self.sample_rate,
                    y_noise=noise_profile,
                    prop_decrease=0.8
                )
                return reduced
            
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  Помилка шумодаву: {e}")
            return audio
    
    def process_audio(self, audio, use_agc=True, use_noise_reducer=True):
        """Повний пайплайн обробки аудіо"""
        print(f"{Fore.CYAN}🔧 Обробка аудіо...")
        
        # 1. AGC (регулює гучність)
        if use_agc:
            audio = self.apply_agc(audio)
            print(f"{Fore.CYAN}   AGC gain: {self.current_gain:.1f}x")
        
        # 2. Noise reducer (видаляє фон)
        if use_noise_reducer:
            audio = self.apply_noise_reduction(audio)
            if self.noise_type != "none":
                print(f"{Fore.CYAN}   Noise: {self.noise_type}")
        
        # 3. Фінальна нормалізація
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val * 0.95
        
        print(f"{Fore.GREEN}✅ Аудіо оброблено")
        return audio


# Глобальний екземпляр
_audio_filter = None

def get_audio_filter(sample_rate=16000):
    """Отримати глобальний екземпляр AudioFilter"""
    global _audio_filter
    if _audio_filter is None:
        _audio_filter = AudioFilter(sample_rate)
    return _audio_filter