# verbalizer_model_only.py
# GPT

import torch
from transformers import MBartForConditionalGeneration, AutoTokenizer
from tkinter import Tk, filedialog
import os

# Оскільки ми покладаємося лише на модель, BASIC_RULES та pymorphy2 видалено.

class Verbalizer:
    def __init__(self, device_str="cpu"):
        model_name = "skypro1111/mbart-large-50-verbalization"

        if device_str == "cuda" and not torch.cuda.is_available():
            device_str = "cpu"
        self.device = torch.device(device_str)

        print("Завантаження моделі...")
        self.model = MBartForConditionalGeneration.from_pretrained(
            model_name,
            low_cpu_mem_usage=True,
        )
        self.model.to(self.device)
        self.model.eval()

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.tokenizer.src_lang = "uk_XX"
        self.tokenizer.tgt_lang = "uk_XX"

    def generate_text(self, text):
        input_text = "<verbalization>:" + text
        encoded = self.tokenizer(
            input_text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=1024,
        )
        input_ids = encoded["input_ids"].to(self.device)
        attention_mask = encoded.get("attention_mask")
        if attention_mask is not None:
            attention_mask = attention_mask.to(self.device)

        output_ids = self.model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            max_length=1024,
            num_beams=5,
            early_stopping=True,
        )

        result = self.tokenizer.decode(output_ids[0], skip_special_tokens=True)
        return result.strip()

# Функцію apply_smart_rules видалено.
# Функцію apply_pymorphy2 видалено.

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
        v = Verbalizer(device_str=device)

        print("Генерація тексту...")
        verbalized_text = v.generate_text(text)

        # Будь-яка додаткова обробка (правила, pymorphy2) видалена
        # згідно з вашим запитом.

        base, ext = os.path.splitext(file_path)
        out_path = base + "_out.txt"
        
        try:
            # Зберігаємо безпосередньо результат роботи моделі
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(verbalized_text)
            print(f"✅ Збережено результат у: {out_path}")
        except Exception as e:
            print(f"Помилка збереження файлу: {e}")

    except Exception as e:
        print(f"Виникла неочікувана помилка під час обробки: {e}")


if __name__ == "__main__":
    main()

