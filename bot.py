import asyncio
import logging
import os

# Новые импорты для улучшений
import re
import time
from datetime import datetime
from typing import Optional

import aiohttp
from aiogram import BaseMiddleware, Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

from operator_handler import OperatorState, UserStatus, operator_handler
from rag_system import RAGModes, rag_system
from schedule_parser import (
    force_update_schedule,
    get_schedule_context,
    get_schedule_context_async,
    schedule_updater_loop,
)

# Настройка логирования (ВАЖНО: настраиваем ПЕРЕД импортом модулей)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# Настройка уровней логирования для разных модулей
logging.getLogger("aiogram.dispatcher").setLevel(logging.WARNING)
logging.getLogger("aiogram.bot").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# Безопасный импорт dateparser
try:
    import dateparser

    DATEPARSER_AVAILABLE = True
    logger.info("✅ dateparser успешно импортирован")
except ImportError:
    DATEPARSER_AVAILABLE = False
    logger.warning("⚠️ dateparser недоступен - используется fallback regex")

# Безопасный импорт redis с обработкой совместимости
try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
    logger.info("✅ redis.asyncio успешно импортирован")
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("⚠️ redis недоступен - используется локальный кэш лимитов")
    redis = None
except Exception as e:
    REDIS_AVAILABLE = False
    logger.warning(f"⚠️ Ошибка импорта redis: {e}")
    logger.info("💡 Используется локальный кэш лимитов")
    redis = None

# Загрузка переменных окружения
load_dotenv()

# Импорт собственных модулей


# Роли: администраторы (из переменной окружения ADMIN_IDS="id1,id2,...")
ADMIN_IDS_ENV = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS = set()
if ADMIN_IDS_ENV:
    for part in ADMIN_IDS_ENV.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ADMIN_IDS.add(int(part))
        except ValueError:
            logger.warning(f"⚠️ Некорректный ID администратора в ADMIN_IDS: {part}")


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# Добавляем импорт парсера расписания


# Добавляем импорт парсера документов
try:
    from documents_parser import (
        documents_updater_loop,
        force_update_documents,
        get_documents_context,
        get_documents_context_async,
    )

    DOCUMENTS_PARSER_AVAILABLE = True
    logger.info("📄 Парсер документов загружен")
except ImportError as e:
    logger.warning(f"⚠️ Парсер документов недоступен: {e}")
    DOCUMENTS_PARSER_AVAILABLE = False

# Добавляем импорт парсера списков
try:
    from lists_parser import (
        get_lists_stats,
        initialize_lists_parser,
        search_name_in_lists,
        update_lists_cache,
    )

    LISTS_PARSER_AVAILABLE = True
    logger.info("📋 Парсер списков загружен")
except ImportError as e:
    logger.warning(f"⚠️ Парсер списков недоступен: {e}")
    LISTS_PARSER_AVAILABLE = False

# Импорт модуля календаря
try:
    from calendar_module import (
        get_calendar_interface,
        get_notification_settings_interface,
        get_shift_info,
    )

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

# Импорт квиз модуля
try:
    from quiz_mod import (
        get_quiz_stats,
        quiz_start,
        quiz_start_callback,
        register_quiz_handlers,
    )

    QUIZ_AVAILABLE = True
    logger.info("🎯 Квиз модуль загружен")
except ImportError as e:
    logger.warning(f"⚠️ Квиз модуль недоступен: {e}")
    QUIZ_AVAILABLE = False

# Импорт модуля брейншторма
try:
    from brainstorm_mod import (
        get_brainstorm_stats,
        init_brainstorm_llm,
        register_brainstorm_handlers,
        register_brainstorm_menu_handler,
    )

    BRAINSTORM_AVAILABLE = True
    logger.info("🧠 Модуль брейншторма загружен")
except ImportError as e:
    logger.warning(f"⚠️ Модуль брейншторма недоступен: {e}")
    BRAINSTORM_AVAILABLE = False

# Глобальные переменные для RAG систем (инициализируются лениво)
optimized_rag = None
modern_rag = None
OPTIMIZED_RAG_AVAILABLE = False
MODERN_RAG_AVAILABLE = False

# Флаги готовности RAG систем
rag_systems_ready = {"optimized": False, "modern": False}


async def init_optimized_rag():
    """Ленивая инициализация оптимизированной RAG системы"""
    global optimized_rag, OPTIMIZED_RAG_AVAILABLE
    try:
        logger.info("🚀 Инициализация оптимизированной RAG системы...")
        from optimized_rag_system import RAGModes, get_optimized_rag

        loop = asyncio.get_running_loop()
        optimized_rag = await loop.run_in_executor(
            None, lambda: get_optimized_rag(RAGModes.ECONOMY)
        )

        OPTIMIZED_RAG_AVAILABLE = True
        rag_systems_ready["optimized"] = True
        logger.info(
            f"✅ Оптимизированная RAG система готова: {optimized_rag.get_stats()}"
        )

    except Exception as e:
        logger.error(f"❌ Ошибка инициализации оптимизированной RAG: {e}")
        OPTIMIZED_RAG_AVAILABLE = False


async def init_modern_rag():
    """Ленивая инициализация современной RAG системы"""
    global modern_rag, MODERN_RAG_AVAILABLE
    try:
        logger.info("📚 Инициализация современной RAG системы...")
        from modern_rag_system import ModernRAGSystem, set_global_instance

        loop = asyncio.get_running_loop()

        # Создаем и инициализируем RAG систему в отдельном потоке
        def create_and_init_rag():
            rag = ModernRAGSystem()
            rag.load_and_index_knowledge()
            return rag

        modern_rag = await loop.run_in_executor(None, create_and_init_rag)
        set_global_instance(modern_rag)

        MODERN_RAG_AVAILABLE = True
        rag_systems_ready["modern"] = True
        stats = modern_rag.get_stats()
        logger.info(
            f"✅ Современная RAG система готова: {stats['total_documents']} документов"
        )

    except Exception as e:
        logger.error(f"❌ Ошибка инициализации современной RAG: {e}")
        MODERN_RAG_AVAILABLE = False


# ========================================
# 🔧 УЛУЧШЕНИЯ: Парсинг дат и лимиты API
# ========================================

# Словарь для надёжного парсинга русских месяцев
MONTHS_PATTERNS = {
    r"январ\w*": 1,
    r"феврал\w*": 2,
    r"март\w*": 3,
    r"апрел\w*": 4,
    r"ма[йя]\w*": 5,
    r"июн\w*": 6,
    r"июл\w*": 7,
    r"август\w*": 8,
    r"сентябр\w*": 9,
    r"октябр\w*": 10,
    r"ноябр\w*": 11,
    r"декабр\w*": 12,
}

# Компилируем regex для парсинга дат
DATE_REGEX = re.compile(
    rf"(?P<day>\d{{1,2}})\s+(?P<month>{'|'.join(MONTHS_PATTERNS)})\s*(?P<year>\d{{4}})?",
    re.IGNORECASE | re.UNICODE,
)


def parse_russian_date(text: str, default_year: int = None) -> Optional[datetime]:
    """
    Надёжный парсер русских дат с fallback на dateparser

    Args:
        text: Текст содержащий дату
        default_year: Год по умолчанию, если не указан

    Returns:
        datetime объект или None если дата не найдена
    """
    if not text:
        return None

    # Очищаем текст от лишних пробелов
    clean_text = re.sub(r"\s+", " ", text.strip())

    # Сначала пробуем dateparser (надёжнее), если доступен
    if DATEPARSER_AVAILABLE:
        try:
            dt = dateparser.parse(
                clean_text,
                languages=["ru"],
                settings={"DATE_ORDER": "DMY", "PREFER_DAY_OF_MONTH": "first"},
            )
            if dt:
                return dt
        except Exception as e:
            logger.warning(f"⚠️ dateparser не смог распарсить '{clean_text}': {e}")

    # Fallback на собственный regex
    try:
        match = DATE_REGEX.search(clean_text)
        if match:
            day = int(match.group("day"))
            month_text = match.group("month")
            year = int(match.group("year") or default_year or datetime.now().year)

            # Находим номер месяца
            month = None
            for pattern, num in MONTHS_PATTERNS.items():
                if re.fullmatch(pattern, month_text, re.IGNORECASE):
                    month = num
                    break

            if month:
                return datetime(year, month, day)
    except Exception as e:
        logger.warning(f"⚠️ Regex не смог распарсить '{clean_text}': {e}")

    return None


# Инициализация Redis для лимитов
redis_client = None
if REDIS_AVAILABLE:
    try:
        # Отложенная инициализация Redis - создаем соединение только при первом использовании
        logger.info("🔴 Redis модуль готов к использованию")
    except Exception as e:
        logger.warning(f"⚠️ Redis модуль недоступен: {e}")
        REDIS_AVAILABLE = False

# Семафор для ограничения одновременных LLM запросов
LLM_CONCURRENCY = 10
llm_semaphore = asyncio.Semaphore(LLM_CONCURRENCY)


