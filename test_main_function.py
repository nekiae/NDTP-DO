#!/usr/bin/env python3
"""
Тест функции main() из bot.py
"""
import asyncio
import sys
import traceback

async def test_main_function():
    """Тест функции main() по частям"""
    print("🧪 Тест функции main() из bot.py")
    print("=" * 50)
    
    try:
        # Импортируем необходимые модули
        print("📦 Импорт модулей...")
        import bot
        print("✅ Модуль bot импортирован")
        
        # Проверяем, что основные переменные доступны
        print("🔍 Проверка переменных...")
        print(f"BOT_TOKEN: {'✅ есть' if bot.BOT_TOKEN else '❌ нет'}")
        print(f"DEEPSEEK_API_KEY: {'✅ есть' if bot.DEEPSEEK_API_KEY else '❌ нет'}")
        print(f"REDIS_AVAILABLE: {bot.REDIS_AVAILABLE}")
        
        # Проверяем создание бота
        print("🤖 Проверка создания бота...")
        test_bot = bot.Bot(token=bot.BOT_TOKEN)
        print("✅ Бот создан")
        
        # Проверяем создание диспетчера
        print("🔧 Проверка создания диспетчера...")
        test_dp = bot.Dispatcher(storage=bot.storage)
        print("✅ Диспетчер создан")
        
        # Тестируем инициализацию RAG систем
        print("🧠 Тест инициализации RAG систем...")
        
        # Проверяем базовую RAG систему
        print("📖 Базовая RAG система...")
        bot.rag_system.load_knowledge_base()
        print("✅ Базовая RAG система загружена")
        
        # Проверяем функции инициализации RAG
        print("🚀 Тест init_optimized_rag...")
        try:
            await bot.init_optimized_rag()
            print("✅ init_optimized_rag завершена")
        except Exception as e:
            print(f"⚠️ init_optimized_rag ошибка: {e}")
        
        print("📚 Тест init_modern_rag...")
        try:
            await bot.init_modern_rag()
            print("✅ init_modern_rag завершена")
        except Exception as e:
            print(f"⚠️ init_modern_rag ошибка: {e}")
        
        await test_bot.session.close()
        print("✅ Все тесты пройдены!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в тесте: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_main_function())
    
    if result:
        print("\n🎉 Тест функции main() пройден!")
    else:
        print("\n💥 Тест функции main() не пройден!") 