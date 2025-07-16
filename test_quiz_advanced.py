#!/usr/bin/env python3
"""
Продвинутый тест для проверки новой логики квиза
"""
import asyncio
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

async def test_quiz_psychology():
    """Тестирует психологический подход квиза"""
    print("🧠 Тестирование психологического подхода квиза...")
    
    try:
        from quiz_mod import ask_llm, DEEPSEEK_AVAILABLE, SYSTEM_PROMPT
        
        if not DEEPSEEK_AVAILABLE:
            print("❌ DeepSeek API недоступен")
            return
        
        # Проверяем, что в промпте есть психологические теги
        if "psychology_tags" in SYSTEM_PROMPT:
            print("✅ Психологические теги найдены в промпте")
        else:
            print("❌ Психологические теги не найдены")
            
        if "косвенные" in SYSTEM_PROMPT:
            print("✅ Инструкции о косвенных вопросах найдены")
        else:
            print("❌ Инструкции о косвенных вопросах не найдены")
            
        # Тест первого вопроса
        print("\n🎯 Тестирование первого вопроса...")
        history = []
        
        first_question = await ask_llm(history)
        print(f"Q1: {first_question}")
        
        # Проверяем, что вопрос косвенный (не содержит названий направлений)
        direct_mentions = [
            "программирование", "робототехника", "биотехнологии", 
            "кибербезопасность", "архитектура", "дизайн", "машинное обучение",
            "электроника", "авиакосмические", "геоинформатика"
        ]
        
        is_indirect = not any(mention.lower() in first_question.lower() for mention in direct_mentions)
        if is_indirect:
            print("✅ Первый вопрос косвенный (не содержит названий направлений)")
        else:
            print("❌ Первый вопрос слишком прямой")
            
        # Тест цепочки вопросов
        print("\n🔗 Тестирование цепочки вопросов...")
        
        # Симулируем ответ творческого типа
        creative_answer = "Мне нравится создавать что-то новое, рисовать, придумывать истории"
        history.append({"role": "assistant", "content": first_question})
        history.append({"role": "user", "content": creative_answer})
        
        second_question = await ask_llm(history)
        print(f"Q2 (после творческого ответа): {second_question}")
        
        # Проверяем, что второй вопрос развивает тему творчества
        creative_keywords = ["создавать", "творить", "придумывать", "вдохновение", "мотивирует"]
        is_following_up = any(keyword in second_question.lower() for keyword in creative_keywords)
        if is_following_up:
            print("✅ Второй вопрос развивает тему из первого ответа")
        else:
            print("❌ Второй вопрос не связан с первым ответом")
            
        print("\n🎉 Тест психологического подхода завершен!")
        
    except Exception as e:
        print(f"❌ Ошибка теста: {e}")

async def test_quiz_analysis():
    """Тестирует анализ ответов"""
    print("\n🔍 Тестирование анализа ответов...")
    
    try:
        from quiz_mod import ask_llm, DEEPSEEK_AVAILABLE
        
        if not DEEPSEEK_AVAILABLE:
            print("❌ DeepSeek API недоступен")
            return
        
        # Симулируем полный диалог
        history = [
            {"role": "assistant", "content": "Представь, что у тебя есть свободный день. Что бы ты предпочел делать?"},
            {"role": "user", "content": "Я бы хотел разобрать старый телефон и понять, как он работает"},
            {"role": "assistant", "content": "Интересно! А что тебе больше нравится - когда ты понимаешь принцип работы или когда можешь что-то улучшить?"},
            {"role": "user", "content": "Мне интересно сначала понять, а потом уже думать как сделать лучше"},
            {"role": "assistant", "content": "А если бы тебе нужно было решить сложную задачу, ты бы предпочел работать один или с командой?"},
            {"role": "user", "content": "Наверное один, чтобы никто не отвлекал и можно было сосредоточиться"},
            {"role": "assistant", "content": "Понимаю. А что тебе интереснее - создавать что-то полностью новое или улучшать существующее?"},
            {"role": "user", "content": "Скорее улучшать, потому что можно понять что не так и исправить"},
            {"role": "assistant", "content": "И последний вопрос: что тебя больше мотивирует - когда твоя работа помогает людям или когда ты решаешь интересную техническую задачу?"},
            {"role": "user", "content": "Больше мотивирует сама техническая задача, это как головоломка"},
            {"role": "user", "content": "Все 5 ответов получены, пора подытожить."}
        ]
        
        final_analysis = await ask_llm(history)
        print("📊 Финальный анализ:")
        print(final_analysis)
        
        # Проверяем структуру ответа
        if "🎯 Анализ твоей личности:" in final_analysis:
            print("✅ Анализ личности присутствует")
        else:
            print("❌ Анализ личности отсутствует")
            
        if "📚 Рекомендуемые направления:" in final_analysis:
            print("✅ Рекомендации направлений присутствуют")
        else:
            print("❌ Рекомендации направлений отсутствуют")
            
        if "💡 Главная рекомендация:" in final_analysis:
            print("✅ Главная рекомендация присутствует")
        else:
            print("❌ Главная рекомендация отсутствует")
            
        print("\n🎯 Анализ завершен!")
        
    except Exception as e:
        print(f"❌ Ошибка анализа: {e}")

if __name__ == "__main__":
    asyncio.run(test_quiz_psychology())
    asyncio.run(test_quiz_analysis()) 