class HourlyLimitMiddleware(BaseMiddleware):
    """Middleware для ограничения количества запросов в час с улучшенной Redis поддержкой"""

    def __init__(self, limit_per_hour: int = 50):
        self.limit = limit_per_hour
        self.fallback_cache = {}  # Fallback для случая без Redis
        self._redis_client = None

    async def __call__(self, handler, event, data):
        if not hasattr(event, "from_user") or not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id

        # Используем Redis если доступен
        if REDIS_AVAILABLE and redis is not None:
            try:
                # Создаем соединение Redis только при необходимости
                if self._redis_client is None:
                    self._redis_client = redis.from_url(
                        "redis://localhost", decode_responses=True
                    )

                key = f"user:{user_id}:quota"
                used = await self._redis_client.incr(key)
                if used == 1:
                    await self._redis_client.expire(key, 3600)  # TTL 1 час

                if used > self.limit:
                    ttl = await self._redis_client.ttl(key)
                    await event.answer(
                        "⌛ Вы исчерпали лимит запросов в час.\n"
                        f"Попробуйте через {ttl if ttl > 0 else 3600} секунд."
                    )
                    return

                # Логируем близкие к лимиту запросы
                if used > self.limit * 0.8:
                    logger.warning(
                        f"⚠️ Пользователь {user_id} близок к лимиту: {used}/{self.limit}"
                    )

                # Успешно использовали Redis, выходим
                return await handler(event, data)

            except Exception as e:
                logger.warning(f"⚠️ Redis недоступен: {e}")
                # Fallback на локальный кэш
                self._redis_client = None

        # Fallback: простой локальный кэш
        current_time = time.time()
        current_hour = int(current_time // 3600)

        if user_id not in self.fallback_cache:
            self.fallback_cache[user_id] = {"hour": current_hour, "count": 0}

        user_data = self.fallback_cache[user_id]

        # Сброс счётчика при смене часа
        if user_data["hour"] != current_hour:
            user_data["hour"] = current_hour
            user_data["count"] = 0

        user_data["count"] += 1

        if user_data["count"] > self.limit:
            await event.answer(
                "⌛ Вы исчерпали лимит запросов в час.\nПопробуйте через час."
            )
            return

        return await handler(event, data)


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
        "Sunday": "воскресенье",
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
logger.info("🤖 Создание экземпляра бота...")
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
logger.info("✅ Бот и диспетчер инициализированы")

# Добавляем middleware для лимитов API
logger.info("🛡️ Установка middleware для лимитов API...")
dp.message.middleware(HourlyLimitMiddleware(limit_per_hour=50))
dp.callback_query.middleware(HourlyLimitMiddleware(limit_per_hour=50))
logger.info("✅ Middleware установлен (50 запросов/час)")


# Регистрируем команды бота в спец-меню Telegram
async def on_startup_set_commands(bot: Bot):
    try:
        commands = [
            types.BotCommand(command="start", description="Запустить бота"),
            types.BotCommand(command="menu", description="Главное меню"),
        ]
        # По желанию пользователя — показываем основные функции
        if CALENDAR_AVAILABLE:
            commands.append(
                types.BotCommand(command="calendar", description="Календарь смен")
            )
        if QUIZ_AVAILABLE:
            commands.append(
                types.BotCommand(command="quiz", description="Квиз: подбор направления")
            )
        if BRAINSTORM_AVAILABLE:
            commands.append(
                types.BotCommand(command="brainstorm", description="Брейншторм идей")
            )
        if LISTS_PARSER_AVAILABLE:
            commands.append(
                types.BotCommand(command="checklists", description="Проверить списки")
            )
        commands.append(
            types.BotCommand(command="help", description="Связаться с консультантом")
        )

        await bot.set_my_commands(commands)
        logger.info("✅ Команды бота зарегистрированы в спец-меню Telegram")
    except Exception as e:
        logger.error(f"❌ Не удалось установить команды бота: {e}")


dp.startup.register(on_startup_set_commands)


# Состояния FSM (дополнительные к OperatorState)
class UserState(StatesGroup):
    IN_QUIZ = State()
    COLLECTING_DOCUMENTS = State()
    SEARCHING_LISTS = State()


# Класс для работы с DeepSeek API
class DeepSeekAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=60), stop=stop_after_attempt(5)
    )
    async def _make_request(self, payload: dict) -> Optional[dict]:
        """Защищённый HTTP запрос с retry логикой"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                DEEPSEEK_API_URL, headers=self.headers, json=payload
            ) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    retry_after = response.headers.get("Retry-After", "60")
                    logger.warning(f"⚠️ Rate limit (429), retry after {retry_after}s")
                    raise aiohttp.ClientResponseError(
                        response.request_info,
                        response.history,
                        status=429,
                        message=f"Rate limit exceeded, retry after {retry_after}s",
                    )
                else:
                    logger.error(f"❌ DeepSeek API error: {response.status}")
                    response.raise_for_status()

    async def get_completion(
        self, messages: list, temperature: float = 0.7
    ) -> Optional[str]:
        """Получить обычный ответ от DeepSeek с защитой от перегрузки"""
        try:
            # Используем семафор для ограничения одновременных запросов
            async with llm_semaphore:
                payload = {
                    "model": "deepseek-chat",
                    "messages": messages,
                    "temperature": temperature,
                }

                result = await self._make_request(payload)
                if result:
                    return result["choices"][0]["message"]["content"]
                return None

        except Exception as e:
            logger.error(f"❌ Error in DeepSeek API call: {e}")
            return None

    async def get_streaming_completion(self, messages: list, temperature: float = 0.7):
        """Генератор для стриминговых ответов с защитой от перегрузки"""
        try:
            # Используем семафор для ограничения одновременных запросов
            async with llm_semaphore:
                payload = {
                    "model": "deepseek-chat",
                    "messages": messages,
                    "temperature": temperature,
                    "stream": True,
                }

                # Повторяем попытки при ошибках
                for attempt in range(3):
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.post(
                                DEEPSEEK_API_URL, headers=self.headers, json=payload
                            ) as response:
                                if response.status == 429:
                                    retry_after = int(
                                        response.headers.get("Retry-After", "60")
                                    )
                                    logger.warning(
                                        f"⚠️ Rate limit при стриминге, ждём {retry_after}s"
                                    )
                                    await asyncio.sleep(retry_after)
                                    continue

                                if response.status == 200:
                                    async for line in response.content:
                                        line = line.decode("utf-8").strip()
                                        if line.startswith("data: "):
                                            line = line[6:]
                                            if line == "[DONE]":
                                                break
                                            try:
                                                import json

                                                data = json.loads(line)
                                                if (
                                                    "choices" in data
                                                    and len(data["choices"]) > 0
                                                ):
                                                    delta = data["choices"][0].get(
                                                        "delta", {}
                                                    )
                                                    if "content" in delta:
                                                        yield delta["content"]
                                            except json.JSONDecodeError:
                                                continue
                                    return
                                else:
                                    logger.error(
                                        f"❌ DeepSeek streaming error: {response.status}"
                                    )
                                    if attempt < 2:
                                        await asyncio.sleep(2**attempt)
                                        continue
                                    else:
                                        yield None
                                        return

                    except Exception as e:
                        logger.error(f"❌ Streaming attempt {attempt + 1} failed: {e}")
                        if attempt < 2:
                            await asyncio.sleep(2**attempt)
                            continue
                        else:
                            yield None
                            return

        except Exception as e:
            logger.error(f"❌ Error in DeepSeek streaming API call: {e}")
            yield None


# Инициализация DeepSeek API
logger.info("🧠 Инициализация DeepSeek API...")
deepseek = DeepSeekAPI(DEEPSEEK_API_KEY)
logger.info("✅ DeepSeek API готов к работе")


# Функция для получения расширенного контекста с информацией о расписании
async def get_enhanced_context(query: str) -> str:
    """Получает контекст из RAG системы, обогащенный актуальной информацией"""
    try:
        # ПРИОРИТЕТ: Современная RAG система (если готова)
        if MODERN_RAG_AVAILABLE and rag_systems_ready["modern"]:
            logger.info("📚 Используем современную векторную RAG систему")
            from modern_rag_system import get_context_for_query_async

            base_context = await get_context_for_query_async(query)
        elif OPTIMIZED_RAG_AVAILABLE and rag_systems_ready["optimized"]:
            logger.info("🚀 Используем оптимизированную RAG систему")
            from optimized_rag_system import RAGModes, get_optimized_context_async

            base_context = await get_optimized_context_async(query, RAGModes.ECONOMY)
        else:
            logger.info("📖 Используем базовую RAG систему")
            base_context = rag_system.get_context_for_query(query)

        query_lower = query.lower()
        enhanced_contexts = []

        # Проверяем, связан ли запрос с расписанием/сменами
        schedule_keywords = [
            "смена",
            "смены",
            "расписание",
            "график",
            "заявк",
            "запис",
            "поступление",
            "когда",
            "дат",
            "период",
            "прием",
            "началь",
            "январ",
            "февраль",
            "март",
            "апрель",
            "май",
            "июн",
            "июл",
            "август",
            "сентябр",
            "октябр",
            "ноябр",
            "декабр",
        ]

        is_schedule_related = any(
            keyword in query_lower for keyword in schedule_keywords
        )

        # Проверяем, связан ли запрос с документами
        document_keywords = [
            "документ",
            "документы",
            "справк",
            "заявлен",
            "согласи",
            "свидетельство",
            "медицинск",
            "рождени",
            "бассейн",
            "инфекц",
            "план",
            "учебный",
            "при заезде",
            "поступлен",
            "регистрац",
            "что нужно",
            "что взять",
            "какие нужны",
            "список документов",
            "необходимые",
        ]

        is_documents_related = any(
            keyword in query_lower for keyword in document_keywords
        )

        # Добавляем актуальную информацию о расписании
        if is_schedule_related:
            logger.info(
                "📅 Запрос связан с расписанием - добавляем актуальную информацию"
            )
            schedule_context = await get_schedule_context_async(query)
            enhanced_contexts.append(schedule_context)

        # Добавляем актуальную информацию о документах
        if is_documents_related and DOCUMENTS_PARSER_AVAILABLE:
            logger.info(
                "📄 Запрос связан с документами - добавляем актуальную информацию"
            )
            documents_context = await get_documents_context_async(query)
            if documents_context:
                enhanced_contexts.append(documents_context)

        # Объединяем все контексты
        if enhanced_contexts:
            if "не найдена в базе знаний" not in base_context:
                final_context = f"{base_context}\n\n" + "\n\n".join(enhanced_contexts)
            else:
                final_context = "\n\n".join(enhanced_contexts)

            logger.info("✅ Контекст обогащен дополнительной информацией")
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
    """Стартовое приветствие по ролям: админ / оператор / пользователь"""
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    logger.info(f"🎯 Команда /start от пользователя {user_id} (@{username})")

    # Админ: отдельное приветствие и подсказки по функциям
    if is_admin(user_id):
        admin_text = (
            "🛠 Админ-панель Технопарка\n\n"
            "Доступные возможности:\n"
            "• /queue — очередь пользователей (принятие заявок доступно операторам)\n"
            "• /consultants_stats — сводная статистика по консультантам\n"
            "• /operators — список операторов\n"
            "• /notifications — статус системы уведомлений\n"
            "• /update_schedule, /update_documents — обновление данных\n\n"
            "Подсказка: используйте /help для теста эскалации в систему консультантов."
        )
        await message.answer(admin_text)
        return

    # Оператор: подробный гайд
    if operator_handler.operator_manager.is_operator(user_id):
        text = (
            "👋 Добро пожаловать в панель консультанта!\n\n"
            "Возможности:\n"
            "• Уведомления о новых запросах c кнопкой: ✅ Принять запрос\n"
            "• /queue — список очереди с возможностью принять заявку\n"
            "• /consultants_stats — агрегированная статистика\n"
            "• /operator_stats — ваша личная статистика\n"
            "• /end_session — завершить текущую сессию\n\n"
            "Во время сессии:\n"
            "• Сообщения пользователя приходят как пересланные (с корректной подписью)\n"
            "• Ваши ответы отправляются пользователю от имени консультанта\n"
        )
        await message.answer(text)
        return

    # Пользователь: обычное приветствие с меню
    welcome_text = (
        "👋 Добро пожаловать в бот Национального детского технопарка!\n\n"
        "🤖 Я ваш интеллектуальный помощник. Выберите интересующую вас тему:"
    )

    keyboard_rows = [
        [
            InlineKeyboardButton(text="🏫 О технопарке", callback_data="info_about"),
            InlineKeyboardButton(
                text="📚 Направления обучения", callback_data="info_programs"
            ),
        ],
        [InlineKeyboardButton(text="📝 Поступление", callback_data="info_admission")],
    ]

    if BRAINSTORM_AVAILABLE:
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="🧠 Брейншторм идей", callback_data="start_brainstorm"
                )
            ]
        )

    if CALENDAR_AVAILABLE:
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="📅 Календарь смен", callback_data="show_calendar"
                )
            ]
        )

    if LISTS_PARSER_AVAILABLE:
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="📋 Проверить списки", callback_data="check_lists"
                )
            ]
        )

    if QUIZ_AVAILABLE:
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="🎯 Квиз: подбор направления", callback_data="start_quiz"
                )
            ]
        )

    keyboard_rows.append(
        [
            InlineKeyboardButton(
                text="👨‍💼 Связаться с консультантом",
                callback_data="request_consultant",
            )
        ]
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await message.answer(welcome_text, reply_markup=keyboard)


@dp.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    logger.info(
        f"🆘 Команда /help от пользователя {user_id} (@{username}) - запрос консультанта"
    )

    # Используем новый API для эскалации к оператору
    success = await operator_handler.escalate_to_operator(
        user_id, message, auto_escalation=False, bot=bot
    )

    if success:
        await state.set_state(OperatorState.WAITING_OPERATOR)
        queue_info = operator_handler.get_queue_info()
        position = len(
            [u for u in queue_info["queue_details"] if u["user_id"] == user_id]
        )

        await message.answer(
            "📞 Ваш запрос передан консультанту.\n"
            "Пожалуйста, ожидайте подключения.\n\n"
            f"📋 Ваша позиция в очереди: {position}\n"
            "⏰ Среднее время ожидания: 3-5 минут\n\n"
            "Вы можете отменить ожидание командой /cancel"
        )
    else:
        await message.answer(
            "❌ Не удалось подключиться к системе операторов. Попробуйте позже."
        )


@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    """Главное меню (аналог callback back_to_menu)"""
    welcome_text = (
        "👋 Добро пожаловать в бот Национального детского технопарка!\n\n"
        "🤖 Я ваш интеллектуальный помощник. Выберите интересующую вас тему:"
    )

    keyboard_rows = [
        [
            InlineKeyboardButton(text="🏫 О технопарке", callback_data="info_about"),
            InlineKeyboardButton(
                text="📚 Направления обучения", callback_data="info_programs"
            ),
        ],
        [InlineKeyboardButton(text="📝 Поступление", callback_data="info_admission")],
    ]

    if CALENDAR_AVAILABLE:
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="📅 Календарь смен", callback_data="show_calendar"
                )
            ]
        )

    if LISTS_PARSER_AVAILABLE:
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="📋 Проверить списки", callback_data="check_lists"
                )
            ]
        )

    if QUIZ_AVAILABLE:
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="🎯 Квиз: подбор направления", callback_data="start_quiz"
                )
            ]
        )

    # Если брейншторм подключен — добавим кнопку (brainstorm_mod также добавляет свою при регистрации)
    if BRAINSTORM_AVAILABLE:
        keyboard_rows.insert(
            0,
            [
                InlineKeyboardButton(
                    text="🧠 Брейншторм идей", callback_data="start_brainstorm"
                )
            ],
        )

    keyboard_rows.append(
        [
            InlineKeyboardButton(
                text="👨‍💼 Связаться с консультантом",
                callback_data="request_consultant",
            )
        ]
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await message.answer(welcome_text, reply_markup=keyboard)


@dp.message(Command("quiz"))
async def cmd_quiz(message: Message, state: FSMContext):
    """Запуск квиза (аналог callback start_quiz)"""
    if not QUIZ_AVAILABLE:
        await message.answer("❌ Квиз временно недоступен")
        return
    try:
        # Используем реализацию из квиз-модуля для запуска из сообщений
        await quiz_start(message, state, bot)
    except Exception as e:
        logger.error(f"❌ Ошибка запуска /quiz: {e}")
        await message.answer("❌ Ошибка запуска квиза")


@dp.message(Command("checklists"))
async def cmd_checklists(message: Message, state: FSMContext):
    """Проверка списков (аналог callback check_lists)"""
    if not LISTS_PARSER_AVAILABLE:
        await message.answer("❌ Проверка списков временно недоступна")
        return
    try:
        await state.set_state(UserState.SEARCHING_LISTS)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Назад в меню", callback_data="back_to_menu"
                    )
                ]
            ]
        )
        await message.answer(
            "🔍 Поиск в списках участников\n\n"
            "Напишите имя фамилия для поиска:\n\n"
            "📝 Примеры:\n"
            "• Анна Иванова\n"
            "• Максим Петров\n"
            "• Елена Сидорова\n\n"
            "💡 Правила поиска:\n"
            "• Одно слово → найдет любые записи с этим словом\n"
            "• Два слова → найдет только точные совпадения фразы\n"
            "• Поддерживается обратный порядок (Имя Фамилия ↔ Фамилия Имя)\n\n"
            "⚠️ 'Иванов Петр' НЕ найдет документы, где есть только 'Иванов' или только 'Петр'\n\n"
            "✏️ Введите данные для поиска:",
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.error(f"❌ Ошибка запуска /checklists: {e}")
        await message.answer("❌ Ошибка запуска поиска")


@dp.message(Command("status"))
async def cmd_status(message: Message):
    """Показать статус пользователя"""
    user_id = message.from_user.id
    user_status = operator_handler.get_user_status(user_id)

    logger.info(
        f"ℹ️ Запрос статуса от пользователя {user_id}, статус: {user_status.value}"
    )

    # Определяем текст статуса
    status_descriptions = {
        UserStatus.NORMAL: "🟢 Обычный режим - можете задавать вопросы",
        UserStatus.WAITING_OPERATOR: "⏳ Ожидаете подключения консультанта",
        UserStatus.WITH_OPERATOR: "💬 Общаетесь с консультантом",
        UserStatus.RATING_OPERATOR: "⭐ Необходимо оценить работу консультанта",
    }

    status_text = (
        f"ℹ️ Ваш статус: {status_descriptions.get(user_status, 'Неизвестно')}\n\n"
    )

    # Дополнительная информация в зависимости от статуса
    if (
        user_status == UserStatus.WAITING_OPERATOR
        and user_id in operator_handler.waiting_queue
    ):
        request_info = operator_handler.waiting_queue[user_id]
        status_text += (
            f"📋 Информация о запросе:\n"
            f"⏰ Время запроса: {request_info['request_time'].strftime('%H:%M:%S')}\n"
            f"📍 Позиция в очереди: {request_info['queue_position']}\n\n"
        )
    elif (
        user_status == UserStatus.WITH_OPERATOR
        and user_id in operator_handler.active_sessions
    ):
        session_info = operator_handler.active_sessions[user_id]
        operator_info = operator_handler.operator_manager.get_operator_info(
            session_info["operator_id"]
        )
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

    logger.info(
        f"🚫 Команда /cancel от пользователя {user_id}, статус: {user_status.value}"
    )

    # Отмена ожидания оператора или активной сессии
    if user_status == UserStatus.WAITING_OPERATOR:
        success, msg = await operator_handler.cancel_waiting(user_id, bot)
        if success:
            await state.clear()
            await message.answer(
                "❌ Ожидание консультанта отменено. Чем еще могу помочь?"
            )
        else:
            await message.answer(f"❌ {msg}")
    elif user_status == UserStatus.WITH_OPERATOR:
        success = await operator_handler.end_session(
            user_id, bot, "завершена пользователем"
        )
        if success:
            await state.clear()
            await message.answer(
                "❌ Сессия с консультантом завершена. Чем еще могу помочь?"
            )
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
        success = await operator_handler.end_session(
            user_id, bot, "завершена консультантом"
        )
        if success:
            await message.answer("✅ Сессия завершена")
        else:
            await message.answer("❌ Ошибка завершения сессии")
    else:
        await message.answer("❌ У вас нет активных сессий")


# Удален дублирующийся обработчик /start — логика объединена выше


@dp.message(Command("operators"))
async def cmd_operators_list(message: Message):
    """Список операторов (для администраторов)"""
    operators_list = "👨‍💼 Список операторов:\n\n"

    for op_id, config in operator_handler.operator_manager.operators_config.items():
        status_emoji = "🟢" if config["is_active"] else "��"
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

    # Новые команды и утилиты для операторов будут ниже


def _build_queue_page_text_and_kb(page: int, page_size: int = 5):
    """Сформировать текст и инлайн-клавиатуру страницы очереди"""
    total = len(operator_handler.waiting_queue)
    items = list(operator_handler.waiting_queue.items())
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, pages))
    start = (page - 1) * page_size
    end = start + page_size
    slice_items = items[start:end]

    header = (
        f"📋 Очередь запросов (стр. {page}/{pages})\n"
        f"⏳ В ожидании: {total} | 💬 Активных: {len(operator_handler.active_sessions)} | 👨‍💼 Онлайн: {len(operator_handler.operator_manager.get_active_operators())}\n\n"
    )
    body = ""
    for idx, (uid, info) in enumerate(slice_items, start=start + 1):
        uname = f"@{info.get('username')}" if info.get("username") else "—"
        req_time = info.get("request_time")
        tstr = req_time.strftime("%H:%M") if hasattr(req_time, "strftime") else "—"
        body += (
            f"{idx}. {info.get('first_name', 'Пользователь')} ({uname})\n"
            f"   ⏰ {tstr}  •  ID: {uid}\n"
        )
    text = header + (body or "Пока пусто")

    # Клавиатура: для каждого элемента - кнопка Принять, затем навигация
    rows = []
    for uid, _ in slice_items:
        rows.append(
            [
                InlineKeyboardButton(
                    text="✅ Принять", callback_data=f"accept_request_{uid}"
                )
            ]
        )
    # Навигация
    nav_row = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"queue_page_{page - 1}")
        )
    if page < pages:
        nav_row.append(
            InlineKeyboardButton(text="▶️ Далее", callback_data=f"queue_page_{page + 1}")
        )
    if nav_row:
        rows.append(nav_row)
    rows.append(
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="queue_status")]
    )
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    return text, kb


@dp.message(Command("queue"))
async def cmd_queue(message: Message):
    """Показать очередь запросов (для операторов)"""
    if not operator_handler.operator_manager.is_operator(message.from_user.id):
        await message.answer("❌ Доступно только операторам")
        return
    text, kb = _build_queue_page_text_and_kb(page=1)
    await message.answer(text, reply_markup=kb)


@dp.callback_query(F.data == "request_consultant")
async def handle_request_consultant(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Связаться с консультантом' — тот же функционал, что и /help"""
    try:
        user = callback.from_user
        chat_id = callback.message.chat.id if callback.message else user.id
        # Эскалируем с явными атрибутами пользователя, чтобы не подставлялись данные бота
        success = await operator_handler.escalate_to_operator(
            user.id,
            callback.message,
            auto_escalation=False,
            bot=bot,
            first_name=user.first_name or "",
            username=user.username or "",
            chat_id=chat_id,
            origin_message_id=None,
            original_message_override="Запрос консультации",
        )
        if success:
            await state.set_state(OperatorState.WAITING_OPERATOR)
            queue_info = operator_handler.get_queue_info()
            position = len(
                [u for u in queue_info["queue_details"] if u["user_id"] == user.id]
            )
            await callback.message.answer(
                "📞 Ваш запрос передан консультанту.\n"
                "Пожалуйста, ожидайте подключения.\n\n"
                f"📋 Ваша позиция в очереди: {position}\n"
                "⏰ Среднее время ожидания: 3-5 минут\n\n"
                "Вы можете отменить ожидание командой /cancel"
            )
        else:
            await callback.message.answer(
                "❌ Не удалось подключиться к системе операторов. Попробуйте позже."
            )
    finally:
        try:
            await callback.answer()
        except Exception:
            pass


