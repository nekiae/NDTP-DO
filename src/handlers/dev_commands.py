"""
DEV ONLY - Команды для разработки и отладки
"""
import logging

from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message

from ..core.config import config
from ..services.context_service import get_rag_stats, reload_knowledge_base

logger = logging.getLogger(__name__)


# DEV ONLY - Тестирование RAG систем
async def cmd_test_rag(message: Message) -> None:
    """DEV ONLY - Команда для тестирования RAG системы"""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ Команда доступна только администраторам")
        return
        
    test_queries = [
        "робототехника",
        "программирование", 
        "поступление",
        "документы",
        "стоимость",
        "программы обучения",
        "где находится технопарк",
    ]

    response_text = "🔧 DEV ONLY - Тест RAG системы:\n\n"
    
    from ..services.context_service import _get_best_rag_context

    for query in test_queries:
        logger.info(f"DEV: Тестируем запрос: {query}")
        try:
            context = await _get_best_rag_context(query)
            
            if "не найдена в базе знаний" in context.lower():
                response_text += f"❌ '{query}' - не найдено\n"
            else:
                response_text += f"✅ '{query}' - найдено ({len(context)} символов)\n"
        except Exception as e:
            response_text += f"⚠️ '{query}' - ошибка: {str(e)[:50]}...\n"

    await message.answer(response_text)


# DEV ONLY - Тестирование поиска местоположения  
async def cmd_test_location(message: Message) -> None:
    """DEV ONLY - Команда для тестирования поиска информации о местоположении"""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ Команда доступна только администраторам")
        return
        
    test_queries = [
        "где находится технопарк",
        "адрес технопарка", 
        "местоположение",
        "как добраться",
        "адрес",
    ]

    response_text = "🗺️ DEV ONLY - Тест поиска местоположения:\n\n"
    
    from ..services.context_service import _get_best_rag_context

    for query in test_queries:
        logger.info(f"DEV: Тестируем запрос о местоположении: {query}")
        try:
            context = await _get_best_rag_context(query)

            if "не найдена в базе знаний" in context.lower():
                response_text += f"❌ '{query}' - не найдено\n"
            else:
                # Проверяем, есть ли адрес в контексте
                if "Технологическая" in context or "Москва" in context:
                    response_text += f"✅ '{query}' - адрес найден\n"
                else:
                    response_text += f"⚠️ '{query}' - найдено, но без адреса\n"
        except Exception as e:
            response_text += f"⚠️ '{query}' - ошибка: {str(e)[:50]}...\n"

    await message.answer(response_text)


# DEV ONLY - Перезагрузка базы знаний
async def cmd_reload_kb(message: Message) -> None:
    """DEV ONLY - Команда для перезагрузки базы знаний"""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ Команда доступна только администраторам")
        return
        
    try:
        success = await reload_knowledge_base()
        if success:
            await message.answer("✅ DEV ONLY - База знаний перезагружена успешно!")
        else:
            await message.answer("❌ DEV ONLY - Ошибка перезагрузки базы знаний")
    except Exception as e:
        logger.error(f"DEV: Ошибка перезагрузки базы знаний: {e}")
        await message.answer(f"❌ DEV ONLY - Ошибка перезагрузки: {e}")


# DEV ONLY - Статистика RAG систем
async def cmd_rag_stats(message: Message) -> None:
    """DEV ONLY - Показать детальную статистику всех RAG систем"""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ Команда доступна только администраторам")
        return
        
    try:
        stats = get_rag_stats()
        
        response_text = "📊 DEV ONLY - ДЕТАЛЬНАЯ СТАТИСТИКА RAG СИСТЕМ\n\n"
        
        # Статистика доступности систем
        response_text += "🔄 Доступность систем:\n"
        for system, available in stats["systems_available"].items():
            status = "✅" if available else "❌"
            ready_status = "🟢" if stats["systems_ready"].get(system, False) else "🔴"
            response_text += f"  {status} {ready_status} {system.capitalize()} RAG\n"
        
        response_text += f"\n🎯 Текущий режим: {stats['current_mode']}\n\n"
        
        # Детальная статистика современной RAG
        if "modern_stats" in stats:
            modern = stats["modern_stats"]
            if "error" not in modern:
                response_text += f"""📚 Современная RAG (ChromaDB):
• Документов: {modern.get('total_documents', 0)}
• Коллекций: {modern.get('collections_count', 1)}
• Модель: {modern.get('model_name', 'неизвестна')}
• Последнее индексирование: {modern.get('last_indexed', 'неизвестно')}
• Размер БД: {modern.get('db_size', 'неизвестно')}

"""
            else:
                response_text += f"📚 Современная RAG: Ошибка - {modern['error']}\n\n"
        
        # Детальная статистика оптимизированной RAG
        if "optimized_stats" in stats:
            optimized = stats["optimized_stats"]
            if "error" not in optimized:
                response_text += f"🚀 Оптимизированная RAG: {optimized}\n\n"
            else:
                response_text += f"🚀 Оптимизированная RAG: Ошибка - {optimized['error']}\n\n"
        
        # Детальная статистика базовой RAG
        if "basic_stats" in stats:
            basic = stats["basic_stats"]
            if "error" not in basic:
                kb_status = "✅" if basic.get("knowledge_base_loaded", False) else "❌"
                kb_size = basic.get("kb_size", 0)
                response_text += f"""📖 Базовая RAG:
• База знаний загружена: {kb_status}
• Размер базы: {kb_size:,} символов

"""
            else:
                response_text += f"📖 Базовая RAG: Ошибка - {basic['error']}\n\n"
        
        response_text += "💡 DEV INFO: Используется автоматический выбор лучшей системы"
        
        await message.answer(response_text)
        
    except Exception as e:
        logger.error(f"DEV: Ошибка получения статистики RAG: {e}")
        await message.answer(f"❌ DEV ONLY - Ошибка получения статистики: {e}")


