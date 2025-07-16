#!/usr/bin/env python3
"""
Упрощенная версия бота с детальным логированием
"""
import os
import logging
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("🚀 Начинаем инициализацию бота...")
    
    # Загрузка переменных окружения
    logger.info("📁 Загружаем переменные окружения...")
    load_dotenv()
    
    # Проверка токена
    logger.info("🔑 Проверяем токен...")
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден в переменных окружения")
        return
    
    logger.info(f"✅ BOT_TOKEN найден: {BOT_TOKEN[:10]}...")
    
    # Создание объектов
    logger.info("🤖 Создаем объект бота...")
    bot = Bot(token=BOT_TOKEN)
    
    logger.info("💾 Создаем хранилище...")
    storage = MemoryStorage()
    
    logger.info("🔧 Создаем диспетчер...")
    dp = Dispatcher(storage=storage)
    
    # Простой обработчик
    logger.info("📝 Регистрируем обработчики...")
    
    @dp.message()
    async def echo(message):
        await message.answer(f"Эхо: {message.text}")
    
    logger.info("✅ Все компоненты инициализированы!")
    
    # Запуск
    logger.info("🚀 Запускаем polling...")
    
    async def start_polling():
        logger.info("🔄 Начинаем polling...")
        await dp.start_polling(bot)
    
    try:
        asyncio.run(start_polling())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске: {e}")

if __name__ == "__main__":
    main() 