@dp.callback_query(F.data.startswith("queue_page_"))
async def handle_queue_page_callback(callback: CallbackQuery):
    if not operator_handler.operator_manager.is_operator(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    try:
        page = int(callback.data.split("_")[2])
    except Exception:
        page = 1
    text, kb = _build_queue_page_text_and_kb(page=page)
    await callback.message.edit_text(text)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@dp.message(Command("consultants_stats"))
async def cmd_consultants_stats(message: Message):
    """Агрегированная статистика по консультантам (для операторов/админов)"""
    if not operator_handler.operator_manager.is_operator(message.from_user.id):
        await message.answer("❌ Доступно только операторам")
        return
    stats = operator_handler.get_consultants_stats()
    hist = stats["rating_histogram"]
    lines = [
        "📊 Общая статистика консультантов:\n",
        f"⭐ Средний рейтинг: {stats['overall_avg_rating']}\n",
        f"📈 Оцененных сессий: {stats['rated_sessions']} / Отчетных сессий: {stats['total_sessions_reported']}\n",
        f"💬 Активных сессий: {stats['active_sessions']} | ⏳ В ожидании: {stats['waiting']}\n",
        "\nРаспределение оценок:",
        f"1⭐: {hist.get(1, 0)}  |  2⭐: {hist.get(2, 0)}  |  3⭐: {hist.get(3, 0)}  |  4⭐: {hist.get(4, 0)}  |  5⭐: {hist.get(5, 0)}",
        "\nТоп консультантов:",
    ]
    # Сортируем консультантов по рейтингу и количеству сессий
    ops = sorted(
        stats["operators"],
        key=lambda x: (x.get("rating", 0), x.get("total_sessions", 0)),
        reverse=True,
    )
    for op in ops:
        lines.append(
            f"• {op['name']} — ⭐ {op['rating']}/5 ({op['total_sessions']} сесс.), {'🟢' if op['is_active'] else '⚪️'}"
        )
    await message.answer("\n".join(lines))


# Обработчики сообщений от операторов (ДОЛЖНЫ БЫТЬ ВЫШЕ ОСНОВНЫХ ОБРАБОТЧИКОВ!)
@dp.message(
    F.text
    & F.from_user.id.in_(
        list(operator_handler.operator_manager.operators_config.keys())
    )
)
async def handle_operator_message(message: Message):
    """Обработка текстовых сообщений от операторов - ПРИОРИТЕТНЫЙ ОБРАБОТЧИК"""
    operator_id = message.from_user.id

    logger.info(f"📨 Получено сообщение от оператора {operator_id}: '{message.text}'")

    # Проверяем специальные команды оператора
    if message.text.startswith("/"):
        logger.info(f"🔧 Команда оператора: {message.text}")
        return  # Команды обрабатываются другими обработчиками

    # Пересылаем обычные сообщения пользователю
    success, msg = await operator_handler.forward_operator_message(
        operator_id, message.text, bot
    )
    if not success:
        await message.answer(f"❌ {msg}")
    else:
        logger.info(f"✅ Сообщение оператора {operator_id} переслано пользователю")


# Обработчики медиа сообщений от операторов
@dp.message(
    (F.photo | F.document | F.voice | F.video | F.audio | F.sticker)
    & F.from_user.id.in_(
        list(operator_handler.operator_manager.operators_config.keys())
    )
)
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

    # Пересылаем медиа пользователю
    success = await operator_handler.forward_operator_media(operator_id, message, bot)
    if not success:
        await message.answer("❌ Ошибка пересылки медиа пользователю")
    else:
        logger.info(
            f"✅ {media_type.capitalize()} от оператора {operator_id} переслано пользователю"
        )


# Регистрируем обработчики квиза ПЕРЕД основным обработчиком текста
if QUIZ_AVAILABLE:
    try:
        register_quiz_handlers(dp, bot)
        logger.info("✅ Обработчики квиза зарегистрированы ПЕРЕД основным обработчиком")
    except Exception as e:
        logger.error(f"❌ Ошибка регистрации квиза: {e}")

# Регистрируем обработчики брейншторма ПЕРЕД основным обработчиком текста
if BRAINSTORM_AVAILABLE:
    try:
        register_brainstorm_handlers(dp, bot)
        register_brainstorm_menu_handler(dp)
        logger.info(
            "✅ Обработчики брейншторма зарегистрированы ПЕРЕД основным обработчиком"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка регистрации брейншторма: {e}")


# Обработчик текстовых сообщений от пользователей
@dp.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    user_id = message.from_user.id
    current_state = await state.get_state()

    # Исключаем операторов из этого обработчика (они обрабатываются выше)
    if operator_handler.operator_manager.is_operator(user_id):
        logger.warning(
            f"⚠️ ВНИМАНИЕ: Сообщение оператора {user_id} попало в обработчик пользователей!"
        )
        return

    # Исключаем команду /quiz и состояния квиза - они обрабатываются в quiz_mod.py
    if QUIZ_AVAILABLE and (
        message.text == "/quiz"
        or (current_state and current_state.startswith("QuizState"))
    ):
        if message.text == "/quiz":
            logger.info(
                f"🎯 Команда /quiz от пользователя {user_id} - передаём в квиз-модуль"
            )
        else:
            logger.info(
                f"🎯 Сообщение в состоянии квиза {current_state} - пропускаем основной обработчик"
            )
        return

    # Исключаем команду /brainstorm и состояния брейншторма - они обрабатываются в brainstorm_mod.py
    if BRAINSTORM_AVAILABLE and (
        message.text == "/brainstorm"
        or (current_state and current_state.startswith("BrainstormState"))
    ):
        if message.text == "/brainstorm":
            logger.info(
                f"🧠 Команда /brainstorm от пользователя {user_id} - передаём в брейншторм-модуль"
            )
        else:
            logger.info(
                f"🧠 Сообщение в состоянии брейншторма {current_state} - пропускаем основной обработчик"
            )
        return

    logger.info(f"📝 Получено сообщение от пользователя {user_id}: '{message.text}'")

    # Проверяем статус пользователя
    user_status = operator_handler.get_user_status(user_id)
    logger.info(f"👤 Статус пользователя {user_id}: {user_status.value}")

    # Пользователь ожидает консультанта
    if user_status == UserStatus.WAITING_OPERATOR:
        logger.info(
            f"⏳ Пользователь {user_id} ожидает консультанта - добавляем сообщение в историю"
        )
        # Добавляем сообщение в историю для консультанта
        operator_handler.add_user_message_to_history(user_id, message.text)
        await message.answer(
            "⏳ Ваш запрос уже передан консультанту. Пожалуйста, ожидайте подключения."
        )
        return

    # Пользователь подключен к консультанту
    if user_status == UserStatus.WITH_OPERATOR:
        logger.info(
            f"💬 Пользователь {user_id} общается с консультантом - пересылаем сообщение"
        )
        # Пересылаем сообщение консультанту
        success = await operator_handler.forward_user_message(user_id, message, bot)
        if not success:
            await message.answer("❌ Ошибка пересылки сообщения консультанту")
        return

    # Пользователь оценивает работу консультанта
    if user_status == UserStatus.RATING_OPERATOR:
        logger.info(f"⭐ Пользователь {user_id} должен оценить работу консультанта")
        await message.answer(
            "⭐ Пожалуйста, сначала оцените работу консультанта, используя кнопки выше."
        )
        return

    # Пользователь в режиме поиска списков
    if current_state == UserState.SEARCHING_LISTS:
        logger.info(f"🔍 Пользователь {user_id} ищет в списках: '{message.text}'")
        await handle_lists_search(message, state)
        return

    # Обычная обработка сообщения с использованием RAG
    logger.info(
        f"🤖 Пользователь {user_id} (@{message.from_user.username}) спрашивает: '{message.text[:50]}{'...' if len(message.text) > 50 else ''}'"
    )
    try:
        logger.info("🔍 Начинаем поиск в базе знаний...")
        # Запомним последнее пользовательское сообщение для возможной быстрой эскалации
        try:
            operator_handler.remember_user_message(message)
        except Exception:
            pass

        # Получаем контекст из RAG системы
        context = await get_enhanced_context(message.text)
        logger.info(
            f"Получен контекст: {context[:200]}..."
            if len(context) > 200
            else f"Получен контекст: {context}"
        )

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
            {"role": "user", "content": user_message},
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
            async for chunk in deepseek.get_streaming_completion(
                messages, temperature=0.3
            ):
                if chunk:
                    response_text += chunk
                    current_time = time.time()

                    # Обновляем сообщение каждые N символов И если прошло минимум 2 секунды
                    if (
                        len(response_text) - last_update >= update_interval
                        and current_time - last_typing_time >= 2.0
                    ):
                        try:
                            # Добавляем индикатор печатания в конце
                            display_text = response_text + " ▌"
                            try:
                                await bot.edit_message_text(
                                    display_text,
                                    chat_id=sent_message.chat.id,
                                    message_id=sent_message.message_id,
                                    parse_mode="Markdown",
                                )
                            except Exception:
                                # Если ошибка markdown, пробуем без форматирования
                                await bot.edit_message_text(
                                    display_text,
                                    chat_id=sent_message.chat.id,
                                    message_id=sent_message.message_id,
                                )
                            last_update = len(response_text)
                            last_typing_time = current_time

                            # Добавляем задержку между обновлениями
                            await asyncio.sleep(1.0)

                        except Exception:
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
                            parse_mode="Markdown",
                        )
                    except Exception:
                        # Если ошибка markdown, пробуем без форматирования
                        await bot.edit_message_text(
                            response_text,
                            chat_id=sent_message.chat.id,
                            message_id=sent_message.message_id,
                        )
                    logger.info(
                        f"✅ Стриминговый ответ завершен: {len(response_text)} символов для пользователя {user_id}"
                    )
                    # Если ответ содержит предложение обратиться к оператору — покажем кнопку для быстрого вызова
                    try:
                        lower_text = response_text.lower()
                        if ("/help" in lower_text) or (
                            "обратит" in lower_text and "оператор" in lower_text
                        ):
                            from aiogram.types import (
                                InlineKeyboardButton,
                                InlineKeyboardMarkup,
                            )

                            help_kb = InlineKeyboardMarkup(
                                inline_keyboard=[
                                    [
                                        InlineKeyboardButton(
                                            text="Связаться с консультантом",
                                            callback_data="escalate_from_last",
                                        )
                                    ]
                                ]
                            )
                            await message.answer(
                                "Нужна помощь консультанта? Нажмите кнопку:",
                                reply_markup=help_kb,
                            )
                    except Exception as kb_error:
                        logger.debug(
                            f"Не удалось показать кнопку эскалации: {kb_error}"
                        )
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
                    message_id=sent_message.message_id,
                )

        except Exception as streaming_error:
            logger.error(f"Ошибка стриминга: {streaming_error}")
            await bot.edit_message_text(
                "😔 Извините, произошла ошибка при обработке вашего запроса.\n"
                "Попробуйте переформулировать вопрос или обратитесь к оператору: /help",
                chat_id=sent_message.chat.id,
                message_id=sent_message.message_id,
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
    logger.info(
        f"📎 Получено {media_type} от пользователя {user_id}, статус: {user_status.value}"
    )

    # Пользователь ожидает консультанта
    if user_status == UserStatus.WAITING_OPERATOR:
        await message.answer(
            "⏳ Ваш запрос уже передан консультанту. Пожалуйста, ожидайте подключения."
        )
        return

    # Пользователь подключен к консультанту
    if user_status == UserStatus.WITH_OPERATOR:
        logger.info(
            f"💬 Пересылаем {media_type} от пользователя {user_id} консультанту"
        )
        success = await operator_handler.forward_user_message(user_id, message, bot)
        if not success:
            await message.answer("❌ Ошибка пересылки медиа консультанту")
        return

    # Пользователь оценивает работу консультанта
    if user_status == UserStatus.RATING_OPERATOR:
        await message.answer(
            "⭐ Пожалуйста, сначала оцените работу консультанта, используя кнопки выше."
        )
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
        "адрес",
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
        "где находится технопарк",
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
    response_text += "\n📊 Статус базы знаний:\n"
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

        # Статистика современной RAG системы (приоритет)
        if MODERN_RAG_AVAILABLE:
            try:
                stats = modern_rag.get_stats()
                response_text += f"""📚 **Современная RAG (ChromaDB + векторы) - АКТИВНАЯ**
• Документов в базе: {stats.get("total_documents", 0)}
• Коллекций: {stats.get("collections_count", 1)}
• Модель эмбеддингов: {stats.get("model_name", "неизвестна")}
• Последнее индексирование: {stats.get("last_indexed", "неизвестно")}
• Размер БД: {stats.get("db_size", "неизвестно")}

"""
            except Exception as e:
                response_text += (
                    f"📚 **Современная RAG - АКТИВНАЯ** (ошибка статистики: {e})\n\n"
                )

        # Статистика оптимизированной RAG системы (резерв)
        if OPTIMIZED_RAG_AVAILABLE:
            stats = optimized_rag.get_stats()
            response_text += f"""🚀 **Оптимизированная RAG - РЕЗЕРВ**
• Общих запросов: {stats.get("total_queries", 0)}
• Попаданий в кэш: {stats.get("cache_hits", 0)}
• Cache Hit Rate: {stats.get("cache_hit_rate", "0%")}
• Сэкономлено токенов: {stats.get("tokens_saved", 0)}
• Сэкономлено времени: {stats.get("processing_time_saved", 0):.2f}с
• Размер точного кэша: {stats.get("exact_cache_size", 0)}
• Семантических групп: {stats.get("semantic_cache_groups", 0)}
• Популярных запросов: {stats.get("popular_cache_size", 0)}
• Топ паттерны: {", ".join(list(stats.get("top_patterns", {}).keys())[:3])}

"""

        # Базовая RAG статистика
        response_text += f"""📖 **Базовая RAG (ключевые слова) - FALLBACK**
• Разделов в БЗ: {len(rag_system.knowledge_base)}
• Файл БЗ: knowledge_base.json
• Основные разделы: {", ".join(list(rag_system.knowledge_base.keys())[:3])}

"""

        # Общая информация о системе
        response_text += f"""⚙️ **КОНФИГУРАЦИЯ СИСТЕМЫ:**
• Современная RAG: {"✅" if MODERN_RAG_AVAILABLE else "❌"}
• Оптимизированная RAG: {"✅" if OPTIMIZED_RAG_AVAILABLE else "❌"}
• Календарь: {"✅" if CALENDAR_AVAILABLE else "❌"}  
• Документы: {"✅" if DOCUMENTS_PARSER_AVAILABLE else "❌"}
• Уведомления: {"✅" if NOTIFICATIONS_AVAILABLE else "❌"}

💡 **Приоритет использования:** Современная → Оптимизированная → Базовая"""

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
        "3D принтеры в лабораториях",
    ]

    response_text = "🧪 **Тест современной RAG системы:**\n\n"

    for query in test_queries:
        logger.info(f"🔍 Тестируем запрос: {query}")
        try:
            search_results = modern_rag.search(query, max_results=2, min_score=0.05)

            if search_results:
                best_result = search_results[0]
                similarity = best_result["similarity"]
                title = best_result["title"]
                response_text += f"✅ **{query}**\n"
                response_text += f"   └ {title} ({similarity:.1%})\n\n"
            else:
                response_text += f"❌ **{query}** - не найдено\n\n"

        except Exception as e:
            response_text += f"⚠️ **{query}** - ошибка: {str(e)[:50]}\n\n"

    await message.answer(response_text)


