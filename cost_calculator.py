#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Калькулятор стоимости работы ТехноБота
На основе реальных данных из логов
"""

# Цены DeepSeek API (за 1M токенов)
DEEPSEEK_PRICES = {
    "standard": {  # UTC 00:30-16:30 (обычное время)
        "input_cache_hit": 0.07,
        "input_cache_miss": 0.27,
        "output": 1.10
    },
    "discount": {  # UTC 16:30-00:30 (скидка 50%)
        "input_cache_hit": 0.035,
        "input_cache_miss": 0.135,
        "output": 0.550
    }
}

# Компоненты токенов (на основе реальных данных)
TOKEN_COMPONENTS = {
    "system_prompt": 355,  # Фиксированный системный промпт
    "user_query_simple": 5,  # "привет"
    "user_query_medium": 15,  # "расскажи о программах"
    "user_query_complex": 25,  # "расскажи по сентябрьскую смену"
    
    # RAG контекст (символы / 4 = токены для русского)
    "rag_context_none": 0,  # Приветствия
    "rag_context_small": 1000 // 4,  # 250 токенов - базовая информация
    "rag_context_medium": 8000 // 4,  # 2000 токенов - средний запрос
    "rag_context_large": 19727 // 4,  # 4932 токенов - сложный запрос (реальные данные)
    
    # Ответы бота
    "response_short": 238 // 4,  # 60 токенов - короткий ответ (реальные данные)
    "response_medium": 800 // 4,  # 200 токенов - средний ответ
    "response_long": 1200 // 4,  # 300 токенов - длинный ответ
}

# Типы запросов и их вероятности
QUERY_TYPES = {
    "simple": {  # Приветствия, /start, простые команды
        "probability": 0.30,
        "input_tokens": TOKEN_COMPONENTS["system_prompt"] + TOKEN_COMPONENTS["user_query_simple"] + TOKEN_COMPONENTS["rag_context_none"],
        "output_tokens": TOKEN_COMPONENTS["response_short"]
    },
    "medium": {  # Вопросы о программах, поступлении
        "probability": 0.50,
        "input_tokens": TOKEN_COMPONENTS["system_prompt"] + TOKEN_COMPONENTS["user_query_medium"] + TOKEN_COMPONENTS["rag_context_medium"],
        "output_tokens": TOKEN_COMPONENTS["response_medium"]
    },
    "complex": {  # Сложные запросы о сменах, подробная информация
        "probability": 0.20,
        "input_tokens": TOKEN_COMPONENTS["system_prompt"] + TOKEN_COMPONENTS["user_query_complex"] + TOKEN_COMPONENTS["rag_context_large"],
        "output_tokens": TOKEN_COMPONENTS["response_long"]
    }
}

def calculate_weighted_average():
    """Вычисляет средневзвешенное количество токенов на запрос"""
    total_input = 0
    total_output = 0
    
    for query_type, data in QUERY_TYPES.items():
        prob = data["probability"]
        total_input += data["input_tokens"] * prob
        total_output += data["output_tokens"] * prob
    
    return total_input, total_output

def calculate_monthly_cost(requests_per_day, cache_hit_rate=0.3, discount_hours_rate=0.4):
    """
    Рассчитывает месячную стоимость
    
    Args:
        requests_per_day: Количество запросов в день
        cache_hit_rate: Доля запросов с cache hit (0.0-1.0)
        discount_hours_rate: Доля запросов в льготные часы (0.0-1.0)
    """
    
    # Средневзвешенные токены на запрос
    avg_input_tokens, avg_output_tokens = calculate_weighted_average()
    
    # Месячные запросы
    monthly_requests = requests_per_day * 30
    
    # Общее количество токенов в месяц
    total_input_tokens = monthly_requests * avg_input_tokens
    total_output_tokens = monthly_requests * avg_output_tokens
    
    # Разделение input токенов на cache hit/miss
    cache_hit_tokens = total_input_tokens * cache_hit_rate
    cache_miss_tokens = total_input_tokens * (1 - cache_hit_rate)
    
    # Разделение по времени суток (обычное vs скидка)
    standard_rate = 1 - discount_hours_rate
    
    # Стоимость в обычные часы
    standard_cost = (
        (cache_hit_tokens * standard_rate / 1_000_000) * DEEPSEEK_PRICES["standard"]["input_cache_hit"] +
        (cache_miss_tokens * standard_rate / 1_000_000) * DEEPSEEK_PRICES["standard"]["input_cache_miss"] +
        (total_output_tokens * standard_rate / 1_000_000) * DEEPSEEK_PRICES["standard"]["output"]
    )
    
    # Стоимость в льготные часы
    discount_cost = (
        (cache_hit_tokens * discount_hours_rate / 1_000_000) * DEEPSEEK_PRICES["discount"]["input_cache_hit"] +
        (cache_miss_tokens * discount_hours_rate / 1_000_000) * DEEPSEEK_PRICES["discount"]["input_cache_miss"] +
        (total_output_tokens * discount_hours_rate / 1_000_000) * DEEPSEEK_PRICES["discount"]["output"]
    )
    
    total_cost = standard_cost + discount_cost
    
    return {
        "requests_per_day": requests_per_day,
        "monthly_requests": monthly_requests,
        "avg_input_tokens": avg_input_tokens,
        "avg_output_tokens": avg_output_tokens,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "cache_hit_tokens": cache_hit_tokens,
        "cache_miss_tokens": cache_miss_tokens,
        "standard_cost": standard_cost,
        "discount_cost": discount_cost,
        "total_cost": total_cost,
        "cost_per_request": total_cost / monthly_requests,
        "cache_hit_rate": cache_hit_rate,
        "discount_hours_rate": discount_hours_rate
    }

def print_cost_analysis():
    """Выводит анализ стоимости для разных сценариев нагрузки"""
    
    print("🤖 АНАЛИЗ СТОИМОСТИ TECHNO-БОТА")
    print("=" * 60)
    
    # Показываем компоненты токенов
    print("\n📊 КОМПОНЕНТЫ ТОКЕНОВ (на основе реальных данных):")
    print(f"├─ Системный промпт: {TOKEN_COMPONENTS['system_prompt']} токенов")
    print(f"├─ Пользовательский запрос: {TOKEN_COMPONENTS['user_query_simple']}-{TOKEN_COMPONENTS['user_query_complex']} токенов")
    print(f"├─ RAG контекст: 0-{TOKEN_COMPONENTS['rag_context_large']} токенов")
    print(f"└─ Ответ бота: {TOKEN_COMPONENTS['response_short']}-{TOKEN_COMPONENTS['response_long']} токенов")
    
    # Показываем средневзвешенные значения
    avg_input, avg_output = calculate_weighted_average()
    print(f"\n⚖️ СРЕДНЕВЗВЕШЕННЫЕ ЗНАЧЕНИЯ:")
    print(f"├─ Средний input: {avg_input:.0f} токенов")
    print(f"├─ Средний output: {avg_output:.0f} токенов")
    print(f"└─ Всего на запрос: {avg_input + avg_output:.0f} токенов")
    
    # Сценарии нагрузки
    scenarios = [
        ("🐌 Низкая нагрузка", 10),
        ("📈 Средняя нагрузка", 50), 
        ("🚀 Высокая нагрузка", 150),
        ("💥 Пиковая нагрузка", 500),
        ("🔥 Экстремальная нагрузка", 1000)
    ]
    
    print(f"\n💰 РАСЧЕТ СТОИМОСТИ ПО СЦЕНАРИЯМ:")
    print("-" * 60)
    
    for scenario_name, requests_per_day in scenarios:
        print(f"\n{scenario_name} ({requests_per_day} запросов/день)")
        
        # Расчет с разными настройками кеширования
        cache_scenarios = [
            ("Плохое кеширование", 0.1, 0.3),
            ("Среднее кеширование", 0.3, 0.4), 
            ("Хорошее кеширование", 0.6, 0.5)
        ]
        
        for cache_name, cache_hit_rate, discount_rate in cache_scenarios:
            result = calculate_monthly_cost(requests_per_day, cache_hit_rate, discount_rate)
            
            print(f"  {cache_name}:")
            print(f"    💵 Месячная стоимость: ${result['total_cost']:.2f}")
            print(f"    💸 Стоимость за запрос: ${result['cost_per_request']:.4f}")
            print(f"    📊 Cache Hit Rate: {cache_hit_rate*100:.0f}%")
            print(f"    🕒 Льготные часы: {discount_rate*100:.0f}%")
    
    # Детальный анализ для среднего сценария
    print(f"\n🔍 ДЕТАЛЬНЫЙ АНАЛИЗ (Средняя нагрузка)")
    print("-" * 60)
    
    result = calculate_monthly_cost(50, 0.3, 0.4)
    
    print(f"📈 Объемы:")
    print(f"├─ Запросов в месяц: {result['monthly_requests']:,}")
    print(f"├─ Input токенов в месяц: {result['total_input_tokens']:,}")
    print(f"├─ Output токенов в месяц: {result['total_output_tokens']:,}")
    print(f"└─ Всего токенов в месяц: {result['total_input_tokens'] + result['total_output_tokens']:,}")
    
    print(f"\n💰 Разбивка стоимости:")
    print(f"├─ Обычные часы: ${result['standard_cost']:.2f}")
    print(f"├─ Льготные часы: ${result['discount_cost']:.2f}")
    print(f"└─ ИТОГО: ${result['total_cost']:.2f}")
    
    # Рекомендации по оптимизации
    print(f"\n💡 РЕКОМЕНДАЦИИ ПО ОПТИМИЗАЦИИ:")
    print("├─ 🕒 Максимально используйте льготные часы (16:30-00:30 UTC)")
    print("├─ 📦 Настройте кеширование для повторяющихся запросов")
    print("├─ ✂️ Сократите размер RAG контекста для простых запросов")
    print("├─ 🎯 Оптимизируйте системный промпт")
    print("└─ 📊 Мониторьте статистику использования")

if __name__ == "__main__":
    print_cost_analysis() 