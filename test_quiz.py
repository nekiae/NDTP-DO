#!/usr/bin/env python3
"""
Тестовый файл для проверки квиз модуля
"""
import asyncio
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

async def test_quiz_module():
    """Тестирует основные функции квиза"""
    print("🎯 Тестирование квиз модуля...")
    
    try:
        # Проверяем импорт модуля
        from quiz_mod import (
            load_system_prompt, 
            check_user_quota, 
            get_quiz_stats,
            DEEPSEEK_AVAILABLE,
            SYSTEM_PROMPT,
            quiz_start_callback
        )
        print("✅ Квиз модуль успешно импортирован")
        
        # Проверяем системный промпт
        if SYSTEM_PROMPT:
            print(f"✅ Системный промпт загружен ({len(SYSTEM_PROMPT)} символов)")
            if "DIRECTIONS" in SYSTEM_PROMPT:
                print("✅ Направления найдены в промпте")
            else:
                print("❌ Направления не найдены в промпте")
        else:
            print("❌ Системный промпт не загружен")
        
        # Проверяем DeepSeek
        if DEEPSEEK_AVAILABLE:
            print("✅ DeepSeek API доступен")
        else:
            print("❌ DeepSeek API недоступен")
        
        # Проверяем квоту пользователя
        test_user_id = 123456789
        quota_ok = await check_user_quota(test_user_id)
        print(f"✅ Квота пользователя: {quota_ok}")
        
        # Проверяем статистику
        stats = get_quiz_stats()
        print(f"✅ Статистика квиза: {stats}")
        
        print("\n🎉 Все тесты пройдены!")
        
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
    except Exception as e:
        print(f"❌ Ошибка теста: {e}")

async def test_deepseek_connection():
    """Тестирует подключение к DeepSeek API"""
    print("\n🧠 Тестирование подключения к DeepSeek API...")
    
    try:
        from quiz_mod import ask_llm, DEEPSEEK_AVAILABLE
        
        if not DEEPSEEK_AVAILABLE:
            print("❌ DeepSeek API недоступен")
            return
        
        # Простой тест запроса
        test_history = [
            {"role": "user", "content": "Привет! Как дела?"}
        ]
        
        response = await ask_llm(test_history)
        if response and not response.startswith("❌"):
            print(f"✅ DeepSeek ответил: {response[:100]}...")
        else:
            print(f"❌ Ошибка DeepSeek: {response}")
            
    except Exception as e:
        print(f"❌ Ошибка теста DeepSeek: {e}")

if __name__ == "__main__":
    asyncio.run(test_quiz_module())
    asyncio.run(test_deepseek_connection()) 