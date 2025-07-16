#!/bin/bash

# 🚀 Скрипт для установки и тестирования улучшений TechnoBot

echo "🚀 Установка и тестирование улучшений TechnoBot"
echo "============================================="

# Проверяем Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Установите Python 3.8+"
    exit 1
fi

echo "✅ Python найден: $(python3 --version)"

# Активируем виртуальное окружение если есть
if [ -f "venv/bin/activate" ]; then
    echo "📦 Активация виртуального окружения..."
    source venv/bin/activate
else
    echo "⚠️ Виртуальное окружение не найдено. Создайте его:"
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate"
fi

# Устанавливаем новые зависимости
echo "📦 Установка новых зависимостей..."
pip3 install dateparser>=1.1.8 aioredis>=2.0.1 tenacity>=8.2.0

# Проверяем установку Redis (опционально)
echo "🔴 Проверка Redis..."
if command -v redis-server &> /dev/null; then
    echo "✅ Redis найден: $(redis-server --version | head -1)"
    
    # Проверяем, запущен ли Redis
    if redis-cli ping &> /dev/null; then
        echo "✅ Redis запущен"
    else
        echo "⚠️ Redis не запущен. Запустите: redis-server"
        echo "   (или Redis будет работать в локальном режиме)"
    fi
else
    echo "⚠️ Redis не найден. Установите:"
    echo "   Ubuntu/Debian: sudo apt install redis-server"
    echo "   macOS: brew install redis"
    echo "   (или Redis будет работать в локальном режиме)"
fi

# Запускаем тесты
echo ""
echo "🧪 Запуск тестов улучшений..."
echo "============================================="
python3 test_improvements.py

# Проверяем синтаксис основного файла
echo ""
echo "🔍 Проверка синтаксиса bot.py..."
python3 -m py_compile bot.py

if [ $? -eq 0 ]; then
    echo "✅ Синтаксис bot.py корректен"
else
    echo "❌ Ошибка синтаксиса в bot.py"
    exit 1
fi

echo ""
echo "🎉 Улучшения готовы к использованию!"
echo "============================================="
echo ""
echo "📝 Новые команды в боте:"
echo "• /test_date_parser - тест парсинга дат"
echo "• /test_limits - статус защиты от перегрузки"
echo ""
echo "🛡️ Защита от перегрузки:"
echo "• Лимит: 50 запросов/час на пользователя"
echo "• Одновременных LLM: 10 запросов"
echo "• Retry: 5 попыток с exponential backoff"
echo ""
echo "📅 Парсинг дат:"
echo "• Поддержка dateparser для русских дат"
echo "• Fallback на улучшенный regex"
echo "• Распознавание склонений и форматов"
echo ""
echo "🚀 Для запуска бота: python3 bot.py" 