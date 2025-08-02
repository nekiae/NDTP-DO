#!/usr/bin/env python3
"""
Демонстрационная версия парсера учащихся НДТП
Показывает, как будет работать парсер, если бы на сайте были списки учащихся
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import os

logger = logging.getLogger(__name__)

class DemoStudentsParser:
    """Демонстрационный парсер учащихся НДТП с тестовыми данными"""
    
    # 15 образовательных направлений НДТП
    EDUCATIONAL_DIRECTIONS = [
        "Авиакосмические технологии",
        "Архитектура и дизайн", 
        "Биотехнологии",
        "Виртуальная и дополненная реальность",
        "Зелёная химия",
        "Инженерная экология",
        "Информационная безопасность",
        "Информационные и компьютерные технологии",
        "Лазерные технологии",
        "Машины и двигатели. Автомобилестроение",
        "Наноиндустрия и нанотехнологии",
        "Природные ресурсы",
        "Робототехника",
        "Электроника и связь",
        "Энергетика будущего"
    ]
    
    def __init__(self):
        self.students_file = "demo_students_list.json"
        self.last_update_file = "last_demo_students_update.txt"
        
        # Тестовые данные учащихся согласно реальной структуре НДТП
        self.demo_students = [
            {
                "table_title": "Образовательное направление «Авиакосмические технологии»",
                "row_number": 1,
                "full_name": "Гражевская Яна Сергеевна",
                "group": "",
                "class": "",
                "additional_info": "Витебская обл., ГУО «Глубокская районная гимназия»"
            },
            {
                "table_title": "Образовательное направление «Авиакосмические технологии»",
                "row_number": 2,
                "full_name": "Ёжиков Дмитрий Владимирович",
                "group": "",
                "class": "",
                "additional_info": "Гомельская обл., ГУО «Приборская средняя школа Гомельского района»"
            },
            {
                "table_title": "Образовательное направление «Авиакосмические технологии»",
                "row_number": 3,
                "full_name": "Инкалёва Дарья Михайловна",
                "group": "",
                "class": "",
                "additional_info": "Гродненская обл., ГУО «Средняя школа №5 г.Слонима»"
            },
            {
                "table_title": "Образовательное направление «Авиакосмические технологии»",
                "row_number": 4,
                "full_name": "Кабась Диана Андреевна",
                "group": "",
                "class": "",
                "additional_info": "г.Минск, ГУО «Гимназия №61 г.Минска»"
            },
            {
                "table_title": "Образовательное направление «Авиакосмические технологии»",
                "row_number": 5,
                "full_name": "Казилецкий Максим Сергеевич",
                "group": "",
                "class": "",
                "additional_info": "Гродненская обл., ГУО «Средняя школа №5 г.Слонима»"
            },
            {
                "table_title": "Образовательное направление «Архитектура и дизайн»",
                "row_number": 1,
                "full_name": "Игнатенко Елизавета Сергеевна",
                "group": "",
                "class": "",
                "additional_info": "Гомельская обл., ГУО «Средняя школа №5 г.Светлогорска»"
            },
            {
                "table_title": "Образовательное направление «Архитектура и дизайн»",
                "row_number": 2,
                "full_name": "Каленкович Виктория Николаевна",
                "group": "",
                "class": "",
                "additional_info": "Гомельская обл., ГУО «Гомельский городской лицей №1»"
            },
            {
                "table_title": "Образовательное направление «Архитектура и дизайн»",
                "row_number": 3,
                "full_name": "Колесникова Виктория Дмитриевна",
                "group": "",
                "class": "",
                "additional_info": "Минская обл., ГУО «Смолевичская районная гимназия»"
            },
            {
                "table_title": "Образовательное направление «Архитектура и дизайн»",
                "row_number": 4,
                "full_name": "Пухова Диана",
                "group": "",
                "class": "",
                "additional_info": "Витебская обл., ГУО «Средняя школа №1 г.Полоцка»"
            },
            {
                "table_title": "Образовательное направление «Информационные и компьютерные технологии»",
                "row_number": 1,
                "full_name": "Сидоров Михаил Александрович",
                "group": "",
                "class": "",
                "additional_info": "г.Минск, ГУО «Гимназия №1 г.Минска»"
            },
            {
                "table_title": "Образовательное направление «Информационные и компьютерные технологии»",
                "row_number": 2,
                "full_name": "Петрова Анна Сергеевна",
                "group": "",
                "class": "",
                "additional_info": "г.Минск, ГУО «Лицей БГУ»"
            },
            {
                "table_title": "Образовательное направление «Робототехника»",
                "row_number": 1,
                "full_name": "Козлова Елена Дмитриевна",
                "group": "",
                "class": "",
                "additional_info": "Гродненская обл., ГУО «Гимназия №2 г.Гродно»"
            },
            {
                "table_title": "Образовательное направление «Робототехника»",
                "row_number": 2,
                "full_name": "Новиков Артем Владимирович",
                "group": "",
                "class": "",
                "additional_info": "Брестская обл., ГУО «Лицей №1 г.Бреста»"
            },
            {
                "table_title": "Образовательное направление «Электроника и связь»",
                "row_number": 1,
                "full_name": "Морозова Дарья Игоревна",
                "group": "",
                "class": "",
                "additional_info": "Могилевская обл., ГУО «СШ №15 г.Могилева»"
            },
            {
                "table_title": "Образовательное направление «Электроника и связь»",
                "row_number": 2,
                "full_name": "Волков Денис Петрович",
                "group": "",
                "class": "",
                "additional_info": "Витебская обл., ГУО «Гимназия №3 г.Витебска»"
            }
        ]
    
    def save_demo_students(self) -> bool:
        """Сохраняет демонстрационные данные учащихся"""
        try:
            students_data = {
                "title": "Демонстрационный список учащихся НДТП",
                "students": self.demo_students,
                "total_count": len(self.demo_students),
                "last_updated": datetime.now().isoformat(),
                "source_url": "https://ndtp.by/schedule/",
                "note": "Это демонстрационные данные для показа работы парсера"
            }
            
            with open(self.students_file, 'w', encoding='utf-8') as f:
                json.dump(students_data, f, ensure_ascii=False, indent=2)
            
            # Сохраняем время обновления
            with open(self.last_update_file, 'w', encoding='utf-8') as f:
                f.write(datetime.now().isoformat())
            
            logger.info(f"💾 Демонстрационные данные учащихся сохранены ({len(self.demo_students)} записей)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения демонстрационных данных: {e}")
            return False
    
    def load_demo_students(self) -> Optional[Dict]:
        """Загружает демонстрационные данные учащихся"""
        try:
            if os.path.exists(self.students_file):
                with open(self.students_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки демонстрационных данных: {e}")
        
        return None
    
    def get_demo_students_context(self, query: str = "") -> str:
        """Получает контекст о демонстрационном списке учащихся"""
        try:
            students_data = self.load_demo_students()
            if not students_data:
                # Создаем демонстрационные данные
                self.save_demo_students()
                students_data = self.load_demo_students()
            
            students = students_data.get('students', [])
            total_count = students_data.get('total_count', 0)
            last_updated = students_data.get('last_updated', 'неизвестно')
            
            if not students:
                return "📋 Демонстрационный список учащихся пуст."
            
            # Формируем ответ
            response = f"📋 **Демонстрационный список учащихся НДТП**\n\n"
            response += f"Всего учащихся: {total_count}\n"
            response += f"Последнее обновление: {last_updated}\n"
            response += f"*Это демонстрационные данные для показа работы парсера*\n\n"
            
            if query:
                # Фильтруем по запросу
                filtered_students = []
                query_lower = query.lower()
                
                for student in students:
                    full_name = student.get('full_name', '').lower()
                    group = student.get('group', '').lower()
                    class_info = student.get('class', '').lower()
                    
                    if (query_lower in full_name or 
                        query_lower in group or 
                        query_lower in class_info):
                        filtered_students.append(student)
                
                if filtered_students:
                    response += f"Найдено по запросу '{query}': {len(filtered_students)}\n\n"
                    for i, student in enumerate(filtered_students[:20], 1):
                        response += self._format_demo_student_info(student, i)
                    
                    if len(filtered_students) > 20:
                        response += f"\n... и еще {len(filtered_students) - 20} записей"
                else:
                    response += f"По запросу '{query}' ничего не найдено."
            else:
                # Показываем первые 15 учащихся
                response += "Первые 15 учащихся:\n\n"
                for i, student in enumerate(students[:15], 1):
                    response += self._format_demo_student_info(student, i)
                
                if len(students) > 15:
                    response += f"\n... и еще {len(students) - 15} учащихся"
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения демонстрационного контекста: {e}")
            return "❌ Ошибка при получении демонстрационного списка учащихся."
    
    def _format_demo_student_info(self, student: Dict, index: int) -> str:
        """Форматирует информацию о демонстрационном учащемся"""
        row_num = student.get('row_number', '')
        name = student.get('full_name', 'Не указано')
        direction = student.get('table_title', '')
        additional = student.get('additional_info', '')
        
        line = f"{index}. "
        if row_num:
            line += f"[{row_num}] "
        
        line += f"**{name}**"
        
        if additional:
            line += f" - {additional}"
        
        # Добавляем образовательное направление в скобках
        if direction and 'образовательное направление' in direction:
            direction_short = direction.replace('Образовательное направление «', '').replace('»', '')
            line += f" ({direction_short})"
        
        return line + "\n"
    
    def get_demo_students_summary(self) -> str:
        """Получает краткую сводку о демонстрационном списке учащихся"""
        try:
            students_data = self.load_demo_students()
            if not students_data:
                return "❌ Демонстрационные данные о списке учащихся недоступны"
            
            total_count = students_data.get('total_count', 0)
            last_updated = students_data.get('last_updated', 'неизвестно')
            
            return f"📋 Демонстрационный список учащихся НДТП: {total_count} записей (обновлено: {last_updated})"
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения демонстрационной сводки: {e}")
            return "❌ Ошибка получения демонстрационных данных о списке учащихся"
    
    def get_educational_directions_info(self) -> str:
        """Возвращает информацию о всех образовательных направлениях НДТП"""
        info = "🎓 Образовательные направления НДТП:\n\n"
        
        for i, direction in enumerate(self.EDUCATIONAL_DIRECTIONS, 1):
            info += f"{i}. {direction}\n"
        
        info += f"\n📚 Всего направлений: {len(self.EDUCATIONAL_DIRECTIONS)}"
        info += "\n\n💡 Учебная программа по каждому направлению рассчитана на 72 часа."
        info += "\n📅 Занятия проводятся 6 раз в неделю по 4 часа в группах по 7-10 человек."
        
        return info


# Демонстрационные функции
def get_demo_students_context(query: str = "") -> str:
    """Синхронная функция для получения демонстрационного контекста учащихся"""
    parser = DemoStudentsParser()
    return parser.get_demo_students_context(query)


async def get_demo_students_context_async(query: str = "") -> str:
    """Асинхронная функция для получения демонстрационного контекста учащихся"""
    parser = DemoStudentsParser()
    return parser.get_demo_students_context(query)


async def demo_students_parser():
    """Демонстрирует работу парсера учащихся"""
    parser = DemoStudentsParser()
    
    print("🎯 Демонстрация парсера учащихся НДТП")
    print("=" * 50)
    
    # Показываем информацию о направлениях
    directions_info = parser.get_educational_directions_info()
    print("\n🎓 Информация о направлениях:")
    print(directions_info)
    
    # Сохраняем демонстрационные данные
    success = parser.save_demo_students()
    if success:
        print("\n✅ Демонстрационные данные учащихся созданы")
        
        # Показываем сводку
        summary = parser.get_demo_students_summary()
        print(f"\n📋 {summary}")
        
        # Показываем полный список
        context = parser.get_demo_students_context()
        print(f"\n📋 Полный список:")
        print(context)
        
        # Показываем поиск
        search_context = parser.get_demo_students_context("10 класс")
        print(f"\n🔍 Поиск по '10 класс':")
        print(search_context)
        
        return True
    else:
        print("❌ Не удалось создать демонстрационные данные")
        return False


if __name__ == "__main__":
    # Запускаем демонстрацию
    asyncio.run(demo_students_parser()) 