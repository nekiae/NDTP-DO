#!/usr/bin/env python3
"""
Тест промпта квиза - проверка что ИИ не дает рекомендации до 5-го вопроса
"""
import asyncio
import logging
from unittest.mock import Mock, AsyncMock

# Настройка логирования
logging.basicConfig(level=logging.INFO)

async def test_quiz_prompt_rules():
    """Тест правил промпта квиза"""
    print("🧪 Тестирую правила промпта квиза...")
    
    try:
        # Читаем промпт
        with open('quiz_system_prompt.txt', 'r', encoding='utf-8') as f:
            prompt = f.read()
        
        # Проверяем критические правила
        critical_rules = [
            "НИКОГДА не давай рекомендации до 5-го вопроса",
            "НИКОГДА не анализируй личность до 5-го вопроса",
            "Только задавай вопросы и слушай ответы",
            "Рекомендации давай ТОЛЬКО после 5-го вопроса",
            "НЕ ДАВАЙ РЕКОМЕНДАЦИИ ДО 5-ГО ВОПРОСА"
        ]
        
        missing_rules = []
        for rule in critical_rules:
            if rule not in prompt:
                missing_rules.append(rule)
        
        if missing_rules:
            print(f"❌ Отсутствуют критические правила:")
            for rule in missing_rules:
                print(f"   - {rule}")
            return False
        else:
            print("✅ Все критические правила присутствуют")
        
        # Проверяем структуру вопросов
        question_structure = [
            "Q1: Задай первый психологический вопрос",
            "Q2: Задай второй вопрос на основе ответа Q1",
            "Q3: Задай третий вопрос на основе ответов Q1+Q2",
            "Q4: Задай четвертый вопрос на основе ответов Q1+Q2+Q3",
            "Q5: Задай пятый вопрос на основе ответов Q1+Q2+Q3+Q4",
            "ПОСЛЕ Q5: Дай анализ и рекомендации"
        ]
        
        missing_structure = []
        for structure in question_structure:
            if structure not in prompt:
                missing_structure.append(structure)
        
        if missing_structure:
            print(f"❌ Отсутствует структура вопросов:")
            for structure in missing_structure:
                print(f"   - {structure}")
            return False
        else:
            print("✅ Структура вопросов определена правильно")
        
        # Проверяем формат финального ответа
        if "ФОРМАТ ФИНАЛЬНОГО ОТВЕТА (ТОЛЬКО ПОСЛЕ 5-ГО ВОПРОСА):" in prompt:
            print("✅ Формат финального ответа правильно ограничен")
        else:
            print("❌ Формат финального ответа не ограничен")
            return False
        
        print("🎉 Все правила промпта корректны!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования промпта: {e}")
        return False

async def test_quiz_import():
    """Тест импорта квиз-модуля"""
    print("🧪 Тестирую импорт квиз-модуля...")
    
    try:
        from quiz_mod import register_quiz_handlers, get_quiz_stats, quiz_start_callback
        print("✅ Все функции квиза успешно импортированы")
        return True
    except Exception as e:
        print(f"❌ Ошибка импорта квиза: {e}")
        return False

async def main():
    """Основная функция тестирования"""
    print("🚀 Тестирование промпта квиза...")
    
    # Тест импорта
    import_success = await test_quiz_import()
    
    # Тест правил промпта
    prompt_success = await test_quiz_prompt_rules()
    
    if import_success and prompt_success:
        print("\n🎉 Все тесты прошли успешно!")
        print("✅ Промпт квиза исправлен и готов к работе")
    else:
        print("\n❌ Некоторые тесты не прошли")
        return False

if __name__ == "__main__":
    asyncio.run(main()) 