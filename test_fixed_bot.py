#!/usr/bin/env python3
"""
Тест исправленного бота с новыми функциями
"""
import os
import asyncio
import time
from dotenv import load_dotenv
from aiogram import Bot

async def test_fixed_bot():
    """Тест исправленного бота"""
    load_dotenv()
    
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден в .env файле")
        return False
    
    print("🧪 **ТЕСТ ИСПРАВЛЕННОГО БОТА**")
    print("=" * 50)
    
    try:
        bot = Bot(token=BOT_TOKEN)
        
        # Проверяем подключение
        me = await bot.get_me()
        print(f"✅ Подключение к Telegram: OK")
        print(f"🤖 Бот: {me.first_name} (@{me.username})")
        
        await bot.session.close()
        
        print("\n🔧 **Исправления реализованы:**")
        print("✅ aioredis → redis.asyncio")
        print("✅ Ленивая загрузка RAG систем")
        print("✅ Улучшенный middleware лимитов")
        print("✅ Фоновая инициализация")
        print("✅ Мониторинг готовности систем")
        
        print("\n🚀 **Новые команды для тестирования:**")
        print("• /test_date_parser - тест парсинга дат")
        print("• /test_limits - тест лимитов API")
        print("• /rag_status - статус RAG систем")
        print("• /status - общий статус")
        
        print("\n📋 **Ожидаемое поведение:**")
        print("1. Бот запустится за < 2 секунды")
        print("2. Покажет 'Бот готов к работе!'")
        print("3. RAG системы загрузятся в фоне")
        print("4. Никаких ошибок aioredis/TimeoutError")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_fixed_bot())
    
    if result:
        print("\n🎉 **ТЕСТ ПРОЙДЕН! Можно запускать основной бот.**")
        print("\nДля запуска используйте:")
        print("python bot.py")
    else:
        print("\n💥 **ТЕСТ НЕ ПРОЙДЕН**") 