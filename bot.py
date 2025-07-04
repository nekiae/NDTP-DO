import os
import logging
from typing import Optional
import asyncio
import time
from datetime import datetime
from dotenv import load_dotenv

import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования (ВАЖНО: настраиваем ПЕРЕД импортом модулей)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Импорт собственных модулей
from operator_handler import operator_handler, OperatorState, UserStatus
from rag_system import rag_system

# Добавляем импорт парсера расписания
from schedule_parser import get_schedule_context_async, get_schedule_context, force_update_schedule, schedule_updater_loop

# Добавляем импорт парсера документов
try:
    from documents_parser import get_documents_context_async, get_documents_context, force_update_documents, documents_updater_loop
    DOCUMENTS_PARSER_AVAILABLE = True
    logger.info("📄 Парсер документов загружен")
except ImportError as e:
    logger.warning(f"⚠️ Парсер документов недоступен: {e}")
    DOCUMENTS_PARSER_AVAILABLE = False

# Парсер списков временно отключен
LISTS_PARSER_AVAILABLE = False
logger.info("📋 Парсер списков временно отключен")

# Импорт модуля календаря
try:
    from calendar_module import get_calendar_interface, get_shift_info, get_notification_settings_interface
    CALENDAR_AVAILABLE = True
    logger.info("📅 Модуль календаря загружен")
except ImportError as e:
    logger.warning(f"⚠️ Модуль календаря недоступен: {e}")
    CALENDAR_AVAILABLE = False

# Импорт системы уведомлений
try:
    from notification_system import notification_system
    NOTIFICATIONS_AVAILABLE = True
    logger.info("🔔 Система уведомлений загружена")
except ImportError as e:
    logger.warning(f"⚠️ Система уведомлений недоступна: {e}")
    NOTIFICATIONS_AVAILABLE = False

# Добавляем импорт оптимизированной RAG системы
try:
    from optimized_rag_system import (
        get_optimized_context_async, 
        get_optimized_context, 
        get_optimized_rag, 
        RAGModes
    )
    # Инициализируем в экономном режиме
    optimized_rag = get_optimized_rag(RAGModes.ECONOMY)
    OPTIMIZED_RAG_AVAILABLE = True
    logger.info(f"🚀 Оптимизированная RAG система готова: {optimized_rag.get_stats()}")
except ImportError as e:
    logger.warning(f"⚠️ Оптимизированная RAG система недоступна: {e}")
    OPTIMIZED_RAG_AVAILABLE = False

# Резервная загрузка современной RAG системы
try:
    from modern_rag_system import ModernRAGSystem, get_context_for_query_async, set_global_instance
    modern_rag = ModernRAGSystem()
    modern_rag.load_and_index_knowledge()
    set_global_instance(modern_rag)  # Устанавливаем глобальную инстанцию
    MODERN_RAG_AVAILABLE = True
    logger.info(f"📚 Резервная RAG система готова: {modern_rag.get_stats()['total_documents']} документов")
except ImportError as e:
    logger.warning(f"⚠️ Современная RAG система недоступна: {e}")
    logger.info("📚 Используем базовую RAG систему")
    MODERN_RAG_AVAILABLE = False
    modern_rag = None

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# Системный промпт для DeepSeek API
def get_system_prompt() -> str:
    """Получает системный промпт с актуальной датой"""
    from datetime import datetime
    current_date = datetime.now().strftime("%d.%m.%Y")
    current_weekday = datetime.now().strftime("%A")
    
    # Переводим день недели на русский
    weekdays_ru = {
        "Monday": "понедельник",
        "Tuesday": "вторник", 
        "Wednesday": "среда",
        "Thursday": "четверг",
        "Friday": "пятница",
        "Saturday": "суббота",
        "Sunday": "воскресенье"
    }
    current_weekday_ru = weekdays_ru.get(current_weekday, current_weekday)
    
    return f"""[ЯЗЫК ОБЩЕНИЯ - СТРОГО РУССКИЙ]
• Ты ТехноБот. Официальный ИИ Ассистент Национального детского технопарка. Отвечай только на вопросы по тематике Национального детского технопарка. Будь вежлив и дружелюбен.

[ТЕКУЩАЯ ДАТА И ВРЕМЯ]
• Сегодня: {current_date} ({current_weekday_ru})
• При работе с датами учитывай эту информацию для корректных расчетов периодов и сроков

[ОБРАБОТКА ЗАПРОСОВ]
• На простые приветствия (привет, здравствуй) отвечай дружелюбно и предлагай помощь
• Если у тебя НЕТ полной и корректной информации для ответа на вопрос пользователя, обязательно предложи: "Для получения точной информации рекомендую обратиться к консультанту через команду /help"
• Не выдумывай информацию, которой нет в базе знаний
• Если информация неполная или устаревшая, честно скажи об этом и предложи консультанта
• ВАЖНО: При ответах о документах ОБЯЗАТЕЛЬНО включай все ссылки с 📎 из контекста - пользователи должны знать, где скачать нужные документы
• Ссылки на документы - это ключевая практическая информация, не пропускай их

[ПРАВИЛА ФОРМАТИРОВАНИЯ ТЕКСТА]
• КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО использовать звездочки (*) в любом виде
• КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО использовать двойные звездочки (**)
• НЕ ИСПОЛЬЗОВАТЬ markdown форматирование (**bold**, *italic*)
• Для выделения важной информации использовать ТОЛЬКО эмодзи в начале строки
• Для структурирования текста использовать отступы и эмодзи
• ОБЯЗАТЕЛЬНО сохранять все ссылки с эмодзи 📎 из контекста - это важная информация для пользователей
• Для заголовков использовать эмодзи + текст, например:
  🏫 Национальный детский технопарк
  📚 Образовательные направления
  🎯 Цель
  🚀 Миссия
  ⚡ Принципы
  🏢 Инфраструктура
  📎 Ссылка на документ (ВСЕГДА включать в ответ если есть в контексте)

В конце своего ответа задавай вопрос, который лаконично и логично продолжает тему разговора.

"""

# Проверка токена
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY не найден в переменных окружения")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния FSM (дополнительные к OperatorState)
class UserState(StatesGroup):
    IN_QUIZ = State()
    COLLECTING_DOCUMENTS = State()

