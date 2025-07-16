#!/usr/bin/env python3
"""
Минимальная версия основного бота без RAG систем
"""
import os
import logging
import sys
from typing import Optional
import asyncio
import time
from datetime import datetime
from dotenv import load_dotenv

import aiohttp
from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Проверка токена
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY не найден в переменных окружения")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния FSM
class UserState(StatesGroup):
    IN_QUIZ = State()

# Простые обработчики
@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Приветственное сообщение"""
    welcome_text = (
        "👋 Добро пожаловать в бот Национального детского технопарка!\n\n"
        "🤖 Я ваш интеллектуальный помощник (минимальная версия).\n\n"
        "📝 Доступные команды:\n"
        "• /help - получить помощь\n"
        "• /status - статус бота\n"
        "• /test - тестовое сообщение\n\n"
        "💬 Или просто напишите мне любое сообщение!"
    )
    
    await message.answer(welcome_text)

@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Помощь"""
    help_text = (
        "📞 Помощь по боту\n\n"
        "Это минимальная версия бота для тестирования.\n"
        "В полной версии доступны:\n"
        "• RAG система для ответов на вопросы\n"
        "• Система операторов\n"
        "• Календарь смен\n"
        "• Проверка списков\n"
        "• И многое другое!"
    )
    
    await message.answer(help_text)

@dp.message(Command("status"))
async def cmd_status(message: Message):
    """Статус бота"""
    status_text = (
        "ℹ️ Статус бота:\n\n"
        "✅ Бот работает\n"
        "✅ Подключение к Telegram активно\n"
        "✅ Команды обрабатываются\n"
        "⚠️ RAG системы отключены (тестовая версия)\n\n"
        f"🕒 Время: {datetime.now().strftime('%H:%M:%S')}\n"
        f"📅 Дата: {datetime.now().strftime('%d.%m.%Y')}"
    )
    
    await message.answer(status_text)

@dp.message(Command("test"))
async def cmd_test(message: Message):
    """Тестовое сообщение"""
    await message.answer("🧪 Тест пройден успешно! Бот работает корректно.")

@dp.message(F.text)
async def handle_text(message: Message):
    """Обработка текстовых сообщений"""
    user_text = message.text.lower()
    
    # Простые ответы
    if any(word in user_text for word in ['привет', 'hello', 'здравствуй']):
        await message.answer(
            "👋 Привет! Я тестовая версия бота технопарка.\n"
            "Для получения полной функциональности нужна основная версия с RAG системой."
        )
    elif any(word in user_text for word in ['спасибо', 'thanks']):
        await message.answer("🙏 Пожалуйста! Рад помочь!")
    elif any(word in user_text for word in ['пока', 'bye', 'до свидания']):
        await message.answer("👋 До свидания! Удачи!")
    else:
        await message.answer(
            f"💬 Вы написали: {message.text}\n\n"
            "ℹ️ Это тестовая версия бота. Для полных ответов на вопросы "
            "нужна основная версия с RAG системой.\n\n"
            "🔧 Доступные команды: /help, /status, /test"
        )

# Запуск бота
async def main():
    logger.info("🚀 Запуск минимальной версии бота Национального детского технопарка...")
    logger.info("⚠️ RAG системы отключены для тестирования")
    logger.info("✅ Бот готов к работе!")
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main()) 