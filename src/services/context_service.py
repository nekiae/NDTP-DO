"""
Сервис для получения контекста из различных RAG систем и парсеров
"""
import logging
from typing import Optional

from ..core.config import config
from ..core.constants import DOCUMENT_KEYWORDS, SCHEDULE_KEYWORDS
from ..utils.helpers import is_context_related_to_keywords

logger = logging.getLogger(__name__)

# Глобальная переменная для базовой RAG системы
basic_rag = None

# Флаг доступности базовой системы
BASIC_RAG_AVAILABLE = False


async def initialize_rag_systems() -> None:
    """Инициализация базовой RAG системы"""
    await _init_basic_rag()


async def _init_basic_rag() -> None:
    """Инициализация базовой RAG системы"""
    global basic_rag, BASIC_RAG_AVAILABLE
    try:
        logger.info("📖 Инициализация базовой RAG системы...")
        from ..services.rag.rag_system import rag_system
        basic_rag = rag_system
        BASIC_RAG_AVAILABLE = True
        logger.info("✅ Базовая RAG система готова")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации базовой RAG: {e}")




async def get_enhanced_context(query: str) -> str:
    """
    Получает контекст из RAG системы, обогащенный актуальной информацией
    
    Args:
        query: Поисковый запрос
        
    Returns:
        Контекст для ответа ИИ
    """
    try:
        # Получаем базовый контекст из лучшей доступной RAG системы
        base_context = await _get_best_rag_context(query)
        
        enhanced_contexts = []

        # Проверяем, связан ли запрос с расписанием/сменами
        if is_context_related_to_keywords(query, SCHEDULE_KEYWORDS):
            logger.info("📅 Запрос связан с расписанием - добавляем актуальную информацию")
            schedule_context = await _get_schedule_context(query)
            if schedule_context:
                enhanced_contexts.append(schedule_context)

        # Проверяем, связан ли запрос с документами
        if is_context_related_to_keywords(query, DOCUMENT_KEYWORDS):
            logger.info("📄 Запрос связан с документами - добавляем актуальную информацию")
            documents_context = await _get_documents_context(query)
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
        return await _get_fallback_context(query)


async def _get_best_rag_context(query: str) -> str:
    """Получить контекст из базовой RAG системы"""
    logger.info("📖 Используем базовую RAG систему")
    if basic_rag and BASIC_RAG_AVAILABLE:
        return basic_rag.get_context_for_query(query)
    else:
        return "Информация не найдена в базе знаний."


async def _get_schedule_context(query: str) -> Optional[str]:
    """Получить контекст о расписании"""
    try:
        if config.enable_documents:
            from ..services.parsers.schedule_parser import get_schedule_context_async
            return await get_schedule_context_async(query)
    except Exception as e:
        logger.error(f"❌ Ошибка получения контекста расписания: {e}")
    return None


async def _get_documents_context(query: str) -> Optional[str]:
    """Получить контекст о документах"""
    try:
        if config.enable_documents:
            from ..services.parsers.documents_parser import get_documents_context_async
            return await get_documents_context_async(query)
    except Exception as e:
        logger.error(f"❌ Ошибка получения контекста документов: {e}")
    return None


async def _get_fallback_context(query: str) -> str:
    """Fallback контекст в случае ошибок"""
    try:
        if basic_rag and BASIC_RAG_AVAILABLE:
            return basic_rag.get_context_for_query(query)
        else:
            return "Информация не найдена в базе знаний."
    except Exception:
        return "Информация временно недоступна."


def get_rag_stats() -> dict:
    """Получить статистику базовой RAG системы"""
    stats = {
        "basic_available": BASIC_RAG_AVAILABLE,
        "current_mode": "basic",
    }
    
    # Добавляем детальную статистику если система доступна
    if BASIC_RAG_AVAILABLE and basic_rag:
        try:
            stats["basic_stats"] = {
                "knowledge_base_loaded": bool(basic_rag.knowledge_base),
                "kb_size": len(str(basic_rag.knowledge_base)) if basic_rag.knowledge_base else 0
            }
        except Exception as e:
            stats["basic_stats"] = {"error": str(e)}
    
    return stats


async def reload_knowledge_base() -> bool:
    """Перезагрузить базу знаний"""
    try:
        if basic_rag and BASIC_RAG_AVAILABLE:
            basic_rag.load_knowledge_base()
            logger.info("✅ Базовая база знаний перезагружена")
            return True
        else:
            logger.warning("⚠️ Базовая RAG система недоступна")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка перезагрузки базы знаний: {e}")
        return False
