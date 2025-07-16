#!/usr/bin/env python3
"""
Тестовый скрипт для проверки улучшений бота
- Парсинг русских дат
- Лимиты API и защита от перегрузки
"""

import asyncio
import time
from datetime import datetime
from typing import Optional

# Импорт для парсинга дат
import re
try:
    import dateparser
    DATEPARSER_AVAILABLE = True
except ImportError:
    print("⚠️ dateparser не установлен. Используйте: pip install dateparser")
    DATEPARSER_AVAILABLE = False

# Импорт для Redis
try:
    import aioredis
    REDIS_AVAILABLE = True
except ImportError:
    print("⚠️ aioredis не установлен. Используйте: pip install aioredis")
    REDIS_AVAILABLE = False

# Импорт для retry
try:
    from tenacity import retry, wait_exponential, stop_after_attempt
    TENACITY_AVAILABLE = True
except ImportError:
    print("⚠️ tenacity не установлен. Используйте: pip install tenacity")
    TENACITY_AVAILABLE = False

# Словарь для парсинга русских месяцев
MONTHS_PATTERNS = {
    r'январ\w*': 1, r'феврал\w*': 2, r'март\w*': 3,
    r'апрел\w*': 4, r'ма[йя]\w*': 5, r'июн\w*': 6,
    r'июл\w*': 7, r'август\w*': 8, r'сентябр\w*': 9,
    r'октябр\w*': 10, r'ноябр\w*': 11, r'декабр\w*': 12,
}

# Компилируем regex для парсинга дат
DATE_REGEX = re.compile(
    rf'(?P<day>\d{{1,2}})\s+(?P<month>{"|".join(MONTHS_PATTERNS)})\s*(?P<year>\d{{4}})?',
    re.IGNORECASE | re.UNICODE,
)

def parse_russian_date(text: str, default_year: int = None) -> Optional[datetime]:
    """Надёжный парсер русских дат с fallback на dateparser"""
    if not text:
        return None
    
    # Очищаем текст от лишних пробелов
    clean_text = re.sub(r'\s+', ' ', text.strip())
    
    # Сначала пробуем dateparser (надёжнее)
    if DATEPARSER_AVAILABLE:
        try:
            dt = dateparser.parse(
                clean_text,
                languages=['ru'],
                settings={
                    'DATE_ORDER': 'DMY',
                    'PREFER_DAY_OF_MONTH': 'first'
                }
            )
            if dt:
                return dt
        except Exception as e:
            print(f"⚠️ dateparser не смог распарсить '{clean_text}': {e}")
    
    # Fallback на собственный regex
    try:
        match = DATE_REGEX.search(clean_text)
        if match:
            day = int(match.group('day'))
            month_text = match.group('month')
            year = int(match.group('year') or default_year or datetime.now().year)
            
            # Находим номер месяца
            month = None
            for pattern, num in MONTHS_PATTERNS.items():
                if re.fullmatch(pattern, month_text, re.IGNORECASE):
                    month = num
                    break
            
            if month:
                return datetime(year, month, day)
    except Exception as e:
        print(f"⚠️ Regex не смог распарсить '{clean_text}': {e}")
    
    return None