@dp.message(Command("test_optimized_rag"))
async def cmd_test_optimized_rag(message: Message):
    """Команда для тестирования оптимизированной RAG системы"""
    if not OPTIMIZED_RAG_AVAILABLE:
        await message.answer("❌ Оптимизированная RAG система недоступна")
        return

    test_queries = [
        "привет",  # Приветствие
        "адрес технопарка",  # Местоположение
        "телефон",  # Контакты
        "список направлений",  # Направления
        "как поступить",  # Поступление
        "цена обучения",  # Стоимость
        "расписание смен",  # Расписание
        "общая информация о технопарке",  # Общая информация
    ]

    response_text = "🚀 **Тест оптимизированной RAG системы:**\n\n"

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
                response_text += (
                    f"   └ Токенов: {tokens} | Время: {processing_time:.3f}с\n"
                )
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
        "когда начинается смена",
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
    status_text += "📊 **Общая статистика:**\n"
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
            await message.answer(
                f"✅ Информация о документах успешно обновлена!\n\n{documents_info}"
            )
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
        "что взять с собой",
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


@dp.message(Command("test_shorten"))
async def cmd_test_shorten(message: Message):
    """Команда для тестирования сокращения названий документов"""
    if not LISTS_PARSER_AVAILABLE:
        await message.answer("❌ Парсер списков недоступен")
        return

    # Примеры длинных названий из реальных документов
    test_names = [
        "Списочный состав участников, допущенных ко второму этапу отбора учащихся для обучения в Национальном детском технопарке с 06.09.2025г. по 26.09.2025г.",
        "Списочный состав группы учащихся, зачисленных в УО Национальный детский технопарк с 03.04.2025г. по 26.04.2025г.",
        "Списочный состав участников, допущенных ко второму этапу отбора учащихся для обучения в Национальном детском технопарке с 05.06.2025г. по 28.06.2025г.",
        "Список итогового состава участников майской смены",
        "Предварительный список участников группы А для обучения",
        "Финальный список зачисленных учащихся",
    ]

    response_text = "🧪 Тест сокращения названий:\n\n"

    for i, original in enumerate(test_names, 1):
        shortened = shorten_document_name(original)
        response_text += f"{i}. \n"
        response_text += (
            f"📄 Было: {original[:60]}{'...' if len(original) > 60 else ''}\n"
        )
        response_text += f"✂️ Стало: {shortened}\n\n"

    await message.answer(response_text)


