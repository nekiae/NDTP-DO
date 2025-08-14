#!/usr/bin/env python3
"""
🚀 Тестовый скрипт для демонстрации максимально оптимизированной RAG системы
"""

import asyncio
import time
from optimized_rag_system import (
    get_optimized_rag, 
    RAGModes,
    get_optimized_context,
    get_optimized_context_async
)

async def demo_optimized_rag():
    """Демонстрация работы максимально оптимизированной RAG системы"""
    
    print("🚀 ДЕМОНСТРАЦИЯ МАКСИМАЛЬНО ОПТИМИЗИРОВАННОЙ RAG СИСТЕМЫ")
    print("=" * 60)
    
    # Тестовые запросы разных типов
    test_queries = [
        ("Приветствие", "привет"),
        ("Местоположение", "где находится технопарк"),
        ("Контакты", "телефон для связи"),
        ("Направления", "список образовательных направлений"),
        ("Поступление", "как поступить в технопарк"),
        ("Стоимость", "цена обучения"),
        ("Общая информация", "расскажи о технопарке"),
        ("Повторный запрос (кэш)", "где находится технопарк"),  # Тестируем кэш
        ("Похожий запрос (семантический кэш)", "адрес технопарка"),
    ]
    
    total_start_time = time.time()
    results = []
    
    print("\n📋 ТЕСТИРОВАНИЕ РАЗНЫХ ТИПОВ ЗАПРОСОВ:")
    print("-" * 60)
    
    for query_type, query in test_queries:
        print(f"\n🔍 Тип: {query_type}")
        print(f"❓ Запрос: '{query}'")
        
        start_time = time.time()
        context = await get_optimized_context_async(query, RAGModes.ECONOMY)
        processing_time = time.time() - start_time
        
        tokens = len(context) // 3
        results.append({
            'type': query_type,
            'query': query,
            'tokens': tokens,
            'time': processing_time,
            'context': context
        })
        
        print(f"⏱️  Время: {processing_time:.3f}с")
        print(f"📊 Токенов: {tokens}")
        
        if context:
            preview = context[:150] + "..." if len(context) > 150 else context
            print(f"💬 Ответ: {preview}")
        else:
            print("💬 Ответ: (пустой контекст)")
    
    total_time = time.time() - total_start_time
    
    # Статистика системы
    print("\n" + "=" * 60)
    print("📊 СТАТИСТИКА СИСТЕМЫ:")
    print("-" * 60)
    
    rag = get_optimized_rag(RAGModes.ECONOMY)
    stats = rag.get_stats()
    
    print(f"🚀 Общих запросов: {stats.get('total_queries', 0)}")
    print(f"⚡ Попаданий в кэш: {stats.get('cache_hits', 0)}")
    print(f"📈 Cache Hit Rate: {stats.get('cache_hit_rate', '0%')}")
    print(f"💾 Токенов сэкономлено: {stats.get('tokens_saved', 0)}")
    print(f"⏱️  Времени сэкономлено: {stats.get('processing_time_saved', 0):.2f}с")
    print(f"🗃️  Размер точного кэша: {stats.get('exact_cache_size', 0)}")
    print(f"🧠 Семантических групп: {stats.get('semantic_cache_groups', 0)}")
    print(f"🔥 Популярных запросов: {stats.get('popular_cache_size', 0)}")
    
    top_patterns = stats.get('top_patterns', {})
    if top_patterns:
        print(f"📋 Топ паттерны: {', '.join(list(top_patterns.keys())[:3])}")
    
    print(f"\n⏱️  Общее время тестирования: {total_time:.3f}с")
    
    # Анализ производительности
    print("\n" + "=" * 60)
    print("🎯 АНАЛИЗ ПРОИЗВОДИТЕЛЬНОСТИ:")
    print("-" * 60)
    
    cache_hits = sum(1 for r in results if r['time'] < 0.01)  # Быстрые запросы = кэш
    avg_tokens = sum(r['tokens'] for r in results) / len(results)
    avg_time = sum(r['time'] for r in results) / len(results)
    
    print(f"🎯 Средние токены на запрос: {avg_tokens:.1f}")
    print(f"⚡ Среднее время на запрос: {avg_time:.3f}с")
    print(f"🚀 Кэш-хитов в тесте: {cache_hits}")
    print(f"💡 Экономия токенов: {100 - (avg_tokens/10)*100:.1f}% (vs 1000 токенов базовый)")
    
    # Демонстрация разных режимов
    print("\n" + "=" * 60)
    print("🎛️  ДЕМОНСТРАЦИЯ РАЗНЫХ РЕЖИМОВ:")
    print("-" * 60)
    
    test_query = "общая информация о технопарке"
    modes = [
        ("ULTRA_ECONOMY", RAGModes.ULTRA_ECONOMY),
        ("ECONOMY", RAGModes.ECONOMY),
        ("BALANCED", RAGModes.BALANCED),
        ("DETAILED", RAGModes.DETAILED)
    ]
    
    for mode_name, mode_value in modes:
        context = await get_optimized_context_async(test_query, mode_value)
        tokens = len(context) // 3
        print(f"📊 {mode_name}: {tokens} токенов (лимит: {mode_value})")
    
    print("\n🎉 ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА!")
    print("✅ Максимально оптимизированная RAG система готова к использованию!")

def demo_cache_efficiency():
    """Демонстрация эффективности кэширования"""
    print("\n" + "=" * 60)
    print("🗃️  ДЕМОНСТРАЦИЯ ЭФФЕКТИВНОСТИ КЭШИРОВАНИЯ:")
    print("-" * 60)
    
    # Создаем несколько запросов для демонстрации кэша
    queries = [
        "адрес технопарка",
        "где находится технопарк",  # Семантически похожий
        "адрес технопарка",  # Повторный - точный кэш
        "местоположение технопарка",  # Семантически похожий
        "адрес",  # Популярный паттерн
    ]
    
    print("🔍 Тестируем последовательность запросов для кэша...")
    
    for i, query in enumerate(queries, 1):
        start_time = time.time()
        get_optimized_context(query, RAGModes.ECONOMY)
        processing_time = time.time() - start_time
        
        cache_indicator = "⚡ КЭШ" if processing_time < 0.01 else "🔄 ОБРАБОТКА"
        print(f"{i}. '{query}' - {cache_indicator} ({processing_time:.4f}с)")

if __name__ == "__main__":
    print("🚀 Запуск демонстрации максимально оптимизированной RAG системы...")
    
    # Запускаем асинхронную демонстрацию
    asyncio.run(demo_optimized_rag())
    
    # Демонстрация кэширования
    demo_cache_efficiency() 