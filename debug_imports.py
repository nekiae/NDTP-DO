#!/usr/bin/env python3
"""
Поэтапная проверка импортов из bot.py
"""
import time as time_module
import sys

def test_import(module_name, description):
    """Тест импорта модуля с логированием"""
    print(f"🔍 Проверяем {description}...")
    start_time = time_module.time()
    
    try:
        if module_name == "base_imports":
            import os
            import logging
            import sys
            from typing import Optional
            import asyncio
            import time
            from datetime import datetime
            from dotenv import load_dotenv
            
        elif module_name == "aiohttp":
            import aiohttp
            
        elif module_name == "aiogram":
            from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
            from aiogram.filters import Command
            from aiogram.fsm.context import FSMContext
            from aiogram.fsm.state import State, StatesGroup
            from aiogram.fsm.storage.memory import MemoryStorage
            from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
            
        elif module_name == "improvements":
            import re
            from tenacity import retry, wait_exponential, stop_after_attempt
            
        elif module_name == "dateparser":
            try:
                import dateparser
            except ImportError:
                print("  ⚠️ dateparser недоступен")
                
        elif module_name == "operator_handler":
            from operator_handler import operator_handler, OperatorState, UserStatus
            
        elif module_name == "rag_system":
            from rag_system import rag_system
            
        elif module_name == "schedule_parser":
            from schedule_parser import get_schedule_context_async, get_schedule_context, force_update_schedule, schedule_updater_loop
            
        elif module_name == "documents_parser":
            from documents_parser import get_documents_context_async, get_documents_context, force_update_documents, documents_updater_loop
            
        elif module_name == "lists_parser":
            from lists_parser import search_name_in_lists, get_lists_stats, update_lists_cache, initialize_lists_parser
            
        elif module_name == "calendar_module":
            from calendar_module import get_calendar_interface, get_shift_info, get_notification_settings_interface
            
        elif module_name == "notification_system":
            from notification_system import notification_system
            
        elif module_name == "optimized_rag":
            from optimized_rag_system import get_optimized_context_async, get_optimized_context, get_optimized_rag, RAGModes
            
        elif module_name == "modern_rag":
            from modern_rag_system import ModernRAGSystem, get_context_for_query_async, set_global_instance
            
        elapsed = time_module.time() - start_time
        print(f"  ✅ {description} - OK ({elapsed:.2f}s)")
        return True
        
    except Exception as e:
        elapsed = time_module.time() - start_time
        print(f"  ❌ {description} - ОШИБКА ({elapsed:.2f}s): {e}")
        return False

def main():
    print("🧪 Поэтапная проверка импортов из bot.py")
    print("=" * 60)
    
    # Список модулей для проверки
    modules_to_test = [
        ("base_imports", "Базовые импорты"),
        ("aiohttp", "aiohttp"),
        ("aiogram", "aiogram"),
        ("improvements", "Улучшения (tenacity, re)"),
        ("dateparser", "dateparser"),
        ("operator_handler", "Обработчик операторов"),
        ("rag_system", "RAG система"),
        ("schedule_parser", "Парсер расписания"),
        ("documents_parser", "Парсер документов"),
        ("lists_parser", "Парсер списков"),
        ("calendar_module", "Модуль календаря"),
        ("notification_system", "Система уведомлений"),
        ("optimized_rag", "Оптимизированная RAG"),
        ("modern_rag", "Современная RAG"),
    ]
    
    success_count = 0
    total_count = len(modules_to_test)
    
    for module_name, description in modules_to_test:
        success = test_import(module_name, description)
        if success:
            success_count += 1
        print()
    
    print("=" * 60)
    print(f"📊 Результат: {success_count}/{total_count} модулей загружено успешно")
    
    if success_count == total_count:
        print("✅ Все модули загружены успешно!")
    else:
        print("❌ Есть проблемы с некоторыми модулями")

if __name__ == "__main__":
    main() 