@dp.message(Command("lists_stats"))
async def cmd_lists_stats(message: Message):
    """Команда для показа статистики парсера списков"""
    if not LISTS_PARSER_AVAILABLE:
        await message.answer("❌ Парсер списков недоступен")
        return

    try:
        stats = get_lists_stats()

        response_text = "📊 Статистика парсера списков:\n\n"
        response_text += f"📋 Смен в базе: {stats.get('total_shifts', 0)}\n"
        response_text += f"📄 Документов загружено: {stats.get('total_documents', 0)}\n"
        response_text += f"📚 Списков участников: {stats.get('student_lists', 0)}\n"
        response_text += (
            f"🔍 OCR доступен: {'✅' if stats.get('ocr_available', False) else '❌'}\n"
        )

        if stats.get("last_update"):
            response_text += f"📅 Последнее обновление: {stats['last_update']}\n"

        response_text += "\n💡 Команды:\n"
        response_text += "• /test_shorten - тест сокращения названий\n"
        response_text += "• /test_lists_search - тест логики поиска\n"
        response_text += "• Используйте кнопку '📋 Проверить списки' в меню"

        await message.answer(response_text)

    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики списков: {e}")
        await message.answer("❌ Ошибка получения статистики")


@dp.message(Command("test_lists_search"))
async def cmd_test_lists_search(message: Message):
    """Команда для тестирования новой логики поиска в списках"""
    if not LISTS_PARSER_AVAILABLE:
        await message.answer("❌ Парсер списков недоступен")
        return

    try:
        # Создаем тестовый текст для проверки логики
        test_text = """
        Иванов Петр Сергеевич
        Петрова Анна Михайловна
        Сидоров Алексей
        Козлов Игорь Петрович
        Петр Николаевич Степанов
        Елена Иванова
        """

        # Импортируем парсер для прямого тестирования
        from lists_parser import ListsParser

        parser = ListsParser()

        # Тестовые запросы
        test_queries = [
            "Иванов Петр",  # Должен найти "Иванов Петр Сергеевич"
            "Петр Иванов",  # Должен найти "Иванов Петр Сергеевич" (обратный порядок)
            "Анна Петрова",  # Должен найти "Петрова Анна Михайловна" (обратный порядок)
            "Петрова Анна",  # Должен найти "Петрова Анна Михайловна"
            "Иванов",  # Должен найти "Иванов Петр Сергеевич" и "Елена Иванова"
            "Петр",  # Должен найти "Иванов Петр Сергеевич" и "Петр Николаевич Степанов"
            "Сидоров Анна",  # НЕ должен найти (нет такой комбинации)
            "Козлов Петр",  # НЕ должен найти (нет такой комбинации)
        ]

        response_text = "🧪 Тест новой логики поиска:\n\n"
        response_text += "📝 Тестовый текст содержит:\n"
        response_text += "• Иванов Петр Сергеевич\n"
        response_text += "• Петрова Анна Михайловна\n"
        response_text += "• Сидоров Алексей\n"
        response_text += "• Козлов Игорь Петрович\n"
        response_text += "• Петр Николаевич Степанов\n"
        response_text += "• Елена Иванова\n\n"

        response_text += "🔍 Результаты поиска:\n\n"

        for query in test_queries:
            query_lower = query.lower()
            query_parts = query_lower.split()

            found, match_info = parser._search_in_text(
                query_lower, query_parts, test_text.lower()
            )

            if found:
                response_text += f"✅ '{query}' → {match_info}\n"
            else:
                response_text += f"❌ '{query}' → не найдено\n"

        response_text += "\n💡 Теперь поиск 'Иванов Петр' НЕ найдет документы, где есть только 'Иванов' или только 'Петр' по отдельности!"

        await message.answer(response_text)

    except Exception as e:
        logger.error(f"❌ Ошибка тестирования логики поиска: {e}")
        await message.answer("❌ Ошибка тестирования")


@dp.message(Command("test_date_parser"))
async def cmd_test_date_parser(message: Message):
    """Команда для тестирования улучшенного парсера дат"""
    test_dates = [
        "13 января 2025 г. в 13:34",
        "5 февраля 2025",
        "март 2025",
        "Августовская смена 2025",
        "10 мая",
        "25 декабря 2024 года",
        "1 июня 2025г.",
        "15 сентября",
        "неправильная дата",
        "01.02.2025",
        "завтра",
        "через 3 дня",
    ]

    response_text = "🧪 **Тест улучшенного парсера дат:**\n\n"
    response_text += "📅 Тестируем `dateparser` + fallback regex:\n\n"

    for date_str in test_dates:
        try:
            parsed_date = parse_russian_date(date_str)
            if parsed_date:
                formatted = parsed_date.strftime("%d.%m.%Y %H:%M")
                response_text += f"✅ '{date_str}' → {formatted}\n"
            else:
                response_text += f"❌ '{date_str}' → не распознано\n"
        except Exception as e:
            response_text += f"⚠️ '{date_str}' → ошибка: {str(e)[:30]}\n"

    response_text += "\n🔧 **Возможности:**\n"
    response_text += "• Распознавание склонений (январь/января)\n"
    response_text += "• Поддержка 'г.' и 'года'\n"
    response_text += "• Относительные даты (завтра, через N дней)\n"
    response_text += "• Fallback на regex при сбое dateparser\n"
    response_text += "• Автоматическое определение текущего года\n"

    await message.answer(response_text)


