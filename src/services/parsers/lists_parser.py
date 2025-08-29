import asyncio
import io
import json
import logging
import os
import re
from datetime import datetime

import PyPDF2
import requests
from bs4 import BeautifulSoup

from src.core.config import config

try:
    from pdf2image import convert_from_bytes
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logging.warning("⚠️ OCR библиотеки недоступны (pdf2image, pytesseract)")

# Настройка логирования
logger = logging.getLogger(__name__)

"""
📋 ПАРСЕР СПИСКОВ ТЕХНОПАРКА

🔍 ЛОГИКА ПОИСКА (обновлено):
• При поиске одного слова - ищет это слово как отдельное слово (с границами)
• При поиске нескольких слов - ищет их ТОЛЬКО как целую фразу
• Поддерживает обратный порядок для двух слов (Имя Фамилия ↔ Фамилия Имя)
• НЕ находит документы, где слова есть по отдельности в разных местах

✅ Примеры правильного поиска:
• "Иванов Петр" → найдет "Иванов Петр Сергеевич"
• "Петр Иванов" → найдет "Иванов Петр Сергеевич" (обратный порядок)
• "Иванов" → найдет любые записи с "Иванов"

❌ Что НЕ найдет:
• "Иванов Анна" не найдет документ, где есть "Иванов" в одном месте и "Анна" в другом
"""

# Базовый URL сайта
BASE_URL = "https://ndtp.by"
SCHEDULE_URL = f"{BASE_URL}/schedule/"

# Добавляем константы для кэширования
PDF_CACHE_FILE = config.cache_dir / 'lists_cache.json'
CACHE_LIFETIME = 3600  # 1 час в секундах
PDF_CACHE_EXPIRY = 86400  # 24 часа в секундах

