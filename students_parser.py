import aiohttp
import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from bs4 import BeautifulSoup
import os
import re

logger = logging.getLogger(__name__)

class StudentsParser:
    """Парсер списка учащихся Национального детского технопарка"""
    
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
        self.url = "https://ndtp.by/schedule/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.students_file = "students_list.json"
        self.last_update_file = "last_students_update.txt"
        self.base_url = "https://ndtp.by"
        
        # Дополнительные URL для поиска списков учащихся
        self.additional_urls = [
            "https://ndtp.by/for_incoming_students/",
            "https://ndtp.by/educational-shifts/",
            "https://ndtp.by/students/"
        ]
        
    async def fetch_page(self) -> Optional[str]:
        """Получает HTML страницы со списком учащихся"""
        try:
            logger.info(f"🌐 Запрос к {self.url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url, headers=self.headers, timeout=30) as response:
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"✅ Страница учащихся успешно загружена ({len(content)} символов)")
                        return content
                    else:
                        logger.error(f"❌ Ошибка загрузки страницы учащихся: HTTP {response.status}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("❌ Таймаут при загрузке страницы учащихся")
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке страницы учащихся: {e}")
        
        return None
    
    def parse_students_list(self, html_content: str) -> Dict:
        """Парсит список учащихся со страницы"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            students_info = {
                "title": "Список учащихся НДТП",
                "students": [],
                "total_count": 0,
                "last_updated": datetime.now().isoformat(),
                "source_url": self.url
            }
            
            # Ищем таблицы со списками учащихся
            tables = soup.find_all('table')
            logger.info(f"📊 Найдено таблиц: {len(tables)}")
            
            for table_idx, table in enumerate(tables):
                try:
                    # Ищем заголовок таблицы или контекст
                    table_title = self._get_table_title(table)
                    
                    # Парсим строки таблицы
                    rows = table.find_all('tr')
                    logger.info(f"📋 Таблица {table_idx + 1}: {len(rows)} строк")
                    
                    table_students = []
                    
                    for row_idx, row in enumerate(rows):
                        # Пропускаем заголовки таблицы
                        if row_idx == 0 and self._is_header_row(row):
                            continue
                        
                        student_data = self._parse_student_row(row, table_title)
                        if student_data:
                            table_students.append(student_data)
                    
                    if table_students:
                        students_info["students"].extend(table_students)
                        logger.info(f"✅ Извлечено учащихся из таблицы {table_idx + 1}: {len(table_students)}")
                
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка обработки таблицы {table_idx + 1}: {e}")
                    continue
            
            # Также ищем списки учащихся в других форматах
            self._parse_students_from_lists(soup, students_info)
            
            # Ищем учащихся в параграфах и div'ах
            self._parse_students_from_text(soup, students_info)
            
            students_info["total_count"] = len(students_info["students"])
            logger.info(f"🎯 Всего извлечено учащихся: {students_info['total_count']}")
            
            return students_info
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга списка учащихся: {e}")
            return {
                "title": "Список учащихся НДТП", 
                "students": [],
                "total_count": 0,
                "last_updated": datetime.now().isoformat(),
                "source_url": self.url,
                "error": str(e)
            }
    
    def _get_table_title(self, table) -> str:
        """Получает заголовок таблицы"""
        # Ищем заголовок перед таблицей
        prev_sibling = table.find_previous_sibling(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        if prev_sibling:
            title = prev_sibling.get_text(strip=True)
            # Проверяем, что это образовательное направление
            if 'образовательное направление' in title.lower():
                return title
            # Проверяем все 15 направлений НДТП
            for direction in self.EDUCATIONAL_DIRECTIONS:
                if direction.lower() in title.lower():
                    return f'Образовательное направление «{direction}»'
        
        # Ищем заголовок внутри таблицы
        caption = table.find('caption')
        if caption:
            caption_text = caption.get_text(strip=True)
            # Проверяем направления в заголовке таблицы
            for direction in self.EDUCATIONAL_DIRECTIONS:
                if direction.lower() in caption_text.lower():
                    return f'Образовательное направление «{direction}»'
            return caption_text
        
        # Ищем заголовок в родительском элементе
        parent = table.find_parent(['div', 'section'])
        if parent:
            # Ищем заголовки в родительском элементе
            headers = parent.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            for header in headers:
                title = header.get_text(strip=True)
                if 'образовательное направление' in title.lower():
                    return title
                # Проверяем направления в заголовках
                for direction in self.EDUCATIONAL_DIRECTIONS:
                    if direction.lower() in title.lower():
                        return f'Образовательное направление «{direction}»'
        
        return "Список учащихся"
    
    def _is_header_row(self, row) -> bool:
        """Проверяет, является ли строка заголовком таблицы"""
        cells = row.find_all(['th', 'td'])
        for cell in cells:
            text = cell.get_text(strip=True).lower()
            if any(keyword in text for keyword in ['№', 'номер', 'фамилия', 'имя', 'отчество', 'группа', 'класс']):
                return True
        return False
    
    def _parse_student_row(self, row, table_title: str) -> Optional[Dict]:
        """Парсит строку с данными учащегося"""
        try:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:  # Минимум номер и фамилия
                return None
            
            student_data = {
                "table_title": table_title,
                "row_number": None,
                "full_name": "",
                "group": "",
                "class": "",
                "additional_info": ""
            }
            
            # Обрабатываем ячейки согласно структуре НДТП
            for i, cell in enumerate(cells):
                cell_text = cell.get_text(strip=True)
                if not cell_text:
                    continue
                
                if i == 0:  # Первая ячейка - номер п/п
                    try:
                        student_data["row_number"] = int(cell_text)
                    except ValueError:
                        student_data["row_number"] = cell_text
                
                elif i == 1:  # Вторая ячейка - ФИО
                    student_data["full_name"] = cell_text
                
                elif i == 2:  # Третья ячейка - Учреждение образования
                    student_data["additional_info"] = cell_text
                
                else:  # Дополнительные ячейки
                    if not student_data["additional_info"]:
                        student_data["additional_info"] = cell_text
                    else:
                        student_data["additional_info"] += f" {cell_text}"
            
            # Проверяем, что есть хотя бы имя
            if not student_data["full_name"]:
                return None
            
            return student_data
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга строки учащегося: {e}")
            return None
    
    def _parse_students_from_lists(self, soup, students_info: Dict):
        """Парсит учащихся из списков (ul, ol)"""
        try:
            lists = soup.find_all(['ul', 'ol'])
            
            for list_elem in lists:
                # Ищем заголовок списка
                list_title = self._get_list_title(list_elem)
                
                for li in list_elem.find_all('li', recursive=False):
                    student_text = li.get_text(strip=True)
                    if len(student_text) < 3:
                        continue
                    
                    # Пытаемся извлечь информацию об учащемся
                    student_data = self._extract_student_from_text(student_text, list_title)
                    if student_data:
                        students_info["students"].append(student_data)
                        
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга учащихся из списков: {e}")
    
    def _get_list_title(self, list_elem) -> str:
        """Получает заголовок списка"""
        prev_sibling = list_elem.find_previous_sibling(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        if prev_sibling:
            return prev_sibling.get_text(strip=True)
        return "Список учащихся"
    
    def _parse_students_from_text(self, soup, students_info: Dict):
        """Парсит учащихся из текстовых блоков"""
        try:
            # Ищем параграфы с именами учащихся
            paragraphs = soup.find_all('p')
            
            for p in paragraphs:
                text = p.get_text(strip=True)
                if len(text) < 5:
                    continue
                
                # Разбиваем текст на строки
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                
                for line in lines:
                    if len(line) < 3:
                        continue
                    
                    student_data = self._extract_student_from_text(line, "Список учащихся")
                    if student_data:
                        students_info["students"].append(student_data)
            
            # Ищем учащихся в div'ах с определенными классами
            student_divs = soup.find_all('div', class_=lambda x: x and any(keyword in x.lower() for keyword in ['student', 'учащийся', 'список', 'list']))
            
            for div in student_divs:
                text = div.get_text(strip=True)
                if len(text) < 5:
                    continue
                
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                
                for line in lines:
                    if len(line) < 3:
                        continue
                    
                    student_data = self._extract_student_from_text(line, "Список учащихся")
                    if student_data:
                        students_info["students"].append(student_data)
            
            # Ищем образовательные направления в заголовках
            headers = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            current_direction = "Список учащихся"
            
            for header in headers:
                title = header.get_text(strip=True)
                if 'образовательное направление' in title.lower():
                    current_direction = title
                    logger.info(f"📚 Найдено образовательное направление: {title}")
                    
                    # Ищем учащихся после этого заголовка
                    next_elements = header.find_all_next(['p', 'div', 'table'])
                    for element in next_elements[:10]:  # Ограничиваем поиск
                        if element.name == 'table':
                            break  # Останавливаемся на следующей таблице
                        
                        text = element.get_text(strip=True)
                        if len(text) < 5:
                            continue
                        
                        lines = [line.strip() for line in text.split('\n') if line.strip()]
                        
                        for line in lines:
                            if len(line) < 3:
                                continue
                            
                            student_data = self._extract_student_from_text(line, current_direction)
                            if student_data:
                                students_info["students"].append(student_data)
                        
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга учащихся из текста: {e}")
    
    def _extract_student_from_text(self, text: str, source: str) -> Optional[Dict]:
        """Извлекает информацию об учащемся из текста"""
        try:
            # Очищаем текст от лишних символов
            text = re.sub(r'^\d+\.?\s*', '', text.strip())
            
            if len(text) < 3:
                return None
            
            # Исключаем навигационные элементы и меню
            exclude_keywords = [
                'онлайн заявка', 'научные выходные', 'льготы для выпускников',
                'инженерно-технические центры', 'платные услуги', 'результат поиска',
                'общая информация', 'наблюдательный совет', 'сми о нас', 'одно окно',
                'администрация', 'отделы', 'проживание', 'история и традиции', 'профсоюз',
                'образовательные смены', 'об образовательных сменах', 'образовательные направления',
                'как попасть', 'календарь образовательных смен', 'для поступивших',
                'дистанционное обучение', 'пул перспективных проектов', 'часто задаваемые вопросы',
                'объединения по интересам', 'способы оплаты', 'наши достижения',
                'методическая деятельность', 'выставочная и экскурсионная деятельность',
                'профориентация', 'международные и республиканские мероприятия', 'juniorskills',
                'ицаэ', 'дополнительное образование', 'списочный состав групп учащихся',
                'зачисленных в учреждение образования', 'национальный детский технопарк',
                'обучения в рамках', 'образовательной смены'
            ]
            
            text_lower = text.lower()
            for keyword in exclude_keywords:
                if keyword in text_lower:
                    return None
            
            # Проверяем, что это похоже на имя (содержит пробелы и буквы)
            if not re.search(r'[а-яё]', text, re.IGNORECASE):
                return None
            
            # Проверяем, что это не слишком длинный текст (не навигация)
            if len(text) > 150:
                return None
            
            # Проверяем, что это не образовательное направление
            if 'образовательное направление' in text_lower:
                return None
            
            # Пытаемся разделить на части
            parts = text.split()
            if len(parts) < 2:
                return None
            
            student_data = {
                "table_title": source,
                "row_number": None,
                "full_name": text,
                "group": "",
                "class": "",
                "additional_info": ""
            }
            
            # Если текст начинается с цифры, это может быть номер
            if re.match(r'^\d+', text):
                match = re.match(r'^(\d+)\.?\s*(.+)', text)
                if match:
                    try:
                        student_data["row_number"] = int(match.group(1))
                        student_data["full_name"] = match.group(2)
                    except ValueError:
                        pass
            
            return student_data
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения учащегося из текста: {e}")
            return None
    
    def save_students_cache(self, students_data: Dict) -> bool:
        """Сохраняет список учащихся в кэш"""
        try:
            with open(self.students_file, 'w', encoding='utf-8') as f:
                json.dump(students_data, f, ensure_ascii=False, indent=2)
            
            # Сохраняем время обновления
            with open(self.last_update_file, 'w', encoding='utf-8') as f:
                f.write(datetime.now().isoformat())
            
            logger.info(f"💾 Список учащихся сохранен в кэш ({len(students_data.get('students', []))} записей)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения кэша учащихся: {e}")
            return False
    
    def load_students_cache(self) -> Optional[Dict]:
        """Загружает список учащихся из кэша"""
        try:
            if os.path.exists(self.students_file):
                with open(self.students_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки кэша учащихся: {e}")
        
        return None
    
    def get_last_update_time(self) -> Optional[datetime]:
        """Получает время последнего обновления"""
        try:
            if os.path.exists(self.last_update_file):
                with open(self.last_update_file, 'r', encoding='utf-8') as f:
                    timestamp = f.read().strip()
                    return datetime.fromisoformat(timestamp)
        except Exception as e:
            logger.error(f"❌ Ошибка получения времени обновления: {e}")
        
        return None
    
    def should_update(self, hours_threshold: int = 24) -> bool:
        """Проверяет, нужно ли обновлять данные"""
        last_update = self.get_last_update_time()
        if not last_update:
            return True
        
        time_diff = datetime.now() - last_update
        return time_diff.total_seconds() > hours_threshold * 3600
    
    async def update_students(self, force: bool = False) -> bool:
        """Обновляет список учащихся"""
        try:
            if not force and not self.should_update():
                logger.info("📋 Кэш учащихся актуален, обновление не требуется")
                return True
            
            logger.info("🔄 Обновление списка учащихся...")
            
            # Парсим основную страницу
            html_content = await self.fetch_page()
            if html_content:
                students_data = self.parse_students_list(html_content)
            else:
                students_data = {
                    "title": "Список учащихся НДТП",
                    "students": [],
                    "total_count": 0,
                    "last_updated": datetime.now().isoformat(),
                    "source_url": self.url
                }
            
            # Парсим дополнительные страницы
            for url in self.additional_urls:
                try:
                    logger.info(f"🔍 Поиск учащихся на {url}")
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers=self.headers, timeout=10) as response:
                            if response.status == 200:
                                content = await response.text()
                                additional_data = self.parse_students_list(content)
                                if additional_data and additional_data.get('students'):
                                    students_data['students'].extend(additional_data['students'])
                                    logger.info(f"✅ Найдено {len(additional_data['students'])} учащихся на {url}")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка при парсинге {url}: {e}")
                    continue
            
            # Обновляем общее количество
            students_data["total_count"] = len(students_data["students"])
            students_data["last_updated"] = datetime.now().isoformat()
            
            if students_data["total_count"] == 0:
                logger.warning("⚠️ Не найдено учащихся на всех страницах")
                return False
            
            success = self.save_students_cache(students_data)
            if success:
                logger.info(f"✅ Список учащихся успешно обновлен ({students_data.get('total_count', 0)} записей)")
            else:
                logger.error("❌ Не удалось сохранить список учащихся")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления списка учащихся: {e}")
            return False
    
    def get_students_context(self, query: str = "") -> str:
        """Получает контекст о списке учащихся для ответа"""
        try:
            students_data = self.load_students_cache()
            if not students_data:
                return "❌ Данные о списке учащихся недоступны. Попробуйте обновить данные."
            
            students = students_data.get('students', [])
            total_count = students_data.get('total_count', 0)
            last_updated = students_data.get('last_updated', 'неизвестно')
            
            if not students:
                return "📋 Список учащихся пуст или недоступен."
            
            # Формируем ответ
            response = f"📋 **Список учащихся НДТП**\n\n"
            response += f"Всего учащихся: {total_count}\n"
            response += f"Последнее обновление: {last_updated}\n\n"
            
            if query:
                # Фильтруем по запросу
                filtered_students = []
                query_lower = query.lower()
                
                for student in students:
                    full_name = student.get('full_name', '').lower()
                    group = student.get('group', '').lower()
                    
                    if query_lower in full_name or query_lower in group:
                        filtered_students.append(student)
                
                if filtered_students:
                    response += f"Найдено по запросу '{query}': {len(filtered_students)}\n\n"
                    for i, student in enumerate(filtered_students[:20], 1):  # Ограничиваем 20 результатами
                        response += self._format_student_info(student, i)
                    
                    if len(filtered_students) > 20:
                        response += f"\n... и еще {len(filtered_students) - 20} записей"
                else:
                    response += f"По запросу '{query}' ничего не найдено."
            else:
                # Показываем первые 20 учащихся
                response += "Первые 20 учащихся:\n\n"
                for i, student in enumerate(students[:20], 1):
                    response += self._format_student_info(student, i)
                
                if len(students) > 20:
                    response += f"\n... и еще {len(students) - 20} учащихся"
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения контекста учащихся: {e}")
            return "❌ Ошибка при получении списка учащихся."
    
    def _format_student_info(self, student: Dict, index: int) -> str:
        """Форматирует информацию об учащемся"""
        row_num = student.get('row_number', '')
        name = student.get('full_name', 'Не указано')
        group = student.get('group', '')
        class_info = student.get('class', '')
        
        line = f"{index}. "
        if row_num:
            line += f"[{row_num}] "
        
        line += f"**{name}**"
        
        if group:
            line += f" - {group}"
        
        if class_info:
            line += f" ({class_info})"
        
        return line + "\n"
    
    def get_students_summary(self) -> str:
        """Получает краткую сводку о списке учащихся"""
        try:
            students_data = self.load_students_cache()
            if not students_data:
                return "❌ Данные о списке учащихся недоступны"
            
            total_count = students_data.get('total_count', 0)
            last_updated = students_data.get('last_updated', 'неизвестно')
            
            return f"📋 Список учащихся НДТП: {total_count} записей (обновлено: {last_updated})"
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения сводки учащихся: {e}")
            return "❌ Ошибка получения данных о списке учащихся"
    
    def get_educational_directions_info(self) -> str:
        """Возвращает информацию о всех образовательных направлениях НДТП"""
        info = "🎓 Образовательные направления НДТП:\n\n"
        
        for i, direction in enumerate(self.EDUCATIONAL_DIRECTIONS, 1):
            info += f"{i}. {direction}\n"
        
        info += f"\n📚 Всего направлений: {len(self.EDUCATIONAL_DIRECTIONS)}"
        info += "\n\n💡 Учебная программа по каждому направлению рассчитана на 72 часа."
        info += "\n📅 Занятия проводятся 6 раз в неделю по 4 часа в группах по 7-10 человек."
        
        return info


# Асинхронные функции для удобства использования
async def get_students_context_async(query: str = "") -> str:
    """Асинхронная функция для получения контекста учащихся"""
    parser = StudentsParser()
    return parser.get_students_context(query)


def get_students_context(query: str = "") -> str:
    """Синхронная функция для получения контекста учащихся"""
    parser = StudentsParser()
    return parser.get_students_context(query)


async def force_update_students() -> bool:
    """Принудительное обновление списка учащихся"""
    parser = StudentsParser()
    return await parser.update_students(force=True)


async def students_updater_loop(interval_hours: int = 24):
    """Цикл обновления списка учащихся"""
    parser = StudentsParser()
    
    while True:
        try:
            await parser.update_students()
            logger.info(f"⏰ Следующее обновление списка учащихся через {interval_hours} часов")
            await asyncio.sleep(interval_hours * 3600)
        except Exception as e:
            logger.error(f"❌ Ошибка в цикле обновления учащихся: {e}")
            await asyncio.sleep(3600)  # Ждем час при ошибке


# Функция для тестирования
async def test_students_parser():
    """Тестирует парсер учащихся"""
    parser = StudentsParser()
    
    print("🧪 Тестирование парсера учащихся НДТП...")
    
    # Обновляем данные
    success = await parser.update_students(force=True)
    if success:
        print("✅ Данные учащихся успешно обновлены")
        
        # Получаем контекст
        context = parser.get_students_context()
        print("\n📋 Результат парсинга:")
        print(context)
    else:
        print("❌ Ошибка обновления данных учащихся")


if __name__ == "__main__":
    # Запускаем тест
    asyncio.run(test_students_parser()) 