@dp.message(Command("test_limits"))
async def cmd_test_limits(message: Message):
    """Команда для тестирования лимитов API"""
    user_id = message.from_user.id

    response_text = "🛡️ **Статус защиты от перегрузки:**\n\n"

    # Проверяем Redis
    if REDIS_AVAILABLE and redis is not None:
        try:
            # Создаем временное соединение для тестирования
            test_redis = redis.from_url("redis://localhost", decode_responses=True)
            key = f"user:{user_id}:quota"
            used = await test_redis.get(key) or 0
            ttl = await test_redis.ttl(key)
            await test_redis.aclose()  # Правильное закрытие для redis.asyncio
            response_text += "🔴 **Redis:** подключен\n"
            response_text += f"📊 **Использовано:** {used}/50 запросов\n"
            response_text += f"⏱️ **Сброс через:** {ttl}с\n\n"
        except Exception as e:
            response_text += f"🔴 **Redis:** ошибка ({str(e)[:50]})\n\n"
    else:
        response_text += "🔴 **Redis:** недоступен (локальный кэш)\n\n"

    # Проверяем семафор LLM
    response_text += f"⚡ **LLM семафор:** {LLM_CONCURRENCY - llm_semaphore._value}/{LLM_CONCURRENCY} занято\n\n"

    # Проверяем middleware
    middleware_info = (
        "✅ активен"
        if any(
            isinstance(m, HourlyLimitMiddleware)
            for m in dp.message.middleware.middlewares
        )
        else "❌ не найден"
    )
    response_text += f"🛡️ **Middleware:** {middleware_info}\n\n"

    # Статистика защиты
    response_text += "🔧 **Настройки защиты:**\n"
    response_text += "• Лимит запросов: 50/час\n"
    response_text += f"• Одновременных LLM: {LLM_CONCURRENCY}\n"
    response_text += "• Retry попытки: 5 (exponential backoff)\n"
    response_text += "• Обработка HTTP 429: автоматическая\n\n"

    response_text += "💡 **Попробуйте:**\n"
    response_text += "• Отправить много запросов подряд\n"
    response_text += "• Проверить автоматические ограничения\n"

    await message.answer(response_text)


@dp.message(Command("rag_status"))
async def cmd_rag_status(message: Message):
    """Команда для проверки статуса RAG систем"""
    response_text = "🧠 **Статус RAG систем:**\n\n"

    # Базовая RAG система
    response_text += f"📖 **Базовая RAG:** {'✅ готова' if rag_system.knowledge_base else '❌ не готова'}\n"

    # Оптимизированная RAG система
    if OPTIMIZED_RAG_AVAILABLE and rag_systems_ready["optimized"]:
        stats = optimized_rag.get_stats()
        response_text += f"🚀 **Оптимизированная RAG:** ✅ готова ({stats.get('cache_hit_rate', '0%')} cache hit)\n"
    else:
        response_text += f"🚀 **Оптимизированная RAG:** {'🔄 загружается' if not rag_systems_ready['optimized'] else '❌ недоступна'}\n"

    # Современная RAG система
    if MODERN_RAG_AVAILABLE and rag_systems_ready["modern"]:
        stats = modern_rag.get_stats()
        response_text += f"📚 **Современная RAG:** ✅ готова ({stats.get('total_documents', 0)} документов)\n"
    else:
        response_text += f"📚 **Современная RAG:** {'🔄 загружается' if not rag_systems_ready['modern'] else '❌ недоступна'}\n"

    response_text += "\n📊 **Готовность RAG систем:**\n"
    response_text += f"• Базовая: {'✅' if rag_system.knowledge_base else '❌'}\n"
    response_text += (
        f"• Оптимизированная: {'✅' if rag_systems_ready['optimized'] else '🔄'}\n"
    )
    response_text += f"• Современная: {'✅' if rag_systems_ready['modern'] else '🔄'}\n"

    response_text += "\n💡 **Приоритет использования:**\n"
    response_text += "1. Современная RAG (векторный поиск)\n"
    response_text += "2. Оптимизированная RAG (кэширование)\n"
    response_text += "3. Базовая RAG (ключевые слова)\n"

    await message.answer(response_text)


@dp.message(Command("brainstorm_status"))
async def cmd_brainstorm_status(message: Message):
    """Команда для проверки статуса брейншторма"""
    if BRAINSTORM_AVAILABLE:
        stats = get_brainstorm_stats()
        response_text = "🧠 **Статус модуля брейншторма:**\n\n"
        response_text += "✅ **Доступен:** Да\n"
        response_text += f"📊 **Направлений:** {stats['directions_count']}\n"
        response_text += f"🎯 **Направления:** {', '.join(stats['directions'][:5])}{'...' if len(stats['directions']) > 5 else ''}\n\n"
        response_text += "💡 **Команды:**\n"
        response_text += "• /brainstorm - запуск брейншторма\n"
        response_text += "• Используйте кнопку '🧠 Брейншторм идей' в меню\n\n"
        response_text += "🔧 **Функции:**\n"
        response_text += "• Выбор из 15 направлений обучения\n"
        response_text += "• Неограниченное количество вопросов\n"
        response_text += "• Помощь в формулировании идей проектов\n"
        response_text += "• Выход в любой момент"
    else:
        response_text = "❌ **Модуль брейншторма недоступен**\n\n"
        response_text += "Возможные причины:\n"
        response_text += "• Ошибка импорта модуля\n"
        response_text += "• Не настроен API ключ\n"
        response_text += "• Технические проблемы"

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
            success = await operator_handler.rate_operator(
                user_id, operator_id, rating, bot
            )
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
            callback.message.text + "\n\n✅ Спасибо за обращение!"
        )
    else:
        await callback.answer("Ошибка обработки оценки")


# Обработчики инлайн-кнопок для операторов
@dp.callback_query(F.data.startswith("accept_request_"))
async def handle_accept_request_callback(callback: CallbackQuery):
    """Принять запрос пользователя (через инлайн-кнопку)"""
    try:
        logger.info(
            f"🔘 Callback от оператора {callback.from_user.id}: {callback.data}"
        )

        user_id = int(callback.data.split("_")[2])
        operator_id = callback.from_user.id

        logger.info(
            f"👤 Оператор {operator_id} принимает запрос пользователя {user_id}"
        )

        # Проверяем, что пользователь является оператором
        if not operator_handler.operator_manager.is_operator(operator_id):
            logger.warning(f"❌ Пользователь {operator_id} не является оператором")
            await callback.answer("❌ У вас нет прав оператора", show_alert=True)
            return

        logger.info(
            f"🔄 Вызываем accept_request для оператора {operator_id} и пользователя {user_id}"
        )
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
                parse_mode="Markdown",
            )
            await callback.answer("✅ Запрос принят!", show_alert=False)
        else:
            logger.error(f"❌ Ошибка принятия запроса: {msg}")
            await callback.message.edit_text(
                f"❌ **Не удалось принять запрос**\n\n{msg}",
                reply_markup=None,
                parse_mode="Markdown",
            )
            await callback.answer(f"❌ {msg}", show_alert=True)

    except (ValueError, IndexError) as e:
        logger.error(f"❌ Ошибка парсинга callback data: {e}, data: {callback.data}")
        await callback.answer("❌ Некорректный ID пользователя", show_alert=True)
    except Exception as e:
        logger.error(
            f"❌ Неожиданная ошибка в accept_request_callback: {e}", exc_info=True
        )
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@dp.callback_query(F.data == "escalate_from_last")
async def handle_escalate_from_last(callback: CallbackQuery):
    """Быстрый вызов консультанта по последнему сообщению"""
    user_id = callback.from_user.id
    try:
        success = await operator_handler.escalate_from_last(user_id, bot)
        if success:
            await callback.message.answer(
                "📞 Ваш запрос передан консультанту. Пожалуйста, ожидайте подключения.\n\n"
                "Вы можете отменить ожидание командой /cancel"
            )
            await callback.answer("Запрос передан консультанту")
        else:
            await callback.answer("Сейчас нельзя вызвать консультанта", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка эскалации из кнопки: {e}")
        await callback.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)


