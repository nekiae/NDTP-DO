# 🚀 Улучшения бота TechnoBot

## 📅 Надёжный парсинг русских дат

### Проблема
Ранее парсинг дат выполнялся самописными regex, что приводило к ошибкам при обработке:
- Разных склонений месяцев ("января" vs "январь")
- Различных форматов ("г." vs "года")
- Неправильных пробелов
- Относительных дат ("завтра", "через 3 дня")

### Решение
Внедрена библиотека `dateparser` с fallback на улучшенный regex:

```python
def parse_russian_date(text: str, default_year: int = None) -> Optional[datetime]:
    """
    Надёжный парсер русских дат с fallback на dateparser
    """
    # Сначала пробуем dateparser (надёжнее)
    dt = dateparser.parse(clean_text, languages=['ru'])
    
    # Fallback на собственный regex
    if not dt:
        dt = regex_parse(text)
    
    return dt
```

### Возможности
- ✅ Распознавание склонений (январь/января)
- ✅ Поддержка 'г.' и 'года'
- ✅ Относительные даты (завтра, через N дней)
- ✅ Fallback на regex при сбое dateparser
- ✅ Автоматическое определение текущего года

### Тестирование
```bash
/test_date_parser  # Команда для тестирования парсера
```

---

## 🛡️ Защита от перегрузки API

### Проблема
Один пользователь мог:
- Отправить сотни запросов подряд
- Исчерпать квоту API за несколько минут
- Заблокировать доступ для других пользователей

### Решение
Внедрена многоуровневая система защиты:

#### 1. Лимит запросов в час (Redis)
```python
class HourlyLimitMiddleware(BaseMiddleware):
    def __init__(self, limit_per_hour: int = 50):
        self.limit = limit_per_hour
        
    async def __call__(self, handler, event, data):
        key = f"user:{user_id}:quota"
        used = await redis.incr(key)
        if used == 1:
            await redis.expire(key, 3600)  # TTL 1 час
        
        if used > self.limit:
            await event.answer("⌛ Лимит исчерпан, попробуйте через час")
            return
```

#### 2. Семафор для LLM запросов
```python
LLM_CONCURRENCY = 10
llm_semaphore = asyncio.Semaphore(LLM_CONCURRENCY)

async def ask_llm(prompt):
    async with llm_semaphore:  # Максимум 10 параллельных запросов
        return await deepseek_api(prompt)
```

#### 3. Автоматический back-off на HTTP 429
```python
@retry(
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5)
)
async def _make_request(self, payload: dict):
    # Автоматическое повторение при rate limit
    if response.status == 429:
        retry_after = response.headers.get('Retry-After', '60')
        await asyncio.sleep(int(retry_after))
```

### Настройки защиты
- **Лимит запросов:** 50/час на пользователя
- **Одновременных LLM:** 10 запросов
- **Retry попытки:** 5 с экспоненциальным back-off
- **Обработка HTTP 429:** автоматическая

### Тестирование
```bash
/test_limits  # Команда для проверки лимитов
```

---

## 🔧 Установка и настройка

### Новые зависимости
```bash
# Улучшенный парсинг дат
dateparser>=1.1.8

# Лимиты API и защита от перегрузки
aioredis>=2.0.0
tenacity>=8.2.0
```

### Установка Redis (опционально)
```bash
# Ubuntu/Debian
sudo apt install redis-server

# macOS
brew install redis

# Запуск Redis
redis-server
```

### Настройка без Redis
Если Redis недоступен, система автоматически переключается на локальный кэш.

---

## 📊 Мониторинг

### Логи защиты
```python
# Близкие к лимиту пользователи
logger.warning(f"⚠️ Пользователь {user_id} близок к лимиту: {used}/{limit}")

# Превышение лимитов
logger.error(f"❌ Пользователь {user_id} превысил лимит: {used}/{limit}")

# Rate limit от API
logger.warning(f"⚠️ Rate limit (429), retry after {retry_after}s")
```

### Метрики Redis
```bash
# Просмотр активных квот
redis-cli KEYS "user:*:quota"

# Статистика использования
redis-cli INFO stats
```

---

## 🚀 Результат

### До улучшений:
- ❌ Неточный парсинг дат
- ❌ Возможность DDoS одним пользователем
- ❌ Частые ошибки при перегрузке API

### После улучшений:
- ✅ Надёжный парсинг любых русских дат
- ✅ Автоматическая защита от перегрузки
- ✅ Справедливое распределение ресурсов
- ✅ Graceful degradation при ошибках

### Команды для тестирования:
- `/test_date_parser` - тест парсинга дат
- `/test_limits` - статус защиты от перегрузки

---

## 📝 Техническая документация

### Архитектура лимитов
```
Пользователь → Middleware → Redis/LocalCache → Семафор → LLM API
                 ↓              ↓                ↓         ↓
              Проверка      Счетчик         Очередь   Retry
              лимитов      запросов         запросов  логика
```

### Fallback стратегия
1. **Redis доступен** → используем распределенный кэш
2. **Redis недоступен** → локальный кэш в памяти
3. **API rate limit** → автоматический back-off
4. **Dateparser сбой** → fallback на regex

Эти улучшения обеспечивают стабильную работу бота даже при высокой нагрузке и защищают от злоупотреблений API. 