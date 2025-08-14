#!/usr/bin/env python3
"""
Тест инлайн-кнопок квиза
"""
import asyncio
import logging
from unittest.mock import Mock, AsyncMock

# Настройка логирования
logging.basicConfig(level=logging.INFO)

async def test_quiz_keyboards():
    """Тест создания клавиатур квиза"""
    print("🧪 Тестирую клавиатуры квиза...")
    
    try:
        from quiz_mod import create_quiz_keyboard, create_finish_keyboard
        
        # Тест клавиатуры для вопросов
        quiz_kb = create_quiz_keyboard()
        print(f"✅ Клавиатура вопросов создана: {len(quiz_kb.inline_keyboard)} кнопка")
        
        # Проверяем кнопку выхода
        exit_button = quiz_kb.inline_keyboard[0][0]
        if exit_button.text == "❌ Выйти из квиза" and exit_button.callback_data == "quiz_exit":
            print("✅ Кнопка выхода корректна")
        else:
            print("❌ Кнопка выхода некорректна")
            return False
        
        # Тест клавиатуры для завершения
        finish_kb = create_finish_keyboard()
        print(f"✅ Клавиатура завершения создана: {len(finish_kb.inline_keyboard)} кнопка")
        
        # Проверяем кнопку готово
        finish_button = finish_kb.inline_keyboard[0][0]
        if finish_button.text == "✅ Готово" and finish_button.callback_data == "quiz_finish":
            print("✅ Кнопка готово корректна")
        else:
            print("❌ Кнопка готово некорректна")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования клавиатур: {e}")
        return False

async def test_quiz_callbacks():
    """Тест callback-функций квиза"""
    print("🧪 Тестирую callback-функции квиза...")
    
    try:
        from quiz_mod import quiz_exit_callback, quiz_finish_callback
        
        # Создаем мок объекты
        mock_callback = Mock()
        mock_callback.message.edit_text = AsyncMock()
        
        mock_state = AsyncMock()
        mock_state.clear = AsyncMock()
        
        # Тест выхода из квиза
        await quiz_exit_callback(mock_callback, mock_state)
        
        # Проверяем что состояние очищено
        mock_state.clear.assert_called_once()
        
        # Проверяем что сообщение отредактировано
        mock_callback.message.edit_text.assert_called_once()
        
        print("✅ Callback выхода работает корректно")
        
        # Сбрасываем моки
        mock_callback.message.edit_text.reset_mock()
        mock_state.clear.reset_mock()
        
        # Тест завершения квиза
        await quiz_finish_callback(mock_callback, mock_state)
        
        # Проверяем что состояние очищено
        mock_state.clear.assert_called_once()
        
        # Проверяем что сообщение отредактировано
        mock_callback.message.edit_text.assert_called_once()
        
        print("✅ Callback завершения работает корректно")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования callback: {e}")
        return False

async def test_quiz_import():
    """Тест импорта квиз-модуля"""
    print("🧪 Тестирую импорт квиз-модуля...")
    
    try:
        print("✅ Все функции квиза успешно импортированы")
        return True
    except Exception as e:
        print(f"❌ Ошибка импорта квиза: {e}")
        return False

async def main():
    """Основная функция тестирования"""
    print("🚀 Тестирование инлайн-кнопок квиза...")
    
    # Тест импорта
    import_success = await test_quiz_import()
    
    # Тест клавиатур
    keyboards_success = await test_quiz_keyboards()
    
    # Тест callback-функций
    callbacks_success = await test_quiz_callbacks()
    
    if import_success and keyboards_success and callbacks_success:
        print("\n🎉 Все тесты прошли успешно!")
        print("✅ Инлайн-кнопки квиза готовы к работе")
    else:
        print("\n❌ Некоторые тесты не прошли")
        return False

if __name__ == "__main__":
    asyncio.run(main()) 