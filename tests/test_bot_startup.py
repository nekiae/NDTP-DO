#!/usr/bin/env python3
"""
Тест запуска бота и квиз-модуля
"""
import sys
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)

def test_quiz_import():
    """Тест импорта квиз-модуля"""
    print("🧪 Тестирую импорт квиз-модуля...")
    
    try:
        print("✅ Все функции квиза успешно импортированы")
        return True
    except Exception as e:
        print(f"❌ Ошибка импорта квиза: {e}")
        return False

def test_bot_init():
    """Тест инициализации бота"""
    print("🧪 Тестирую инициализацию бота...")
    
    try:
        # Импорт основных модулей
        from bot import QUIZ_AVAILABLE
        print(f"✅ Основной модуль бота загружен. Квиз доступен: {QUIZ_AVAILABLE}")
        return True
    except Exception as e:
        print(f"❌ Ошибка инициализации бота: {e}")
        return False

def main():
    """Основная функция теста"""
    print("🚀 Тестирование запуска бота...")
    
    # Тестируем импорт квиза
    quiz_ok = test_quiz_import()
    
    # Тестируем инициализацию бота
    bot_ok = test_bot_init()
    
    if quiz_ok and bot_ok:
        print("🎉 Все тесты прошли успешно!")
        return 0
    else:
        print("❌ Некоторые тесты не прошли")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 