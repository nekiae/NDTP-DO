# Парсер учащихся НДТП

Парсер для извлечения списка учащихся Национального детского технопарка с сайта https://ndtp.by/schedule/

## Описание

`StudentsParser` - это асинхронный парсер, который извлекает информацию о учащихся НДТП с официального сайта. Парсер поддерживает различные форматы представления данных (таблицы, списки, текстовые блоки) и сохраняет результаты в кэш для быстрого доступа.

## Основные возможности

- 🔄 **Асинхронная загрузка** страниц с таймаутом
- 📊 **Парсинг таблиц** со списками учащихся
- 📋 **Обработка списков** (ul, ol) с именами
- 📝 **Извлечение из текста** учащихся в параграфах
- 💾 **Кэширование данных** в JSON формате
- 🔍 **Поиск учащихся** по имени или группе
- 📅 **Автоматическое обновление** данных
- 🛡️ **Обработка ошибок** и некорректных данных

## Структура данных

Каждый учащийся представлен в виде словаря:

```python
{
    "table_title": "Название таблицы/источника",
    "row_number": 1,  # Номер строки (может быть None)
    "full_name": "Иванов Иван Иванович",
    "group": "Группа А",  # Может быть пустым
    "class": "10 класс",  # Может быть пустым
    "additional_info": "Дополнительная информация"
}
```

## Использование

### Базовое использование

```python
from students_parser import StudentsParser

# Создание парсера
parser = StudentsParser()

# Обновление данных
success = await parser.update_students(force=True)

# Получение списка учащихся
context = parser.get_students_context()
print(context)

# Поиск конкретного учащегося
search_result = parser.get_students_context("Иванов")
print(search_result)
```

### Асинхронные функции

```python
from students_parser import get_students_context_async, force_update_students

# Принудительное обновление
await force_update_students()

# Получение контекста асинхронно
context = await get_students_context_async("поисковый запрос")
```

### Синхронные функции

```python
from students_parser import get_students_context

# Получение контекста синхронно
context = get_students_context("поисковый запрос")
```

## Методы класса StudentsParser

### Основные методы

- `fetch_page()` - Загружает HTML страницы
- `parse_students_list(html_content)` - Парсит HTML и извлекает учащихся
- `update_students(force=False)` - Обновляет данные учащихся
- `get_students_context(query="")` - Получает форматированный список учащихся
- `get_students_summary()` - Получает краткую сводку

### Методы кэширования

- `save_students_cache(data)` - Сохраняет данные в кэш
- `load_students_cache()` - Загружает данные из кэша
- `get_last_update_time()` - Получает время последнего обновления
- `should_update(hours_threshold=24)` - Проверяет необходимость обновления

### Вспомогательные методы

- `_parse_student_row(row, table_title)` - Парсит строку таблицы
- `_extract_student_from_text(text, source)` - Извлекает учащегося из текста
- `_format_student_info(student, index)` - Форматирует информацию об учащемся

## Файлы данных

- `students_list.json` - Кэш со списком учащихся
- `last_students_update.txt` - Время последнего обновления

## Примеры вывода

### Полный список учащихся

```
📋 Список учащихся НДТП

Всего учащихся: 150
Последнее обновление: 2024-01-15T10:30:00

Первые 20 учащихся:

1. [1] **Иванов Иван Иванович** - Группа А (10 класс)
2. [2] **Петров Петр Петрович** - Группа Б (11 класс)
3. [3] **Сидоров Сидор Сидорович** - Группа В (9 класс)
...
```

### Поиск по запросу

```
📋 Список учащихся НДТП

Всего учащихся: 150
Последнее обновление: 2024-01-15T10:30:00

Найдено по запросу 'Иванов': 3

1. [1] **Иванов Иван Иванович** - Группа А (10 класс)
2. [45] **Иванова Анна Петровна** - Группа Д (11 класс)
3. [78] **Ивановский Михаил Сергеевич** - Группа Е (9 класс)
```

## Тестирование

Запустите тесты для проверки функциональности:

```bash
python test_students_parser.py
```

Тесты проверяют:
- ✅ Базовую функциональность парсера
- ✅ Кэширование данных
- ✅ Генерацию контекста
- ✅ Обработку ошибок
- ✅ Форматированный вывод

## Интеграция с ботом

Для интеграции с Telegram ботом добавьте в `bot.py`:

```python
from students_parser import get_students_context, force_update_students

# В обработчике команды
@bot.message_handler(commands=['students'])
async def handle_students_command(message):
    context = get_students_context()
    await bot.reply_to(message, context)

# В обработчике поиска
@bot.message_handler(func=lambda message: 'учащиеся' in message.text.lower())
async def handle_students_search(message):
    query = message.text.replace('учащиеся', '').strip()
    context = get_students_context(query)
    await bot.reply_to(message, context)
```

## Автоматическое обновление

Для автоматического обновления данных запустите цикл:

```python
from students_parser import students_updater_loop

# Запуск цикла обновления (каждые 24 часа)
asyncio.create_task(students_updater_loop(24))
```

## Обработка ошибок

Парсер включает комплексную обработку ошибок:

- 🔄 Повторные попытки при сбоях сети
- ⏰ Таймауты для предотвращения зависания
- 🛡️ Валидация HTML данных
- 📝 Логирование всех операций
- 💾 Graceful fallback на кэш при ошибках

## Логирование

Парсер использует стандартное логирование Python:

```python
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

Уровни логирования:
- `INFO` - Основные операции
- `WARNING` - Предупреждения
- `ERROR` - Ошибки
- `DEBUG` - Детальная отладка

## Зависимости

```txt
aiohttp>=3.8.0
beautifulsoup4>=4.9.0
asyncio
logging
json
datetime
typing
re
os
```

## Лицензия

Парсер создан для образовательных целей и использования в рамках проекта TechnoBot-DO.

## Поддержка

При возникновении проблем:
1. Проверьте подключение к интернету
2. Убедитесь, что сайт https://ndtp.by/schedule/ доступен
3. Проверьте логи на наличие ошибок
4. Попробуйте принудительное обновление данных

---

**Автор**: TechnoBot-DO Team  
**Версия**: 1.0.0  
**Дата**: 2024-01-15 