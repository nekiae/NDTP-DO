#!/usr/bin/env python3
"""
Тест подключения к Telegram API
"""
import os
import asyncio
from dotenv import load_dotenv
from aiogram import Bot

async def test_telegram_connection():
    """Тест подключения к Telegram API"""
    load_dotenv()
    
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден в .env файле")
        return False
    
    print(f"🔑 BOT_TOKEN найден: {BOT_TOKEN[:10]}...")
    
    try:
        bot = Bot(token=BOT_TOKEN)
        print("🤖 Создан объект бота")
        
        # Проверяем подключение
        me = await bot.get_me()
        print("✅ Успешное подключение к Telegram API")
        print(f"🤖 Имя бота: {me.first_name}")
        print(f"🆔 ID бота: {me.id}")
        print(f"👤 Username: @{me.username}")
        
        await bot.session.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка подключения к Telegram API: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Тест подключения к Telegram API")
    print("=" * 50)
    
    result = asyncio.run(test_telegram_connection())
    
    if result:
        print("\n✅ Тест пройден успешно!")
    else:
        print("\n❌ Тест не пройден!") 