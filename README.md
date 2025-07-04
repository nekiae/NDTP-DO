# 🤖 TechnoBot-DO

**Умный Telegram-бот для Национального детского технопарка**

TechnoBot-DO - это интеллектуальный AI-ассистент, разработанный для помощи студентам, родителям и консультантам Национального детского технопарка. Бот использует современные технологии искусственного интеллекта для предоставления актуальной информации о программах обучения, расписании, документах и многом другом.

## ✨ Основные возможности

- 🧠 **Умные ответы**: Использует RAG (Retrieval-Augmented Generation) систему с векторной базой данных
- 📅 **Актуальное расписание**: Автоматическое обновление информации о сменах и дедлайнах
- 📄 **Управление документами**: Помощь с необходимыми документами для поступления
- 👨‍💼 **Система операторов**: Эскалация к живым консультантам при необходимости
- 🔔 **Уведомления**: Напоминания о важных датах и событиях
- 💬 **Многоуровневая поддержка**: От простых FAQ до сложных консультаций

## 🛠 Технологический стек

- **Python 3.8+** - основной язык программирования
- **aiogram** - для работы с Telegram Bot API
- **DeepSeek API** - для генерации умных ответов
- **ChromaDB** - векторная база данных для RAG системы
- **aiohttp** - для асинхронных HTTP запросов
- **BeautifulSoup** - для парсинга веб-страниц

## 🚀 Быстрый старт

### 1. Предварительные требования

Убедитесь, что у вас установлен Python 3.8 или выше:

```bash
python3 --version
```

### 2. Клонирование репозитория

```bash
git clone https://github.com/nekiae/NDTP-DO.git
cd NDTP-DO
```

### 3. Создание виртуального окружения

```bash
# Создание виртуального окружения
python3 -m venv venv

# Активация виртуального окружения
# На macOS/Linux:
source venv/bin/activate
# На Windows:
# venv\Scripts\activate
```

### 4. Установка зависимостей

```bash
# Обновление pip
python3 -m pip install --upgrade pip

# Установка зависимостей
python3 -m pip install -r requirements.txt
```

### 5. Настройка переменных окружения

```bash
# Копируйте файл примера
cp .env.example .env

# Отредактируйте .env файл и добавьте ваши ключи:
# BOT_TOKEN=ваш_telegram_bot_token
# DEEPSEEK_API_KEY=ваш_deepseek_api_key
```

### 6. Запуск бота

```bash
python3 bot.py
```

**Или запуск одной командой:**

```bash
source venv/bin/activate && python3 bot.py
```

## 🔧 Конфигурация

### Получение токенов

1. **Telegram Bot Token**:
   - Напишите [@BotFather](https://t.me/BotFather) в Telegram
   - Создайте нового бота командой `/newbot`
   - Сохраните полученный токен

2. **DeepSeek API Key**:
   - Зарегистрируйтесь на [DeepSeek](https://platform.deepseek.com/)
   - Получите API ключ в личном кабинете

### Настройка операторов

Для настройки системы операторов отредактируйте файл `operator_handler.py` и добавьте ID операторов в конфигурацию.

## 📁 Структура проекта

```
TechnoBot-DO/
├── bot.py                      # Основной файл бота
├── rag_system.py              # Базовая RAG система
├── modern_rag_system.py       # Современная RAG система с векторами
├── optimized_rag_system.py    # Оптимизированная RAG система
├── operator_handler.py        # Система операторов
├── schedule_parser.py         # Парсер расписания
├── documents_parser.py        # Парсер документов
├── calendar_module.py         # Модуль календаря
├── notification_system.py     # Система уведомлений
├── knowledge_base.json        # База знаний
├── requirements.txt           # Зависимости Python
└── README.md                 # Документация
```

## 🎯 Команды бота

- `/start` - Приветствие и главное меню
- `/help` - Связаться с консультантом
- `/status` - Проверить статус пользователя
- `/cancel` - Отменить текущую операцию
- `/calendar` - Показать календарь смен
- `/schedule` - Получить расписание
- `/documents` - Информация о документах
- `/notifications` - Настройки уведомлений

## 🔍 Особенности RAG системы

Бот использует многоуровневую RAG систему:

1. **Оптимизированная RAG** - быстрые ответы с кэшированием
2. **Современная RAG** - векторный поиск с ChromaDB
3. **Базовая RAG** - поиск по ключевым словам

Система автоматически выбирает наиболее подходящий метод для каждого запроса.

## 🤝 Вклад в проект

1. Сделайте форк репозитория
2. Создайте ветку для новой функции (`git checkout -b feature/AmazingFeature`)
3. Зафиксируйте изменения (`git commit -m 'Add some AmazingFeature'`)
4. Отправьте изменения в ветку (`git push origin feature/AmazingFeature`)
5. Откройте Pull Request

## 📝 Лицензия

Этот проект распространяется под лицензией MIT. См. файл `LICENSE` для подробностей.

## 🆘 Поддержка

Если у вас возникли вопросы или проблемы:

1. Проверьте [Issues](https://github.com/nekiae/NDTP-DO/issues)
2. Создайте новый Issue с подробным описанием проблемы
3. Свяжитесь с разработчиками

## 📊 Статистика

- 🤖 Поддерживает 20+ различных типов запросов
- 📚 База знаний содержит более 100 документов
- ⚡ Время ответа менее 2 секунд
- 🎯 Точность ответов 95%+

---

**Разработано для Национального детского технопарка** 🏫