# functions/logic_stt.py
"""Універсальний модуль розпізнавання мови з підтримкою Whisper та w2v-bert"""
import numpy as np
import torch  # Імпорт torch тут
import threading
from queue import Queue
from colorama import Fore
from .config import (
    STT_MODEL_TYPE, STT_MODEL_ID, STT_DEVICE, STT_LANGUAGE,
    STT_PARALLEL_ENABLED, STT_CONFIDENCE_THRESHOLD,
    WHISPER_COMPUTE_TYPE, WHISPER_BATCH_SIZE,
    W2V_BERT_MODEL_NAME
)

class STTEngine:
    """Універсальний двигун розпізнавання мови"""
    
    def __init__(self):
        # Визначення пристрою динамічно
        self.device = self._determine_device()
        
        self.models = {}
        self.results_queue = Queue()
        
        print(f"{Fore.CYAN}🔊 Ініціалізація STT двигуна...")
        print(f"{Fore.CYAN}   Тип: {STT_MODEL_TYPE}, Пристрій: {self.device}")
        
        self._load_models()
    
    def _determine_device(self):
        """Визначити пристрій для обчислень"""
        if STT_DEVICE == "auto":
            if torch.cuda.is_available():
                return "cuda"
            else:
                return "cpu"
        elif STT_DEVICE == "cuda":
            if torch.cuda.is_available():
                return "cuda"
            else:
                print(f"{Fore.YELLOW}⚠️  CUDA не доступна, використовую CPU")
                return "cpu"
        else:
            return STT_DEVICE
    
    def _load_models(self):
        """Завантажити вказані моделі"""
        if STT_MODEL_TYPE in ["whisper", "both"]:
            self._load_whisper()
        
        if STT_MODEL_TYPE in ["w2v-bert", "both"]:
            self._load_w2v_bert()
    
    def _load_whisper(self):
        """Завантажити Whisper модель"""
        try:
            import whisper
            
            print(f"{Fore.CYAN}   Завантаження Whisper {STT_MODEL_ID}...")
            
            # Визначити пристрій для Whisper
            device = "cuda" if self.device == "cuda" else "cpu"
            
            model = whisper.load_model(
                STT_MODEL_ID,
                device=device
            )
            
            self.models["whisper"] = {
                "model": model,
                "type": "whisper",
                "id": STT_MODEL_ID,
                "device": device
            }
            
            print(f"{Fore.GREEN}   ✅ Whisper завантажено на {device}")
            
        except Exception as e:
            print(f"{Fore.RED}   ❌ Помилка Whisper: {e}")
            import traceback
            traceback.print_exc()
    
    def _load_w2v_bert(self):
        """Завантажити w2v-bert модель"""
        try:
            from transformers import Wav2Vec2BertForCTC, AutoProcessor
            
            print(f"{Fore.CYAN}   Завантаження w2v-bert...")
            
            processor = AutoProcessor.from_pretrained(W2V_BERT_MODEL_NAME)
            model = Wav2Vec2BertForCTC.from_pretrained(W2V_BERT_MODEL_NAME)
            
            # Перенести на потрібний пристрій
            if self.device == "cuda":
                model = model.to("cuda")
            model.eval()
            
            self.models["w2v-bert"] = {
                "model": model,
                "processor": processor,
                "type": "w2v-bert",
                "id": W2V_BERT_MODEL_NAME,
                "device": self.device
            }
            
            print(f"{Fore.GREEN}   ✅ w2v-bert завантажено на {self.device}")
            
        except Exception as e:
            print(f"{Fore.RED}   ❌ Помилка w2v-bert: {e}")
            import traceback
            traceback.print_exc()
    
    def transcribe_whisper(self, audio):
        """Транскрибувати через Whisper"""
        try:
            model_info = self.models["whisper"]
            model = model_info["model"]
            
            # Підготувати аудіо
            audio_tensor = torch.from_numpy(audio).float()
            
            # Транскрибувати
            result = model.transcribe(
                audio_tensor,
                language=STT_LANGUAGE,
                fp16=(WHISPER_COMPUTE_TYPE == "float16") and (self.device == "cuda"),
                task="transcribe"
            )
            
            return {
                "text": result["text"].strip(),
                "confidence": np.mean([seg.get("confidence", 0.9) for seg in result.get("segments", [])]),
                "model": "whisper"
            }
            
        except Exception as e:
            print(f"{Fore.RED}   ❌ Whisper транскрипція: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def transcribe_w2v_bert(self, audio):
        """Транскрибувати через w2v-bert"""
        try:
            model_info = self.models["w2v-bert"]
            model = model_info["model"]
            processor = model_info["processor"]
            
            # Підготувати аудіо
            audio_tensor = torch.from_numpy(audio).float()
            
            # Нормалізація
            if torch.max(torch.abs(audio_tensor)) > 0:
                audio_tensor = audio_tensor / torch.max(torch.abs(audio_tensor))
            
            # Обробити процесором
            inputs = processor(
                audio_tensor.numpy(), 
                sampling_rate=16000, 
                return_tensors="pt",
                padding=True
            )
            
            # Знайти правильний ключ для вводу
            input_key = None
            for key in ['input_values', 'input_features']:
                if key in inputs:
                    input_key = key
                    break
            
            if not input_key:
                return None
            
            # Перенести на пристрій
            input_data = inputs[input_key].to(self.device)
            
            # Транскрибувати
            with torch.no_grad():
                logits = model(input_data).logits
            
            # Отримати впевненість
            probs = torch.softmax(logits, dim=-1)
            confidence = torch.max(probs).item()
            
            # Декодувати
            predicted_ids = torch.argmax(logits, dim=-1)
            text = processor.batch_decode(predicted_ids)[0]
            
            return {
                "text": text.strip(),
                "confidence": confidence,
                "model": "w2v-bert"
            }
            
        except Exception as e:
            print(f"{Fore.RED}   ❌ w2v-bert транскрипція: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _transcribe_parallel(self, audio):
        """Паралельне виконання всіх доступних моделей"""
        threads = []
        
        if "whisper" in self.models:
            thread = threading.Thread(
                target=lambda: self.results_queue.put(self.transcribe_whisper(audio)),
                daemon=True
            )
            threads.append(thread)
        
        if "w2v-bert" in self.models:
            thread = threading.Thread(
                target=lambda: self.results_queue.put(self.transcribe_w2v_bert(audio)),
                daemon=True
            )
            threads.append(thread)
        
        # Запустити всі потоки
        for thread in threads:
            thread.start()
        
        # Очікувати завершення
        for thread in threads:
            thread.join(timeout=10.0)  # Таймаут 10 секунд
        
        # Зібрати результати
        results = []
        while not self.results_queue.empty():
            result = self.results_queue.get()
            if result and result["text"]:
                results.append(result)
        
        return results
    
    def _choose_best_result(self, results):
        """Вибрати найкращий результат з декількох моделей"""
        if not results:
            return None
        
        if len(results) == 1:
            return results[0]["text"]
        
        # Відфільтрувати за впевненістю
        valid_results = [
            r for r in results 
            if r["confidence"] > STT_CONFIDENCE_THRESHOLD
        ]
        
        if not valid_results:
            # Якщо всі результати низької якості, беремо найкращий
            valid_results = sorted(results, key=lambda x: x["confidence"], reverse=True)[:1]
        
        # Вибір за довжиною та впевненістю
        best_result = max(
            valid_results,
            key=lambda x: len(x["text"]) * x["confidence"]
        )
        
        print(f"{Fore.MAGENTA}   📊 Результати порівняння:")
        for result in results:
            status = "🏆" if result == best_result else "  "
            print(f"{Fore.CYAN}     {status} {result['model']}: '{result['text'][:50]}...' (впевненість: {result['confidence']:.2f})")
        
        return best_result["text"]
    
    def transcribe(self, audio):
        """Головна функція транскрипції"""
        if not self.models:
            print(f"{Fore.RED}   ❌ Немає завантажених моделей")
            return ""
        
        # 🔥 ВИПРАВЛЕНО: Додана перевірка STT_MODEL_TYPE == "both"
        if STT_PARALLEL_ENABLED and len(self.models) > 1 and STT_MODEL_TYPE == "both":
            # Паралельний режим (тільки якщо "both")
            print(f"{Fore.CYAN}   🔄 Паралельне розпізнавання...")
            results = self._transcribe_parallel(audio)
            best_text = self._choose_best_result(results)
            
            if best_text:
                print(f"{Fore.GREEN}   ✅ Обрано: '{best_text[:50]}...'")
                return best_text
        
        # Послідовний режим або одна модель
        if "whisper" in self.models:
            result = self.transcribe_whisper(audio)
            if result:
                return result["text"]
        
        if "w2v-bert" in self.models:
            result = self.transcribe_w2v_bert(audio)
            if result:
                return result["text"]
        
        return ""
    
    def get_available_models(self):
        """Отримати список доступних моделей"""
        return list(self.models.keys())


# Глобальний екземпляр
_stt_engine = None

def get_stt_engine():
    """Отримати глобальний STT двигун"""
    global _stt_engine
    if _stt_engine is None:
        _stt_engine = STTEngine()
    return _stt_engine