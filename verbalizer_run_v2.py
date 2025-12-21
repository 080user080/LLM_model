# verbalizer_with_grammar_correction.py
# GPT

import re
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from tkinter import Tk, filedialog
import os
import traceback

# ---- Налаштування ----
# Максимальна довжина символів одного чанка (щоб не трекати втрату через truncation)
MAX_CHUNK_CHARS = 2000
# Максимальна довжина токенів для генерації (безпечно для більшості моделей)
GEN_MAX_LENGTH = 512
# Символи, які часто вказують на русизм у кирилиці (проста heuristic)
RUSSIAN_SIGN_CHARS = set("ыэё")

# ---- Клас для вербалізації (перетворення чисел/дат у слова) ----
class Verbalizer:
    def __init__(self, device_str="cpu", model_name="skypro1111/mbart-large-50-verbalization"):
        self.device = torch.device(device_str)
        self.model_name = model_name

        print(f"Завантаження моделі вербалізації: {self.model_name}...")
        self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
        self.model.to(self.device)
        self.model.eval()

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)

        model_type = getattr(self.model.config, "model_type", "")
        self._is_mbart = "mbart" in model_type.lower() or "mbart" in self.model_name.lower()
        if self._is_mbart:
            try:
                # GPT: примусово встановлюємо українську, якщо токенізатор підтримує
                if hasattr(self.tokenizer, "lang_code_to_id") and "uk_XX" in self.tokenizer.lang_code_to_id:
                    self.tokenizer.src_lang = "uk_XX"
                    self.tokenizer.tgt_lang = "uk_XX"
                else:
                    # деякі mbart токенізатори приймають просте присвоєння
                    self.tokenizer.src_lang = "uk_XX"
                    self.tokenizer.tgt_lang = "uk_XX"
            except Exception:
                pass

    def generate_text(self, text, max_length=GEN_MAX_LENGTH):
        input_text = "<verbalization>:" + text
        encoded = self.tokenizer(
            input_text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_length,
        )
        input_ids = encoded["input_ids"].to(self.device)
        attention_mask = encoded.get("attention_mask")
        if attention_mask is not None:
            attention_mask = attention_mask.to(self.device)

        with torch.no_grad():
            output_ids = self.model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_length=max_length,
                num_beams=5,
                early_stopping=True,
            )

        result = self.tokenizer.decode(output_ids[0], skip_special_tokens=True)
        return result.strip()

# ---- Універсальний клас для корекції граматики (українська лише) ----
class GrammarCorrector:
    def __init__(
            self,
            device_str="cpu",
            model_name="schhwmn/mt5-base-finetuned-ukr-gec",
            fallback="sdadas/byt5-text-correction",
            enforce_uk=True
        ):
        self.device = torch.device(device_str)
        self.model_name = model_name
        self.fallback = fallback
        self.enforce_uk = enforce_uk

        try:
            print(f"Завантаження моделі корекції граматики: {self.model_name}...")
            self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        except Exception as e:
            print(f"Не вдалося завантажити {self.model_name}: {e}")
            print(f"Спроба fallback: {self.fallback}")
            try:
                self.model = AutoModelForSeq2SeqLM.from_pretrained(self.fallback)
                self.tokenizer = AutoTokenizer.from_pretrained(self.fallback)
                self.model_name = self.fallback
                print(f"Завантажено fallback модель: {self.fallback}")
            except Exception as e2:
                print("Помилка завантаження fallback-моделі:")
                traceback.print_exc()
                raise RuntimeError("Не вдалося завантажити модель для корекції граматики.") from e2

        # Перемістити модель на пристрій
        try:
            self.model.to(self.device)
        except Exception as e:
            print("Помилка при переміщенні моделі на пристрій:", e)
            raise

        self.model.eval()

        model_type = getattr(self.model.config, "model_type", "")
        self._is_t5 = "t5" in model_type.lower() or "byt5" in model_type.lower()

        # GPT: якщо можливо — примусово встановимо українську мову для токенізатора
        try:
            if self.enforce_uk:
                if hasattr(self.tokenizer, "lang_code_to_id") and "uk_XX" in self.tokenizer.lang_code_to_id:
                    self.tokenizer.src_lang = "uk_XX"
                    self.tokenizer.tgt_lang = "uk_XX"
                else:
                    # деякі токенізатори приймають просте присвоєння
                    self.tokenizer.src_lang = "uk_XX"
                    self.tokenizer.tgt_lang = "uk_XX"
        except Exception:
            pass

    def _generate_once(self, input_text, max_length=GEN_MAX_LENGTH, num_beams=5):
        encoded = self.tokenizer(
            input_text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_length,
        )
        input_ids = encoded["input_ids"].to(self.device)
        attention_mask = encoded.get("attention_mask")
        if attention_mask is not None:
            attention_mask = attention_mask.to(self.device)

        with torch.no_grad():
            output_ids = self.model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_length=max_length,
                num_beams=num_beams,
                early_stopping=True,
            )
        result = self.tokenizer.decode(output_ids[0], skip_special_tokens=True)
        return result.strip()

    def correct_grammar(self, text, max_length=GEN_MAX_LENGTH):
        # якщо T5-похідна — додаємо префікс "correct:"
        if self._is_t5:
            input_text = f"correct: {text}"
        else:
            input_text = text

        # Перша спроба
        out = self._generate_once(input_text, max_length=max_length, num_beams=5)

        # Перевірка на наявність типових русизм-символів, якщо виявлено — пробуємо повторно з більшим числом променів або fallback
        if any((ch in RUSSIAN_SIGN_CHARS) for ch in out):
            print("У результаті знайдено символи, характерні для російської мови; спроба повторної генерації з іншим налаштуванням...")
            try:
                out2 = self._generate_once(input_text, max_length=max_length, num_beams=8)
                # якщо друга спроба має менше русизм-символів — беремо її
                rus_count1 = sum(1 for ch in out if ch in RUSSIAN_SIGN_CHARS)
                rus_count2 = sum(1 for ch in out2 if ch in RUSSIAN_SIGN_CHARS)
                if rus_count2 < rus_count1:
                    out = out2
                else:
                    # пробуємо fallback модель (якщо вона відрізняється)
                    if self.fallback and self.model_name != self.fallback:
                        print("Спроба використати fallback-модель для отримання чисто українського тексту...")
                        try:
                            fb_model = AutoModelForSeq2SeqLM.from_pretrained(self.fallback)
                            fb_tokenizer = AutoTokenizer.from_pretrained(self.fallback)
                            if hasattr(fb_tokenizer, "lang_code_to_id") and "uk_XX" in fb_tokenizer.lang_code_to_id:
                                fb_tokenizer.src_lang = "uk_XX"
                                fb_tokenizer.tgt_lang = "uk_XX"
                            fb_model.to(self.device)
                            fb_model.eval()
                            encoded = fb_tokenizer(
                                input_text,
                                return_tensors="pt",
                                padding=True,
                                truncation=True,
                                max_length=max_length,
                            )
                            input_ids = encoded["input_ids"].to(self.device)
                            attention_mask = encoded.get("attention_mask")
                            if attention_mask is not None:
                                attention_mask = attention_mask.to(self.device)
                            with torch.no_grad():
                                output_ids = fb_model.generate(
                                    input_ids=input_ids,
                                    attention_mask=attention_mask,
                                    max_length=max_length,
                                    num_beams=5,
                                    early_stopping=True,
                                )
                            out_fb = fb_tokenizer.decode(output_ids[0], skip_special_tokens=True)
                            # якщо в fallback менше русизм-символів — беремо його
                            if sum(1 for ch in out_fb if ch in RUSSIAN_SIGN_CHARS) < rus_count1:
                                out = out_fb
                        except Exception as e:
                            print("Fallback спроба не вдалася:", e)
            except Exception as e:
                print("Повторна генерація не вдалася:", e)

        # Невелика нормалізація: українські апострофи та лапки
        out = out.replace("’", "'").replace("ʼ", "'")
        out = re.sub(r"\s+([,.:;!?])", r"\1", out)  # прибрати зайві пробіли перед пунктуацією
        out = re.sub(r"(?<=\d)\s+(?=[.,])", "", out)  # прибрати пробіли перед комами/крапками після цифр

        return out

