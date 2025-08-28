"""
NDTP Bot - Главная точка входа приложения
Национальный детский технопарк
"""
import asyncio
import logging
import signal
import sys
from pathlib import Path

# Добавляем src в путь для импортов
sys.path.insert(0, str(Path(__file__).parent / "src"))

from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage

from src.core.config import config
from src.core.constants import PROJECT_NAME, VERSION, AUTHOR
from src.core.middleware import (
    HourlyLimitMiddleware, 
    LoggingMiddleware, 
    AdminCheckMiddleware
)
from src.handlers.basic_commands import register_basic_commands
from src.handlers.message_handlers import register_message_handlers
from src.handlers.dev_commands import register_dev_commands
from src.services.context_service import initialize_rag_systems

logger = logging.getLogger(__name__)


class NDTPBot:
    """
    Основной класс бота Национального детского технопарка
    
    Управляет инициализацией, запуском и остановкой бота
    """
    
    def __init__(self):
        self.bot: Bot = None
        self.dp: Dispatcher = None
        self.is_running = False
        self._setup_signal_handlers()
        
    def _setup_signal_handlers(self) -> None:
        """Настройка обработчиков сигналов для graceful shutdown"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame) -> None:
        """Обработчик сигналов завершения"""
        logger.info(f"🛑 Получен сигнал {signum}, начинаем graceful shutdown...")
        self.is_running = False
        
    async def initialize(self) -> bool:
        """
        Инициализация всех компонентов бота
        
        Returns:
            True если инициализация прошла успешно
        """
        try:
            logger.info(f"🚀 Инициализация {PROJECT_NAME} v{VERSION} by {AUTHOR}")
            
            # Создание экземпляров бота и диспетчера
            self.bot = Bot(token=config.bot_token)
            storage = MemoryStorage()
            self.dp = Dispatcher(storage=storage)
            
            logger.info("✅ Бот и диспетчер инициализированы")
            
            # Настройка middleware
            await self._setup_middleware()
            
            # Регистрация обработчиков
            await self._register_handlers()
            
            # Инициализация RAG систем
            logger.info("📚 Инициализация RAG систем...")
            await initialize_rag_systems()
            
            # Инициализация модулей
            await self._initialize_modules()
            
            # Настройка команд бота
            await self._setup_bot_commands()
            
            logger.info(f"✅ {PROJECT_NAME} успешно инициализирован")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации бота: {e}", exc_info=True)
            return False
    
    async def _setup_middleware(self) -> None:
        """Настройка middleware"""
        logger.info("🛡️ Настройка middleware...")
        
        #Middleware для логирования
        self.dp.message.middleware(LoggingMiddleware())
        self.dp.callback_query.middleware(LoggingMiddleware())
        
        #Middleware для лимитов API
        #limit_middleware = HourlyLimitMiddleware()
        #self.dp.message.middleware(limit_middleware)
        #self.dp.callback_query.middleware(limit_middleware)
        
        #Middleware для проверки прав администратора
        self.dp.message.middleware(AdminCheckMiddleware())
        
        logger.info(f"✅ Middleware настроен (лимит: {config.hourly_request_limit} запросов/час)")
    
    async def _register_handlers(self) -> None:
        """Регистрация всех обработчиков"""
        logger.info("📝 Регистрация обработчиков...")
        
        # Основные команды
        register_basic_commands(self.dp, self.bot)

        # Регистрируем обработчики операторов ПЕРЕД основными
        self.register_operator_handlers()
        
        # Регистрируем модули ПЕРЕД основными обработчиками
        self.register_module_handlers()
        
        # Обработчики сообщений (должны быть последними)
        register_message_handlers(self.dp, self.bot)
        
        # DEV команды (если включены)
        #register_dev_commands(self.dp, self.bot)
        
        logger.info("✅ Все обработчики зарегистрированы")
    
    def register_operator_handlers(self) -> None:
        """Регистрация обработчиков операторов"""
        
        from src.handlers.operator_handler import register_operator_handlers
        register_operator_handlers(self.dp, self.bot)
        logger.info("✅ Обработчики операторов зарегистрированы")

    
    def register_module_handlers(self) -> None:
        """Регистрация обработчиков модулей"""
        # Квиз модуль
        if config.enable_quiz:
            try:
                from src.modules.quiz_mod import register_quiz_handlers
                register_quiz_handlers(self.dp, self.bot)
                logger.info("✅ Обработчики квиза зарегистрированы")
            except Exception as e:
                logger.error(f"⚠️ Ошибка регистрации модулей: {e}")
        
        # Брейншторм модуль
        if config.enable_brainstorm:
            try:
                from src.modules.brainstorm_mod import (
                    register_brainstorm_handlers,
                    register_brainstorm_menu_handler
                )
                register_brainstorm_handlers(self.dp, self.bot)
                register_brainstorm_menu_handler(self.dp)
                logger.info("✅ Обработчики брейншторма зарегистрированы")
            except Exception as e:
                logger.error(f"⚠️ Ошибка регистрации брейншторма: {e}")
        if config.enable_brainstorm:
            try:
                from src.modules.calendar_module import register_calendar_hadler
                register_calendar_hadler(self.dp)
                logger.info("✅ Обработчики календаря зарегистрированы")
            except Exception as e:
                logger.error(f"⚠️ Ошибка регистрации календаря: {e}")
    
    async def _initialize_modules(self) -> None:
        """Инициализация дополнительных модулей"""
        # Инициализация модуля брейншторма
        if config.enable_brainstorm:
            try:
                from src.modules.brainstorm_mod import init_brainstorm_llm
                await init_brainstorm_llm()
                logger.info("✅ Модуль брейншторма инициализирован")
            except Exception as e:
                logger.error(f"⚠️ Ошибка инициализации брейншторма: {e}")
        
        # Инициализация парсера списков
        if config.enable_lists:
            try:
                from src.services.parsers.lists_parser import initialize_lists_parser
                await initialize_lists_parser()
                logger.info("✅ Парсер списков инициализирован")
            except Exception as e:
                logger.error(f"⚠️ Ошибка инициализации парсера списков: {e}")
    
    async def _setup_bot_commands(self) -> None:
        """Настройка команд бота в меню Telegram"""
        try:
            commands = [
                types.BotCommand(command="start", description="Запустить бота"),
                types.BotCommand(command="menu", description="Главное меню"),
                types.BotCommand(command="help", description="Связаться с консультантом"),
                types.BotCommand(command="status", description="Показать статус"),
                types.BotCommand(command="cancel", description="Отменить операцию"),
            ]
            
            # Добавляем команды модулей если они доступны
            if config.enable_calendar:
                commands.append(
                    types.BotCommand(command="calendar", description="Календарь смен")
                )
            if config.enable_quiz:
                commands.append(
                    types.BotCommand(command="quiz", description="Квиз: подбор направления")
                )
            if config.enable_brainstorm:
                commands.append(
                    types.BotCommand(command="brainstorm", description="Брейншторм идей")
                )
            if config.enable_lists:
                commands.append(
                    types.BotCommand(command="checklists", description="Проверить списки")
                )
            
            await self.bot.set_my_commands(commands)
            logger.info("✅ Команды бота зарегистрированы в меню Telegram")
            
        except Exception as e:
            logger.error(f"❌ Не удалось установить команды бота: {e}")
    
    async def start_polling(self) -> None:
        """Запуск бота в режиме polling"""
        try:
            logger.info(f"🚀 Запуск {PROJECT_NAME} в режиме polling...")
            self.is_running = True
            
            # Запуск фоновых задач
            await self._start_background_tasks()
            
            # Основной цикл polling
            await self.dp.start_polling(self.bot, skip_updates=True)
            
        except Exception as e:
            logger.error(f"❌ Ошибка при работе бота: {e}", exc_info=True)
        finally:
            await self.shutdown()
    
    async def _start_background_tasks(self) -> None:
        """Запуск фоновых задач"""
        # Запуск цикла обновления расписания
        if config.enable_documents:
            try:
                from src.services.parsers.schedule_parser import schedule_updater_loop
                asyncio.create_task(schedule_updater_loop())
                logger.info("✅ Фоновое обновление расписания запущено")
            except Exception as e:
                logger.error(f"⚠️ Ошибка запуска обновления расписания: {e}")
        
        # Запуск цикла обновления документов
        if config.enable_documents:
            try:
                from src.services.parsers.documents_parser import documents_updater_loop
                asyncio.create_task(documents_updater_loop())
                logger.info("✅ Фоновое обновление документов запущено")
            except Exception as e:
                logger.error(f"⚠️ Ошибка запуска обновления документов: {e}")
    
    async def shutdown(self) -> None:
        """Graceful shutdown бота"""
        logger.info("🛑 Начинаем graceful shutdown...")
        
        try:
            if self.bot:
                await self.bot.session.close()
                logger.info("✅ Сессия бота закрыта")
            
            # Дополнительная очистка ресурсов
            await self._cleanup_resources()
            
            logger.info(f"✅ {PROJECT_NAME} успешно остановлен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке бота: {e}")
    
    async def _cleanup_resources(self) -> None:
        """Очистка ресурсов при остановке"""
        try:
            # Очистка RAG систем
            logger.info("🧹 Очистка ресурсов RAG систем...")
            
            # Дополнительная очистка может быть добавлена здесь
            
        except Exception as e:
            logger.error(f"⚠️ Ошибка очистки ресурсов: {e}")


async def main() -> None:
    """Главная функция приложения"""

    
    # Создание и инициализация бота
    bot_instance = NDTPBot()
    
    if not await bot_instance.initialize():
        logger.error("❌ Не удалось инициализировать бота")
        sys.exit(1)
    
    # Запуск бота
    try:
        await bot_instance.start_polling()
    except KeyboardInterrupt:
        logger.info("🔑 Получен KeyboardInterrupt")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 До свидания!")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка запуска: {e}")
        sys.exit(1)
