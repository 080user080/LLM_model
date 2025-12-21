import re
import os
import shutil
from tkinter import Tk, filedialog
from datetime import datetime

# --- КОНФІГУРАЦІЯ ТЕГІВ І ПРАВИЛ ---
# "position": "precede_line" (на окремому рядку перед рядком) або "after_match_newline" (на окремому рядку одразу після збігу).

SFX_MAP = [
    # ----------------------------------------------------
    # 1. СТРУКТУРНІ ТЕГИ (precede_line) - Включено #p2 після #r
    # ----------------------------------------------------
    {
        "tag": "#r",
        # Шукає "РОЗДІЛ X", "ЧАСТИНА III" або просто "ГЛАВА".
        "keywords": re.compile(r"^\s*(РОЗДІЛ|ЧАСТИНА|ГЛАВА)\s*([IVXLCDM\d]+\.?|\s*)$", re.IGNORECASE | re.MULTILINE),
        "confidence": 1.0,
        "position": "precede_line",
        "post_tag": "#p2", # Додаємо #p2 після заголовка (на тому ж рядку)
        "description": "Розділ/Глава + Пауза"
    },
    # ----------------------------------------------------
    # 2. ТЕГИ ДІЇ/ЕФЕКТУ (after_match_newline)
    # ----------------------------------------------------
    {
        "tag": "#d",
        "keywords": re.compile(r"(\w+\s+(відчинив|зачинив|заскрипіли|стук у)\s+двері)", re.IGNORECASE),
        "confidence": 0.95,
        "position": "after_match_newline",
        "description": "Двері/Скрип"
    },
    {
        "tag": "#v",
        "keywords": re.compile(r"(прогримів вибух|голосно бахнуло|постріл пролунав|грім вдарив|крик пролунав)", re.IGNORECASE),
        "confidence": 0.9,
        "position": "after_match_newline",
        "description": "Вибух/Постріл/Різка дія"
    },
    {
        "tag": "#heart",
        "keywords": re.compile(r"(серце шалено калатало|прискорене серцебиття|завмерло серце|жах охопив)", re.IGNORECASE),
        "confidence": 0.85,
        "position": "after_match_newline",
        "description": "Серцебиття/Напруга"
    },
    {
        "tag": "#rain",
        "keywords": re.compile(r"(за вікном зашумів дощ|тихо падає дощ|шум дощу|вітер завив)", re.IGNORECASE),
        "confidence": 0.8,
        "position": "after_match_newline",
        "description": "Дощ/Вітер (Атмосфера)"
    },
    {
        "tag": "#step",
        "keywords": re.compile(r"(кроки пролунали|чути кроки|ступив на підлогу|тихий стукіт каблуків)", re.IGNORECASE),
        "confidence": 0.8,
        "position": "after_match_newline",
        "description": "Кроки/Рух"
    },
]

def process_text(text: str) -> str:
    """Обробляє текст, вставляючи SFX теги згідно з правилами SFX_MAP."""
    # Змінна, що зберігає оброблений текст. Початкове значення - текст, що обробляється.
    processed_text = text
    tags_found = 0
    
    # 1. Обробка структурних тегів (precede_line)
    lines = processed_text.splitlines(keepends=True) 
    
    for i in range(len(lines)):
        line = lines[i]
        line_stripped = line.strip()
        
        if not line_stripped or line_stripped.startswith('#'):
            continue

        for rule in SFX_MAP:
            if rule["position"] == "precede_line":
                if rule["keywords"].search(line):
                    # 1.1. Вставка #r на окремий рядок
                    tag_r = f"\n{rule['tag']}\n"
                    
                    # 1.2. Додавання #p2 після заголовка на тому ж рядку
                    if "post_tag" in rule:
                        # Перевіряємо, чи немає вже тегу в кінці рядка
                        if not line_stripped.endswith(rule["post_tag"]):
                             # Додаємо post_tag до самого рядка
                             lines[i] = lines[i].rstrip() + f" {rule['post_tag']}" + lines[i][-1:]
                        
                    # 1.3. Вставляємо #r на окремий рядок перед поточним рядком
                    if i > 0 and lines[i-1].strip() == rule['tag']:
                         continue
                        
                    lines[i] = f"{tag_r}{lines[i]}"
                    tags_found += 1
                    break 
    
    processed_text = "".join(lines)


    # 2. Обробка тегів дії/ефекту (after_match_newline)
    for rule in SFX_MAP:
        if rule["position"] == "after_match_newline":
            
            def tag_replacer(match):
                """Вставляє тег на окремому рядку одразу після знайденого збігу."""
                nonlocal tags_found
                full_match = match.group(0)
                tag_to_insert = f"\n{rule['tag']}"
                
                # Запобігання дублюванню тегу (проста перевірка)
                if full_match.endswith(rule['tag']):
                    return full_match

                tags_found += 1
                
                # Вставляємо тег із перенесенням рядка
                if not full_match.endswith('\n'):
                    return f"{full_match}{tag_to_insert}\n"
                else:
                    return f"{full_match.rstrip()}{tag_to_insert}\n"


            # Використовуємо re.sub для заміни всіх збігів у тексті
            processed_text, count = rule["keywords"].subn(tag_replacer, processed_text)
            
    # Фінальне очищення: видаляємо зайві пробіли та множинні переноси рядків
    processed_text = re.sub(r' +', ' ', processed_text)
    processed_text = re.sub(r'\n{3,}', '\n\n', processed_text).strip()
    
    print(f"\n✅ Обробка завершена. Знайдено та вставлено {tags_found} нових тегів.")
    
    # ВИПРАВЛЕННЯ: Повертаємо processed_text
    return processed_text

def main():
    """Головна функція для вибору файлу, створення бекапу та обробки."""
    root = Tk()
    root.withdraw()

    file_path = filedialog.askopenfilename(
        title="Виберіть текстовий файл (.txt) для автоматичної розмітки",
        filetypes=(("Текстові файли", "*.txt"), ("Всі файли", "*.*"))
    )

    if not file_path:
        print("Операцію скасовано. Файл не вибрано.")
        return

    print(f"\n📁 Вибрано файл: {file_path}")

    # 1. Створення резервної копії для безпечного перезапису
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{file_path}.{timestamp}.bak"
    try:
        shutil.copy2(file_path, backup_path)
        print(f"💾 Створено резервну копію: {backup_path}")
    except Exception as e:
        print(f"❌ Помилка створення резервної копії. Перезапис неможливий: {e}")
        return

    # 2. Читання вмісту файлу
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        print("📄 Файл успішно прочитано. Початок обробки...")
    except Exception as e:
        print(f"❌ Помилка читання файлу: {e}")
        return

    # 3. Обробка тексту
    processed_content = process_text(original_content)

    # 4. Перевірка та безпечний перезапис
    if processed_content.strip() == original_content.strip():
        print("ℹ️ Змін не знайдено. Файл не буде перезаписано.")
        os.remove(backup_path) 
        return

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(processed_content)
        print(f"✨ Файл успішно оновлено та перезаписано: {file_path}")
    except Exception as e:
        print(f"❌ Помилка при перезапису файлу: {e}")
        print(f"❗ Оригінальний файл не змінено. Оригінал збережено у: {backup_path}")


if __name__ == "__main__":
    print("--- Автоматична розмітка тексту SFX-тегами ---")
    print("❗ Структурні теги вставляються перед рядком, теги дії - після ключової фрази.")
    main()