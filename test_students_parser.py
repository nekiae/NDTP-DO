#!/usr/bin/env python3
"""
Тестовый файл для парсера учащихся НДТП
"""

import asyncio
import logging
import sys
import os

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Добавляем текущую директорию в путь для импорта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from students_parser import StudentsParser, get_students_context, get_students_context_async, force_update_students


async def test_basic_functionality():
    """Тестирует базовую функциональность парсера"""
    print("🧪 Тест 1: Базовая функциональность")
    
    parser = StudentsParser()
    
    # Проверяем инициализацию
    assert parser.url == "https://ndtp.by/schedule/"
    assert parser.students_file == "students_list.json"
    print("✅ Инициализация парсера прошла успешно")
    
    # Проверяем загрузку страницы
    html_content = await parser.fetch_page()
    if html_content:
        print(f"✅ Страница успешно загружена ({len(html_content)} символов)")
    else:
        print("❌ Не удалось загрузить страницу")
        return False
    
    # Парсим данные
    students_data = parser.parse_students_list(html_content)
    if students_data:
        print(f"✅ Данные успешно распарсены ({students_data.get('total_count', 0)} учащихся)")
        return True
    else:
        print("❌ Не удалось распарсить данные")
        return False


async def test_cache_functionality():
    """Тестирует функциональность кэширования"""
    print("\n🧪 Тест 2: Функциональность кэширования")
    
    parser = StudentsParser()
    
    # Принудительно обновляем данные
    success = await parser.update_students(force=True)
    if success:
        print("✅ Данные успешно обновлены и сохранены в кэш")
        
        # Проверяем загрузку из кэша
        cached_data = parser.load_students_cache()
        if cached_data:
            print(f"✅ Кэш успешно загружен ({cached_data.get('total_count', 0)} учащихся)")
            return True
        else:
            print("❌ Не удалось загрузить кэш")
            return False
    else:
        print("❌ Не удалось обновить данные")
        return False


async def test_context_generation():
    """Тестирует генерацию контекста"""
    print("\n🧪 Тест 3: Генерация контекста")
    
    # Тестируем синхронную функцию
    context = get_students_context()
    if context and "Список учащихся НДТП" in context:
        print("✅ Синхронная генерация контекста работает")
    else:
        print("❌ Ошибка в синхронной генерации контекста")
        return False
    
    # Тестируем асинхронную функцию
    async_context = await get_students_context_async()
    if async_context and "Список учащихся НДТП" in async_context:
        print("✅ Асинхронная генерация контекста работает")
    else:
        print("❌ Ошибка в асинхронной генерации контекста")
        return False
    
    # Тестируем поиск по запросу
    search_context = get_students_context("тест")
    if search_context:
        print("✅ Поиск по запросу работает")
        return True
    else:
        print("❌ Ошибка в поиске по запросу")
        return False


async def test_error_handling():
    """Тестирует обработку ошибок"""
    print("\n🧪 Тест 4: Обработка ошибок")
    
    parser = StudentsParser()
    
    # Тестируем обработку пустых данных
    empty_data = parser.parse_students_list("")
    if empty_data and empty_data.get('total_count', 0) == 0:
        print("✅ Обработка пустых данных работает")
    else:
        print("❌ Ошибка в обработке пустых данных")
        return False
    
    # Тестируем обработку некорректного HTML
    invalid_html = "<html><body><p>Некорректный HTML</p></body></html>"
    invalid_data = parser.parse_students_list(invalid_html)
    if invalid_data and invalid_data.get('total_count', 0) <= 1:  # Может найти 1 элемент
        print("✅ Обработка некорректного HTML работает")
        return True
    else:
        print("❌ Ошибка в обработке некорректного HTML")
        return False


async def test_formatted_output():
    """Тестирует форматированный вывод"""
    print("\n🧪 Тест 5: Форматированный вывод")
    
    parser = StudentsParser()
    
    # Получаем сводку
    summary = parser.get_students_summary()
    if summary and "Список учащихся НДТП" in summary:
        print("✅ Сводка генерируется корректно")
    else:
        print("❌ Ошибка в генерации сводки")
        return False
    
    # Получаем полный контекст
    context = parser.get_students_context()
    if context and len(context) > 100:  # Должен быть достаточно длинным
        print("✅ Полный контекст генерируется корректно")
        return True
    else:
        print("❌ Ошибка в генерации полного контекста")
        return False


async def run_all_tests():
    """Запускает все тесты"""
    print("🚀 Запуск тестов парсера учащихся НДТП")
    print("=" * 50)
    
    tests = [
        ("Базовая функциональность", test_basic_functionality),
        ("Кэширование", test_cache_functionality),
        ("Генерация контекста", test_context_generation),
        ("Обработка ошибок", test_error_handling),
        ("Форматированный вывод", test_formatted_output)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            if result:
                passed += 1
                print(f"✅ Тест '{test_name}' пройден")
            else:
                print(f"❌ Тест '{test_name}' провален")
        except Exception as e:
            print(f"❌ Тест '{test_name}' завершился с ошибкой: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Результаты тестирования: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все тесты пройдены успешно!")
        return True
    else:
        print("⚠️ Некоторые тесты провалены")
        return False


async def demo_usage():
    """Демонстрирует использование парсера"""
    print("\n🎯 Демонстрация использования парсера учащихся")
    print("=" * 50)
    
    # Принудительно обновляем данные
    print("🔄 Обновление данных учащихся...")
    success = await force_update_students()
    
    if success:
        print("✅ Данные успешно обновлены")
        
        # Показываем сводку
        parser = StudentsParser()
        summary = parser.get_students_summary()
        print(f"\n📋 {summary}")
        
        # Показываем первые несколько учащихся
        context = parser.get_students_context()
        print(f"\n📋 Первые записи:")
        lines = context.split('\n')[:15]  # Показываем первые 15 строк
        for line in lines:
            print(line)
        
        if len(context.split('\n')) > 15:
            print("...")
        
        return True
    else:
        print("❌ Не удалось обновить данные")
        return False


if __name__ == "__main__":
    async def main():
        # Запускаем тесты
        tests_passed = await run_all_tests()
        
        if tests_passed:
            # Демонстрируем использование
            await demo_usage()
        else:
            print("\n⚠️ Некоторые тесты провалены, демонстрация пропущена")
    
    # Запускаем основную функцию
    asyncio.run(main()) 