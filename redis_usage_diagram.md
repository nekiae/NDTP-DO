# 🔴 Полное использование Redis в проекте TechnoBot

## 📊 Архитектура Redis в проекте

```mermaid
graph TB
    %% Основные компоненты
    subgraph "🔧 Система защиты от перегрузки"
        A[Пользователь] --> B[Middleware]
        B --> C{Redis доступен?}
        C -->|Да| D[Redis Rate Limiting]
        C -->|Нет| E[Локальный кэш]
        D --> F[Счетчик запросов]
        E --> F
        F --> G{Лимит превышен?}
        G -->|Да| H[Блокировка запроса]
        G -->|Нет| I[Пропуск запроса]
    end

    subgraph "🛡️ Redis операции"
        J[INCR user:123:quota] --> K[TTL 3600s]
        L[GET user:123:quota] --> M[Проверка лимита]
        N[EXPIRE user:123:quota 3600] --> O[Автоудаление]
    end

    subgraph "📈 Мониторинг и метрики"
        P[redis-cli KEYS user:*:quota] --> Q[Активные квоты]
        R[redis-cli INFO stats] --> S[Статистика Redis]
        T[TTL проверка] --> U[Время до сброса]
    end

    subgraph "🔄 Fallback стратегия"
        V[Ошибка Redis] --> W[Локальный словарь]
        W --> X[Счетчик в памяти]
        X --> Y[Сброс по часам]
    end

    subgraph "⚙️ Конфигурация"
        Z[REDIS_AVAILABLE] --> AA[Проверка импорта]
        BB[redis.from_url] --> CC[Подключение]
        DD[decode_responses=True] --> EE[UTF-8 строки]
    end

    %% Связи между компонентами
    A --> J
    D --> J
    F --> L
    G --> T
    C --> V
    V --> W
    AA --> BB
    BB --> DD

    %% Стили
    classDef redisNode fill:#ff6b6b,stroke:#d63031,stroke-width:2px,color:#fff
    classDef fallbackNode fill:#74b9ff,stroke:#0984e3,stroke-width:2px,color:#fff
    classDef monitoringNode fill:#55a3ff,stroke:#2d3436,stroke-width:2px,color:#fff
    classDef configNode fill:#a29bfe,stroke:#6c5ce7,stroke-width:2px,color:#fff

    class D,J,K,L,M,N,O redisNode
    class E,W,X,Y fallbackNode
    class P,Q,R,S,T,U monitoringNode
    class Z,AA,BB,CC,DD,EE configNode
```

## 🔧 Детальная схема работы Redis

```mermaid
sequenceDiagram
    participant U as Пользователь
    participant M as Middleware
    participant R as Redis
    participant L as Локальный кэш
    participant B as Бот

    Note over U,B: Запрос пользователя

    U->>M: Отправляет сообщение
    M->>M: Проверяет REDIS_AVAILABLE
    
    alt Redis доступен
        M->>R: INCR user:{id}:quota
        R->>M: Возвращает счетчик
        
        alt Первый запрос
            M->>R: EXPIRE user:{id}:quota 3600
        end
        
        M->>M: Проверяет лимит (50/час)
        
        alt Лимит превышен
            M->>U: "Лимит исчерпан"
        else Лимит не превышен
            M->>B: Пропускает запрос
        end
        
    else Redis недоступен
        M->>L: Проверяет локальный кэш
        L->>M: Возвращает счетчик
        
        M->>M: Проверяет лимит
        
        alt Лимит превышен
            M->>U: "Лимит исчерпан"
        else Лимит не превышен
            M->>B: Пропускает запрос
        end
    end
```

## 📊 Структура данных Redis