# Симуляция лимитов API
class RateLimitSimulator:
    def __init__(self, limit_per_hour: int = 50):
        self.limit = limit_per_hour
        self.cache = {}
        
    def check_limit(self, user_id: int) -> bool:
        """Проверка лимита пользователя"""
        current_time = time.time()
        current_hour = int(current_time // 3600)
        
        if user_id not in self.cache:
            self.cache[user_id] = {'hour': current_hour, 'count': 0}
        
        user_data = self.cache[user_id]
        
        # Сброс счётчика при смене часа
        if user_data['hour'] != current_hour:
            user_data['hour'] = current_hour
            user_data['count'] = 0
        
        user_data['count'] += 1
        
        if user_data['count'] > self.limit:
            return False
        
        return True
    
    def get_usage(self, user_id: int) -> tuple:
        """Получить использование пользователя"""
        if user_id not in self.cache:
            return 0, self.limit
        
        user_data = self.cache[user_id]
        current_hour = int(time.time() // 3600)
        
        if user_data['hour'] != current_hour:
            return 0, self.limit
        
        return user_data['count'], self.limit

# Симуляция семафора
class SemaphoreSimulator:
    def __init__(self, limit: int = 10):
        self.limit = limit
        self.current = 0
        
    async def acquire(self):
        while self.current >= self.limit:
            await asyncio.sleep(0.1)
        self.current += 1
        
    def release(self):
        if self.current > 0:
            self.current -= 1
    
    async def __aenter__(self):
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.release()

# Симуляция retry декоратора
def simple_retry(max_attempts: int = 3):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    print(f"⚠️ Попытка {attempt + 1} не удалась: {e}")
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        raise
            return None
        return wrapper
    return decorator

# Тесты
def test_date_parser():
    """Тест парсинга дат"""
    print("🧪 Тест парсинга русских дат:")
    print("=" * 50)
    
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
        "через 3 дня"
    ]
    
    for date_str in test_dates:
        try:
            parsed_date = parse_russian_date(date_str)
            if parsed_date:
                formatted = parsed_date.strftime("%d.%m.%Y %H:%M")
                print(f"✅ '{date_str}' → {formatted}")
            else:
                print(f"❌ '{date_str}' → не распознано")
        except Exception as e:
            print(f"⚠️ '{date_str}' → ошибка: {str(e)[:30]}")
    
    print("\n💡 Возможности:")
    print("• Распознавание склонений (январь/января)")
    print("• Поддержка 'г.' и 'года'")
    print("• Относительные даты (завтра, через N дней)")
    print("• Fallback на regex при сбое dateparser")
    print("• Автоматическое определение текущего года")

def test_rate_limits():
    """Тест лимитов API"""
    print("\n🛡️ Тест лимитов API:")
    print("=" * 50)
    
    rate_limiter = RateLimitSimulator(limit_per_hour=5)  # Низкий лимит для теста
    
    # Тестируем несколько пользователей
    users = [12345, 67890, 11111]
    
    for user_id in users:
        print(f"\n👤 Пользователь {user_id}:")
        
        # Отправляем запросы
        for i in range(7):
            allowed = rate_limiter.check_limit(user_id)
            used, limit = rate_limiter.get_usage(user_id)
            
            status = "✅" if allowed else "❌"
            print(f"  {status} Запрос {i+1}: {used}/{limit}")
            
            if not allowed:
                print(f"  ⌛ Лимит исчерпан")
                break
    
    print("\n💡 Возможности:")
    print("• Индивидуальные лимиты для каждого пользователя")
    print("• Автоматический сброс каждый час")
    print("• Защита от DDoS")
    print("• Fallback на локальный кэш без Redis")

async def test_semaphore():
    """Тест семафора для LLM"""
    print("\n⚡ Тест семафора LLM:")
    print("=" * 50)
    
    semaphore = SemaphoreSimulator(limit=3)  # Лимит 3 одновременных запроса
    
    @simple_retry(max_attempts=2)
    async def mock_llm_request(request_id: int):
        """Симуляция запроса к LLM"""
        async with semaphore:
            print(f"  🚀 Запрос {request_id} обрабатывается...")
            await asyncio.sleep(1)  # Симуляция обработки
            print(f"  ✅ Запрос {request_id} завершён")
            return f"Ответ {request_id}"
    
    # Отправляем 5 запросов одновременно
    tasks = [mock_llm_request(i) for i in range(1, 6)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    print(f"\n📊 Результаты:")
    for i, result in enumerate(results, 1):
        if isinstance(result, Exception):
            print(f"  ❌ Запрос {i}: {result}")
        else:
            print(f"  ✅ Запрос {i}: {result}")
    
    print("\n💡 Возможности:")
    print("• Ограничение одновременных запросов")
    print("• Автоматические повторы при ошибках")
    print("• Graceful degradation")

async def test_redis_connection():
    """Тест подключения к Redis"""
    print("\n🔴 Тест подключения к Redis:")
    print("=" * 50)
    
    if not REDIS_AVAILABLE:
        print("❌ aioredis не установлен")
        return
    
    try:
        redis = aioredis.from_url("redis://localhost", decode_responses=True)
        
        # Тестируем подключение
        await redis.ping()
        print("✅ Redis подключён")
        
        # Тестируем операции
        await redis.set("test_key", "test_value", ex=10)
        value = await redis.get("test_key")
        print(f"✅ Тест записи/чтения: {value}")
        
        # Тестируем счётчик
        await redis.incr("test_counter")
        counter = await redis.get("test_counter")
        print(f"✅ Тест счётчика: {counter}")
        
        # Очищаем тестовые данные
        await redis.delete("test_key", "test_counter")
        
        await redis.close()
        
    except Exception as e:
        print(f"❌ Ошибка Redis: {e}")
        print("💡 Убедитесь, что Redis запущен: redis-server")

async def main():
    """Основная функция тестирования"""
    print("🚀 Тестирование улучшений TechnoBot")
    print("=" * 60)
    
    # Тест парсинга дат
    test_date_parser()
    
    # Тест лимитов API
    test_rate_limits()
    
    # Тест семафора
    await test_semaphore()
    
    # Тест Redis
    await test_redis_connection()
    
    print("\n🎉 Тестирование завершено!")
    print("=" * 60)
    
    # Проверка зависимостей
    print("\n📦 Статус зависимостей:")
    print(f"• dateparser: {'✅' if DATEPARSER_AVAILABLE else '❌'}")
    print(f"• aioredis: {'✅' if REDIS_AVAILABLE else '❌'}")
    print(f"• tenacity: {'✅' if TENACITY_AVAILABLE else '❌'}")
    
    if not all([DATEPARSER_AVAILABLE, REDIS_AVAILABLE, TENACITY_AVAILABLE]):
        print("\n💡 Для полного функционала установите:")
        print("pip install dateparser aioredis tenacity")

if __name__ == "__main__":
    asyncio.run(main()) 