# Класс для работы с DeepSeek API
class DeepSeekAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async def get_completion(self, messages: list, temperature: float = 0.7) -> Optional[str]:
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": "deepseek-chat",
                    "messages": messages,
                    "temperature": temperature
                }
                
                async with session.post(
                    DEEPSEEK_API_URL,
                    headers=self.headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result["choices"][0]["message"]["content"]
                    else:
                        logger.error(f"DeepSeek API error: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error in DeepSeek API call: {e}")
            return None

    async def get_streaming_completion(self, messages: list, temperature: float = 0.7):
        """Генератор для стриминговых ответов от DeepSeek API"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": "deepseek-chat", 
                    "messages": messages,
                    "temperature": temperature,
                    "stream": True
                }
                
                async with session.post(
                    DEEPSEEK_API_URL,
                    headers=self.headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        async for line in response.content:
                            line = line.decode('utf-8').strip()
                            if line.startswith('data: '):
                                line = line[6:]  # Убираем 'data: '
                                if line == '[DONE]':
                                    break
                                try:
                                    import json
                                    data = json.loads(line)
                                    if 'choices' in data and len(data['choices']) > 0:
                                        delta = data['choices'][0].get('delta', {})
                                        if 'content' in delta:
                                            yield delta['content']
                                except json.JSONDecodeError:
                                    continue
                    else:
                        logger.error(f"DeepSeek API streaming error: {response.status}")
                        yield None
        except Exception as e:
            logger.error(f"Error in DeepSeek streaming API call: {e}")
            yield None

# Инициализация DeepSeek API
deepseek = DeepSeekAPI(DEEPSEEK_API_KEY)



# Функция для получения расширенного контекста с информацией о расписании
async def get_enhanced_context(query: str) -> str:
    """Получает МАКСИМАЛЬНО ОПТИМИЗИРОВАННЫЙ контекст из RAG системы, обогащенный актуальной информацией"""
    try:
        # ПРИОРИТЕТ: Максимально оптимизированная RAG система
        if OPTIMIZED_RAG_AVAILABLE:
            logger.info("🚀 Используем МАКСИМАЛЬНО ОПТИМИЗИРОВАННУЮ RAG систему")
            base_context = await get_optimized_context_async(query, RAGModes.ECONOMY)
        elif MODERN_RAG_AVAILABLE:
            logger.info("📚 Используем современную векторную RAG систему")
            base_context = await get_context_for_query_async(query)
        else:
            logger.info("📖 Используем базовую RAG систему")
            base_context = rag_system.get_context_for_query(query)
        
        query_lower = query.lower()
        enhanced_contexts = []
        
        # Проверяем, связан ли запрос с расписанием/сменами
        schedule_keywords = [
            'смена', 'смены', 'расписание', 'график', 'заявк', 'запис', 
            'поступление', 'когда', 'дат', 'период', 'прием', 'началь',
            'январ', 'февраль', 'март', 'апрель', 'май', 'июн',
            'июл', 'август', 'сентябр', 'октябр', 'ноябр', 'декабр'
        ]
        
        is_schedule_related = any(keyword in query_lower for keyword in schedule_keywords)
        
        # Проверяем, связан ли запрос с документами
        document_keywords = [
            'документ', 'документы', 'справк', 'заявлен', 'согласи', 'свидетельство',
            'медицинск', 'рождени', 'бассейн', 'инфекц', 'план', 'учебный',
            'при заезде', 'поступлен', 'регистрац', 'что нужно', 'что взять',
            'какие нужны', 'список документов', 'необходимые'
        ]
        
        is_documents_related = any(keyword in query_lower for keyword in document_keywords)
        
        # Добавляем актуальную информацию о расписании
        if is_schedule_related:
            logger.info("📅 Запрос связан с расписанием - добавляем актуальную информацию")
            schedule_context = await get_schedule_context_async(query)
            enhanced_contexts.append(schedule_context)
        
        # Добавляем актуальную информацию о документах
        if is_documents_related and DOCUMENTS_PARSER_AVAILABLE:
            logger.info("📄 Запрос связан с документами - добавляем актуальную информацию")
            documents_context = await get_documents_context_async(query)
            if documents_context:
                enhanced_contexts.append(documents_context)
        
        # Объединяем все контексты
        if enhanced_contexts:
            if "не найдена в базе знаний" not in base_context:
                final_context = f"{base_context}\n\n" + "\n\n".join(enhanced_contexts)
            else:
                final_context = "\n\n".join(enhanced_contexts)
            
            logger.info(f"✅ Контекст обогащен дополнительной информацией")
            return final_context
        else:
            logger.info("📚 Используем только базовый контекст")
            return base_context
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения расширенного контекста: {e}")
        # В случае ошибки возвращаем базовый контекст
        if MODERN_RAG_AVAILABLE:
            return await get_context_for_query_async(query)
        else:
            return rag_system.get_context_for_query(query)

# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Приветственное сообщение с инлайн кнопками"""
    welcome_text = (
        "👋 Добро пожаловать в бот Национального детского технопарка!\n\n"
        "🤖 Я ваш интеллектуальный помощник. Выберите интересующую вас тему:"
    )
    
    # Создаем инлайн клавиатуру
    keyboard_rows = [
        [
            InlineKeyboardButton(text="🏫 О технопарке", callback_data="info_about"),
            InlineKeyboardButton(text="📚 Направления обучения", callback_data="info_programs")
        ],
        [
            InlineKeyboardButton(text="📝 Поступление", callback_data="info_admission")
        ]
    ]
    
    # Добавляем кнопку календаря, если модуль доступен
    if CALENDAR_AVAILABLE:
        keyboard_rows.append([
            InlineKeyboardButton(text="📅 Календарь смен", callback_data="show_calendar")
        ])
    
    keyboard_rows.append([
        InlineKeyboardButton(text="👨‍💼 Связаться с консультантом", callback_data="request_consultant")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await message.answer(welcome_text, reply_markup=keyboard)

@dp.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Используем новый API для эскалации к оператору
    success = await operator_handler.escalate_to_operator(
        user_id, 
        message, 
        auto_escalation=False,
        bot=bot
    )
    
    if success:
        await state.set_state(OperatorState.WAITING_OPERATOR)
        queue_info = operator_handler.get_queue_info()
        position = len([u for u in queue_info["queue_details"] if u["user_id"] == user_id])
        
        await message.answer(
            "📞 Ваш запрос передан консультанту.\n"
            "Пожалуйста, ожидайте подключения.\n\n"
            f"📋 Ваша позиция в очереди: {position}\n"
            "⏰ Среднее время ожидания: 3-5 минут\n\n"
            "Вы можете отменить ожидание командой /cancel"
        )
    else:
        await message.answer("❌ Не удалось подключиться к системе операторов. Попробуйте позже.")

@dp.message(Command("status"))
async def cmd_status(message: Message):
    """Показать статус пользователя"""
    user_id = message.from_user.id
    user_status = operator_handler.get_user_status(user_id)
    
    logger.info(f"ℹ️ Запрос статуса от пользователя {user_id}, статус: {user_status.value}")
    
    # Определяем текст статуса
    status_descriptions = {
        UserStatus.NORMAL: "🟢 Обычный режим - можете задавать вопросы",
        UserStatus.WAITING_OPERATOR: "⏳ Ожидаете подключения консультанта",
        UserStatus.WITH_OPERATOR: "💬 Общаетесь с консультантом", 
        UserStatus.RATING_OPERATOR: "⭐ Необходимо оценить работу консультанта"
    }
    
    status_text = f"ℹ️ Ваш статус: {status_descriptions.get(user_status, 'Неизвестно')}\n\n"
    
    # Дополнительная информация в зависимости от статуса
    if user_status == UserStatus.WAITING_OPERATOR and user_id in operator_handler.waiting_queue:
        request_info = operator_handler.waiting_queue[user_id]
        status_text += (
            f"📋 Информация о запросе:\n"
            f"⏰ Время запроса: {request_info['request_time'].strftime('%H:%M:%S')}\n"
            f"📍 Позиция в очереди: {request_info['queue_position']}\n\n"
        )
    elif user_status == UserStatus.WITH_OPERATOR and user_id in operator_handler.active_sessions:
        session_info = operator_handler.active_sessions[user_id]
        operator_info = operator_handler.operator_manager.get_operator_info(session_info['operator_id'])
        status_text += (
            f"👨‍💼 Консультант: {operator_info['name']}\n"
            f"⏰ Начало сессии: {session_info['start_time'].strftime('%H:%M:%S')}\n"
            f"📝 Сообщений: {session_info.get('message_count', 0)}\n\n"
        )
    
    # Дополнительная информация о системе
    queue_info = operator_handler.get_queue_info()
    status_text += (
        f"📊 Статус системы:\n"
        f"⏳ В очереди ожидания: {queue_info['waiting_count']}\n"
        f"💬 Активные сессии: {queue_info['active_sessions']}\n"
        f"👨‍💼 Операторов онлайн: {queue_info['active_operators']}\n\n"
        f"Команды: /help - запросить консультанта, /cancel - отмена"
    )
    
    await message.answer(status_text)

@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    user_id = message.from_user.id
    current_state = await state.get_state()
    user_status = operator_handler.get_user_status(user_id)
    
    logger.info(f"🚫 Команда /cancel от пользователя {user_id}, статус: {user_status.value}")
    
    # Отмена ожидания оператора или активной сессии
    if user_status == UserStatus.WAITING_OPERATOR:
        success, msg = await operator_handler.cancel_waiting(user_id, bot)
        if success:
            await state.clear()
            await message.answer("❌ Ожидание консультанта отменено. Чем еще могу помочь?")
        else:
            await message.answer(f"❌ {msg}")
    elif user_status == UserStatus.WITH_OPERATOR:
        success = await operator_handler.end_session(user_id, bot, "завершена пользователем")
        if success:
            await state.clear()
            await message.answer("❌ Сессия с консультантом завершена. Чем еще могу помочь?")
        else:
            await message.answer("❌ Ошибка завершения сессии")
    elif user_status == UserStatus.RATING_OPERATOR:
        # Пропускаем оценку и завершаем
        operator_handler.set_user_status(user_id, UserStatus.NORMAL)
        await state.clear()
        await message.answer("❌ Оценка пропущена. Чем еще могу помочь?")
    elif current_state is not None:
        await state.clear()
        await message.answer("❌ Операция отменена. Чем еще могу помочь?")
    else:
        await message.answer("❌ Нечего отменять.")

# Обработчик для команд операторов (добавить в админ-панель)
@dp.message(Command("operator_stats"))
async def cmd_operator_stats(message: Message):
    """Статистика для операторов"""
    operator_id = message.from_user.id
    
    if operator_handler.operator_manager.is_operator(operator_id):
        config = operator_handler.operator_manager.get_operator_info(operator_id)
        stats_text = (
            f"👨‍💼 Статистика оператора {config['name']}:\n\n"
            f"⭐ Рейтинг: {config['rating']}/5\n"
            f"📊 Сессий проведено: {config['total_sessions']}\n"
            f"🟢 Статус: {'Активен' if config['is_active'] else 'Неактивен'}"
        )
        await message.answer(stats_text)
    else:
        await message.answer("❌ Вы не являетесь оператором системы")

# Удаляем старую команду /accept, заменяем на callback-обработчики

@dp.message(Command("end_session"))
async def cmd_end_session(message: Message):
    """Завершить сессию с пользователем"""
    operator_id = message.from_user.id
    
    # Найти активную сессию для оператора
    user_id = None
    for uid, session in operator_handler.active_sessions.items():
        if session.get("operator_id") == operator_id:
            user_id = uid
            break
    
    if user_id:
        success = await operator_handler.end_session(user_id, bot, "завершена консультантом")
        if success:
            await message.answer("✅ Сессия завершена")
        else:
            await message.answer("❌ Ошибка завершения сессии")
    else:
        await message.answer("❌ У вас нет активных сессий")

@dp.message(Command("operators"))
async def cmd_operators_list(message: Message):
    """Список операторов (для администраторов)"""
    operators_list = "👨‍💼 Список операторов:\n\n"
    
    for op_id, config in operator_handler.operator_manager.operators_config.items():
        status_emoji = "🟢" if config["is_active"] else "🔴"
        operators_list += (
            f"{status_emoji} {config['name']} (ID: {op_id})\n"
            f"   ⭐ {config['rating']}/5 ({config['total_sessions']} сессий)\n\n"
        )
    
    await message.answer(operators_list)

@dp.message(Command("check_operator"))
async def cmd_check_operator(message: Message):
    """Проверить, является ли пользователь оператором"""
    user_id = message.from_user.id
    
    if operator_handler.operator_manager.is_operator(user_id):
        config = operator_handler.operator_manager.get_operator_info(user_id)
        status_text = (
            f"✅ Вы являетесь оператором!\n\n"
            f"👤 Имя: {config['name']}\n"
            f"🟢 Статус: {'Активен' if config['is_active'] else 'Неактивен'}\n"
            f"⭐ Рейтинг: {config['rating']}/5\n"
            f"📊 Сессий: {config['total_sessions']}\n\n"
            f"Доступные команды:\n"
            f"• /operator_stats - статистика\n"
            f"• /end_session - завершить сессию\n"
            f"• Принятие запросов через инлайн-кнопки в уведомлениях"
        )
        await message.answer(status_text)
    else:
        await message.answer(f"❌ Ваш ID ({user_id}) не найден в списке операторов")

# Обработчики сообщений от операторов (ДОЛЖНЫ БЫТЬ ВЫШЕ ОСНОВНЫХ ОБРАБОТЧИКОВ!)
@dp.message(F.text & F.from_user.id.in_(list(operator_handler.operator_manager.operators_config.keys())))
async def handle_operator_message(message: Message):
    """Обработка текстовых сообщений от операторов - ПРИОРИТЕТНЫЙ ОБРАБОТЧИК"""
    operator_id = message.from_user.id
    
    logger.info(f"📨 Получено сообщение от оператора {operator_id}: '{message.text}'")
    
    # Проверяем специальные команды оператора
    if message.text.startswith('/'):
        logger.info(f"🔧 Команда оператора: {message.text}")
        return  # Команды обрабатываются другими обработчиками
    
    # Пересылаем обычные сообщения пользователю
    success, msg = await operator_handler.forward_operator_message(operator_id, message.text, bot)
    if not success:
        await message.answer(f"❌ {msg}")
    else:
        logger.info(f"✅ Сообщение оператора {operator_id} переслано пользователю")

# Обработчики медиа сообщений от операторов
@dp.message((F.photo | F.document | F.voice | F.video | F.audio | F.sticker) & 
           F.from_user.id.in_(list(operator_handler.operator_manager.operators_config.keys())))
async def handle_operator_media(message: Message):
    """Обработка медиа сообщений от операторов - ПРИОРИТЕТНЫЙ ОБРАБОТЧИК"""
    operator_id = message.from_user.id
    
    media_type = "unknown"
    if message.photo:
        media_type = "фото"
    elif message.document:
        media_type = "документ"
    elif message.voice:
        media_type = "голосовое сообщение"
    elif message.video:
        media_type = "видео"
    elif message.audio:
        media_type = "аудио"
    elif message.sticker:
        media_type = "стикер"
    
    logger.info(f"📎 Получено {media_type} от оператора {operator_id}")
    
    # Пересылаем медиа пользователю (упрощенная версия - только текст)
    success, msg = await operator_handler.forward_operator_message(
        operator_id, f"[{media_type}]", bot
    )
    if not success:
        await message.answer(f"❌ Ошибка пересылки медиа: {msg}")
    else:
        logger.info(f"✅ {media_type.capitalize()} от оператора {operator_id} переслано пользователю")

# Обработчик текстовых сообщений от пользователей
@dp.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    user_id = message.from_user.id
    current_state = await state.get_state()
    
    # Исключаем операторов из этого обработчика (они обрабатываются выше)
    if operator_handler.operator_manager.is_operator(user_id):
        logger.warning(f"⚠️ ВНИМАНИЕ: Сообщение оператора {user_id} попало в обработчик пользователей!")
        return
    
    logger.info(f"📝 Получено сообщение от пользователя {user_id}: '{message.text}'")
    
    # Проверяем статус пользователя
    user_status = operator_handler.get_user_status(user_id)
    logger.info(f"👤 Статус пользователя {user_id}: {user_status.value}")
    
    # Пользователь ожидает консультанта
    if user_status == UserStatus.WAITING_OPERATOR:
        logger.info(f"⏳ Пользователь {user_id} ожидает консультанта - добавляем сообщение в историю")
        # Добавляем сообщение в историю для консультанта
        operator_handler.add_user_message_to_history(user_id, message.text)
        await message.answer("⏳ Ваш запрос уже передан консультанту. Пожалуйста, ожидайте подключения.")
        return
    
    # Пользователь подключен к консультанту
    if user_status == UserStatus.WITH_OPERATOR:
        logger.info(f"💬 Пользователь {user_id} общается с консультантом - пересылаем сообщение")
        # Пересылаем сообщение консультанту
        success = await operator_handler.forward_user_message(user_id, message, bot)
        if not success:
            await message.answer("❌ Ошибка пересылки сообщения консультанту")
        return
    
    # Пользователь оценивает работу консультанта
    if user_status == UserStatus.RATING_OPERATOR:
        logger.info(f"⭐ Пользователь {user_id} должен оценить работу консультанта")
        await message.answer("⭐ Пожалуйста, сначала оцените работу консультанта, используя кнопки выше.")
        return
    
    # Обычная обработка сообщения с использованием RAG
    logger.info(f"🤖 Пользователь {user_id} в обычном режиме - запускаем ИИ-обработку")
    try:
        logger.info("🔍 Начинаем поиск в базе знаний...")
        
        # Получаем контекст из МАКСИМАЛЬНО ОПТИМИЗИРОВАННОЙ RAG системы
        context = await get_enhanced_context(message.text)
        logger.info(f"Получен контекст: {context[:200]}..." if len(context) > 200 else f"Получен контекст: {context}")
        
        # Все запросы теперь обрабатываются ИИ, который сам решает, когда предложить консультанта
        # Убираем проверку контекста - пусть ИИ сам решает на основе промпта
        
        # Подготовка сообщений для DeepSeek API
        system_message = get_system_prompt()
        
        user_message = f"""
ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ:
{context}

ВОПРОС ПОЛЬЗОВАТЕЛЯ: {message.text}

Ответьте на вопрос пользователя, используя только информацию выше.
"""
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]

        logger.info("🚀 Отправляем стриминговый запрос к DeepSeek API...")
        
        # Отправляем начальное сообщение для редактирования
        sent_message = await message.answer("🤔 Думаю...")
        
        # Получение стримингового ответа от DeepSeek API
        response_text = ""
        last_update = 0
        last_typing_time = 0
        update_interval = 100  # Обновляем каждые 100 символов (реже)
        
        try:
            async for chunk in deepseek.get_streaming_completion(messages, temperature=0.3):
                if chunk:
                    response_text += chunk
                    current_time = time.time()
                    
                    # Обновляем сообщение каждые N символов И если прошло минимум 2 секунды
                    if (len(response_text) - last_update >= update_interval and 
                        current_time - last_typing_time >= 2.0):
                        try:
                            # Добавляем индикатор печатания в конце
                            display_text = response_text + " ▌"
                            try:
                                await bot.edit_message_text(
                                    display_text,
                                    chat_id=sent_message.chat.id,
                                    message_id=sent_message.message_id,
                                    parse_mode="Markdown"
                                )
                            except Exception as markdown_error:
                                # Если ошибка markdown, пробуем без форматирования
                                await bot.edit_message_text(
                                    display_text,
                                    chat_id=sent_message.chat.id,
                                    message_id=sent_message.message_id
                                )
                            last_update = len(response_text)
                            last_typing_time = current_time
                            
                            # Добавляем задержку между обновлениями
                            await asyncio.sleep(1.0)
                            
                        except Exception as edit_error:
                            # Игнорируем ошибки редактирования
                            pass
            
            # Финальное обновление без индикатора печатания
            if response_text:
                try:
                    try:
                        await bot.edit_message_text(
                            response_text,
                            chat_id=sent_message.chat.id,
                            message_id=sent_message.message_id,
                            parse_mode="Markdown"
                        )
                    except Exception as markdown_error:
                        # Если ошибка markdown, пробуем без форматирования
                        await bot.edit_message_text(
                            response_text,
                            chat_id=sent_message.chat.id,
                            message_id=sent_message.message_id
                        )
                    logger.info(f"✅ Стриминговый ответ завершен: {len(response_text)} символов")
                except Exception as final_edit_error:
                    logger.error(f"Ошибка финального обновления: {final_edit_error}")
                    # Если не можем отредактировать, отправляем новое сообщение
                    try:
                        await message.answer(response_text, parse_mode="Markdown")
                    except Exception:
                        await message.answer(response_text)
            else:
                await bot.edit_message_text(
                    "😔 Извините, произошла ошибка при получении ответа.\n"
                    "Попробуйте переформулировать вопрос или обратитесь к оператору: /help",
                    chat_id=sent_message.chat.id,
                    message_id=sent_message.message_id
                )
                
        except Exception as streaming_error:
            logger.error(f"Ошибка стриминга: {streaming_error}")
            await bot.edit_message_text(
                "😔 Извините, произошла ошибка при обработке вашего запроса.\n"
                "Попробуйте переформулировать вопрос или обратитесь к оператору: /help",
                chat_id=sent_message.chat.id,
                message_id=sent_message.message_id
            )
    
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}", exc_info=True)
        await message.answer(
            "😔 Произошла техническая ошибка.\n"
            "Пожалуйста, попробуйте позже или обратитесь к оператору: /help"
        )

# Обработчики медиа сообщений
@dp.message(F.photo)
async def handle_photo(message: Message):
    await handle_media_message(message, "фото")

@dp.message(F.document)
async def handle_document(message: Message):
    await handle_media_message(message, "документ")

@dp.message(F.voice)
async def handle_voice(message: Message):
    await handle_media_message(message, "голосовое сообщение")

@dp.message(F.video)
async def handle_video(message: Message):
    await handle_media_message(message, "видео")

@dp.message(F.audio)
async def handle_audio(message: Message):
    await handle_media_message(message, "аудио")

@dp.message(F.sticker)
async def handle_sticker(message: Message):
    await handle_media_message(message, "стикер")

async def handle_media_message(message: Message, media_type: str):
    """Обработка медиа сообщений с учетом статуса пользователя"""
    user_id = message.from_user.id
    
    # Исключаем операторов
    if operator_handler.operator_manager.is_operator(user_id):
        logger.info(f"📨 Медиа от оператора {user_id}: {media_type}")
        # Пересылаем медиа пользователю
        success = await operator_handler.forward_operator_media(user_id, message, bot)
        if not success:
            await message.answer("❌ Ошибка пересылки медиа")
        return
    
    user_status = operator_handler.get_user_status(user_id)
    logger.info(f"📎 Получено {media_type} от пользователя {user_id}, статус: {user_status.value}")
    
    # Пользователь ожидает консультанта
    if user_status == UserStatus.WAITING_OPERATOR:
        await message.answer("⏳ Ваш запрос уже передан консультанту. Пожалуйста, ожидайте подключения.")
        return
    
    # Пользователь подключен к консультанту
    if user_status == UserStatus.WITH_OPERATOR:
        logger.info(f"💬 Пересылаем {media_type} от пользователя {user_id} консультанту")
        success = await operator_handler.forward_user_message(user_id, message, bot)
        if not success:
            await message.answer("❌ Ошибка пересылки медиа консультанту")
        return
    
    # Пользователь оценивает работу консультанта
    if user_status == UserStatus.RATING_OPERATOR:
        await message.answer("⭐ Пожалуйста, сначала оцените работу консультанта, используя кнопки выше.")
        return
    
    # Обычный режим - медиа не поддерживается ИИ
    await message.answer(
        f"🎤 Извините, обработка медиа ({media_type}) временно недоступна.\n"
        "📝 Пожалуйста, отправьте ваш вопрос текстом или обратитесь к оператору: /help"
    )

@dp.message(Command("test_location"))
async def cmd_test_location(message: Message):
    """Команда для тестирования поиска информации о местоположении"""
    test_queries = [
        "где находится технопарк",
        "адрес технопарка", 
        "местоположение",
        "как добраться",
        "адрес"
    ]
    
    response_text = "🗺️ Тест поиска местоположения:\n\n"
    
    for query in test_queries:
        logger.info(f"Тестируем запрос о местоположении: {query}")
        context = rag_system.get_context_for_query(query)
        
        if "не найдена в базе знаний" in context:
            response_text += f"❌ '{query}' - не найдено\n"
        else:
            # Проверяем, есть ли адрес в контексте
            if "Технологическая" in context or "Москва" in context:
                response_text += f"✅ '{query}' - адрес найден\n"
            else:
                response_text += f"⚠️ '{query}' - найдено, но без адреса\n"
    
    await message.answer(response_text)

@dp.message(Command("test_rag"))
async def cmd_test_rag(message: Message):
    """Команда для тестирования RAG системы"""
    test_queries = [
        "робототехника",
        "программирование", 
        "поступление",
        "документы",
        "стоимость",
        "программы обучения",
        "где находится технопарк"
    ]
    
    response_text = "🔧 Тест RAG системы:\n\n"
    
    for query in test_queries:
        logger.info(f"Тестируем запрос: {query}")
        context = rag_system.get_context_for_query(query)
        
        if "не найдена в базе знаний" in context:
            response_text += f"❌ '{query}' - не найдено\n"
        else:
            response_text += f"✅ '{query}' - найдено ({len(context)} символов)\n"
    
    # Дополнительная информация
    response_text += f"\n📊 Статус базы знаний:\n"
    response_text += f"Загружена: {'✅' if rag_system.knowledge_base else '❌'}\n"
    
    if rag_system.knowledge_base:
        technopark_info = rag_system.knowledge_base.get("technopark_info", {})
        programs_count = len(technopark_info.get("educational_programs", []))
        faq_count = len(technopark_info.get("faq", []))
        general_info = technopark_info.get("general", {})
        
        response_text += f"Программ: {programs_count}\n"
        response_text += f"FAQ: {faq_count}\n"
        response_text += f"Общая информация: {'✅' if general_info else '❌'}\n"
        
        # Проверяем наличие адреса
        if general_info:
            contacts = general_info.get("contacts", {})
            address = contacts.get("address", "")
            response_text += f"Адрес в базе: {'✅' if address else '❌'} ({address})\n"
    
    await message.answer(response_text)

@dp.message(Command("reload_kb"))
async def cmd_reload_kb(message: Message):
    """Команда для перезагрузки базы знаний"""
    try:
        if MODERN_RAG_AVAILABLE:
            modern_rag.reload_knowledge_base()
            await message.answer("✅ Современная база знаний перезагружена успешно!")
        else:
            rag_system.load_knowledge_base()
            await message.answer("✅ Базовая база знаний перезагружена успешно!")
    except Exception as e:
        logger.error(f"Ошибка перезагрузки базы знаний: {e}")
        await message.answer(f"❌ Ошибка перезагрузки: {e}")

@dp.message(Command("rag_stats"))
async def cmd_rag_stats(message: Message):
    """Показать детальную статистику всех RAG систем"""
    try:
        response_text = "📊 **ДЕТАЛЬНАЯ СТАТИСТИКА RAG СИСТЕМ**\n\n"
        
        # Статистика максимально оптимизированной RAG системы
        if OPTIMIZED_RAG_AVAILABLE:
            stats = optimized_rag.get_stats()
            response_text += f"""🚀 **МАКСИМАЛЬНО ОПТИМИЗИРОВАННАЯ RAG (АКТИВНАЯ)**
• Общих запросов: {stats.get('total_queries', 0)}
• Попаданий в кэш: {stats.get('cache_hits', 0)}
• Cache Hit Rate: {stats.get('cache_hit_rate', '0%')}
• Сэкономлено токенов: {stats.get('tokens_saved', 0)}
• Сэкономлено времени: {stats.get('processing_time_saved', 0):.2f}с
• Размер точного кэша: {stats.get('exact_cache_size', 0)}
• Семантических групп: {stats.get('semantic_cache_groups', 0)}
• Популярных запросов: {stats.get('popular_cache_size', 0)}
• Топ паттерны: {', '.join(list(stats.get('top_patterns', {}).keys())[:3])}

"""
            
            # Статистика по режимам
            response_text += "🎯 **Режимы экономии токенов:**\n"
            modes = [
                ("ULTRA_ECONOMY", 300, "максимальная экономия"),
                ("ECONOMY", 500, "экономный (активный)"),
                ("BALANCED", 800, "сбалансированный"),
                ("DETAILED", 1200, "подробный")
            ]
            for mode_name, tokens, desc in modes:
                response_text += f"  • {mode_name}: {tokens} токенов ({desc})\n"
            response_text += "\n"
        
        # Статистика современной RAG системы (резерв)
        if MODERN_RAG_AVAILABLE:
            try:
                stats = modern_rag.get_stats()
                response_text += f"""📚 **Современная RAG (ChromaDB + векторы) - РЕЗЕРВ**
• Документов в базе: {stats.get('total_documents', 0)}
• Коллекций: {stats.get('collections_count', 1)}
• Модель эмбеддингов: {stats.get('model_name', 'неизвестна')}
• Последнее индексирование: {stats.get('last_indexed', 'неизвестно')}
• Размер БД: {stats.get('db_size', 'неизвестно')}

"""
            except Exception as e:
                response_text += f"📚 **Современная RAG - РЕЗЕРВ** (ошибка статистики: {e})\n\n"
        
        # Базовая RAG статистика
        response_text += f"""📖 **Базовая RAG (ключевые слова) - FALLBACK**
• Разделов в БЗ: {len(rag_system.knowledge_base)}
• Файл БЗ: knowledge_base.json
• Основные разделы: {', '.join(list(rag_system.knowledge_base.keys())[:3])}

"""
        
        # Общая информация о системе
        response_text += f"""⚙️ **КОНФИГУРАЦИЯ СИСТЕМЫ:**
• Оптимизированная RAG: {'✅' if OPTIMIZED_RAG_AVAILABLE else '❌'}
• Современная RAG: {'✅' if MODERN_RAG_AVAILABLE else '❌'}
• Календарь: {'✅' if CALENDAR_AVAILABLE else '❌'}  
• Документы: {'✅' if DOCUMENTS_PARSER_AVAILABLE else '❌'}
• Уведомления: {'✅' if NOTIFICATIONS_AVAILABLE else '❌'}

💡 **Приоритет использования:** Оптимизированная → Современная → Базовая"""
        
        await message.answer(response_text)
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики RAG: {e}")
        await message.answer(f"❌ Ошибка получения статистики: {e}")

@dp.message(Command("test_modern_rag"))
async def cmd_test_modern_rag(message: Message):
    """Команда для тестирования современной RAG системы"""
    if not MODERN_RAG_AVAILABLE:
        await message.answer("❌ Современная RAG система недоступна")
        return
    
    test_queries = [
        "робототехника для детей",
        "как записаться на курсы программирования", 
        "адрес технопарка",
        "стоимость обучения",
        "какие документы нужны для поступления",
        "когда проходят хакатоны",
        "3D принтеры в лабораториях"
    ]
    
    response_text = "🧪 **Тест современной RAG системы:**\n\n"
    
    for query in test_queries:
        logger.info(f"🔍 Тестируем запрос: {query}")
        try:
            search_results = modern_rag.search(query, max_results=2, min_score=0.05)
            
            if search_results:
                best_result = search_results[0]
                similarity = best_result['similarity']
                title = best_result['title']
                response_text += f"✅ **{query}**\n"
                response_text += f"   └ {title} ({similarity:.1%})\n\n"
            else:
                response_text += f"❌ **{query}** - не найдено\n\n"
                
        except Exception as e:
            response_text += f"⚠️ **{query}** - ошибка: {str(e)[:50]}\n\n"
    
    await message.answer(response_text)

@dp.message(Command("test_optimized_rag"))
async def cmd_test_optimized_rag(message: Message):
    """Команда для тестирования МАКСИМАЛЬНО ОПТИМИЗИРОВАННОЙ RAG системы"""
    if not OPTIMIZED_RAG_AVAILABLE:
        await message.answer("❌ Максимально оптимизированная RAG система недоступна")
        return
    
    test_queries = [
        "привет",  # Приветствие
        "адрес технопарка",  # Местоположение  
        "телефон",  # Контакты
        "список направлений",  # Направления
        "как поступить",  # Поступление
        "цена обучения",  # Стоимость
        "расписание смен",  # Расписание
        "общая информация о технопарке"  # Общая информация
    ]
    
    response_text = "🚀 **Тест МАКСИМАЛЬНО ОПТИМИЗИРОВАННОЙ RAG системы:**\n\n"
    
    import time
    total_start_time = time.time()
    
    for query in test_queries:
        logger.info(f"🔍 Тестируем оптимизированный запрос: {query}")
        try:
            start_time = time.time()
            context = await get_optimized_context_async(query, RAGModes.ECONOMY)
            processing_time = time.time() - start_time
            
            tokens = len(context) // 3
            
            if context:
                response_text += f"✅ **{query}**\n"
                response_text += f"   └ Токенов: {tokens} | Время: {processing_time:.3f}с\n"
                if len(context) > 100:
                    response_text += f"   └ Превью: {context[:100]}...\n\n"
                else:
                    response_text += f"   └ Ответ: {context}\n\n"
            else:
                response_text += f"⚪ **{query}** - пустой контекст (приветствие)\n\n"
                
        except Exception as e:
            response_text += f"⚠️ **{query}** - ошибка: {str(e)[:50]}\n\n"
    
    total_time = time.time() - total_start_time
    response_text += f"⏱️ **Общее время тестирования: {total_time:.3f}с**\n"
    
    # Статистика системы
    stats = optimized_rag.get_stats()
    response_text += f"📊 Cache Hit Rate: {stats.get('cache_hit_rate', '0%')}\n"
    response_text += f"💾 Токенов сэкономлено: {stats.get('tokens_saved', 0)}"
    
    await message.answer(response_text)

@dp.message(Command("schedule"))
async def cmd_schedule(message: Message):
    """Команда для получения актуального расписания смен"""
    try:
        schedule_info = await get_schedule_context_async()
        if schedule_info:
            await message.answer(schedule_info)
        else:
            await message.answer("❌ Не удалось получить информацию о расписании")
    except Exception as e:
        logger.error(f"Ошибка команды /schedule: {e}")
        await message.answer("❌ Ошибка получения расписания")

@dp.message(Command("update_schedule"))
async def cmd_update_schedule(message: Message):
    """Команда для принудительного обновления расписания"""
    try:
        await message.answer("🔄 Обновляю расписание смен...")
        success = await force_update_schedule()
        
        if success:
            schedule_info = get_schedule_context()
            await message.answer(f"✅ Расписание успешно обновлено!\n\n{schedule_info}")
        else:
            await message.answer("❌ Не удалось обновить расписание")
    except Exception as e:
        logger.error(f"Ошибка команды /update_schedule: {e}")
        await message.answer("❌ Ошибка обновления расписания")

@dp.message(Command("test_schedule"))
async def cmd_test_schedule(message: Message):
    """Команда для тестирования парсера расписания"""
    test_queries = [
        "когда прием заявок на январскую смену",
        "расписание смен на 2025 год",
        "даты февральской смены", 
        "график поступления",
        "когда начинается смена"
    ]
    
    response_text = "🧪 **Тест парсера расписания:**\n\n"
    
    for query in test_queries:
        logger.info(f"🔍 Тестируем запрос о расписании: {query}")
        try:
            context = await get_enhanced_context(query)
            
            if "недоступна" in context or "не найдена" in context:
                response_text += f"❌ **{query}** - информация не найдена\n\n"
            else:
                response_text += f"✅ **{query}** - найдена информация\n\n"
                
        except Exception as e:
            response_text += f"⚠️ **{query}** - ошибка: {str(e)[:50]}\n\n"
    
    await message.answer(response_text)

# Команды парсера списков временно отключены

@dp.message(Command("calendar"))
async def cmd_calendar(message: Message):
    """Команда для показа календаря смен"""
    if not CALENDAR_AVAILABLE:
        await message.answer("❌ Календарь смен временно недоступен")
        return
    
    try:
        user_id = message.from_user.id
        text, keyboard = get_calendar_interface(user_id)
        await message.answer(text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"❌ Ошибка команды /calendar: {e}")
        await message.answer("❌ Ошибка загрузки календаря")

@dp.message(Command("notifications"))
async def cmd_notifications(message: Message):
    """Команда для управления уведомлениями"""
    if not NOTIFICATIONS_AVAILABLE:
        await message.answer("❌ Система уведомлений временно недоступна")
        return
    
    try:
        user_id = message.from_user.id
        text, keyboard = get_notification_settings_interface(user_id)
        await message.answer(text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"❌ Ошибка команды /notifications: {e}")
        await message.answer("❌ Ошибка загрузки настроек уведомлений")

@dp.message(Command("test_notifications"))
async def cmd_test_notifications(message: Message):
    """Команда для тестирования системы уведомлений (только для разработки)"""
    if not NOTIFICATIONS_AVAILABLE:
        await message.answer("❌ Система уведомлений временно недоступна")
        return
    
    user_id = message.from_user.id
    
    # Получаем статус подписок
    subscriptions = notification_system.get_user_subscriptions(user_id)
    
    status_text = "🔔 **Статус системы уведомлений**\n\n"
    status_text += f"📅 Обновления расписания: {'✅ Включены' if subscriptions['schedule_updates'] else '❌ Отключены'}\n"
    status_text += f"⏰ Напоминания о дедлайнах: {'✅ Включены' if subscriptions['application_reminders'] else '❌ Отключены'}\n\n"
    
    # Статистика подписчиков
    all_subscriptions = notification_system.load_subscriptions()
    status_text += f"📊 **Общая статистика:**\n"
    status_text += f"• Подписчиков на расписание: {len(all_subscriptions.get('schedule_updates', []))}\n"
    status_text += f"• Подписчиков на дедлайны: {len(all_subscriptions.get('application_reminders', []))}\n\n"
    
    status_text += "🛠️ Используйте /notifications для управления подписками"
    
    await message.answer(status_text)

@dp.message(Command("documents"))
async def cmd_documents(message: Message):
    """Команда для получения актуальной информации о документах"""
    if not DOCUMENTS_PARSER_AVAILABLE:
        await message.answer("❌ Парсер документов временно недоступен")
        return
    
    try:
        documents_info = await get_documents_context_async()
        if documents_info and documents_info.strip():
            await message.answer(documents_info)
        else:
            await message.answer("❌ Не удалось получить информацию о документах")
    except Exception as e:
        logger.error(f"Ошибка команды /documents: {e}")
        await message.answer("❌ Ошибка получения информации о документах")

@dp.message(Command("update_documents"))
async def cmd_update_documents(message: Message):
    """Команда для принудительного обновления информации о документах"""
    if not DOCUMENTS_PARSER_AVAILABLE:
        await message.answer("❌ Парсер документов временно недоступен")
        return
    
    try:
        await message.answer("🔄 Обновляю информацию о документах...")
        success = await force_update_documents()
        
        if success:
            documents_info = get_documents_context()
            await message.answer(f"✅ Информация о документах успешно обновлена!\n\n{documents_info}")
        else:
            await message.answer("❌ Не удалось обновить информацию о документах")
    except Exception as e:
        logger.error(f"Ошибка команды /update_documents: {e}")
        await message.answer("❌ Ошибка обновления информации о документах")

@dp.message(Command("test_documents"))
async def cmd_test_documents(message: Message):
    """Команда для тестирования парсера документов"""
    if not DOCUMENTS_PARSER_AVAILABLE:
        await message.answer("❌ Парсер документов временно недоступен")
        return
    
    test_queries = [
        "какие документы нужны при поступлении",
        "необходимые документы для заезда",
        "список документов технопарк",
        "заявление на поступление", 
        "медицинские справки",
        "согласие родителей",
        "что взять с собой"
    ]
    
    response_text = "🧪 **Тест парсера документов:**\n\n"
    
    for query in test_queries:
        logger.info(f"🔍 Тестируем запрос о документах: {query}")
        try:
            context = await get_enhanced_context(query)
            
            if "недоступна" in context or "не найдена" in context:
                response_text += f"❌ **{query}** - информация не найдена\n\n"
            elif "📄 НЕОБХОДИМЫЕ ДОКУМЕНТЫ" in context:
                response_text += f"✅ **{query}** - найдена информация о документах\n\n"
            else:
                response_text += f"⚠️ **{query}** - базовый контекст без документов\n\n"
                
        except Exception as e:
            response_text += f"⚠️ **{query}** - ошибка: {str(e)[:50]}\n\n"
    
    await message.answer(response_text)

# Обработчик для инлайн-кнопок оценки
@dp.callback_query(F.data.startswith("rate_"))
async def handle_rating_callback(callback: CallbackQuery):
    """Обработка оценки работы консультанта"""
    user_id = callback.from_user.id
    data = callback.data.split("_")
    
    if len(data) >= 3 and data[1].isdigit():
        rating = int(data[1])
        operator_id = int(data[2]) if data[2].isdigit() else None
        
        if operator_id:
            success = await operator_handler.rate_operator(user_id, operator_id, rating, bot)
            if success:
                await callback.answer(f"Спасибо за оценку: {'⭐' * rating}")
                await callback.message.edit_text(
                    callback.message.text + f"\n\n✅ Оценка: {'⭐' * rating}"
                )
            else:
                await callback.answer("Ошибка сохранения оценки")
        else:
            await callback.answer("Ошибка: неверный ID оператора")
    elif data[1] == "skip":
        # Пропустить оценку
        operator_handler.set_user_status(user_id, UserStatus.NORMAL)
        await callback.answer("Спасибо за обращение!")
        await callback.message.edit_text(
            callback.message.text + f"\n\n✅ Спасибо за обращение!"
        )
    else:
        await callback.answer("Ошибка обработки оценки")

# Обработчики инлайн-кнопок для операторов
@dp.callback_query(F.data.startswith("accept_request_"))
async def handle_accept_request_callback(callback: CallbackQuery):
    """Принять запрос пользователя (через инлайн-кнопку)"""
    try:
        logger.info(f"🔘 Callback от оператора {callback.from_user.id}: {callback.data}")
        
        user_id = int(callback.data.split("_")[2])
        operator_id = callback.from_user.id
        
        logger.info(f"👤 Оператор {operator_id} принимает запрос пользователя {user_id}")
        
        # Проверяем, что пользователь является оператором
        if not operator_handler.operator_manager.is_operator(operator_id):
            logger.warning(f"❌ Пользователь {operator_id} не является оператором")
            await callback.answer("❌ У вас нет прав оператора", show_alert=True)
            return
        
        logger.info(f"🔄 Вызываем accept_request для оператора {operator_id} и пользователя {user_id}")
        success, msg = await operator_handler.accept_request(operator_id, user_id, bot)
        
        logger.info(f"📋 Результат accept_request: success={success}, msg='{msg}'")
        
        if success:
            logger.info(f"✅ Запрос успешно принят оператором {operator_id}")
            # Обновляем сообщение-уведомление
            await callback.message.edit_text(
                f"✅ **Запрос принят!**\n\n"
                f"👤 Оператор: {callback.from_user.first_name}\n"
                f"📞 Подключен к пользователю ID: {user_id}\n"
                f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"{msg}",
                reply_markup=None,
                parse_mode="Markdown"
            )
            await callback.answer("✅ Запрос принят!", show_alert=False)
        else:
            logger.error(f"❌ Ошибка принятия запроса: {msg}")
            await callback.message.edit_text(
                f"❌ **Не удалось принять запрос**\n\n{msg}",
                reply_markup=None,
                parse_mode="Markdown"
            )
            await callback.answer(f"❌ {msg}", show_alert=True)
            
    except (ValueError, IndexError) as e:
        logger.error(f"❌ Ошибка парсинга callback data: {e}, data: {callback.data}")
        await callback.answer("❌ Некорректный ID пользователя", show_alert=True)
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка в accept_request_callback: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

@dp.callback_query(F.data.startswith("request_details_"))
async def handle_request_details_callback(callback: CallbackQuery):
    """Показать подробную информацию о запросе"""
    try:
        user_id = int(callback.data.split("_")[2])
        operator_id = callback.from_user.id
        
        if not operator_handler.operator_manager.is_operator(operator_id):
            await callback.answer("❌ У вас нет прав оператора", show_alert=True)
            return
        
        # Получаем детальную информацию о запросе
        if user_id in operator_handler.waiting_queue:
            request_info = operator_handler.waiting_queue[user_id]
            message_history = request_info.get('message_history', [])
            
            details_text = (
                f"📋 **Детали запроса**\n\n"
                f"👤 **Пользователь:** {request_info['first_name']}\n"
                f"📱 **Username:** @{request_info['username']}\n"
                f"⏰ **Время запроса:** {request_info['request_time'].strftime('%H:%M:%S')}\n"
                f"📋 **Позиция в очереди:** {request_info['queue_position']}\n\n"
                f"💬 **Оригинальный запрос:**\n_{request_info['original_message']}_\n\n"
            )
            
            if message_history:
                details_text += "📜 **История сообщений:**\n"
                for i, msg in enumerate(message_history, 1):
                    timestamp = msg.get('timestamp', 'неизвестно')
                    if isinstance(timestamp, datetime):
                        timestamp = timestamp.strftime('%H:%M')
                    text = msg.get('text', '[медиа]')
                    details_text += f"{i}. [{timestamp}] {text}\n"
            
            # Создаем кнопки для действий
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Принять запрос", 
                        callback_data=f"accept_request_{user_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Назад к уведомлению", 
                        callback_data=f"refresh_request_{user_id}"
                    )
                ]
            ])
            
            await callback.message.edit_text(
                details_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text(
                "❌ **Запрос не найден**\n\nВозможно, запрос уже был обработан другим оператором.",
                reply_markup=None,
                parse_mode="Markdown"
            )
        
        await callback.answer()
        
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный ID пользователя", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

@dp.callback_query(F.data == "queue_status")
async def handle_queue_status_callback(callback: CallbackQuery):
    """Показать статус очереди"""
    if not operator_handler.operator_manager.is_operator(callback.from_user.id):
        await callback.answer("❌ У вас нет прав оператора", show_alert=True)
        return
    
    queue_info = operator_handler.get_queue_info()
    
    status_text = (
        f"📊 **Статус системы операторов**\n\n"
        f"⏳ **В очереди ожидания:** {queue_info['waiting_count']}\n"
        f"💬 **Активные сессии:** {queue_info['active_sessions']}\n"
        f"👨‍💼 **Операторов онлайн:** {queue_info['active_operators']}\n\n"
    )
    
    if queue_info['queue_details']:
        status_text += "📋 **Детали очереди:**\n"
        for i, user_info in enumerate(queue_info['queue_details'][:5], 1):  # Показываем первые 5
            status_text += (
                f"{i}. {user_info['first_name']} - "
                f"{user_info['request_time'].strftime('%H:%M')}\n"
            )
        if len(queue_info['queue_details']) > 5:
            status_text += f"... и еще {len(queue_info['queue_details']) - 5} запросов\n"
    
    await callback.message.edit_text(status_text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("refresh_request_"))
async def handle_refresh_request_callback(callback: CallbackQuery):
    """Обновить информацию о запросе"""
    try:
        user_id = int(callback.data.split("_")[2])
        operator_id = callback.from_user.id
        
        if not operator_handler.operator_manager.is_operator(operator_id):
            await callback.answer("❌ У вас нет прав оператора", show_alert=True)
            return
        
        # Повторно отправляем уведомление с обновленной информацией
        await operator_handler._notify_available_operators(user_id, bot)
        await callback.answer("🔄 Информация обновлена", show_alert=False)
        
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный ID пользователя", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

@dp.callback_query(F.data == "end_user_session")
async def handle_end_user_session_callback(callback: CallbackQuery):
    """Завершить сессию по инициативе пользователя"""
    user_id = callback.from_user.id
    user_status = operator_handler.get_user_status(user_id)
    
    logger.info(f"🔚 Пользователь {user_id} завершает сессию через кнопку")
    
    if user_status != UserStatus.WITH_OPERATOR:
        await callback.answer("❌ У вас нет активной сессии с консультантом", show_alert=True)
        return
    
    success = await operator_handler.end_session(user_id, bot, "завершена пользователем")
    
    if success:
        await callback.message.edit_text(
            "❌ Консультация завершена по вашей инициативе.\n\n"
            "Спасибо за обращение! Ожидайте форму оценки качества консультации.",
            reply_markup=None
        )
        await callback.answer("✅ Сессия завершена")
        logger.info(f"✅ Сессия пользователя {user_id} успешно завершена")
    else:
        await callback.answer("❌ Ошибка завершения сессии", show_alert=True)
        logger.error(f"❌ Ошибка завершения сессии пользователя {user_id}")

@dp.callback_query(F.data.startswith("operator_end_session_"))
async def handle_operator_end_session_callback(callback: CallbackQuery):
    """Завершить сессию по инициативе консультанта"""
    try:
        user_id = int(callback.data.split("_")[3])
        operator_id = callback.from_user.id
        
        logger.info(f"🔚 Консультант {operator_id} завершает сессию с пользователем {user_id}")
        
        # Проверяем, что это действительно консультант этой сессии
        if user_id in operator_handler.active_sessions:
            session = operator_handler.active_sessions[user_id]
            if session.get("operator_id") != operator_id:
                await callback.answer("❌ Это не ваша сессия", show_alert=True)
                return
        else:
            await callback.answer("❌ Сессия не найдена", show_alert=True)
            return
        
        success = await operator_handler.end_session(user_id, bot, "завершена консультантом")
        
        if success:
            await callback.message.edit_text(
                f"🔚 Сессия с пользователем завершена.\n\n"
                f"👤 Пользователь получит форму оценки качества консультации.\n"
                f"⏰ Время завершения: {datetime.now().strftime('%H:%M:%S')}",
                reply_markup=None
            )
            await callback.answer("✅ Сессия завершена")
            logger.info(f"✅ Сессия между консультантом {operator_id} и пользователем {user_id} успешно завершена")
        else:
            await callback.answer("❌ Ошибка завершения сессии", show_alert=True)
            logger.error(f"❌ Ошибка завершения сессии консультантом {operator_id}")
            
    except (ValueError, IndexError) as e:
        logger.error(f"❌ Ошибка парсинга callback data: {e}, data: {callback.data}")
        await callback.answer("❌ Некорректные данные", show_alert=True)
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка в operator_end_session_callback: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

# Обработчики для инлайн кнопок главного меню
@dp.callback_query(F.data == "info_about")
async def handle_info_about(callback: CallbackQuery):
    """Информация о технопарке"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
    ])
    
    info_text = (
        "🏫 **О Национальном детском технопарке**\n\n"
        "Национальный детский технопарк - это современное образовательное учреждение, "
        "где дети и подростки могут изучать передовые технологии и развивать инновационные навыки.\n\n"
        "🎯 **Наша миссия:**\n"
        "• Развитие технического творчества у детей\n"
        "• Подготовка будущих инженеров и изобретателей\n"
        "• Популяризация науки и технологий\n\n"
        "🏢 **Современная инфраструктура:**\n"
        "• Высокотехнологичные лаборатории\n"
        "• Современное оборудование\n"
        "• Опытные преподаватели\n\n"
        "📞 Для получения подробной информации свяжитесь с консультантом."
    )
    
    await callback.message.edit_text(info_text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "info_programs")
async def handle_info_programs(callback: CallbackQuery):
    """Информация о направлениях обучения"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
    ])
    
    info_text = (
        "📚 **Направления обучения в технопарке**\n\n"
        "🤖 **Робототехника**\n"
        "• Конструирование роботов\n"
        "• Программирование микроконтроллеров\n"
        "• Участие в соревнованиях\n\n"
        "💻 **Программирование**\n"
        "• Изучение различных языков программирования\n"
        "• Разработка мобильных приложений\n"
        "• Создание веб-сайтов\n\n"
        "🔬 **Инженерные технологии**\n"
        "• 3D-моделирование и печать\n"
        "• Лазерные технологии\n"
        "• Прототипирование\n\n"
        "🧬 **Биотехнологии**\n"
        "• Лабораторные исследования\n"
        "• Современные методы анализа\n"
        "• Практические работы\n\n"
        "📞 Для получения подробной информации о направлениях свяжитесь с консультантом."
    )
    
    await callback.message.edit_text(info_text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "info_admission")
