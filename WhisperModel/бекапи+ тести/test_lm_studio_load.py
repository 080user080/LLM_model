#!/usr/bin/env python3
"""
Тестовий скрипт для автоматичного завантаження моделі в LM Studio
"""
import requests
import time
import json

BASE_URL = "http://localhost:1234"
DESIRED_MODEL = "openai/gpt-oss-20b"

def get_current_model():
    """Отримати поточну завантажену модель"""
    try:
        response = requests.get(f"{BASE_URL}/v1/models", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                return data['data'][0]['id']
        return None
    except Exception as e:
        print(f"❌ Помилка отримання моделі: {e}")
        return None

def load_model(model_name):
    """Спроба завантажити модель через API"""
    print(f"🔄 Спроба завантажити {model_name}...")
    
    # Варіант 1: POST /v1/models/load
    try:
        response = requests.post(
            f"{BASE_URL}/v1/models/load",
            json={"model": model_name},
            timeout=30
        )
        print(f"   Статус код: {response.status_code}")
        print(f"   Відповідь: {response.text[:200]}")
        
        if response.status_code in [200, 201, 204]:
            return True
    except Exception as e:
        print(f"   ⚠️  Варіант 1 не спрацював: {e}")
    
    # Варіант 2: POST /v1/models з параметром model
    try:
        response = requests.post(
            f"{BASE_URL}/v1/models",
            json={"model": model_name, "action": "load"},
            timeout=30
        )
        print(f"   Варіант 2 - Статус: {response.status_code}")
        if response.status_code in [200, 201, 204]:
            return True
    except Exception as e:
        print(f"   ⚠️  Варіант 2 не спрацював: {e}")
    
    # Варіант 3: PATCH /v1/models
    try:
        response = requests.patch(
            f"{BASE_URL}/v1/models",
            json={"model": model_name},
            timeout=30
        )
        print(f"   Варіант 3 - Статус: {response.status_code}")
        if response.status_code in [200, 201, 204]:
            return True
    except Exception as e:
        print(f"   ⚠️  Варіант 3 не спрацював: {e}")
    
    return False

def wait_for_model(model_name, max_wait=30):
    """Почекати поки модель завантажиться"""
    print(f"⏳ Очікування завантаження {model_name}...")
    
    for i in range(max_wait):
        time.sleep(1)
        current = get_current_model()
        
        if current == model_name:
            print(f"✅ Модель {model_name} завантажена за {i+1}с!")
            return True
        
        if i % 5 == 0:
            print(f"   {i}с... (поточна: {current})")
    
    print(f"⏱️  Тайм-аут {max_wait}с")
    return False

def main():
    """Головна функція тестування"""
    print("=" * 60)
    print("🧪 ТЕСТ АВТОЗАВАНТАЖЕННЯ МОДЕЛІ В LM STUDIO")
    print("=" * 60)
    
    # 1. Перевірка з'єднання
    print("\n1️⃣ Перевірка з'єднання з LM Studio...")
    try:
        response = requests.get(f"{BASE_URL}/v1/models", timeout=3)
        if response.status_code == 200:
            print("   ✅ LM Studio доступний")
        else:
            print(f"   ❌ LM Studio повернув код {response.status_code}")
            return
    except Exception as e:
        print(f"   ❌ LM Studio недоступний: {e}")
        print("   💡 Переконайтеся що LM Studio запущено")
        return
    
    # 2. Перевірка поточної моделі
    print("\n2️⃣ Перевірка поточної моделі...")
    current_model = get_current_model()
    
    if current_model:
        print(f"   📝 Поточна модель: {current_model}")
        
        if current_model == DESIRED_MODEL:
            print(f"   ✅ Потрібна модель вже завантажена!")
            return
        else:
            print(f"   ⚠️  Потрібна інша модель: {DESIRED_MODEL}")
    else:
        print("   ⚠️  Жодної моделі не завантажено")
    
    # 3. Спроба завантажити модель
    print(f"\n3️⃣ Завантаження {DESIRED_MODEL}...")
    
    if load_model(DESIRED_MODEL):
        # 4. Очікування завантаження
        print("\n4️⃣ Очікування завантаження...")
        if wait_for_model(DESIRED_MODEL, max_wait=30):
            print("\n✅ УСПІХ! Модель готова до роботи")
            
            # 5. Тестовий запит
            print("\n5️⃣ Тестовий запит до моделі...")
            try:
                test_response = requests.post(
                    f"{BASE_URL}/v1/chat/completions",
                    json={
                        "model": DESIRED_MODEL,
                        "messages": [{"role": "user", "content": "Привіт!"}],
                        "max_tokens": 50,
                        "stream": False
                    },
                    timeout=30
                )
                if test_response.status_code == 200:
                    result = test_response.json()
                    answer = result['choices'][0]['message']['content']
                    print(f"   ✅ Відповідь моделі: {answer}")
                else:
                    print(f"   ⚠️  Помилка: {test_response.status_code}")
            except Exception as e:
                print(f"   ⚠️  Помилка тестового запиту: {e}")
        else:
            print("\n⚠️  Модель не завантажилась за 30 секунд")
            print("   💡 Спробуйте завантажити вручну в LM Studio")
    else:
        print("\n❌ Не вдалося завантажити модель через API")
        print("💡 Можливі причини:")
        print("   • API завантаження не підтримується вашою версією LM Studio")
        print("   • Модель не скачана (перевірте в LM Studio -> My Models)")
        print("   • LM Studio зайнятий іншою операцією")
        print("\n💡 Рішення:")
        print("   1. Завантажте модель вручну в LM Studio")
        print("   2. Або дочекайтесь доки код автоматично перевірить через 15с")

if __name__ == "__main__":
    main()
