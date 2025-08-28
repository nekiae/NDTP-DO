import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import aiohttp
from aiogram import Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Импорт для инлайн-кнопок
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import config

logger = logging.getLogger(__name__)

# Импорт DeepSeek API - создаём собственный клиент вместо импорта из bot.py


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

class DeepSeekAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5)
    )
    async def _make_request(self, payload: dict) -> Optional[dict]:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                DEEPSEEK_API_URL,
                headers=self.headers,
                json=payload
            ) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    retry_after = response.headers.get('Retry-After', '60')
                    wait_time = int(retry_after)
                    logger.warning(f"⚠️ Rate limit hit, waiting {wait_time} seconds")
                    await asyncio.sleep(wait_time)
                    raise Exception("Rate limit exceeded")
                else:
                    error_text = await response.text()
                    logger.error(f"❌ DeepSeek API error {response.status}: {error_text}")
                    raise Exception(f"API error: {response.status}")

    async def get_response(self, messages: list, temperature: float = 0.7) -> str:
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2000,
            "stream": False
        }
        
        try:
            response = await self._make_request(payload)
            return response['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"❌ Ошибка DeepSeek API: {e}")
            raise

# Создаём глобальный экземпляр DeepSeek API
if DEEPSEEK_API_KEY:
    deepseek = DeepSeekAPI(DEEPSEEK_API_KEY)
    DEEPSEEK_AVAILABLE = True
    logger.info("✅ DeepSeek API подключен для квиза")
else:
    deepseek = None
    DEEPSEEK_AVAILABLE = False
    logger.warning("⚠️ DeepSeek API key не найден")

# Создаём собственный семафор для контроля количества запросов
llm_semaphore = asyncio.Semaphore(3)  # Максимум 3 одновременных запроса

# FSM состояния для квиза
class QuizState(StatesGroup):
    Q1 = State()
    Q2 = State()
    Q3 = State()
    Q4 = State()
    Q5 = State()
    DONE = State()

# Семафор для ограничения параллельных квизов
QUIZ_SEMAPHORE = asyncio.Semaphore(3)

# Хранилище квот пользователей (в реальном проекте использовать Redis)
user_quiz_quota = {}

# Загрузка системного промпта
def load_system_prompt() -> str:
    """Загружает системный промпт для квиза"""
    try:
        with open(config.prompts_dir / "quiz_system_prompt.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error("❌ Файл quiz_system_prompt.txt не найден")
        return ""
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки системного промпта: {e}")
        return ""

SYSTEM_PROMPT = load_system_prompt()

async def check_user_quota(user_id: int) -> bool:
    """Проверяет квоту пользователя (2 квиза в день)"""
    today = datetime.now().date()
    user_key = f"quiz_runs:{user_id}"
    
    if user_key not in user_quiz_quota:
        user_quiz_quota[user_key] = {"date": today, "count": 0}
    
    user_data = user_quiz_quota[user_key]
    
    # Сбрасываем счетчик если новый день
    if user_data["date"] != today:
        user_data["date"] = today
        user_data["count"] = 0
    
    return user_data["count"] < 2

async def increment_user_quota(user_id: int):
    """Увеличивает счетчик квизов пользователя"""
    today = datetime.now().date()
    user_key = f"quiz_runs:{user_id}"
    
    if user_key not in user_quiz_quota:
        user_quiz_quota[user_key] = {"date": today, "count": 0}
    
    user_quiz_quota[user_key]["count"] += 1

async def ask_llm(history: list) -> Optional[str]:
    """Отправляет запрос к DeepSeek API и возвращает ответ"""
    if not DEEPSEEK_AVAILABLE or not deepseek:
        return "❌ Сервис квиза временно недоступен"
    
    try:
        # Используем семафор для ограничения одновременных запросов
        async with llm_semaphore:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
            response = await deepseek.get_response(messages, temperature=0.7)
            return response if response else "❌ Произошла ошибка при обработке запроса"
    except Exception as e:
        logger.error(f"❌ Ошибка запроса к DeepSeek: {e}")
        return "❌ Произошла ошибка при обработке запроса"

# --- Helper functions to avoid premature recommendations/analysis before 5th answer ---

def contains_early_recommendations(text: str) -> bool:
    """Проверяет, содержит ли текст преждевременный анализ или рекомендации."""
    keywords = [
        "🎯",  # маркер анализа личности
        "анализ твоей личности",
        "рекомендуемые направления",
        "главная рекомендация",
        "📚",  # маркер списка направлений
        "💡"
    ]
    lowered = text.lower()
    return any(k.lower() in lowered for k in keywords)


def strip_recommendations(text: str) -> str:
    """Возвращает часть ответа до появления анализа/рекомендаций."""
    delimiters = [
        "🎯",
        "📚",
        "💡",
        "анализ твоей личности",
        "рекомендуемые направления"
    ]
    lowered = text.lower()
    cut_idx = len(text)
    for d in delimiters:
        idx = lowered.find(d.lower())
        if idx != -1 and idx < cut_idx:
            cut_idx = idx
    return text[:cut_idx].strip()

# ------------------------------------------------------------------------------

def create_quiz_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для квиза"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="❌ Выйти из квиза", callback_data="quiz_exit"))
    return builder.as_markup()

def create_finish_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для завершения квиза"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Готово", callback_data="quiz_finish"))
    return builder.as_markup()