@dp.callback_query(F.data == "rate_skip")
async def handle_rate_skip(callback: CallbackQuery):
    """Пользователь пропускает оценку"""
    user_id = callback.from_user.id
    try:
        ok = await operator_handler.skip_rating(user_id, bot)
        if ok:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            await callback.answer("Спасибо!", show_alert=False)
        else:
            await callback.answer("Оценка сейчас недоступна", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка при пропуске оценки: {e}")
        await callback.answer("Ошибка. Попробуйте позже.", show_alert=True)


@dp.callback_query(F.data.startswith("rate_"))
async def handle_rate_callback(callback: CallbackQuery):
    """Обработка оценки качества от пользователя"""
    data = callback.data
    user_id = callback.from_user.id
    try:
        if data == "rate_skip":
            # Обрабатывается отдельным хэндлером
            await callback.answer()
            return
        parts = data.split("_")
        if len(parts) != 3:
            await callback.answer("Некорректные данные оценки", show_alert=True)
            return
        _, rating_str, operator_id_str = parts
        if rating_str not in {"1", "2", "3", "4", "5"}:
            await callback.answer("Некорректная оценка", show_alert=True)
            return
        rating = int(rating_str)
        operator_id = int(operator_id_str)
        ok = await operator_handler.rate_operator(user_id, operator_id, rating, bot)
        if ok:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            await callback.answer("Спасибо за оценку!", show_alert=False)
        else:
            await callback.answer("Сейчас оценка недоступна", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка обработки оценки: {e}")
        await callback.answer("Ошибка при обработке оценки", show_alert=True)


@dp.callback_query(F.data.startswith("request_details_"))
async def handle_request_details_callback(callback: CallbackQuery):
    """Детали отключены: обработчик сохраняем для совместимости, но не используем."""
    try:
        await callback.answer("Кнопка 'Детали' больше не используется", show_alert=True)
    except Exception:
        pass


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

    if queue_info["queue_details"]:
        status_text += "📋 **Детали очереди:**\n"
        for i, user_info in enumerate(
            queue_info["queue_details"][:5], 1
        ):  # Показываем первые 5
            status_text += (
                f"{i}. {user_info['first_name']} - "
                f"{user_info['request_time'].strftime('%H:%M')}\n"
            )
        if len(queue_info["queue_details"]) > 5:
            status_text += (
                f"... и еще {len(queue_info['queue_details']) - 5} запросов\n"
            )

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
        await callback.answer(
            "❌ У вас нет активной сессии с консультантом", show_alert=True
        )
        return

    success = await operator_handler.end_session(
        user_id, bot, "завершена пользователем"
    )

    if success:
        await callback.message.edit_text(
            "❌ Консультация завершена по вашей инициативе.\n\n"
            "Спасибо за обращение! Ожидайте форму оценки качества консультации.",
            reply_markup=None,
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

        logger.info(
            f"🔚 Консультант {operator_id} завершает сессию с пользователем {user_id}"
        )

        # Проверяем, что это действительно консультант этой сессии
        if user_id in operator_handler.active_sessions:
            session = operator_handler.active_sessions[user_id]
            if session.get("operator_id") != operator_id:
                await callback.answer("❌ Это не ваша сессия", show_alert=True)
                return
        else:
            await callback.answer("❌ Сессия не найдена", show_alert=True)
            return

        success = await operator_handler.end_session(
            user_id, bot, "завершена консультантом"
        )

        if success:
            await callback.message.edit_text(
                f"🔚 Сессия с пользователем завершена.\n\n"
                f"👤 Пользователь получит форму оценки качества консультации.\n"
                f"⏰ Время завершения: {datetime.now().strftime('%H:%M:%S')}",
                reply_markup=None,
            )
            await callback.answer("✅ Сессия завершена")
            logger.info(
                f"✅ Сессия между консультантом {operator_id} и пользователем {user_id} успешно завершена"
            )
        else:
            await callback.answer("❌ Ошибка завершения сессии", show_alert=True)
            logger.error(f"❌ Ошибка завершения сессии консультантом {operator_id}")

    except (ValueError, IndexError) as e:
        logger.error(f"❌ Ошибка парсинга callback data: {e}, data: {callback.data}")
        await callback.answer("❌ Некорректные данные", show_alert=True)
    except Exception as e:
        logger.error(
            f"❌ Неожиданная ошибка в operator_end_session_callback: {e}", exc_info=True
        )
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# Обработчики для инлайн кнопок главного меню
@dp.callback_query(F.data == "info_about")
async def handle_info_about(callback: CallbackQuery):
    """Информация о технопарке"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
        ]
    )

    info_text = (
        "🎯 **Национальный детский технопарк (НДТ)**\n"
        "— учреждение дополнительного образования для одаренных учащихся 9–11 классов, созданное с целью развития интереса к науке, технике и инновациям.\n\n"
        "🚀 **Наша миссия:**\n"
        "Отслеживать образовательные тренды, определять приоритеты и помогать талантливым школьникам реализовать свой научно-технический потенциал, вдохновлять на открытия.\n\n"
        "📚 **Что такое образовательная смена?**\n"
        "Это бесплатное обучение в течение 24 дней, включающее обучение по выбранному направлению, школьные уроки и насыщенную внеучебную программу: экскурсии, занятия в бассейне, хореография и друго\n\n"
        "🔄 **Продолжение после смены:**\n"
        "Успешные участники могут продолжить проект дистанционно и получить рекомендации от Наблюдательного совета — для поступления в лицеи и вузы без вступительных испытаний."
    )

    await callback.message.edit_text(
        info_text, reply_markup=keyboard, parse_mode="Markdown"
    )
    await callback.answer()


@dp.callback_query(F.data == "info_programs")
async def handle_info_programs(callback: CallbackQuery):
    """Информация о направлениях обучения"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
        ]
    )

    info_text = (
        "📖 **Образовательные направления (15 наименований):**\n"
        "Занятия длятся 72 часа (6 раз в неделю по 4 ч) в группах 7–10 человек.\n\n"
        "Список актуальных направлений (с ноября 2022 г.):\n"
        "- Авиакосмические технологии\n"
        "- Архитектура и дизайн\n"
        "- Биотехнологии\n"
        "- Виртуальная и дополненная реальность\n"
        "- Зелёная химия\n"
        "- Инженерная экология\n"
        "- Информационная безопасность\n"
        "- Информационные и компьютерные технологии\n"
        "- Лазерные технологии\n"
        "- Машины и двигатели, автомобилестроение\n"
        "- Наноиндустрия и нанотехнологии\n"
        "- Природные ресурсы\n"
        "- Робототехника\n"
        "- Электроника и связь\n"
        "- Энергетика будущего\n\n"
        "🛠 **Что происходит на смене:**\n"
        "Учащиеся осваивают теорию и защищают исследовательский проект — некоторые из них затем развиваются дальше онлайн и участвуют в конкурсах и конференциях "
    )

    await callback.message.edit_text(
        info_text, reply_markup=keyboard, parse_mode="Markdown"
    )
    await callback.answer()


@dp.callback_query(F.data == "info_admission")
async def handle_info_admission(callback: CallbackQuery):
    """Информация о поступлении"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
        ]
    )

    info_text = (
        "📥 **Как попасть в Национальный детский технопарк**\n"
        "Отбор проходит в 2 этапа: заочный (онлайн) и очный (в областных учреждениях образования).\n\n"
        "━━━━━━━━━━━━━━\n"
        "🔹 **Этап 1. Заочный (дистанционный)**\n"
        "1. Заполнить онлайн-заявку.\n"
        "2. Прикрепить исследовательский проект и/или диплом победителя или участника международных, республиканских, областных образовательных мероприятий.\n\n"
        "**Критерии оценки проекта (макс. 30 баллов):**\n"
        "- 📌 Соответствие образовательному направлению — 0–2 б.\n"
        "- 📌 Актуальность проблемы — до 6 б. (значимость идеи — 0–3, научная новизна — 0–3).\n"
        "- 📌 Теоретическая и практическая ценность — до 6 б.\n"
        "- 📌 Качество содержания — до 8 б. (выводы, оригинальность, наличие исследовательского аспекта, перспективы развития).\n"
        "- 📌 Оформление — до 8 б. (структура, титульный лист, оглавление, источники, рисунки и таблицы).\n\n"
        "⚠ Если проект не соответствует выбранному направлению, дальнейшая оценка не проводится.\n\n"
        "━━━━━━━━━━━━━━\n"
        "🔹 **Этап 2. Очный**\n"
        "Проводится в областных учреждениях образования и включает:\n"
        "1. **Тест** (по программе до 9 класса):\n"
        "   - Общая физика  \n"
        "   - Математика  \n"
        "   - Логика  \n"
        "   - Пространственное мышление  \n"
        "   - Естественные науки  \n"
        "   **Структура теста:**\n"
        "     - Блок А — 30 вопросов × 1 балл.\n"
        "     - Блок Б — 10 вопросов × 2 балла.\n"
        "   На каждую смену готовится новый тест. Достаточно хорошо учиться в школе и иметь широкий кругозор.\n\n"
        "2. **Собеседование**  \n"
        "   Цель — выявить мотивацию и понимание выбранного направления.  \n"
        "   Возможные вопросы:\n"
        "   - Проект или диплом, представленный на 1 этапе.\n"
        "   - Суть проекта и ход работы над ним.\n"
        "   - Причины выбора направления.\n\n"
        "━━━━━━━━━━━━━━\n"
        "📜 **Результат**: по итогам 2 этапов приёмная комиссия принимает решение о зачислении или отказе в участии в образовательной смене."
    )

    await callback.message.edit_text(
        info_text, reply_markup=keyboard, parse_mode="Markdown"
    )
    await callback.answer()


# Обработчики для расписания, контактов и стоимости удалены


@dp.callback_query(F.data == "request_consultant")
async def handle_request_consultant(callback: CallbackQuery, state: FSMContext):
    """Обработка запроса консультанта через инлайн кнопку"""
    user_id = callback.from_user.id

    # Используем существующую логику эскалации к оператору
    success = await operator_handler.escalate_to_operator(
        user_id, callback.message, auto_escalation=False, bot=bot
    )

    if success:
        await state.set_state(OperatorState.WAITING_OPERATOR)
        queue_info = operator_handler.get_queue_info()
        position = len(
            [u for u in queue_info["queue_details"] if u["user_id"] == user_id]
        )

        await callback.message.edit_text(
            "📞 Ваш запрос передан консультанту.\n"
            "Пожалуйста, ожидайте подключения.\n\n"
            f"📋 Ваша позиция в очереди: {position}\n"
            "⏰ Среднее время ожидания: 3-5 минут\n\n"
            "Вы можете отменить ожидание командой /cancel"
        )
        await callback.answer("✅ Запрос отправлен консультанту")
    else:
        await callback.answer(
            "❌ Не удалось подключиться к системе операторов", show_alert=True
        )


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
            InlineKeyboardButton(
                text="📚 Направления обучения", callback_data="info_programs"
            ),
        ],
        [InlineKeyboardButton(text="📝 Поступление", callback_data="info_admission")],
    ]

    # Добавляем кнопку календаря, если модуль доступен
    if CALENDAR_AVAILABLE:
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="📅 Календарь смен", callback_data="show_calendar"
                )
            ]
        )

    # Добавляем кнопку проверки списков, если модуль доступен
    if LISTS_PARSER_AVAILABLE:
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="📋 Проверить списки", callback_data="check_lists"
                )
            ]
        )

    # Добавляем кнопку квиза, если модуль доступен
    if QUIZ_AVAILABLE:
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="🎯 Квиз: подбор направления", callback_data="start_quiz"
                )
            ]
        )

    keyboard_rows.append(
        [
            InlineKeyboardButton(
                text="👨‍💼 Связаться с консультантом",
                callback_data="request_consultant",
            )
        ]
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(welcome_text, reply_markup=keyboard)
    await callback.answer()


# Обработчик для квиза
@dp.callback_query(F.data == "start_quiz")
async def handle_start_quiz(callback: CallbackQuery, state: FSMContext):
    """Запуск квиза через callback"""
    if not QUIZ_AVAILABLE:
        await callback.answer("❌ Квиз временно недоступен", show_alert=True)
        return

    try:
        await quiz_start_callback(callback, state)
        await callback.answer()
    except Exception as e:
        logger.error(f"❌ Ошибка запуска квиза: {e}")
        await callback.answer("❌ Ошибка запуска квиза", show_alert=True)


# Обработчики для проверки списков
@dp.callback_query(F.data == "check_lists")
async def handle_check_lists(callback: CallbackQuery, state: FSMContext):
    """Начало проверки списков"""
    if not LISTS_PARSER_AVAILABLE:
        await callback.answer(
            "❌ Проверка списков временно недоступна", show_alert=True
        )
        return

    try:
        await state.set_state(UserState.SEARCHING_LISTS)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Назад в меню", callback_data="back_to_menu"
                    )
                ]
            ]
        )

        await callback.message.edit_text(
            "🔍 Поиск в списках участников\n\n"
            "Напишите имя фамилия для поиска:\n\n"
            "📝 Примеры:\n"
            "• Анна Иванова\n"
            "• Максим Петров\n"
            "• Елена Сидорова\n\n"
            "💡 Правила поиска:\n"
            "• Одно слово → найдет любые записи с этим словом\n"
            "• Два слова → найдет только точные совпадения фразы\n"
            "• Поддерживается обратный порядок (Имя Фамилия ↔ Фамилия Имя)\n\n"
            "⚠️ 'Иванов Петр' НЕ найдет документы, где есть только 'Иванов' или только 'Петр'\n\n"
            "✏️ Введите данные для поиска:",
            reply_markup=keyboard,
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"❌ Ошибка при запуске поиска списков: {e}")
        await callback.answer("❌ Ошибка запуска поиска", show_alert=True)


def shorten_document_name(doc_name: str) -> str:
    """Умное сокращение названий документов"""
    if not doc_name:
        return "Документ"

    # Убираем лишние символы и пробелы
    doc_name = doc_name.strip()

    # Словарь замен для сокращения
    replacements = {
        # Основные сокращения
        "Списочный состав участников": "Список участников",
        "Списочный состав группы": "Список группы",
        "Списочный состав": "Список",
        "состав участников": "участники",
        "состав группы": "группа",
        # Этапы отбора
        "допущенных ко второму этапу отбора учащихся": "2 этап отбора",
        "допущенных к первому этапу отбора учащихся": "1 этап отбора",
        "допущенных ко второму этапу отбора": "2 этап отбора",
        "допущенных к первому этапу отбора": "1 этап отбора",
        "второму этапу отбора": "2 этап отбора",
        "первому этапу отбора": "1 этап отбора",
        "этапу отбора": "этап отбора",
        "ко второму этапу": "2 этап",
        "к первому этапу": "1 этап",
        # Обучение
        "для обучения в Национальном детском технопарке": "",
        "в Национальном детском технопарке": "",
        "Национальном детском технопарке": "технопарке",
        "учащихся для обучения": "учащихся",
        "для обучения": "",
        # Статусы
        "зачисленных в УО": "зачисленные",
        "зачисленных": "зачисленные",
        "принятых": "принятые",
        "отобранных": "отобранные",
        "допущенных": "допущенные",
        "прошедших": "прошедшие",
        "поступивших": "поступившие",
        # Группы и направления
        "группы учащихся": "группа",
        "участников группы": "группа",
        "учащихся группы": "группа",
        "группы А": "группа А",
        "группы Б": "группа Б",
        "группы В": "группа В",
        # Результаты и итоги
        "итогового списка": "итоги",
        "финального списка": "финал",
        "окончательного списка": "финал",
        "предварительного списка": "предварит.",
        "промежуточного списка": "промежут.",
    }

    # Применяем замены
    result = doc_name
    for old, new in replacements.items():
        result = result.replace(old, new)

    # Убираем даты в формате "с ДД.ММ.ГГГГ по ДД.ММ.ГГГГ"
    import re

    result = re.sub(
        r"\s*с\s+\d{2}\.\d{2}\.\d{4}г?\.\s*по\s+\d{2}\.\d{2}\.\d{4}г?\.\s*", "", result
    )
    result = re.sub(
        r"\s*\d{2}\.\d{2}\.\d{4}г?\.\s*-\s*\d{2}\.\d{2}\.\d{4}г?\.\s*", "", result
    )

    # Убираем лишние пробелы и точки
    result = re.sub(r"\s+", " ", result)
    result = result.strip(" .,")

    # Специальная логика для разных типов документов
    result_lower = result.lower()

    # Определяем тип списка по ключевым словам
    if "2 этап" in result_lower or (
        "второму этапу" in result_lower and "допущенных" in result_lower
    ):
        result = "Прошедшие 1 этап отбора"
    elif "1 этап" in result_lower or (
        "первому этапу" in result_lower and "допущенных" in result_lower
    ):
        result = "Прошедшие 1 этап отбора"
    elif "зачисленные" in result_lower or "зачисленных" in result_lower:
        result = "Зачисленные участники"
    elif "допущенные" in result_lower or "допущенных" in result_lower:
        result = "Допущенные к участию"
    elif "итоги" in result_lower or "итогового" in result_lower:
        result = "Итоговый список"
    elif "финал" in result_lower or "финального" in result_lower:
        result = "Финальный список"
    elif "группа а" in result_lower:
        result = "Группа А"
    elif "группа б" in result_lower:
        result = "Группа Б"
    elif "группа в" in result_lower:
        result = "Группа В"
    elif "группа" in result_lower:
        result = "Участники группы"
    elif "участников" in result_lower:
        result = "Список участников"
    elif "список" in result_lower:
        result = "Общий список"

    # Ограничиваем длину
    if len(result) > 45:
        # Разбиваем по словам и берем важные
        words = result.split()
        if len(words) > 3:
            result = " ".join(words[:3]) + "..."
        else:
            result = result[:42] + "..."

    return result if result else "Список участников"


async def handle_lists_search(message: Message, state: FSMContext):
    """Обработка поиска в списках участников"""
    try:
        query = message.text.strip()

        if not query:
            await message.answer(
                "❌ Пустой запрос\n\n"
                "Пожалуйста, напишите имя фамилия для поиска.\n\n"
                "📝 Пример: Анна Иванова"
            )
            return

        # Отправляем сообщение о начале поиска
        search_message = await message.answer(
            f"🔍 Поиск: {query}\n\nПроверяю списки участников..."
        )

        # Выполняем поиск
        results = await search_name_in_lists(query, search_type="student_lists")

        # Очищаем состояние
        await state.clear()

        # Формируем ответ
        if not results:
            response_text = (
                f"❌ Результат поиска: '{query}'\n\n"
                "🔍 В списках участников технопарка совпадений не найдено.\n\n"
                "💡 Рекомендации:\n"
                "• Проверьте правильность написания\n"
                "• Попробуйте ввести только имя или фамилию\n"
                "• Обратитесь к консультанту для уточнения"
            )

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔍 Поиск другого имени", callback_data="check_lists"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="👨‍💼 Связаться с консультантом",
                            callback_data="request_consultant",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔙 Главное меню", callback_data="back_to_menu"
                        )
                    ],
                ]
            )
        else:
            response_text = f"✅ Найдено: {len(results)} совпадений\n\n"
            response_text += f"👤 Поиск: {query}\n\n"

            # Группируем результаты по сменам
            shifts_data = {}
            for result in results:
                shift_name = result["shift"]
                if shift_name not in shifts_data:
                    shifts_data[shift_name] = []
                shifts_data[shift_name].append(result)

            # Сортируем смены по году (новые сверху)
            def extract_year_from_shift(shift_name):
                import re

                # Ищем год в названии смены
                year_match = re.search(r"20\d{2}", shift_name)
                if year_match:
                    return int(year_match.group())

                # Если год не найден, определяем по месяцам
                months_order = {
                    "январь": 1,
                    "февраль": 2,
                    "март": 3,
                    "апрель": 4,
                    "май": 5,
                    "июнь": 6,
                    "июль": 7,
                    "август": 8,
                    "сентябрь": 9,
                    "октябрь": 10,
                    "ноябрь": 11,
                    "декабрь": 12,
                }

                shift_lower = shift_name.lower()
                for month, order in months_order.items():
                    if month in shift_lower:
                        # Предполагаем текущий год, если не указан
                        from datetime import datetime

                        current_year = datetime.now().year
                        return (
                            current_year * 100 + order
                        )  # Комбинируем год и месяц для сортировки

                return 0  # Неизвестные смены в конец

            # Сортируем по году/месяцу (новые сверху)
            sorted_shifts = sorted(
                shifts_data.items(),
                key=lambda x: extract_year_from_shift(x[0]),
                reverse=True,
            )

            # Формируем список найденных смен
            for i, (shift_name, shift_results) in enumerate(sorted_shifts, 1):
                response_text += f"📋 {shift_name}\n"

                # Показываем сокращенные названия документов
                unique_docs = set()
                for result in shift_results:
                    doc_name = result["document"]
                    # Применяем умное сокращение названий
                    short_name = shorten_document_name(doc_name)
                    unique_docs.add(short_name)

                for doc in sorted(unique_docs):
                    response_text += f"   ✓ {doc}\n"

                response_text += "\n"

            # Добавляем пояснение
            response_text += "💡 Данные найдены в официальных списках технопарка\n"

            # Если результатов много, обрезаем
            if len(response_text) > 3500:
                response_text = (
                    response_text[:3500] + "\n\n📄 *Показаны основные результаты*"
                )

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔍 Поиск другого имени", callback_data="check_lists"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔙 Главное меню", callback_data="back_to_menu"
                        )
                    ],
                ]
            )

        # Обновляем сообщение с результатами
        await search_message.edit_text(response_text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"❌ Ошибка поиска в списках: {e}")
        await message.answer(
            "⚠️ Временная ошибка поиска\n\n"
            "Система поиска временно недоступна.\n"
            "Попробуйте позже или обратитесь к консультанту.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="👨‍💼 Связаться с консультантом",
                            callback_data="request_consultant",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔙 Главное меню", callback_data="back_to_menu"
                        )
                    ],
                ]
            ),
        )
        await state.clear()


# Обработчики для календаря смен
@dp.callback_query(F.data == "show_calendar")
async def handle_show_calendar(callback: CallbackQuery):
    """Показать календарь смен"""
    if not CALENDAR_AVAILABLE:
        await callback.answer("❌ Календарь смен временно недоступен", show_alert=True)
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
        await callback.answer(
            "❌ Система уведомлений временно недоступна", show_alert=True
        )
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
        await callback.answer(
            "❌ Система уведомлений временно недоступна", show_alert=True
        )
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
                logger.info(
                    f"👤 Пользователь {user_id} отписался от {notification_type}"
                )
            else:
                await callback.answer("❌ Ошибка отписки", show_alert=True)
        else:
            # Подписываемся
            success = notification_system.subscribe_user(user_id, notification_type)
            if success:
                await callback.answer("✅ Вы подписались на уведомления")
                logger.info(
                    f"👤 Пользователь {user_id} подписался на {notification_type}"
                )
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
    print("=" * 60)
    print("🚀 ЗАПУСК БОТА НАЦИОНАЛЬНОГО ДЕТСКОГО ТЕХНОПАРКА")
    print("=" * 60)

    logger.info("🚀 Запуск бота Национального детского технопарка...")
    logger.info("📚 Загрузка базовой базы знаний...")

    # Загружаем базовую RAG систему синхронно (быстро)
    rag_system.load_knowledge_base()
    logger.info("✅ Базовая RAG система загружена")

    # Запускаем инициализацию RAG систем в фоне
    logger.info("🔄 Запуск фоновой инициализации RAG систем...")

    # Создаем фоновые задачи для RAG систем
    rag_tasks = []

    # Запускаем оптимизированную RAG систему
    try:
        rag_tasks.append(asyncio.create_task(init_optimized_rag()))
        logger.info("🚀 Оптимизированная RAG система запущена в фоне")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска оптимизированной RAG: {e}")

    # Запускаем современную RAG систему
    try:
        rag_tasks.append(asyncio.create_task(init_modern_rag()))
        logger.info("📚 Современная RAG система запущена в фоне")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска современной RAG: {e}")

    # Функция для мониторинга готовности RAG систем
    async def monitor_rag_systems():
        while True:
            await asyncio.sleep(10)  # Проверяем каждые 10 секунд
            ready_systems = [k for k, v in rag_systems_ready.items() if v]
            if ready_systems:
                logger.info(f"✅ Готовые RAG системы: {', '.join(ready_systems)}")

            # Если все системы готовы, завершаем мониторинг
            if all(rag_systems_ready.values()):
                logger.info("🎉 Все RAG системы готовы к работе!")
                break

    # Запускаем мониторинг RAG систем
    if rag_tasks:
        asyncio.create_task(monitor_rag_systems())

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

    # Инициализируем парсер списков
    if LISTS_PARSER_AVAILABLE:
        logger.info("📋 Запуск системы парсинга списков...")
        try:
            # Инициализируем парсер списков
            success = await initialize_lists_parser()
            if success:
                logger.info("✅ Система парсинга списков активна")
            else:
                logger.warning("⚠️ Система парсинга списков не инициализирована")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации парсера списков: {e}")
    else:
        logger.warning("⚠️ Парсер списков недоступен")

    # Квиз модуль уже зарегистрирован ПЕРЕД основным обработчиком
    if QUIZ_AVAILABLE:
        logger.info("✅ Квиз модуль готов к работе")
    else:
        logger.warning("⚠️ Квиз модуль недоступен")

    # Инициализируем модуль брейншторма
    global BRAINSTORM_AVAILABLE
    if BRAINSTORM_AVAILABLE:
        try:
            # Инициализируем LLM для брейншторма
            init_brainstorm_llm(DEEPSEEK_API_KEY)
            logger.info("✅ Модуль брейншторма готов к работе")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации брейншторма: {e}")
            BRAINSTORM_AVAILABLE = False
    else:
        logger.warning("⚠️ Модуль брейншторма недоступен")

    print("=" * 60)
    print("✅ БОТ ГОТОВ К РАБОТЕ!")
    print("=" * 60)

    logger.info("✅ Бот готов к работе!")
    logger.info("📡 Начинаем polling обновлений от Telegram...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