async def handle_info_admission(callback: CallbackQuery):
    """Информация о поступлении"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
    ])
    
    info_text = (
        "📝 **Поступление в технопарк**\n\n"
        "🎯 **Кого мы принимаем:**\n"
        "• Детей от 5 до 18 лет\n"
        "• Заинтересованных в изучении технологий\n"
        "• Готовых к активному обучению\n\n"
        "📋 **Процедура поступления:**\n"
        "1️⃣ Подача заявки через сайт или лично\n"
        "2️⃣ Предоставление необходимых документов\n"
        "3️⃣ Собеседование (при необходимости)\n"
        "4️⃣ Зачисление на выбранное направление\n\n"
        "📄 **Необходимые документы:**\n"
        "• Заявление от родителей/законных представителей\n"
        "• Копия свидетельства о рождении/паспорта\n"
        "• Медицинская справка (при необходимости)\n\n"
        "⏰ **Сроки подачи заявок:**\n"
        "Прием заявок ведется круглогодично в зависимости от направления и наличия мест.\n\n"
        "📞 Для получения подробной информации о поступлении свяжитесь с консультантом."
    )
    
    await callback.message.edit_text(info_text, reply_markup=keyboard)
    await callback.answer()

# Обработчики для расписания, контактов и стоимости удалены

@dp.callback_query(F.data == "request_consultant")
async def handle_request_consultant(callback: CallbackQuery, state: FSMContext):
    """Обработка запроса консультанта через инлайн кнопку"""
    user_id = callback.from_user.id
    
    # Используем существующую логику эскалации к оператору
    success = await operator_handler.escalate_to_operator(
        user_id, 
        callback.message, 
        auto_escalation=False,
        bot=bot
    )
    
    if success:
        await state.set_state(OperatorState.WAITING_OPERATOR)
        queue_info = operator_handler.get_queue_info()
        position = len([u for u in queue_info["queue_details"] if u["user_id"] == user_id])
        
        await callback.message.edit_text(
            "📞 Ваш запрос передан консультанту.\n"
            "Пожалуйста, ожидайте подключения.\n\n"
            f"📋 Ваша позиция в очереди: {position}\n"
            "⏰ Среднее время ожидания: 3-5 минут\n\n"
            "Вы можете отменить ожидание командой /cancel"
        )
        await callback.answer("✅ Запрос отправлен консультанту")
    else:
        await callback.answer("❌ Не удалось подключиться к системе операторов", show_alert=True)

@dp.callback_query(F.data == "back_to_menu")
async def handle_back_to_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    welcome_text = (
        "👋 Добро пожаловать в бот Национального детского технопарка!\n\n"
        "🤖 Я ваш интеллектуальный помощник. Выберите интересующую вас тему:"
    )
    
    keyboard_rows = [
        [
            InlineKeyboardButton(text="🏫 О технопарке", callback_data="info_about"),
            InlineKeyboardButton(text="📚 Направления обучения", callback_data="info_programs")
        ],
        [
            InlineKeyboardButton(text="📝 Поступление", callback_data="info_admission")
        ]
    ]
    
    # Добавляем кнопку календаря, если модуль доступен
    if CALENDAR_AVAILABLE:
        keyboard_rows.append([
            InlineKeyboardButton(text="📅 Календарь смен", callback_data="show_calendar")
        ])
    
    keyboard_rows.append([
        InlineKeyboardButton(text="👨‍💼 Связаться с консультантом", callback_data="request_consultant")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await callback.message.edit_text(welcome_text, reply_markup=keyboard)
    await callback.answer()

# Обработчики для календаря смен
@dp.callback_query(F.data == "show_calendar")
async def handle_show_calendar(callback: CallbackQuery):
    """Показать календарь смен"""
    if not CALENDAR_AVAILABLE:
        await callback.answer("❌ Календарь временно недоступен", show_alert=True)
        return
    
    try:
        user_id = callback.from_user.id
        text, keyboard = get_calendar_interface(user_id)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"❌ Ошибка показа календаря: {e}")
        await callback.answer("❌ Ошибка загрузки календаря", show_alert=True)

@dp.callback_query(F.data.startswith("calendar_shift_"))
async def handle_calendar_shift(callback: CallbackQuery):
    """Показать информацию о конкретной смене"""
    if not CALENDAR_AVAILABLE:
        await callback.answer("❌ Календарь временно недоступен", show_alert=True)
        return
    
    try:
        month_number = int(callback.data.split("_")[2])
        text, keyboard = await get_shift_info(month_number)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    except (ValueError, IndexError) as e:
        logger.error(f"❌ Ошибка парсинга данных смены: {e}")
        await callback.answer("❌ Ошибка обработки запроса", show_alert=True)
    except Exception as e:
        logger.error(f"❌ Ошибка получения информации о смене: {e}")
        await callback.answer("❌ Ошибка загрузки информации", show_alert=True)

@dp.callback_query(F.data == "back_to_calendar")
async def handle_back_to_calendar(callback: CallbackQuery):
    """Вернуться к календарю смен"""
    if not CALENDAR_AVAILABLE:
        await callback.answer("❌ Календарь временно недоступен", show_alert=True)
        return
    
    try:
        user_id = callback.from_user.id
        text, keyboard = get_calendar_interface(user_id)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"❌ Ошибка возврата к календарю: {e}")
        await callback.answer("❌ Ошибка загрузки календаря", show_alert=True)

# Обработчики для системы уведомлений
@dp.callback_query(F.data == "notification_settings")
async def handle_notification_settings(callback: CallbackQuery):
    """Показать настройки уведомлений"""
    if not CALENDAR_AVAILABLE or not NOTIFICATIONS_AVAILABLE:
        await callback.answer("❌ Система уведомлений временно недоступна", show_alert=True)
        return
    
    try:
        user_id = callback.from_user.id
        text, keyboard = get_notification_settings_interface(user_id)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"❌ Ошибка показа настроек уведомлений: {e}")
        await callback.answer("❌ Ошибка загрузки настроек", show_alert=True)

@dp.callback_query(F.data.startswith("toggle_notification_"))
async def handle_toggle_notification(callback: CallbackQuery):
    """Переключить подписку на уведомления"""
    if not NOTIFICATIONS_AVAILABLE:
        await callback.answer("❌ Система уведомлений временно недоступна", show_alert=True)
        return
    
    try:
        user_id = callback.from_user.id
        notification_type = callback.data.replace("toggle_notification_", "")
        
        # Проверяем текущий статус подписки
        is_subscribed = notification_system.is_subscribed(user_id, notification_type)
        
        if is_subscribed:
            # Отписываемся
            success = notification_system.unsubscribe_user(user_id, notification_type)
            if success:
                await callback.answer("✅ Вы отписались от уведомлений")
                logger.info(f"👤 Пользователь {user_id} отписался от {notification_type}")
            else:
                await callback.answer("❌ Ошибка отписки", show_alert=True)
        else:
            # Подписываемся
            success = notification_system.subscribe_user(user_id, notification_type)
            if success:
                await callback.answer("✅ Вы подписались на уведомления")
                logger.info(f"👤 Пользователь {user_id} подписался на {notification_type}")
            else:
                await callback.answer("❌ Ошибка подписки", show_alert=True)
        
        # Обновляем интерфейс
        text, keyboard = get_notification_settings_interface(user_id)
        await callback.message.edit_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"❌ Ошибка переключения уведомлений: {e}")
        await callback.answer("❌ Ошибка изменения настроек", show_alert=True)

# Фоновая задача для проверки дедлайнов
async def deadline_checker_loop():
    """Фоновая задача для проверки дедлайнов подачи заявок"""
    while True:
        try:
            if NOTIFICATIONS_AVAILABLE:
                await notification_system.check_application_deadlines()
                # Проверяем каждые 6 часов
                await asyncio.sleep(6 * 60 * 60)
            else:
                # Если система недоступна, проверяем каждые 30 минут
                await asyncio.sleep(30 * 60)
        except Exception as e:
            logger.error(f"❌ Ошибка в проверке дедлайнов: {e}")
            await asyncio.sleep(60 * 60)  # Ждем час при ошибке

# Запуск бота
async def main():
    logger.info("🚀 Запуск бота Национального детского технопарка...")
    logger.info("📚 Загрузка базы знаний...")
    
    # Загружаем базовую RAG систему
    rag_system.load_knowledge_base()
    
    # Если доступна современная RAG система, показываем её статус
    if MODERN_RAG_AVAILABLE:
        try:
            stats = modern_rag.get_stats()
            logger.info(f"🚀 Современная RAG система готова: {stats['total_documents']} документов")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации современной RAG: {e}")
    
    # Инициализируем систему уведомлений
    if NOTIFICATIONS_AVAILABLE:
        try:
            notification_system.set_bot(bot)
            logger.info("🔔 Система уведомлений инициализирована")
            
            # Запускаем фоновую проверку дедлайнов
            asyncio.create_task(deadline_checker_loop())
            logger.info("⏰ Система проверки дедлайнов активна")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации системы уведомлений: {e}")
    
    # Запускаем фоновое обновление расписания
    logger.info("📅 Запуск системы обновления расписания...")
    try:
        # Сразу пробуем обновить расписание при старте
        await force_update_schedule()
        
        # Запускаем фоновый цикл обновления
        asyncio.create_task(schedule_updater_loop(interval_hours=6))
        logger.info("✅ Система обновления расписания активна")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска системы обновления расписания: {e}")
    
    # Запускаем систему обновления документов
    if DOCUMENTS_PARSER_AVAILABLE:
        logger.info("📄 Запуск системы обновления документов...")
        try:
            # Сразу пробуем обновить документы при старте
            await force_update_documents()
            
            # Запускаем фоновый цикл обновления документов
            asyncio.create_task(documents_updater_loop(interval_hours=24))
            logger.info("✅ Система обновления документов активна")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска системы обновления документов: {e}")
    
    # Парсер списков временно отключен
    logger.info("📋 Парсер списков временно отключен")
    
    logger.info("✅ Бот готов к работе!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main()) 