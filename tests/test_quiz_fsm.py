#!/usr/bin/env python3
"""
Быстрый тест для проверки FSM состояний квиза
"""
import asyncio
from unittest.mock import MagicMock

async def test_quiz_states():
    """Тестирует состояния квиза"""
    print("🎯 Тестирование состояний квиза...")
    
    try:
        from quiz_mod import QuizState, register_quiz_handlers
        
        # Проверяем, что состояния существуют
        states = [QuizState.Q1, QuizState.Q2, QuizState.Q3, QuizState.Q4, QuizState.Q5, QuizState.DONE]
        print(f"✅ Состояния квиза: {[state.state for state in states]}")
        
        # Создаем мок диспетчера
        mock_dp = MagicMock()
        mock_bot = MagicMock()
        
        # Регистрируем обработчики
        register_quiz_handlers(mock_dp, mock_bot)
        
        # Проверяем, что обработчики зарегистрированы
        call_count = mock_dp.message.call_count
        print(f"✅ Зарегистрировано обработчиков: {call_count}")
        
        if call_count >= 6:  # /quiz, 5 состояний, /quiz_stats
            print("✅ Все обработчики зарегистрированы")
        else:
            print("❌ Не все обработчики зарегистрированы")
        
        print("\n🎉 Тест состояний завершен!")
        
    except Exception as e:
        print(f"❌ Ошибка теста: {e}")

if __name__ == "__main__":
    asyncio.run(test_quiz_states()) 