async def quiz_exit_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик выхода из квиза"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Квиз отменен.\n\n"
        "🔄 Для нового квиза используйте команду /quiz\n"
        "📚 Для получения информации о направлениях: /help"
    )

async def quiz_finish_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик завершения квиза"""
    await state.clear()
    await callback.message.edit_text(
        "✅ Квиз завершен!\n\n"
        "🔄 Для нового квиза используйте команду /quiz\n"
        "📚 Для получения информации о направлениях: /help"
    )

async def quiz_start(message: Message, state: FSMContext, bot: Bot):
    """Начинает квиз"""
    user_id = message.from_user.id
    
    # Проверяем квоту
    if not await check_user_quota(user_id):
        await message.answer(
            "🚫 Вы уже прошли максимальное количество квизов на сегодня (2 квиза в день).\n"
            "Попробуйте завтра! 📅"
        )
        return
    
    # Проверяем семафор
    if QUIZ_SEMAPHORE.locked():
        await message.answer(
            "⏳ Сейчас очень много пользователей проходят квиз.\n"
            "Попробуйте через несколько минут."
        )
        return
    
    async with QUIZ_SEMAPHORE:
        # Увеличиваем квоту
        await increment_user_quota(user_id)
        
        # Инициализация истории
        history = []
        
        # Получаем первый вопрос
        first_question = await ask_llm(history)
        if not first_question:
            await message.answer("❌ Ошибка запуска квиза. Попробуйте позже.")
            return
        
        await message.answer(
            f"🎯 **Квиз по подбору направления в НДТП**\n\n"
            f"Сейчас я задам тебе 5 вопросов, чтобы подобрать подходящие образовательные направления!\n\n"
            f"{first_question}",
            parse_mode="Markdown",
            reply_markup=create_quiz_keyboard()
        )
        
        # Сохраняем историю и устанавливаем состояние
        history.append({"role": "assistant", "content": first_question})
        await state.update_data(history=history)
        await state.set_state(QuizState.Q1)

async def quiz_start_callback(callback: CallbackQuery, state: FSMContext):
    """Начинает квиз через callback"""
    user_id = callback.from_user.id
    
    # Проверяем квоту
    if not await check_user_quota(user_id):
        await callback.message.edit_text(
            "🚫 Вы уже прошли максимальное количество квизов на сегодня (2 квиза в день).\n"
            "Попробуйте завтра! 📅"
        )
        return
    
    # Проверяем семафор
    if QUIZ_SEMAPHORE.locked():
        await callback.message.edit_text(
            "⏳ Сейчас очень много пользователей проходят квиз.\n"
            "Попробуйте через несколько минут."
        )
        return
    
    async with QUIZ_SEMAPHORE:
        # Увеличиваем квоту
        await increment_user_quota(user_id)
        
        # Инициализация истории
        history = []
        
        # Получаем первый вопрос
        first_question = await ask_llm(history)
        if not first_question:
            await callback.message.edit_text("❌ Ошибка запуска квиза. Попробуйте позже.")
            return
        
        await callback.message.edit_text(
            f"🎯 **Квиз по подбору направления в НДТП**\n\n"
            f"Сейчас я задам тебе 5 вопросов, чтобы подобрать подходящие образовательные направления!\n\n"
            f"{first_question}",
            parse_mode="Markdown",
            reply_markup=create_quiz_keyboard()
        )
        
        # Сохраняем историю и устанавливаем состояние
        history.append({"role": "assistant", "content": first_question})
        await state.update_data(history=history)
        await state.set_state(QuizState.Q1)

async def handle_quiz_question(message: Message, state: FSMContext, bot: Bot, current_state: str):
    """Обрабатывает ответ на вопрос квиза"""
    async with QUIZ_SEMAPHORE:
        data = await state.get_data()
        history = data.get("history", [])
        
        # Добавляем ответ пользователя
        history.append({"role": "user", "content": message.text})
        
        # Определяем следующее состояние
        state_mapping = {
            "Q1": QuizState.Q2,
            "Q2": QuizState.Q3,
            "Q3": QuizState.Q4,
            "Q4": QuizState.Q5,
            "Q5": QuizState.DONE
        }
        
        next_state = state_mapping.get(current_state)
        
        if current_state == "Q5":
            # Последний вопрос - получаем рекомендации
            history.append({"role": "user", "content": "Все 5 ответов получены, пора подытожить."})
            
            response = await ask_llm(history)
            if response:
                await message.answer(
                    response, 
                    parse_mode="Markdown",
                    reply_markup=create_finish_keyboard()
                )
            else:
                await message.answer("❌ Ошибка получения рекомендаций. Попробуйте позже.")
            
            await state.clear()
        else:
            # Получаем следующий вопрос
            response = await ask_llm(history)

            # Проверяем, не появились ли рекомендации раньше времени
            if current_state != "Q5" and response and contains_early_recommendations(response):
                # Сначала пробуем обрезать лишнюю часть
                cleaned = strip_recommendations(response)
                if cleaned and len(cleaned) > 3:
                    response = cleaned
                else:
                    # Если обрезать не удалось, запрашиваем модель повторно с уточнением
                    history.append({"role": "assistant", "content": response})
                    history.append({"role": "user", "content": "Ты дал рекомендации слишком рано. Пожалуйста, задай только следующий вопрос, без анализа и рекомендаций."})
                    response = await ask_llm(history)

            if response:
                await message.answer(
                    response,
                    parse_mode="Markdown",
                    reply_markup=create_quiz_keyboard()
                )

                # Обновляем историю и состояние
                history.append({"role": "assistant", "content": response})
                await state.update_data(history=history)
                await state.set_state(next_state)
            else:
                await message.answer("❌ Ошибка получения следующего вопроса. Попробуйте позже.")
                await state.clear()

async def handle_quiz_q1(message: Message, state: FSMContext, bot: Bot):
    """Обрабатывает ответ на первый вопрос"""
    await handle_quiz_question(message, state, bot, "Q1")

async def handle_quiz_q2(message: Message, state: FSMContext, bot: Bot):
    """Обрабатывает ответ на второй вопрос"""
    await handle_quiz_question(message, state, bot, "Q2")

async def handle_quiz_q3(message: Message, state: FSMContext, bot: Bot):
    """Обрабатывает ответ на третий вопрос"""
    await handle_quiz_question(message, state, bot, "Q3")

async def handle_quiz_q4(message: Message, state: FSMContext, bot: Bot):
    """Обрабатывает ответ на четвертый вопрос"""
    await handle_quiz_question(message, state, bot, "Q4")

async def handle_quiz_q5(message: Message, state: FSMContext, bot: Bot):
    """Обрабатывает ответ на пятый вопрос (финальный)"""
    await handle_quiz_question(message, state, bot, "Q5")

async def handle_quiz_off_topic(message: Message, state: FSMContext, bot: Bot):
    """Обрабатывает сообщения вне контекста квиза"""
    await message.answer(
        "📝 Сейчас идёт квиз по подбору направления!\n\n"
        "Пожалуйста, ответь на текущий вопрос или используй /cancel для отмены квиза."
    )

def get_quiz_stats() -> Dict[str, Any]:
    """Возвращает статистику квиза"""
    total_users = len(user_quiz_quota)
    today_users = sum(1 for data in user_quiz_quota.values() 
                     if data["date"] == datetime.now().date())
    
    return {
        "total_users": total_users,
        "today_users": today_users,
        "active_quizzes": QUIZ_SEMAPHORE._value if hasattr(QUIZ_SEMAPHORE, '_value') else 0,
        "deepseek_available": DEEPSEEK_AVAILABLE
    }

# Функция для интеграции в основной бот
def register_quiz_handlers(dp, bot: Bot):
    """Регистрирует обработчики квиза в диспетчере"""
    
    # Команда начала квиза
    @dp.message(F.text == "/quiz")
    async def quiz_command(message: Message, state: FSMContext):
        await quiz_start(message, state, bot)

    @dp.callback_query(F.data == "start_quiz")
    async def quiz_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer()
        await quiz_start(callback.message, state, bot)
    
    # Обработчики состояний квиза
    @dp.message(QuizState.Q1)
    async def quiz_q1_handler(message: Message, state: FSMContext):
        await handle_quiz_q1(message, state, bot)
    
    @dp.message(QuizState.Q2)
    async def quiz_q2_handler(message: Message, state: FSMContext):
        await handle_quiz_q2(message, state, bot)
    
    @dp.message(QuizState.Q3)
    async def quiz_q3_handler(message: Message, state: FSMContext):
        await handle_quiz_q3(message, state, bot)
    
    @dp.message(QuizState.Q4)
    async def quiz_q4_handler(message: Message, state: FSMContext):
        await handle_quiz_q4(message, state, bot)
    
    @dp.message(QuizState.Q5)
    async def quiz_q5_handler(message: Message, state: FSMContext):
        await handle_quiz_q5(message, state, bot)
    
    # Обработчики callback-кнопок
    @dp.callback_query(F.data == "quiz_exit")
    async def quiz_exit_handler(callback: CallbackQuery, state: FSMContext):
        await quiz_exit_callback(callback, state)
    
    @dp.callback_query(F.data == "quiz_finish")
    async def quiz_finish_handler(callback: CallbackQuery, state: FSMContext):
        await quiz_finish_callback(callback, state)
    
    # Команда статистики квиза
    @dp.message(F.text == "/quiz_stats")
    async def quiz_stats_command(message: Message):
        stats = get_quiz_stats()
        await message.answer(
            f"📊 **Статистика квиза:**\n\n"
            f"👥 Всего пользователей: {stats['total_users']}\n"
            f"📅 Сегодня прошли: {stats['today_users']}\n"
            f"🔄 Активных квизов: {3 - stats['active_quizzes']}/3\n"
            f"🧠 DeepSeek доступен: {'✅' if stats['deepseek_available'] else '❌'}"
        )
    
    logger.info("✅ Обработчики квиза зарегистрированы") 