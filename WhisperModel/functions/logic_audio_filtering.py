# functions/logic_audio_filtering.py
"""GPU-прискорена фільтрація аудіо для покращення розпізнавання"""
import numpy as np
import torch
import scipy.signal as signal
from colorama import Fore

class AudioFilter:
    """Система фільтрації аудіо з GPU-підтримкою"""
    
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        # Ініціалізація компонентів
        self.deepfilter = None
        self.vad_model = None
        self.silero_utils = None
        
        self._init_deepfilter()
        self._init_vad()
        
        print(f"{Fore.GREEN}✅ AudioFilter ініціалізовано на {self.device}")
    
    def _init_deepfilter(self):
        """Ініціалізація GPU шумодаву (альтернатива DeepFilterNet)"""
        try:
            # Спроба 1: noisereduce з GPU
            import noisereduce as nr
            self.noisereduce = nr
            print(f"{Fore.GREEN}✅ NoiseReduce готовий")
        except ImportError:
            print(f"{Fore.YELLOW}⚠️  NoiseReduce недоступний, використовую Spectral Gating")
            self.noisereduce = None
    
    def _init_vad(self):
        """Ініціалізація Silero VAD"""
        try:
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False
            )
            
            self.vad_model = model.to(self.device)
            self.silero_utils = utils
            print(f"{Fore.GREEN}✅ Silero VAD готовий")
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  Silero VAD недоступний: {e}")
    
    def apply_bandpass_filter(self, audio):
        """Частотний коридор: 100 Hz - 7500 Hz"""
        try:
            nyquist = self.sample_rate / 2
            low = 100 / nyquist
            high = 7500 / nyquist
            
            # Butterworth фільтр 4-го порядку
            b, a = signal.butter(4, [low, high], btype='band')
            filtered = signal.filtfilt(b, a, audio)
            
            return filtered.astype(np.float32)
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  Bandpass помилка: {e}")
            return audio
    
    def apply_compression(self, audio, threshold_db=-20, ratio=3.0, makeup_db=4):
        """Компресія для стабілізації гучності"""
        try:
            # Конвертація dB у лінійний масштаб
            threshold = 10 ** (threshold_db / 20)
            makeup = 10 ** (makeup_db / 20)
            
            # Обчислення envelope
            abs_audio = np.abs(audio)
            
            # Компресія
            compressed = np.where(
                abs_audio > threshold,
                threshold + (abs_audio - threshold) / ratio,
                abs_audio
            )
            
            # Відновлення знаку
            compressed = np.sign(audio) * compressed
            
            # Makeup gain
            compressed *= makeup
            
            # Нормалізація
            max_val = np.max(np.abs(compressed))
            if max_val > 0:
                compressed = compressed / max_val * 0.95
            
            return compressed.astype(np.float32)
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  Компресія помилка: {e}")
            return audio
    
    def adaptive_wiener_filter(self, audio):
        """Адаптивний Wiener фільтр для шуму (GPU)"""
        try:
            audio_tensor = torch.from_numpy(audio).to(self.device)
            
            # STFT
            n_fft = 512
            hop_length = 160
            
            stft = torch.stft(
                audio_tensor,
                n_fft=n_fft,
                hop_length=hop_length,
                return_complex=True
            )
            
            magnitude = torch.abs(stft)
            phase = torch.angle(stft)
            
            # Оцінка SNR для кожної частоти
            noise_est = torch.median(magnitude, dim=1, keepdim=True)[0]
            
            # Wiener gain
            snr = (magnitude ** 2) / (noise_est ** 2 + 1e-8)
            wiener_gain = snr / (snr + 1)
            
            # Застосувати фільтр
            filtered_mag = magnitude * wiener_gain
            filtered_stft = filtered_mag * torch.exp(1j * phase)
            
            # Inverse STFT
            audio_filtered = torch.istft(
                filtered_stft,
                n_fft=n_fft,
                hop_length=hop_length,
                length=len(audio_tensor)
            )
            
            result = audio_filtered.cpu().numpy()
            print(f"{Fore.CYAN}🎛️  Wiener фільтр застосовано (GPU)")
            return result.astype(np.float32)
            
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  Wiener помилка: {e}")
            return audio
    
    def remove_silence_vad(self, audio):
        """Видалення тиші за допомогою Silero VAD"""
        if self.vad_model is None or self.silero_utils is None:
            return audio
        
        try:
            # Конвертація в torch tensor
            audio_tensor = torch.from_numpy(audio).to(self.device)
            
            # Отримання мітки мовлення
            speech_timestamps = self.silero_utils[0](
                audio_tensor,
                self.vad_model,
                sampling_rate=self.sample_rate
            )
            
            if not speech_timestamps:
                print(f"{Fore.YELLOW}⚠️  VAD: мовлення не виявлено")
                return audio
            
            # Вирізати тільки частини з мовленням
            speech_parts = []
            for timestamp in speech_timestamps:
                start = timestamp['start']
                end = timestamp['end']
                speech_parts.append(audio[start:end])
            
            if speech_parts:
                result = np.concatenate(speech_parts)
                print(f"{Fore.CYAN}✂️  VAD: {len(audio)} → {len(result)} семплів")
                return result
            
            return audio
            
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  VAD помилка: {e}")
            return audio
    
    def spectral_gate_denoise(self, audio):
        """Спектральне шумоподавлення (GPU-прискорене через torch)"""
        try:
            # Конвертувати в torch для GPU обчислень
            audio_tensor = torch.from_numpy(audio).to(self.device)
            
            # STFT (Short-Time Fourier Transform)
            n_fft = 512
            hop_length = 160
            
            # Обчислення STFT на GPU
            stft = torch.stft(
                audio_tensor,
                n_fft=n_fft,
                hop_length=hop_length,
                return_complex=True
            )
            
            # Magnitude та Phase
            magnitude = torch.abs(stft)
            phase = torch.angle(stft)
            
            # Оцінка шумового профілю (перші 0.5 секунди)
            noise_frames = int(0.5 * self.sample_rate / hop_length)
            noise_profile = torch.mean(magnitude[:, :noise_frames], dim=1, keepdim=True)
            
            # Spectral Gating (м'яке придушення)
            noise_threshold = 2.0  # Агресивність (1.5-3.0)
            mask = magnitude / (noise_profile + 1e-8)
            mask = torch.clamp(mask / noise_threshold, 0, 1)
            
            # Застосувати маску
            filtered_magnitude = magnitude * mask
            
            # Відновити сигнал
            filtered_stft = filtered_magnitude * torch.exp(1j * phase)
            
            # Inverse STFT
            audio_filtered = torch.istft(
                filtered_stft,
                n_fft=n_fft,
                hop_length=hop_length,
                length=len(audio_tensor)
            )
            
            result = audio_filtered.cpu().numpy()
            print(f"{Fore.CYAN}🎛️  Spectral Gate застосовано (GPU)")
            return result.astype(np.float32)
            
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  Spectral Gate помилка: {e}")
            return audio
    
    def deepfilter_denoise(self, audio):
        """Шумоподавлення (noisereduce або spectral gating)"""
        if self.noisereduce is not None:
            try:
                # NoiseReduce (CPU, але швидкий)
                result = self.noisereduce.reduce_noise(
                    y=audio,
                    sr=self.sample_rate,
                    stationary=True,
                    prop_decrease=0.8
                )
                print(f"{Fore.CYAN}🎛️  NoiseReduce застосовано")
                return result.astype(np.float32)
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️  NoiseReduce помилка: {e}")
        
        # Fallback: Spectral Gating (GPU)
        return self.spectral_gate_denoise(audio)
    
    def process_audio(self, audio, use_vad=True, use_deepfilter=True, use_wiener=True):
        """Повний пайплайн обробки аудіо"""
        print(f"{Fore.CYAN}🔧 Обробка аудіо...")
        
        # 1. VAD (видалення тиші)
        if use_vad:
            audio = self.remove_silence_vad(audio)
        
        # 2. Адаптивний Wiener (найкраще для кімнатного шуму)
        if use_wiener and self.device == 'cuda':
            audio = self.adaptive_wiener_filter(audio)
        
        # 3. Spectral Gate або NoiseReduce
        if use_deepfilter:
            audio = self.deepfilter_denoise(audio)
        
        # 4. Частотний фільтр
        audio = self.apply_bandpass_filter(audio)
        
        # 5. Компресія
        audio = self.apply_compression(audio)
        
        # 6. Фінальна нормалізація
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val * 0.95
        
        print(f"{Fore.GREEN}✅ Аудіо оброблено")
        return audio


# Глобальний екземпляр фільтра
_audio_filter = None

def get_audio_filter(sample_rate=16000):
    """Отримати глобальний екземпляр AudioFilter"""
    global _audio_filter
    if _audio_filter is None:
        _audio_filter = AudioFilter(sample_rate)
    return _audio_filter
