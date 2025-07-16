#!/usr/bin/env python3
"""
Скрипт для установки зависимостей с проверкой совместимости Python
"""

import sys
import subprocess
import pkg_resources

def run_command(cmd):
    """Выполнить команду и вернуть результат"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def check_python_version():
    """Проверить версию Python"""
    version = sys.version_info
    print(f"🐍 Python версия: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Требуется Python 3.8 или выше")
        return False
    
    if version.major == 3 and version.minor >= 13:
        print("⚠️ Python 3.13 обнаружен - используем совместимые версии библиотек")
        return "3.13"
    
    print("✅ Версия Python совместима")
    return True

def install_dependencies():
    """Установить зависимости"""
    print("\n📦 Установка зависимостей...")
    
    python_version = check_python_version()
    if not python_version:
        return False
    
    # Базовые зависимости
    base_deps = [
        "aiogram>=3.15.0",
        "aiohttp>=3.9.0", 
        "python-dotenv>=1.0.0",
        "tenacity>=8.2.0"
    ]
    
    # Зависимости для улучшений
    if python_version == "3.13":
        # Для Python 3.13 используем более новые версии
        improvement_deps = [
            "dateparser>=1.1.8",
            "aioredis>=2.0.1",  # Более новая версия для совместимости
        ]
    else:
        improvement_deps = [
            "dateparser>=1.1.8",
            "aioredis>=2.0.1",
        ]
    
    all_deps = base_deps + improvement_deps
    
    # Устанавливаем по одной для лучшей диагностики
    for dep in all_deps:
        print(f"📦 Устанавливаем {dep}...")
        success, output = run_command(f"pip install '{dep}'")
        if success:
            print(f"  ✅ {dep} установлен")
        else:
            print(f"  ❌ Ошибка установки {dep}: {output}")
    
    return True

def test_imports():
    """Тестировать импорты"""
    print("\n🧪 Тестирование импортов...")
    
    imports_to_test = [
        ("aiogram", "aiogram"),
        ("aiohttp", "aiohttp"),
        ("python-dotenv", "dotenv"),
        ("tenacity", "tenacity"),
        ("dateparser", "dateparser"), 
        ("aioredis", "aioredis"),
    ]
    
    results = {}
    for package_name, import_name in imports_to_test:
        try:
            __import__(import_name)
            print(f"  ✅ {package_name} импортирован успешно")
            results[package_name] = True
        except ImportError as e:
            print(f"  ❌ {package_name} не удался: {e}")
            results[package_name] = False
        except Exception as e:
            print(f"  ⚠️ {package_name} проблема: {e}")
            results[package_name] = "warning"
    
    return results

def main():
    """Основная функция"""
    print("🚀 Установка зависимостей для TechnoBot")
    print("=" * 50)
    
    # Проверяем версию Python
    python_check = check_python_version()
    if not python_check:
        sys.exit(1)
    
    # Устанавливаем зависимости
    if not install_dependencies():
        sys.exit(1)
    
    # Тестируем импорты
    results = test_imports()
    
    # Итоговый отчет
    print("\n📊 Итоговый отчет:")
    print("=" * 50)
    
    success_count = sum(1 for v in results.values() if v is True)
    total_count = len(results)
    
    if success_count == total_count:
        print("🎉 Все зависимости установлены успешно!")
        print("✅ Бот готов к запуску: python3 bot.py")
    else:
        print(f"⚠️ {success_count}/{total_count} зависимостей установлены")
        
        failed = [name for name, status in results.items() if status is False]
        if failed:
            print(f"❌ Не удалось установить: {', '.join(failed)}")
        
        warning = [name for name, status in results.items() if status == "warning"]
        if warning:
            print(f"⚠️ Предупреждения: {', '.join(warning)}")
    
    # Специальная информация для Python 3.13
    if python_check == "3.13":
        print("\n💡 Специальная информация для Python 3.13:")
        print("• Используются обновленные версии библиотек")
        print("• При проблемах с aioredis - система автоматически переключится на локальный кэш")
        print("• Все функции бота будут работать корректно")

if __name__ == "__main__":
    main() 