# ---- Допоміжні функції для chunking (щоб не втратити частини великого тексту) ----
def split_into_sentences(text):
    # Простий роздільник речень: крапка, знак питання, знак оклику, нова лінія
    # Зберігає розділові знаки
    parts = re.split(r'(?<=[\.\!\?])\s+|\n+', text)
    parts = [p.strip() for p in parts if p.strip()]
    return parts

def chunk_sentences(sentences, max_chars=MAX_CHUNK_CHARS):
    chunks = []
    cur = []
    cur_len = 0
    for s in sentences:
        if cur_len + len(s) + 1 > max_chars and cur:
            chunks.append(" ".join(cur))
            cur = [s]
            cur_len = len(s)
        else:
            cur.append(s)
            cur_len += len(s) + 1
    if cur:
        chunks.append(" ".join(cur))
    return chunks

# ---- main ----
def main():
    Tk().withdraw()
    file_path = filedialog.askopenfilename(
        title="Виберіть TXT файл",
        filetypes=[("Text files", "*.txt")],
    )
    if not file_path:
        print("Файл не вибрано.")
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read().strip()
    except Exception as e:
        print(f"Помилка читання файлу: {e}")
        return

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Використовується пристрій: {device}")

    try:
        # Ініціалізація моделей
        v = Verbalizer(device_str=device)
        corrector = GrammarCorrector(device_str=device)

        # Чанкуємо вхідний текст, щоб не втратити частини
        sentences = split_into_sentences(text)
        chunks = chunk_sentences(sentences, max_chars=MAX_CHUNK_CHARS)

        verbalized_chunks = []
        for i, ch in enumerate(chunks, 1):
            print(f"Вербалізація чанк {i}/{len(chunks)}...")
            verbalized = v.generate_text(ch, max_length=GEN_MAX_LENGTH)
            verbalized_chunks.append(verbalized)

        # Склеюємо вербалізовані чанки і коригуємо теж по чанках
        verbalized_full = " ".join(verbalized_chunks)

        # Коригуємо по чанках знову (щоб уникнути усічення)
        sentences2 = split_into_sentences(verbalized_full)
        chunks2 = chunk_sentences(sentences2, max_chars=MAX_CHUNK_CHARS)

        corrected_chunks = []
        for i, ch in enumerate(chunks2, 1):
            print(f"Корекція граматики чанк {i}/{len(chunks2)}...")
            corrected = corrector.correct_grammar(ch, max_length=GEN_MAX_LENGTH)
            corrected_chunks.append(corrected)

        corrected_full = " ".join(corrected_chunks)

        # Збереження
        base, ext = os.path.splitext(file_path)
        out_path = base + "_out.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(corrected_full)

        print(f"✅ Збережено результат у: {out_path}")
        print("Короткий превʼю результату:")
        print(corrected_full[:2000])

    except Exception as e:
        print(f"Виникла неочікувана помилка під час обробки: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
