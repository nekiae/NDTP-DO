# Сравнение RAG систем

## 🔧 Базовая RAG система (`rag_system.py`)

### Принцип работы:
- **Поиск по ключевым словам**: Использует простое текстовое сравнение
- **Предопределенные синонимы**: Жестко заданный словарь синонимов
- **SequenceMatcher**: Сравнение строк для определения релевантности
- **JSON поиск**: Прямой поиск в структуре JSON файла

### Преимущества:
✅ Быстрая работа (нет загрузки моделей)
✅ Простая отладка и понимание логики
✅ Малое потребление памяти
✅ Не требует дополнительных зависимостей

### Недостатки:
❌ Не понимает семантику (смысл) запросов
❌ Работает только с точными совпадениями ключевых слов
❌ Не адаптируется к новым типам запросов
❌ Жесткие ограничения синонимов
❌ Может пропускать релевантную информацию

## 🚀 Современная RAG система (`modern_rag_system.py`)

### Принцип работы:
- **Векторные эмбеддинги**: SentenceTransformers преобразует текст в векторы
- **Семантический поиск**: ChromaDB ищет по смысловому сходству
- **Cosine similarity**: Вычисляет семантическую близость между запросом и документами
- **Автоматическое переиндексирование**: Обновляется при изменении базы знаний

### Преимущества:
✅ Понимает смысл запросов (семантический поиск)
✅ Находит релевантную информацию даже при разной формулировке
✅ Работает с синонимами и похожими концепциями автоматически
✅ Поддерживает многоязычность
✅ Адаптируется к новым типам запросов
✅ Возможность обучения и улучшения
✅ Количественная оценка релевантности (similarity score)

### Недостатки:
❌ Требует загрузки модели эмбеддингов (~500MB)
❌ Потребляет больше памяти и CPU
❌ Первый запуск медленнее (создание эмбеддингов)
❌ Требует дополнительные зависимости

## 📊 Сравнительная таблица

| Критерий | Базовая RAG | Современная RAG |
|----------|-------------|------------------|
| **Понимание смысла** | ❌ Нет | ✅ Да |
| **Скорость запуска** | ✅ Быстро | ❌ Медленно |
| **Потребление памяти** | ✅ Мало (~50MB) | ❌ Много (~500MB) |
| **Точность поиска** | ❌ Низкая | ✅ Высокая |
| **Гибкость** | ❌ Жесткая | ✅ Адаптивная |
| **Простота отладки** | ✅ Простая | ❌ Сложная |
| **Работа с синонимами** | ❌ Предопределенные | ✅ Автоматически |
| **Многоязычность** | ❌ Ограниченная | ✅ Полная |

## 🎯 Когда использовать что?

### Базовая RAG подходит для:
- Прототипирования и тестирования
- Ограниченных ресурсов (память, CPU)
- Простых запросов с известными ключевыми словами
- Быстрого развертывания без дополнительных зависимостей

### Современная RAG подходит для:
- Продакшн-систем с высокими требованиями к качеству
- Сложных и разнообразных пользовательских запросов
- Необходимости понимания семантики и контекста
- Систем, где важна точность поиска

## 🔄 Автоматическое переключение

Бот автоматически определяет доступность современной RAG системы:

```python
# Если доступны зависимости - используем современную RAG
if MODERN_RAG_AVAILABLE:
    context = await get_context_for_query_async(message.text)
else:
    # Fallback на базовую RAG
    context = rag_system.get_context_for_query(message.text)
```

## 🛠️ Команды для тестирования

- `/test_rag` - Тестирование базовой RAG системы
- `/test_modern_rag` - Тестирование современной RAG системы  
- `/rag_stats` - Статистика текущей RAG системы
- `/reload_kb` - Перезагрузка базы знаний

## 📈 Примеры улучшений

### Базовая RAG:
```
Запрос: "робототехника для детей"
Поиск: ["робототехника", "детей"] → точное совпадение в JSON
```

### Современная RAG:
```
Запрос: "курсы по роботам для школьников"  
Поиск: векторное сходство → находит "робототехника для детей"
Similarity: 0.87 (87% сходства)
```

Современная RAG понимает, что "курсы по роботам" ≈ "робототехника", а "школьники" ≈ "дети". 