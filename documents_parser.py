import aiohttp
import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class DocumentsParser:
    """Парсер страницы с необходимыми документами для поступления"""
    
    def __init__(self):
        self.url = "https://ndtp.by/for_incoming_students/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.cache_file = "documents_cache.json"
        self.last_update_file = "last_documents_update.txt"
        self.base_url = "https://ndtp.by"
        
    async def fetch_page(self) -> Optional[str]:
        """Получает HTML страницы с документами"""
        try:
            logger.info(f"🌐 Запрос к {self.url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url, headers=self.headers, timeout=30) as response:
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"✅ Страница документов успешно загружена ({len(content)} символов)")
                        return content
                    else:
                        logger.error(f"❌ Ошибка загрузки страницы документов: HTTP {response.status}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("❌ Таймаут при загрузке страницы документов")
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке страницы документов: {e}")
        
        return None
    
    def parse_documents_section(self, html_content: str) -> Dict:
        """Парсит раздел с необходимыми документами"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Ищем заголовок "Необходимые документы" (используем лямбда как в гайде)
            documents_header = soup.find(
                lambda tag: tag.name in {"h1", "h2", "h3", "h4"} and
                           "необходимые документы" in tag.get_text(strip=True).lower()
            )
            
            if not documents_header:
                logger.warning("⚠️ Не найден заголовок 'Необходимые документы'")
                return {}
            
            logger.info("📋 Найден раздел 'Необходимые документы'")
            
            # Парсим документы
            documents_info = {
                "title": documents_header.get_text(strip=True),
                "items": [],
                "raw_html": str(documents_header),
                "last_updated": datetime.now().isoformat()
            }
            
            # Используем find_all_next() для обхода всех следующих элементов
            for element in documents_header.find_all_next():
                # Останавливаемся при встрече нового заголовка того же или более высокого уровня
                if element.name in {"h1", "h2", "h3", "h4"} and element is not documents_header:
                    logger.info(f"📍 Достигнут следующий заголовок: {element.get_text(strip=True)[:50]}")
                    break
                
                # Обрабатываем ненумерованные списки
                if element.name == "ul":
                    logger.info(f"📋 Найден список с {len(element.find_all('li', recursive=False))} элементами")
                    for li in element.find_all("li", recursive=False):
                        item_info = self._parse_document_item(li)
                        if item_info:
                            documents_info["items"].append(item_info)
                            logger.info(f"✅ Добавлен документ: {item_info['text'][:50]}...")
                
                # Обрабатываем параграфы с маркерами
                elif element.name == "p":
                    paragraph_text = element.get_text(strip=True)
                    if paragraph_text and len(paragraph_text) > 10:
                        # Разбиваем по строкам для обработки маркеров
                        lines = [
                            line.strip(" *•–\u2022").strip()
                            for line in element.get_text("\n").splitlines()
                            if line.strip(" *•–\u2022").strip()
                        ]
                        
                        if lines:
                            # Если есть несколько строк с маркерами, обрабатываем каждую
                            for line in lines:
                                if len(line) > 10:  # Игнорируем короткие строки
                                    links = self._extract_links_from_element(element)
                                    item_info = {
                                        "type": "description",
                                        "text": line,
                                        "links": links,
                                        "document_type": "other"
                                    }
                                    documents_info["items"].append(item_info)
                                    logger.info(f"✅ Добавлено описание: {line[:50]}...")
                        else:
                            # Обычный параграф без маркеров
                            links = self._extract_links_from_element(element)
                            item_info = {
                                "type": "description", 
                                "text": paragraph_text,
                                "links": links,
                                "document_type": "other"
                            }
                            documents_info["items"].append(item_info)
                            logger.info(f"✅ Добавлен параграф: {paragraph_text[:50]}...")
                
                # Сохраняем HTML для отладки
                documents_info["raw_html"] += str(element)
            
            logger.info(f"📄 Извлечено элементов документов: {len(documents_info['items'])}")
            return documents_info
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга документов: {e}")
            return {}
    
    def _parse_document_item(self, li_element) -> Optional[Dict]:
        """Парсит отдельный элемент списка документов"""
        try:
            # Используем пробел как разделитель для лучшего форматирования текста
            text = li_element.get_text(" ", strip=True)
            if not text or len(text) < 5:
                return None
            
            # Извлекаем ссылки
            links = self._extract_links_from_element(li_element)
            
            # Определяем тип документа
            doc_type = self._classify_document_type(text)
            
            logger.debug(f"🔍 Парсинг элемента: {text[:50]}... (ссылок: {len(links)})")
            
            return {
                "type": "document",
                "text": text,
                "links": links,
                "document_type": doc_type
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга элемента документа: {e}")
            return None
    
    def _extract_links_from_element(self, element) -> List[Dict]:
        """Извлекает все ссылки из элемента"""
        links = []
        
        try:
            for link in element.find_all('a', href=True):
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                if href and text:
                    # Формируем полную ссылку
                    if href.startswith('/'):
                        full_url = self.base_url + href
                    elif href.startswith('http'):
                        full_url = href
                    else:
                        full_url = self.base_url + '/' + href
                    
                    links.append({
                        "text": text,
                        "url": full_url,
                        "original_href": href
                    })
                    
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения ссылок: {e}")
        
        return links
    
    def _classify_document_type(self, text: str) -> str:
        """Классифицирует тип документа по тексту"""
        text_lower = text.lower()
        
        if 'заявление' in text_lower:
            return 'application'
        elif 'согласие' in text_lower:
            return 'consent'
        elif 'план' in text_lower and 'учебный' in text_lower:
            return 'study_plan'
        elif 'свидетельство' in text_lower and 'рождени' in text_lower:
            return 'birth_certificate'
        elif 'медицинская' in text_lower and 'справка' in text_lower:
            return 'medical_certificate'
        elif 'справка' in text_lower and 'бассейн' in text_lower:
            return 'pool_certificate'
        elif 'справка' in text_lower and 'инфекц' in text_lower:
            return 'infection_certificate'
        else:
            return 'other'
    
    def save_documents_cache(self, documents_data: Dict) -> bool:
        """Сохраняет данные о документах в кеш"""
        try:
            cache_data = {
                "last_updated": datetime.now().isoformat(),
                "source_url": self.url,
                "documents": documents_data
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            # Обновляем время последнего обновления
            with open(self.last_update_file, 'w', encoding='utf-8') as f:
                f.write(datetime.now().isoformat())
            
            logger.info(f"💾 Данные о документах сохранены в {self.cache_file}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения данных о документах: {e}")
            return False
    
    def load_documents_cache(self) -> Optional[Dict]:
        """Загружает данные о документах из кеша"""
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.info("📄 Файл кеша документов не найден")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки кеша документов: {e}")
            return None
    
    def get_last_update_time(self) -> Optional[datetime]:
        """Получает время последнего обновления"""
        try:
            with open(self.last_update_file, 'r', encoding='utf-8') as f:
                time_str = f.read().strip()
                return datetime.fromisoformat(time_str)
        except (FileNotFoundError, ValueError):
            return None
    
    def should_update(self, hours_threshold: int = 24) -> bool:
        """Проверяет, нужно ли обновление (по умолчанию каждые 24 часа)"""
        last_update = self.get_last_update_time()
        if not last_update:
            return True
        
        time_diff = datetime.now() - last_update
        return time_diff > timedelta(hours=hours_threshold)
    
    async def update_documents(self, force: bool = False) -> bool:
        """Обновляет данные о документах"""
        try:
            if not force and not self.should_update():
                logger.info("⏰ Обновление документов не требуется")
                return True
            
            logger.info("🔄 Начинаем обновление данных о документах...")
            
            # Получаем страницу
            html_content = await self.fetch_page()
            if not html_content:
                return False
            
            # Парсим документы
            documents_data = self.parse_documents_section(html_content)
            if not documents_data:
                logger.warning("⚠️ Не удалось извлечь данные о документах")
                return False
            
            # Сохраняем данные
            if self.save_documents_cache(documents_data):
                logger.info(f"✅ Данные о документах успешно обновлены: {len(documents_data.get('items', []))} элементов")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка обновления данных о документах: {e}")
            return False
    
    def get_documents_context(self, query: str = "") -> str:
        """Возвращает контекст о документах для ИИ"""
        try:
            # Проверяем, связан ли запрос с документами
            document_keywords = [
                'документ', 'документы', 'справк', 'заявлен', 'согласи', 'свидетельство',
                'медицинск', 'рождени', 'бассейн', 'инфекц', 'план', 'учебный',
                'при заезде', 'поступлен', 'регистрац', 'что нужно', 'что взять',
                'какие нужны', 'список документов', 'необходимые'
            ]
            
            query_lower = query.lower()
            is_documents_related = any(keyword in query_lower for keyword in document_keywords)
            
            if not is_documents_related and query:
                return ""
            
            # Загружаем данные из кеша
            cache_data = self.load_documents_cache()
            if not cache_data:
                return "Информация о необходимых документах временно недоступна."
            
            documents_info = cache_data.get("documents", {})
            if not documents_info:
                return "Информация о необходимых документах не найдена."
            
            # Формируем контекст
            context_parts = [
                "📄 НЕОБХОДИМЫЕ ДОКУМЕНТЫ ДЛЯ ПОСТУПЛЕНИЯ В НАЦИОНАЛЬНЫЙ ДЕТСКИЙ ТЕХНОПАРК",
                f"Источник: {self.url}",
                f"Обновлено: {cache_data['last_updated'][:16]}",
                ""
            ]
            
            for item in documents_info.get("items", []):
                if item["type"] == "document":
                    context_parts.append(f"• {item['text']}")
                    
                    # Добавляем ссылки, если есть
                    for link in item.get("links", []):
                        context_parts.append(f"  📎 {link['text']}: {link['url']}")
                    
                elif item["type"] == "description":
                    context_parts.append(f"\n{item['text']}")
                    
                    # Добавляем ссылки из описания
                    for link in item.get("links", []):
                        context_parts.append(f"📎 {link['text']}: {link['url']}")
                
                context_parts.append("")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения контекста документов: {e}")
            return "Ошибка загрузки информации о документах."

# Глобальный экземпляр парсера
documents_parser = DocumentsParser()

# Функции для интеграции с ботом
async def get_documents_context_async(query: str = "") -> str:
    """Асинхронно получает контекст о документах"""
    try:
        # Попробуем обновить данные, если нужно
        await documents_parser.update_documents()
        return documents_parser.get_documents_context(query)
    except Exception as e:
        logger.error(f"❌ Ошибка получения контекста документов: {e}")
        return documents_parser.get_documents_context(query)  # Попробуем с кешем

def get_documents_context(query: str = "") -> str:
    """Синхронно получает контекст о документах"""
    return documents_parser.get_documents_context(query)

async def force_update_documents() -> bool:
    """Принудительно обновляет данные о документах"""
    return await documents_parser.update_documents(force=True)

async def documents_updater_loop(interval_hours: int = 24):
    """Фоновый цикл обновления данных о документах"""
    logger.info(f"🔄 Запущен цикл обновления документов (каждые {interval_hours} часов)")
    
    while True:
        try:
            await asyncio.sleep(interval_hours * 60 * 60)  # Ждем заданное количество часов
            
            if documents_parser.should_update():
                logger.info("⏰ Запуск планового обновления документов...")
                success = await documents_parser.update_documents()
                if success:
                    logger.info("✅ Плановое обновление документов завершено")
                else:
                    logger.error("❌ Ошибка планового обновления документов")
            else:
                logger.info("✅ Данные о документах актуальны")
                
        except Exception as e:
            logger.error(f"❌ Ошибка в цикле обновления документов: {e}")
            await asyncio.sleep(60 * 60)  # Ждем час при ошибке 