class ListsParser:
    """Класс для парсинга и поиска в списках участников технопарка"""
    
    def __init__(self):
        self.ensure_cache_dir()
        self.pdf_cache = self.load_pdf_cache()
        self.last_update = None
    
    @staticmethod
    def ensure_cache_dir():
        """Создание директории для кэша если её нет"""
        try:
            cache_dir = config.cache_dir
            if not cache_dir.exists():
                cache_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"📁 Создана директория для кэша: {cache_dir}")
        except Exception as e:
            logger.error(f"❌ Ошибка создания директории кэша: {e}")
    
    def load_pdf_cache(self):
        """Загрузка кэша PDF-файлов"""
        try:
            if os.path.exists(PDF_CACHE_FILE):
                with open(PDF_CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    logger.info(f"📚 Загружен кэш PDF-файлов: {len(cache_data)} смен")
                    return cache_data
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке кэша PDF: {e}")
        return {}
    
    def save_pdf_cache(self, cache):
        """Сохранение кэша PDF-файлов"""
        try:
            with open(PDF_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            logger.info(f"💾 Кэш PDF-файлов сохранен: {len(cache)} смен")
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении кэша PDF: {e}")
    
    async def get_shifts_info(self):
        """Получение информации о всех сменах с сайта"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            }
            
            logger.info(f"🌐 Запрос к {SCHEDULE_URL}")
            response = requests.get(SCHEDULE_URL, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            shifts = []
            panels = soup.find_all('div', class_='panel-default')
            
            logger.info(f"📋 Найдено панелей: {len(panels)}")
            
            for panel in panels:
                try:
                    title_elem = panel.find(['h1', 'h2', 'h3', 'h4', 'h5'], 
                        string=lambda x: x and ('смена' in x.lower() or 'смены' in x.lower()))
                    
                    if not title_elem:
                        continue
                    
                    shift_name = title_elem.text.strip()
                    panel_body = panel.find('div', class_='panel-body')
                    
                    if not panel_body:
                        continue
                    
                    # Поиск дат
                    dates = self._extract_dates(panel_body)
                    if not dates:
                        continue
                    
                    # Поиск информации о заявках
                    application_period = self._extract_application_info(panel_body)
                    if not application_period:
                        continue
                    
                    # Поиск документов
                    documents = self._extract_documents(panel_body)
                    if not documents:
                        continue
                    
                    shifts.append({
                        'name': shift_name,
                        'dates': dates,
                        'application_period': application_period,
                        'documents': documents
                    })
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка при обработке панели: {e}")
                    continue
            
            logger.info(f"✅ Обработано смен: {len(shifts)}")
            return shifts
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о сменах: {e}")
            return []
    
    def _extract_dates(self, panel_body):
        """Извлечение дат из панели"""
        date_patterns = [
            r'\d{2}[\.,-]\d{2}[\.,-]202\d',
            r'\d{2}[\.,-]\d{2}',
            r'\d+\s*[–-]\s*\d+',
        ]
        
        for pattern in date_patterns:
            for elem in panel_body.find_all(['h5', 'p', 'div']):
                if elem.text and re.search(pattern, elem.text):
                    return elem.text.strip()
        return None
    
    def _extract_application_info(self, panel_body):
        """Извлечение информации о приеме заявок"""
        for p in panel_body.find_all(['p', 'div']):
            text = p.text.lower()
            if any(word in text for word in ['прием', 'заявк', 'регистрац', 'подач']):
                return p.text.strip()
        return None
    
    def _extract_documents(self, panel_body):
        """Извлечение документов из панели"""
        documents = []
        
        for link in panel_body.find_all('a', href=True):
            href = link['href']
            
            if any(ext in href.lower() for ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx']) or \
               any(keyword in href.lower() for keyword in ['download', 'media_dl', 'document']):
                doc_url = href if href.startswith('http') else f"{BASE_URL}{href}"
                
                doc_name = link.text.strip()
                if not doc_name and link.parent:
                    doc_name = link.parent.text.strip()
                if doc_name:
                    doc_name = ' '.join(doc_name.split())
                    if not any(d['url'] == doc_url for d in documents):
                        documents.append({
                            'name': doc_name,
                            'url': doc_url,
                            'type': self._detect_document_type(doc_name, doc_url)
                        })
        
        return documents
    
    def _detect_document_type(self, doc_name, doc_url):
        """Определение типа документа"""
        name_lower = doc_name.lower()
        
        # Ключевые слова для определения списков участников
        student_list_keywords = [
            'список', 'зачислен', 'групп', 'участник', 'допущен', 
            'состав', 'учащи', 'поступивш', 'абитуриент', 'результат',
            'принят', 'отобран', 'кандидат'
        ]
        
        if any(keyword in name_lower for keyword in student_list_keywords):
            return 'student_list'
        elif any(keyword in name_lower for keyword in ['программа', 'план', 'описание']):
            return 'program'
        elif any(keyword in name_lower for keyword in ['заявлен', 'анкет', 'форм']):
            return 'application'
        else:
            return 'other'
    
    async def extract_text_from_pdf(self, url, force_ocr=False):
        """Извлечение текста из PDF-файла"""
        try:
            logger.info(f"📄 Извлекаем текст из PDF: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            pdf_content = response.content
            text = ""
            
            # Пробуем стандартное извлечение
            try:
                with io.BytesIO(pdf_content) as file_stream:
                    reader = PyPDF2.PdfReader(file_stream)
                    for page in reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
            except Exception as e:
                logger.warning(f"⚠️ Стандартное извлечение не удалось: {e}")
            
            # Если OCR доступен и нужен
            if (force_ocr or len(text.strip()) < 100) and OCR_AVAILABLE:
                try:
                    logger.info("🔍 Используем OCR для извлечения текста")
                    images = convert_from_bytes(pdf_content)
                    ocr_text = ""
                    for i, image in enumerate(images):
                        logger.info(f"📖 Обрабатываем страницу {i+1}/{len(images)}")
                        page_text = pytesseract.image_to_string(image, lang='rus')
                        ocr_text += page_text + "\n"
                    
                    if len(ocr_text.strip()) > len(text.strip()):
                        text = ocr_text
                        logger.info(f"✅ OCR дал лучший результат: {len(text)} символов")
                except Exception as e:
                    logger.warning(f"⚠️ OCR не удался: {e}")
            
            logger.info(f"✅ Извлечено {len(text)} символов из PDF")
            return text if text.strip() else None
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения текста из PDF {url}: {e}")
            return None
    
    async def preload_pdf_files(self, force_reload=False):
        """Предзагрузка PDF-файлов"""
        try:
            logger.info("🚀 Начинаем предзагрузку PDF-файлов...")
            
            current_time = datetime.now().timestamp()
            shifts = await self.get_shifts_info()
            
            if not shifts:
                logger.warning("⚠️ Не найдено смен для загрузки")
                return self.pdf_cache
            
            total_docs = sum(len(shift['documents']) for shift in shifts if shift['documents'])
            processed_docs = 0
            
            logger.info(f"📊 Найдено {len(shifts)} смен, {total_docs} документов")
            
            for shift in shifts:
                shift_name = shift['name']
                if shift_name not in self.pdf_cache:
                    self.pdf_cache[shift_name] = {}
                
                logger.info(f"📝 Обрабатываем смену: {shift_name}")
                
                for doc in shift['documents']:
                    processed_docs += 1
                    doc_url = doc['url']
                    doc_name = doc['name']
                    doc_type = doc['type']
                    
                    logger.info(f"[{processed_docs}/{total_docs}] {doc_name}")
                    
                    is_pdf = doc_url.lower().endswith('.pdf') or ('media_dl=' in doc_url.lower())
                    
                    if is_pdf:
                        # Проверяем кэш
                        if not force_reload and doc_url in self.pdf_cache[shift_name]:
                            cached_doc = self.pdf_cache[shift_name][doc_url]
                            if current_time - cached_doc['timestamp'] < PDF_CACHE_EXPIRY:
                                logger.info("📚 Используем кэшированную версию")
                                continue
                        
                        is_student_list = doc_type == 'student_list'
                        
                        try:
                            text = await self.extract_text_from_pdf(doc_url, force_ocr=is_student_list)
                            if text:
                                self.pdf_cache[shift_name][doc_url] = {
                                    'name': doc_name,
                                    'text': text,
                                    'timestamp': current_time,
                                    'is_student_list': is_student_list,
                                    'type': doc_type
                                }
                                logger.info(f"✅ Загружен: {doc_name}")
                            else:
                                logger.warning(f"⚠️ Не удалось извлечь текст: {doc_name}")
                        except Exception as e:
                            logger.error(f"❌ Ошибка загрузки {doc_name}: {e}")
            
            self.save_pdf_cache(self.pdf_cache)
            self.last_update = datetime.now()
            
            total_cached = sum(len(docs) for docs in self.pdf_cache.values())
            logger.info(f"🎉 Предзагрузка завершена! Кэшировано {total_cached} документов")
            
            return self.pdf_cache
            
        except Exception as e:
            logger.error(f"❌ Ошибка предзагрузки PDF-файлов: {e}")
            return {}
    
    async def search_in_lists(self, query: str, search_type='all') -> list:
        """Поиск в списках участников"""
        try:
            logger.info(f"🔍 Поиск: '{query}' (тип: {search_type})")
            
            if not query or not query.strip():
                return []
            
            # Нормализуем запрос
            query_lower = query.lower().strip()
            query_parts = query_lower.split()
            
            results = []
            total_docs = sum(len(docs) for docs in self.pdf_cache.values())
            processed = 0
            
            logger.info(f"📊 Поиск в {total_docs} документах")
            
            for shift_name, docs in self.pdf_cache.items():
                for doc_url, doc_data in docs.items():
                    processed += 1
                    
                    # Фильтруем по типу поиска
                    if search_type == 'student_lists' and not doc_data.get('is_student_list', False):
                        continue
                    
                    doc_text = doc_data['text'].lower()
                    doc_name = doc_data['name']
                    
                    # Поиск
                    found, match_info = self._search_in_text(query_lower, query_parts, doc_text)
                    
                    if found:
                        logger.info(f"✅ НАЙДЕНО! {match_info} в '{doc_name}' ({shift_name})")
                        
                        context = self._get_context(doc_text, query_lower, query_parts)
                        
                        result = {
                            'shift': shift_name,
                            'document': doc_name,
                            'url': doc_url,
                            'type': doc_data.get('type', 'other'),
                            'match_info': match_info,
                            'context': context,
                            'is_student_list': doc_data.get('is_student_list', False)
                        }
                        
                        # Приоритет для списков студентов
                        if doc_data.get('is_student_list', False):
                            results.insert(0, result)
                        else:
                            results.append(result)
            
            logger.info(f"🎉 Найдено результатов: {len(results)}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска: {e}")
            return []
    
    def _search_in_text(self, query, query_parts, text):
        """Поиск в тексте с защитой от частичных совпадений"""
        # 1. Точное совпадение полной фразы
        if query in text:
            return True, "полное совпадение"
        
        # 2. Если несколько слов - ищем только целую фразу
        if len(query_parts) >= 2:
            # Убираем логику поиска по частям - только полное совпадение фразы
            # Проверяем различные варианты написания (с разными пробелами)
            import re
            
            # Создаем паттерн для поиска с учетом возможных вариаций пробелов
            pattern = r'\b' + r'\s+'.join(re.escape(part) for part in query_parts) + r'\b'
            
            if re.search(pattern, text, re.IGNORECASE):
                return True, f"найдена фраза: {query}"
            
            # Проверяем инвертированный порядок (Имя Фамилия -> Фамилия Имя)
            if len(query_parts) == 2:
                reversed_query = f"{query_parts[1]} {query_parts[0]}"
                if reversed_query in text:
                    return True, f"найдена фраза (обратный порядок): {reversed_query}"
                
                # И с regex для обратного порядка
                reversed_pattern = r'\b' + re.escape(query_parts[1]) + r'\s+' + re.escape(query_parts[0]) + r'\b'
                if re.search(reversed_pattern, text, re.IGNORECASE):
                    return True, f"найдена фраза (обратный порядок): {reversed_query}"
        
        # 3. Одно слово (если достаточно длинное)
        elif len(query_parts) == 1 and len(query_parts[0]) >= 3:
            # Используем границы слов для точного поиска
            import re
            pattern = r'\b' + re.escape(query_parts[0]) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                return True, f"найдено слово: {query_parts[0]}"
        
        return False, ""
    
    def _get_context(self, text, query, query_parts, context_size=100):
        """Получение контекста вокруг найденного текста"""
        try:
            index = text.find(query)
            if index == -1 and query_parts:
                index = text.find(query_parts[0])
            
            if index >= 0:
                start = max(0, index - context_size)
                end = min(len(text), index + len(query) + context_size)
                context = text[start:end].strip()
                context = re.sub(r'\s+', ' ', context)
                return context[:200] + "..." if len(context) > 200 else context
            
            return ""
        except Exception:
            return ""
    
    def get_cache_stats(self):
        """Статистика кэша"""
        try:
            total_shifts = len(self.pdf_cache)
            total_docs = sum(len(docs) for docs in self.pdf_cache.values())
            student_lists = 0
            
            for docs in self.pdf_cache.values():
                for doc_data in docs.values():
                    if doc_data.get('is_student_list', False):
                        student_lists += 1
            
            return {
                'total_shifts': total_shifts,
                'total_documents': total_docs,
                'student_lists': student_lists,
                'last_update': self.last_update.strftime('%Y-%m-%d %H:%M:%S') if self.last_update else 'Никогда',
                'cache_file_exists': os.path.exists(PDF_CACHE_FILE),
                'ocr_available': OCR_AVAILABLE
            }
        except Exception as e:
            logger.error(f"❌ Ошибка статистики: {e}")
            return {}
    
    async def update_cache(self, force=False):
        """Обновление кэша"""
        try:
            logger.info("🔄 Обновление кэша...")
            await self.preload_pdf_files(force_reload=force)
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка обновления кэша: {e}")
            return False

# Глобальная инстанция
lists_parser = ListsParser()

# Функции для использования в других модулях
async def search_name_in_lists(query: str, search_type='all'):
    """Поиск имени в списках технопарка"""
    return await lists_parser.search_in_lists(query, search_type)

async def update_lists_cache(force=False):
    """Обновление кэша списков"""
    return await lists_parser.update_cache(force)

def get_lists_stats():
    """Статистика списков"""
    return lists_parser.get_cache_stats()

async def initialize_lists_parser():
    """Инициализация парсера списков"""
    try:
        logger.info("🚀 Инициализация парсера списков...")
        stats = lists_parser.get_cache_stats()
        
        if stats.get('total_documents', 0) == 0:
            logger.info("📥 Кэш пуст, загружаем документы...")
            await lists_parser.preload_pdf_files()
        else:
            logger.info(f"📚 Загружен кэш: {stats['total_documents']} документов")
        
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации: {e}")
        return False

# Тестовый код для проверки работы модуля
if __name__ == "__main__":
    import asyncio
    
    async def test_module():
        print("🧪 Тестирование парсера списков...")
        
        # Тест инициализации
        print("📋 Инициализация...")
        success = await initialize_lists_parser()
        print(f"Результат: {'✅' if success else '❌'}")
        
        # Статистика
        print("\n📊 Статистика:")
        stats = get_lists_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # Простой тест поиска (если есть кэш)
        if stats.get('total_documents', 0) > 0:
            print("\n🔍 Тест поиска...")
            test_queries = ["Иванов", "Петрова"]
            
            for query in test_queries:
                print(f"Поиск: '{query}'")
                results = await search_name_in_lists(query)
                print(f"  Найдено: {len(results)} результат(ов)")
        
        print("\n✅ Тестирование завершено!")
    
    # Запускаем тест
    asyncio.run(test_module())