"""
Middleware для NDTP Bot
"""
import logging
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

from .config import config

logger = logging.getLogger(__name__)

# Импорты для Redis с безопасной обработкой
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


class HourlyLimitMiddleware(BaseMiddleware):
    """
    Middleware для ограничения количества запросов в час
    
    Использует Redis если доступен, иначе fallback на локальный кэш
    """
    
    def __init__(self, limit_per_hour: int = None):
        self.limit = limit_per_hour or config.hourly_request_limit
        self.fallback_cache: Dict[int, Dict[str, Any]] = {}  # Fallback для случая без Redis
        self._redis_client = None

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        """Обработка middleware"""
        
        if hasattr(event, "text") and event.text:
            if len(event.text) < 10 and event.text.startswith("/"):
                return await handler(event, data)
        if not hasattr(event, "from_user") or not event.from_user:
            
            return await handler(event, data)

        user_id = event.from_user.id

        # Используем Redis если доступен
        if REDIS_AVAILABLE and redis is not None:
            try:
                return await self._handle_with_redis(handler, event, data, user_id)
            except Exception as e:
                logger.warning(f"⚠️ Redis недоступен: {e}")
                # Fallback на локальный кэш при ошибке Redis
                self._redis_client = None

        # Fallback: простой локальный кэш
        return await self._handle_with_local_cache(handler, event, data, user_id)

    async def _handle_with_redis(
        self, 
        handler: Callable, 
        event: Message, 
        data: Dict[str, Any], 
        user_id: int
    ) -> Any:
        """Обработка с использованием Redis"""
        # Создаем соединение Redis только при необходимости
        if self._redis_client is None:
            self._redis_client = redis.from_url(
                config.redis_url, decode_responses=True
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
        
        
        return await handler(event, data)

    async def _handle_with_local_cache(
        self, 
        handler: Callable, 
        event: Message, 
        data: Dict[str, Any], 
        user_id: int
    ) -> Any:
        """Обработка с локальным кэшем"""
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


class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования всех запросов"""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        """Логирование запросов"""
        if hasattr(event, "from_user") and event.from_user:
            user_id = event.from_user.id
            username = event.from_user.username or "без username"
            fsm = data.get("state")

            if fsm is not None:
                # пример: получить текущее состояние
                state = await fsm.get_state()
                print(f"Текущее состояние: {state}")
            # Обрезаем длинные сообщения для логов
            message_text = ""
            if hasattr(event, "text") and event.text:
                message_text = event.text[:100] + ("..." if len(event.text) > 100 else "")
            
            logger.info(
                f"📨 Запрос от пользователя {user_id} (@{username}): '{message_text}'"
            )
        
        return await handler(event, data)


class AdminCheckMiddleware(BaseMiddleware):
    """Middleware для проверки административных прав"""
    
    def __init__(self, admin_only_commands: set = None):
        self.admin_only_commands = admin_only_commands or {
            "operators", "consultants_stats", "queue", 
            "update_schedule", "update_documents",
            # DEV ONLY команды
            "test_rag", "test_location", "reload_kb", "rag_stats"
        }
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        """Проверка прав доступа"""
        if (hasattr(event, "text") and event.text and 
            event.text.startswith("/") and hasattr(event, "from_user")):
            
            command = event.text[1:].split()[0]  # Убираем '/' и берем первое слово
            
            if command in self.admin_only_commands:
                user_id = event.from_user.id
                
                if not config.is_admin(user_id):
                    await event.answer(
                        "❌ У вас нет прав для выполнения этой команды.\n"
                        "Обратитесь к администратору."
                    )
                    logger.warning(
                        f"🚫 Попытка доступа к админ-команде /{command} "
                        f"от пользователя {user_id}"
                    )
                    return
        
        return await handler(event, data)
