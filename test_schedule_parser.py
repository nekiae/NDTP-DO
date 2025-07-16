#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы парсера расписания смен
"""

import asyncio
import logging
import json
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from schedule_parser import ScheduleParser, get_schedule_context_async, get_schedule_context

async def test_parser():
    """Тестирует парсер расписания"""
    print("🧪 ТЕСТИРОВАНИЕ ПАРСЕРА РАСПИСАНИЯ СМЕН")
    print("=" * 50)
    
    parser = ScheduleParser()
    
    # Тест 1: Получение страницы
    print("\n1️⃣ Тест получения страницы...")
    html_content = await parser.fetch_page()
    
    if html_content:
        print(f"✅ Страница загружена: {len(html_content)} символов")
        
        # Сохраним HTML для анализа
        with open("test_page.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("💾 HTML сохранен в test_page.html")
    else:
        print("❌ Не удалось загрузить страницу")
        return
    
    # Тест 2: Парсинг данных
    print("\n2️⃣ Тест парсинга данных...")
    shifts = parser.parse_shifts(html_content)
    
    if shifts:
        print(f"✅ Найдено смен: {len(shifts)}")
        for i, shift in enumerate(shifts, 1):
            print(f"   {i}. {shift['name']}: {shift['start_date']} - {shift['end_date']}")
            print(f"      Заявки: {shift['application_period']}")
        
        # Сохраняем результат
        with open("test_shifts.json", "w", encoding="utf-8") as f:
            json.dump(shifts, f, ensure_ascii=False, indent=2)
        print("💾 Результаты сохранены в test_shifts.json")
    else:
        print("❌ Смены не найдены")
    
    # Тест 3: Сохранение и загрузка данных
    print("\n3️⃣ Тест сохранения/загрузки данных...")
    if parser.save_shifts(shifts):
        print("✅ Данные успешно сохранены")
        
        loaded_data = parser.load_shifts()
        if loaded_data:
            print(f"✅ Данные успешно загружены: {loaded_data['total_shifts']} смен")
        else:
            print("❌ Ошибка загрузки данных")
    else:
        print("❌ Ошибка сохранения данных")
    
    # Тест 4: Функции для получения контекста
    print("\n4️⃣ Тест функций контекста...")
    
    # Общая информация
    general_info = parser.get_current_shifts_info()
    print("📅 Общая информация о сменах:")
    print(general_info[:300] + "..." if len(general_info) > 300 else general_info)
    
    # Поиск по запросу
    test_queries = [
        "январская смена",
        "когда прием заявок",
        "февральская смена",
        "расписание"
    ]
    
    for query in test_queries:
        query_info = parser.get_shifts_for_query(query)
        print(f"\n🔍 Запрос: '{query}'")
        print(query_info[:200] + "..." if len(query_info) > 200 else query_info)
    
    # Тест 5: Асинхронные функции
    print("\n5️⃣ Тест асинхронных функций...")
    
    async_context = await get_schedule_context_async("январь")
    print("📅 Асинхронный контекст:")
    print(async_context[:300] + "..." if len(async_context) > 300 else async_context)
    
    print("\n✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 50)

def test_sync_functions():
    """Тестирует синхронные функции"""
    print("\n🔄 ТЕСТ СИНХРОННЫХ ФУНКЦИЙ")
    print("-" * 30)
    
    # Тест синхронной функции
    sync_context = get_schedule_context("март")
    print("📅 Синхронный контекст:")
    print(sync_context[:300] + "..." if len(sync_context) > 300 else sync_context)

def test_regex_patterns():
    """Тестирует регулярные выражения"""
    print("\n🔍 ТЕСТ РЕГУЛЯРНЫХ ВЫРАЖЕНИЙ")
    print("-" * 30)
    
    parser = ScheduleParser()
    
    # Тестовые строки
    test_strings = [
        "Прием заявок с 23.09.2024 по 7.10.2024г.",
        "Прием заявок с 23.09 по 7.10.2024г.",
        "Прием заявок с 21.10 по 4.11.2024г.",
        "Списочный состав участников, допущенных ко второму этапу отбора учащихся для обучения в Национальном детском технопарке с 08.01.2025г. по 31.01.2025г.",
        "с 06.02.2025г. по 01.03.2025г."
    ]
    
    import re
    
    for test_str in test_strings:
        print(f"\n📝 Тестируем: '{test_str}'")
        
        # Тест паттерна для заявок
        app_match = re.search(parser.app_period_pattern, test_str)
        if app_match:
            print(f"✅ Заявки: {app_match.group(1)} - {app_match.group(2)}")
        
        # Тест паттерна для смен
        shift_match = re.search(parser.shift_period_pattern, test_str)
        if shift_match:
            print(f"✅ Смена: {shift_match.group(1)} - {shift_match.group(2)}")
        
        if not app_match and not shift_match:
            print("❌ Не найдено совпадений")

def main():
    """Главная функция тестирования"""
    print("🚀 ЗАПУСК ТЕСТОВ ПАРСЕРА РАСПИСАНИЯ")
    print("=" * 50)
    print(f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Тест регулярных выражений
    test_regex_patterns()
    
    # Тест синхронных функций
    test_sync_functions()
    
    # Основной асинхронный тест
    asyncio.run(test_parser())
    
    print(f"\n🏁 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО: {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    main() 