# DEV ONLY - Тест API подключения
async def cmd_test_api(message: Message) -> None:
    """DEV ONLY - Тестирование подключения к внешним API"""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ Команда доступна только администраторам")
        return
        
    response_text = "🔌 DEV ONLY - Тест API подключений:\n\n"
    
    # Тест DeepSeek API
    try:
        from ..services.deepseek_client import deepseek_client
        
        api_working = await deepseek_client.test_connection()
        
        if api_working:
            response_text += "✅ DeepSeek API - подключение работает\n"
        else:
            response_text += "❌ DeepSeek API - ошибка подключения\n"
            
        # Статистика использования
        usage_stats = deepseek_client.get_usage_stats()
        response_text += f"   🔑 API ключ: {'✅' if usage_stats['has_api_key'] else '❌'}\n"
        response_text += f"   🌐 URL: {usage_stats['api_url']}\n"
        response_text += f"   🔄 Лимит конкурентности: {usage_stats['concurrency_limit']}\n\n"
        
    except Exception as e:
        response_text += f"❌ DeepSeek API - ошибка тестирования: {str(e)[:100]}...\n\n"
    
    await message.answer(response_text)


# DEV ONLY - Информация о конфигурации
async def cmd_config_info(message: Message) -> None:
    """DEV ONLY - Показать информацию о текущей конфигурации"""
    if not config.is_admin(message.from_user.id):
        await message.answer("❌ Команда доступна только администраторам")
        return
        
    response_text = "⚙️ DEV ONLY - Информация о конфигурации:\n\n"
    
    response_text += f"🐛 DEBUG режим: {'✅' if config.debug else '❌'}\n"
    response_text += f"📁 Корень проекта: {config.project_root}\n"
    response_text += f"📝 Уровень логирования: {config.log_level}\n\n"
    
    response_text += "🔧 Модули:\n"
    response_text += f"  📅 Календарь: {'✅' if config.enable_calendar else '❌'}\n"
    response_text += f"  🎯 Квиз: {'✅' if config.enable_quiz else '❌'}\n"
    response_text += f"  🧠 Брейншторм: {'✅' if config.enable_brainstorm else '❌'}\n"
    response_text += f"  📋 Списки: {'✅' if config.enable_lists else '❌'}\n"
    response_text += f"  📄 Документы: {'✅' if config.enable_documents else '❌'}\n\n"
    
    response_text += "⚡ Лимиты:\n"
    response_text += f"  ⏰ Запросов в час: {config.hourly_request_limit}\n"
    response_text += f"  🔄 Конкурентность LLM: {config.llm_concurrency_limit}\n\n"
    
    response_text += f"👑 Администраторов: {len(config.admin_ids)}\n"
    response_text += f"🗄️ RAG режим: {config.rag_mode}\n"
    
    await message.answer(response_text)


def register_dev_commands(dp, bot: Bot) -> None:
    """DEV ONLY - Регистрация команд для разработки"""
    if not config.debug:
        logger.info("🚫 DEV команды отключены (DEBUG=false)")
        return
        
    dp.message.register(cmd_test_rag, Command("test_rag"))
    dp.message.register(cmd_test_location, Command("test_location"))
    dp.message.register(cmd_reload_kb, Command("reload_kb"))
    dp.message.register(cmd_rag_stats, Command("rag_stats"))
    dp.message.register(cmd_test_api, Command("test_api"))
    dp.message.register(cmd_config_info, Command("config_info"))
    
    logger.info("🐛 DEV ONLY команды зарегистрированы")
