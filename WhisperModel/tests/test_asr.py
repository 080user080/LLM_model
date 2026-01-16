# tests/test_asr.py
"""Тест точності ASR (Automatic Speech Recognition)"""
import sys
import os
import time
from pathlib import Path

# Додаємо шлях до проєкту
sys.path.append(str(Path(__file__).parent.parent))

import sounddevice as sd
import numpy as np
from colorama import Fore, Back, Style, init  # ДОДАНО: Back
from functions.logic_stt import get_stt_engine
from functions.logic_audio_filtering import get_audio_filter
from functions.logic_audio import text_similarity
from functions.config import SAMPLE_RATE, AGC_TARGET_VOLUME

# Ініціалізація colorama
init(autoreset=True)

# Тестові команди (50 штук - покриття всіх категорій)
TEST_COMMANDS = [
    # Базові команди (10)
    "відкрий блокнот",
    "закрий блокнот",
    "відкрий хром",
    "відкрий калькулятор",
    "який час",
    "яка дата",
    "порахуй два плюс два",
    "порахуй п'ять множити на три",
    "дякую",
    "до побачення",
    
    # Команди з помилками (10) - тест виправлень
    "вікрий блокнот",  # помилка в "відкрий"
    "відкри блокнот",   # пропущена "й"
    "блокнат",          # помилка в "блокнот"
    "відкрий блукнот",  # перестановка
    "парахуй два",      # помилка в "порахуй"
    "який тас",         # помилка в "час"
    "закрий хром",      # правильно, тест базової
    "закрий калькулятор", # правильно
    
    # Складні команди (10)
    "відкрий сайт гугл і знайди погоду",
    "створи папку тест на диску С",
    "покажи список файлів у папці документи",
    "відкрий провідник і перейди до диска Д",
    "запиши у файл test.txt рядок привіт світ",
    "порахуй скільки буде двадцять один поділити на три",
    "відкрий блокнот з файлом C:\\\\test.txt",
    "закрий всі програми крім хрому",
    "яка погода в Києві",
    "переклади слово hello на українську",
    
    # Голосові команди (10)
    "Марк відкрий блокнот",
    "Марк який час",
    "Марк порахуй три плюс чотири",
    "Марк дякую",
    "Марк закрий хром",
    "привіт Марк відкрий калькулятор",
    "Марк відкрий сайт ютуб",
    "Марк покажи дату",
    "Марк створи папку",
    "Марк до побачення",
    
    # Шумові команди (10) - з паузами
    "відкрий    блокнот",  # подвійний пробіл
    "відкрий ... блокнот", # пауза
    "який     час",        # множинні пробіли
    "порахуй (пауза) два плюс два",
    "закрий   хром",
    "Марк   відкрий   хром",
    "блокнот",             # тільки ключове слово
    "час",                 # тільки ключове слово
    "відкрий",            # неповна команда
    "Марк",               # тільки ім'я
]