```mermaid
graph LR
    subgraph "🔑 Ключи Redis"
        A[user:123:quota] --> B[Счетчик запросов]
        C[user:456:quota] --> D[TTL 3600s]
        E[user:789:quota] --> F[Автоудаление]
    end

    subgraph "📈 Операции"
        G[INCR] --> H[Атомарное увеличение]
        I[EXPIRE] --> J[Установка TTL]
        K[TTL] --> L[Проверка времени]
        M[GET] --> N[Чтение значения]
    end

    subgraph "🛡️ Защита"
        O[50 запросов/час] --> P[Лимит на пользователя]
        Q[3600 секунд] --> R[Время жизни ключа]
        S[0.8 * лимит] --> T[Предупреждение]
    end

    A --> G
    C --> I
    E --> K
    B --> O
    D --> Q
    F --> S
```

## 🔄 Жизненный цикл Redis ключа

```mermaid
stateDiagram-v2
    [*] --> Создание
    Создание --> Активен: INCR
    Активен --> Увеличение: Запрос
    Увеличение --> Активен: < 50
    Увеличение --> Блокировка: >= 50
    Блокировка --> Ожидание: TTL > 0
    Ожидание --> Удаление: TTL = 0
    Удаление --> [*]
    
    Активен --> Предупреждение: > 40
    Предупреждение --> Активен: < 50
    Предупреждение --> Блокировка: >= 50
```

## 📋 Команды мониторинга

```mermaid
graph TD
    subgraph "🔍 Диагностика"
        A[redis-cli ping] --> B[Проверка подключения]
        C[redis-cli KEYS user:*:quota] --> D[Активные квоты]
        E[redis-cli INFO stats] --> F[Статистика сервера]
        G[redis-cli TTL user:123:quota] --> H[Время до сброса]
    end

    subgraph "📊 Метрики"
        I[Количество активных пользователей] --> J[Нагрузка на систему]
        K[Среднее время жизни ключей] --> L[Эффективность TTL]
        M[Частота превышения лимитов] --> N[Качество защиты]
    end

    subgraph "🛠️ Управление"
        O[redis-cli FLUSHDB] --> P[Очистка всех данных]
        Q[redis-cli DEL user:123:quota] --> R[Удаление конкретной квоты]
        S[redis-cli CONFIG SET maxmemory] --> T[Настройка памяти]
    end

    B --> I
    D --> K
    F --> M
    H --> N
```

## 🎯 Интеграция с ботом

```mermaid
graph TB
    subgraph "🤖 Основной бот"
        A[bot.py] --> B[Импорт redis.asyncio]
        B --> C[REDIS_AVAILABLE проверка]
        C --> D[Middleware инициализация]
    end

    subgraph "🛡️ Middleware"
        E[HourlyLimitMiddleware] --> F[Проверка лимитов]
        F --> G[Redis операции]
        G --> H[Fallback логика]
    end

    subgraph "📊 Команды"
        I[/test_limits] --> J[Проверка статуса]
        J --> K[Redis диагностика]
        K --> L[Отображение метрик]
    end

    subgraph "🔧 Конфигурация"
        M[requirements.txt] --> N[redis>=5]
        O[run_improvements.sh] --> P[Установка Redis]
        Q[FIX_PYTHON_313.md] --> R[Совместимость]
    end

    A --> E
    E --> I
    I --> M
    M --> O
    O --> Q
```

## 📝 Резюме использования Redis

### ✅ **Что использует Redis:**
- **Rate Limiting** - ограничение запросов пользователей
- **Распределенное хранение** - для нескольких экземпляров бота
- **Автоматический TTL** - самоочистка старых данных
- **Атомарные операции** - безопасное увеличение счетчиков

### ❌ **Что НЕ использует Redis:**
- **Очереди операторов** - реализованы в памяти
- **Кэширование RAG** - используется ChromaDB
- **Сессии пользователей** - хранятся в FSM
- **История сообщений** - локальное хранение

### 🔧 **Ключевые особенности:**
- **Graceful degradation** - fallback на локальный кэш
- **Совместимость с Python 3.13** - безопасные импорты
- **Мониторинг** - команды для диагностики
- **Настраиваемые лимиты** - 50 запросов/час на пользователя 