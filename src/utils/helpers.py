"""
Вспомогательные утилиты для NDTP Bot
"""
import logging
import re
from datetime import datetime
from typing import Optional

from ..core.constants import DATE_REGEX, MONTHS_PATTERNS, WEEKDAYS_RU

logger = logging.getLogger(__name__)

# Безопасный импорт dateparser
try:
    import dateparser
    DATEPARSER_AVAILABLE = True
    logger.info("✅ dateparser успешно импортирован")
except ImportError:
    DATEPARSER_AVAILABLE = False
    logger.warning("⚠️ dateparser недоступен - используется fallback regex")


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


def get_russian_weekday(date: datetime) -> str:
    """Получить русское название дня недели"""
    english_weekday = date.strftime("%A")
    return WEEKDAYS_RU.get(english_weekday, english_weekday)


def truncate_text(text: str, max_length: int = 100) -> str:
    """Обрезать текст до указанной длины"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def format_user_info(user_id: int, username: str = None, first_name: str = None) -> str:
    """Форматирование информации о пользователе для логов"""
    parts = [str(user_id)]
    
    if username:
        parts.append(f"@{username}")
    elif first_name:
        parts.append(first_name)
    else:
        parts.append("без имени")
    
    return f"({' - '.join(parts)})"


def safe_int_conversion(value: str, default: int = 0) -> int:
    """Безопасное преобразование строки в число"""
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.warning(f"⚠️ Не удалось преобразовать '{value}' в число, используется {default}")
        return default


def extract_command_args(text: str) -> tuple[str, list[str]]:
    """
    Извлечь команду и аргументы из текста сообщения
    
    Returns:
        Кортеж (команда, список_аргументов)
    """
    if not text or not text.startswith("/"):
        return "", []
    
    parts = text[1:].split()  # Убираем '/' и разделяем по пробелам
    
    if not parts:
        return "", []
    
    command = parts[0]
    args = parts[1:] if len(parts) > 1 else []
    
    return command, args


def is_context_related_to_keywords(query: str, keywords: list[str]) -> bool:
    """
    Проверить, связан ли запрос с определенными ключевыми словами
    
    Args:
        query: Текст запроса
        keywords: Список ключевых слов для поиска
        
    Returns:
        True если найдено хотя бы одно ключевое слово
    """
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in keywords)


def format_time_duration(seconds: int) -> str:
    """
    Форматирование времени в читаемый вид
    
    Args:
        seconds: Количество секунд
        
    Returns:
        Строка вида "2 ч 30 мин" или "45 сек"
    """
    if seconds < 60:
        return f"{seconds} сек"
    
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    
    if minutes < 60:
        if remaining_seconds > 0:
            return f"{minutes} мин {remaining_seconds} сек"
        return f"{minutes} мин"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if remaining_minutes > 0:
        return f"{hours} ч {remaining_minutes} мин"
    return f"{hours} ч"


def clean_text_for_telegram(text: str) -> str:
    """
    Очистка текста для отправки в Telegram
    
    Удаляет или заменяет проблемные символы
    """
    # Удаляем или заменяем markdown символы
    text = text.replace("*", "")  # Убираем звездочки
    text = text.replace("_", "")  # Убираем подчеркивания
    text = text.replace("`", "'")  # Заменяем обратные кавычки
    
    # Ограничиваем длину для Telegram
    max_length = 4096
    if len(text) > max_length:
        text = text[:max_length-3] + "..."
    
    return text


def validate_user_input(text: str, min_length: int = 1, max_length: int = 1000) -> bool:
    """
    Валидация пользовательского ввода
    
    Args:
        text: Текст для проверки
        min_length: Минимальная длина
        max_length: Максимальная длина
        
    Returns:
        True если текст валиден
    """
    if not text or not isinstance(text, str):
        return False
    
    text = text.strip()
    return min_length <= len(text) <= max_length


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
    result = re.sub(r'\s*с\s+\d{2}\.\d{2}\.\d{4}г?\.\s*по\s+\d{2}\.\d{2}\.\d{4}г?\.\s*', '', result)
    result = re.sub(r'\s*\d{2}\.\d{2}\.\d{4}г?\.\s*-\s*\d{2}\.\d{2}\.\d{4}г?\.\s*', '', result)
    
    # Убираем лишние пробелы и точки
    result = re.sub(r'\s+', ' ', result)
    result = result.strip(' .,')
    
    # Специальная логика для разных типов документов
    result_lower = result.lower()
    
    # Определяем тип списка по ключевым словам
    if "2 этап" in result_lower or ("второму этапу" in result_lower and "допущенных" in result_lower):
        result = "Прошедшие 1 этап отбора"
    elif "1 этап" in result_lower or ("первому этапу" in result_lower and "допущенных" in result_lower):
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

# DEV ONLY - Утилиты для отладки
def debug_log_context(context: str, query: str) -> None:
    """DEV ONLY - Логирование контекста для отладки"""
    logger.debug(f"🔍 DEBUG: Запрос '{query[:50]}...'")
    logger.debug(f"📄 DEBUG: Контекст ({len(context)} символов): '{context[:200]}...'")


def debug_log_user_action(user_id: int, action: str, details: str = "") -> None:
    """DEV ONLY - Логирование действий пользователя для отладки"""
    logger.debug(f"👤 DEBUG: Пользователь {user_id} -> {action} {details}")


def debug_measure_time(start_time: float, operation: str) -> float:
    """DEV ONLY - Измерение времени выполнения операции"""
    import time
    end_time = time.time()
    duration = end_time - start_time
    logger.debug(f"⏱️ DEBUG: {operation} выполнено за {duration:.3f} сек")
    return duration