def record_command(prompt_text, duration=3):
    """Записати одну команду з візуальним зворотним відліком"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.YELLOW}🎯 {prompt_text}")
    print(f"{Fore.CYAN}{'='*60}")
    print(f"{Fore.WHITE}Говоріть через 2 секунди...")
    
    # Зворотній відлік
    for i in range(2, 0, -1):
        print(f"{Fore.YELLOW}{i}...", end="", flush=True)
        time.sleep(1)
    
    print(f"{Fore.GREEN}🎤 ЗАПИС!", end="", flush=True)
    
    # Запис
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype=np.float32,
        blocking=True
    )
    audio = np.squeeze(audio)
    
    print(f" {Fore.GREEN}✓")
    return audio

def test_asr_accuracy():
    """Головна функція тестування"""
    print(f"{Back.BLUE}{Fore.WHITE}{'='*60}")
    print(f"{Back.BLUE}{Fore.WHITE}  ТЕСТ ASR: 50 КОМАНД  {Style.RESET_ALL}")
    print(f"{Back.BLUE}{Fore.WHITE}{'='*60}\n")
    
    # Ініціалізація
    stt = get_stt_engine()
    audio_filter = get_audio_filter()
    
    print(f"{Fore.CYAN}📊 Модель: {stt.get_available_models()}")
    print(f"{Fore.CYAN}🎛️  AGC: {'ON' if audio_filter.current_gain > 1.0 else 'OFF'}")
    print(f"{Fore.CYAN}🔇 Noise reducer: {'ON' if audio_filter.noise_reducer else 'OFF'}\n")
    
    # Запит підтвердження
    input(f"{Fore.YELLOW}Натисніть Enter для початку тесту...")
    
    results = []
    correct_count = 0
    
    for idx, expected_command in enumerate(TEST_COMMANDS, 1):
        # Запис команди
        audio = record_command(
            f"Команда {idx}/50: {expected_command}",
            duration=4
        )
        
        # Фільтрація
        audio_filtered = audio_filter.process_audio(audio)
        
        # Розпізнавання
        result = stt.transcribe(audio_filtered)
        
        # Вимкнути AGC після першої команди (калібрування завершено)
        if idx == 1:
            audio_filter.current_gain = min(audio_filter.current_gain, 10.0)
        
        # Оцінка
        similarity = text_similarity(result, expected_command)
        is_correct = similarity >= 0.8
        
        # Зберегти результат
        results.append({
            "expected": expected_command,
            "actual": result,
            "similarity": similarity,
            "correct": is_correct
        })
        
        # Вивести результат
        status = f"{Fore.GREEN}✓" if is_correct else f"{Fore.RED}✗"
        print(f"\n{status} Результат: '{result}' (схожість: {similarity:.2f})")
        
        if is_correct:
            correct_count += 1
        
        # Пауза між командами
        time.sleep(0.5)
    
    # Звіт
    print(f"\n\n{Back.CYAN}{Fore.BLACK}{'='*60}")
    print(f"{Back.CYAN}{Fore.BLACK}  ПІДСУМКИ  {Style.RESET_ALL}")
    print(f"{Back.CYAN}{Fore.BLACK}{'='*60}\n")
    
    accuracy = correct_count / len(TEST_COMMANDS)
    
    print(f"{Fore.CYAN}📊 Загальна точність: {correct_count}/{len(TEST_COMMANDS)} = {Fore.WHITE}{accuracy:.1%}\n")
    
    # Детальний звіт
    print(f"{Fore.YELLOW}📋 Деталі по категоріях:")
    
    categories = {
        "Базові": (0, 10),
        "З помилками": (10, 20),
        "Складні": (20, 30),
        "Голосові": (30, 40),
        "Шумові": (40, 50),
    }
    
    for cat_name, (start, end) in categories.items():
        cat_results = results[start:end]
        cat_correct = sum(r["correct"] for r in cat_results)
        cat_acc = cat_correct / len(cat_results)
        
        status_icon = "✅" if cat_acc >= 0.9 else "⚠️" if cat_acc >= 0.7 else "❌"
        print(f"   {status_icon} {cat_name}: {cat_correct}/{len(cat_results)} = {cat_acc:.1%}")
    
    # Невірні команди
    print(f"\n{Fore.RED}❌ Невірні команди:")
    wrong = [r for r in results if not r["correct"]]
    for r in wrong[:10]:  # Тільки перші 10
        print(f"   Очікувалось: '{r['expected']}'")
        print(f"   Отримано:    '{r['actual']}'")
        print(f"   Схожість:    {r['similarity']:.2f}\n")
    
    # Фінальний вердикт
    print(f"{Fore.CYAN}{'='*60}")
    if accuracy >= 0.9:
        print(f"{Fore.GREEN}✅ ТЕСТ ПРОЙДЕНО! ASR готовий до використання.")
        print(f"{Fore.GREEN}   Точність {accuracy:.1%} >= 90%")
    elif accuracy >= 0.8:
        print(f"{Fore.YELLOW}⚠️  ТЕСТ СЕРЕДНІЙ! ASR потребує доопрацювання.")
        print(f"{Fore.YELLOW}   Точність {accuracy:.1%} >= 80%")
    else:
        print(f"{Fore.RED}❌ ТЕСТ НЕ ПРОЙДЕНО! ASR не працює.")
        print(f"{Fore.RED}   Точність {accuracy:.1%} < 80%")
    print(f"{Fore.CYAN}{'='*60}\n")
    
    # Зберегти звіт
    report_path = Path("tests/asr_report.json")
    report_path.parent.mkdir(exist_ok=True)
    
    import json
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "accuracy": accuracy,
            "correct": correct_count,
            "total": len(TEST_COMMANDS),
            "results": results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"{Fore.CYAN}💾 Звіт збережено: {report_path}\n")
    
    return accuracy >= 0.9

if __name__ == "__main__":
    try:
        success = test_asr_accuracy()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}Тест перервано користувачем.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n{Fore.RED}❌ Помилка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)