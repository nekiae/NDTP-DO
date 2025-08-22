import asyncio
import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import aiohttp
from bs4 import BeautifulSoup
import os

logger = logging.getLogger(__name__)

class ScheduleParser:
    """Парсер расписания смен Национального детского технопарка"""
    
    def __init__(self):
        from ...core.config import config
        self.url = "https://ndtp.by/educational-shifts/schedule/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.shifts_file = config.parsers_data_dir / "current_shifts.json"
        self.last_update_file = config.parsers_data_dir / "last_schedule_update.txt"
        
        # Словарь для названий месяцев
        self.month_map = {
            1: "Январская смена",
            2: "Февральская смена", 
            3: "Мартовская смена",
            4: "Апрельская смена",
            5: "Майская смена",
            6: "Июньская смена",
            7: "Июльская смена",
            8: "Августская смена",
            9: "Сентябрьская смена",
            10: "Октябрьская смена",
            11: "Ноябрьская смена",
            12: "Декабрьская смена"
        }
        
        # Регулярные выражения для извлечения дат
        self.app_period_pattern = r'^Прием заявок с (\d{2}\.\d{2}\.(?:\d{4}|\d{2})) по (\d{2}\.\d{2}\.(?:\d{4}|\d{2}))г\.$'
        self.shift_period_pattern = r'с (\d{2}\.\d{2}\.\d{4})г\. по (\d{2}\.\d{2}\.\d{4})г\.'
    
    def normalize_date(self, date_str: str) -> str:
        """Нормализует дату в формат DD.MM.YYYY"""
        parts = date_str.split('.')
        if len(parts) == 3:
            day, month, year = parts
            # Если год двузначный, добавляем 20
            if len(year) == 2:
                if int(year) < 50:  # Предполагаем 20XX
                    year = "20" + year
                else:  # Предполагаем 19XX
                    year = "19" + year
            return f"{day.zfill(2)}.{month.zfill(2)}.{year}"
        return date_str
    
    def get_month_from_date(self, date_str: str) -> int:
        """Извлекает номер месяца из даты"""
        try:
            parts = date_str.split('.')
            if len(parts) >= 2:
                return int(parts[1])
        except (ValueError, IndexError):
            logger.error(f"Не удалось извлечь месяц из даты: {date_str}")
        return 0
    
    async def fetch_page(self) -> Optional[str]:
        """Получает HTML страницы с расписанием"""
        try:
            logger.info(f"🌐 Запрос к {self.url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url, headers=self.headers, timeout=30) as response:
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"✅ Страница успешно загружена ({len(content)} символов)")
                        return content
                    else:
                        logger.error(f"❌ Ошибка загрузки страницы: HTTP {response.status}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("❌ Таймаут при загрузке страницы")
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке страницы: {e}")
        
        return None
    
    def parse_shifts(self, html_content: str) -> List[Dict]:
        """Парсит HTML и извлекает информацию о сменах"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Найдем все панели аккордеона
            panels = soup.find_all('div', class_='fusion-panel')
            logger.info(f"🔗 Найдено {len(panels)} панелей аккордеона")
            
            results = []
            
            for i, panel in enumerate(panels):
                try:
                    # Извлекаем заголовок смены
                    title_elem = panel.find('span', class_='fusion-toggle-heading')
                    if not title_elem:
                        continue
                    
                    title_text = title_elem.get_text(strip=True)
                    
                    # Ищем название смены и даты в заголовке
                    shift_pattern = r'(Январская|Февральская|Мартовская|Апрельская|Майская|Июньская|Июльская|Августовская|Сентябрьская|Октябрьская|Ноябрьская|Декабрьская)\s+смена.*?(\d{2}\.\d{2}\.\d{4})\s*[–-]\s*(\d{2}\.\d{2}\.\d{4})'
                    
                    shift_match = re.search(shift_pattern, title_text)
                    if not shift_match:
                        continue
                    
                    month_name = shift_match.group(1)
                    start_date = shift_match.group(2)
                    end_date = shift_match.group(3)
                    
                    # Ищем статус подачи в заголовке
                    status = "Подачи нет" if "Подачи нет" in title_text else "Неизвестно"
                    
                    # Извлекаем контент панели для поиска информации о заявках
                    content = panel.find('div', class_='panel-body')
                    app_start_date = None
                    app_end_date = None
                    
                    if content:
                        content_text = content.get_text(strip=True)
                        
                        # Ищем период приема заявок в контенте этой конкретной панели
                        app_patterns = [
                            r'Прием заявок с (\d{1,2}\.\d{1,2}) по (\d{1,2}\.\d{1,2})\.(\d{4})г?\.',
                            r'Прием заявок с (\d{1,2}\.\d{1,2})\.(\d{4}) по (\d{1,2}\.\d{1,2})\.(\d{4})г?\.',
                            r'Прием заявок с (\d{1,2}\.\d{1,2}) по (\d{1,2}\.\d{1,2})\.(\d{4}) г\.'
                        ]
                        
                        for pattern in app_patterns:
                            app_match = re.search(pattern, content_text)
                            if app_match:
                                if len(app_match.groups()) == 3:  # Формат: dd.mm по dd.mm.yyyy
                                    app_start_date = f"{app_match.group(1)}.{app_match.group(3)}"
                                    app_end_date = f"{app_match.group(2)}.{app_match.group(3)}"
                                elif len(app_match.groups()) == 4:  # Формат: dd.mm.yyyy по dd.mm.yyyy
                                    app_start_date = f"{app_match.group(1)}.{app_match.group(2)}"
                                    app_end_date = f"{app_match.group(3)}.{app_match.group(4)}"
                                break
                    
                    # Создаем запись о смене
                    shift_data = {
                        'name': f"{month_name} смена",
                        'start_date': start_date,
                        'end_date': end_date,
                        'month_number': self.get_month_from_name(month_name),
                        'raw_status': status,
                        'application_start_date': app_start_date,
                        'application_end_date': app_end_date
                    }
                    
                    results.append(shift_data)
                    logger.info(f"✅ Найдена смена: {month_name} смена ({start_date} - {end_date})")
                    if app_start_date and app_end_date:
                        logger.info(f"📅 Заявки: {app_start_date} - {app_end_date}")
                    else:
                        logger.info(f"📅 Заявки: {status}")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка обработки панели {i+1}: {e}")
                    continue
            
            logger.info(f"🎯 Всего извлечено смен: {len(results)}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга HTML: {e}")
            return []
    
    def get_month_from_name(self, month_name: str) -> int:
        """Получает номер месяца по названию"""
        month_mapping = {
            "Январская": 1, "Февральская": 2, "Мартовская": 3, "Апрельская": 4,
            "Майская": 5, "Июньская": 6, "Июльская": 7, "Августовская": 8,
            "Сентябрьская": 9, "Октябрьская": 10, "Ноябрьская": 11, "Декабрьская": 12
        }
        return month_mapping.get(month_name, 1)
    
    def save_shifts(self, shifts: List[Dict]) -> bool:
        """Сохраняет список смен в JSON файл"""
        try:
            # Добавляем метаданные
            data = {
                "last_updated": datetime.now().isoformat(),
                "total_shifts": len(shifts),
                "source_url": self.url,
                "shifts": shifts
            }
            
            with open(self.shifts_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # Сохраняем время последнего обновления
            with open(self.last_update_file, 'w', encoding='utf-8') as f:
                f.write(datetime.now().isoformat())
            
            logger.info(f"💾 Данные сохранены в {self.shifts_file}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения данных: {e}")
            return False
    
    def load_shifts(self) -> Optional[Dict]:
        """Загружает сохраненные данные о сменах"""
        try:
            if os.path.exists(self.shifts_file):
                with open(self.shifts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"📖 Загружены данные: {data.get('total_shifts', 0)} смен")
                return data
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки данных: {e}")
        return None
    
    def get_last_update_time(self) -> Optional[datetime]:
        """Получает время последнего обновления"""
        try:
            if os.path.exists(self.last_update_file):
                with open(self.last_update_file, 'r', encoding='utf-8') as f:
                    time_str = f.read().strip()
                return datetime.fromisoformat(time_str)
        except Exception as e:
            logger.error(f"❌ Ошибка получения времени обновления: {e}")
        return None
    
    def should_update(self, hours_threshold: int = 6) -> bool:
        """Проверяет, нужно ли обновлять данные"""
        last_update = self.get_last_update_time()
        if not last_update:
            return True
        
        time_diff = datetime.now() - last_update
        should_update = time_diff.total_seconds() > hours_threshold * 3600
        
        if should_update:
            logger.info(f"⏰ Данные устарели (последнее обновление: {last_update})")
        else:
            logger.info(f"✅ Данные актуальны (последнее обновление: {last_update})")
        
        return should_update
    
    async def update_schedule(self, force: bool = False) -> bool:
        """Обновляет расписание смен"""
        try:
            if not force and not self.should_update():
                return True
            
            logger.info("🔄 Начинаем обновление расписания смен...")
            
            # Получаем страницу
            html_content = await self.fetch_page()
            if not html_content:
                return False
            
            # Парсим данные
            shifts = self.parse_shifts(html_content)
            if not shifts:
                logger.warning("⚠️ Не удалось извлечь данные о сменах")
                return False
            
            # Создаем новые данные для проверки изменений
            new_shifts_data = {
                "last_updated": datetime.now().isoformat(),
                "total_shifts": len(shifts),
                "source_url": self.url,
                "shifts": shifts
            }
            
            # Проверяем изменения в расписании для уведомлений
            try:
                from notification_system import notification_system
                changes = notification_system.check_schedule_changes(new_shifts_data)
                
                # Сохраняем данные
                if self.save_shifts(shifts):
                    logger.info(f"✅ Расписание успешно обновлено: {len(shifts)} смен")
                    
                    # Отправляем уведомления об изменениях (если есть)
                    if changes and changes.get("has_changes"):
                        logger.info("📬 Обнаружены изменения в расписании - отправляем уведомления")
                        await notification_system.send_schedule_update_notification(changes)
                    
                    return True
                else:
                    return False
                    
            except ImportError:
                logger.warning("⚠️ Система уведомлений недоступна")
                # Сохраняем данные без уведомлений
                if self.save_shifts(shifts):
                    logger.info(f"✅ Расписание успешно обновлено: {len(shifts)} смен")
                    return True
                else:
                    return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка обновления расписания: {e}")
            return False
    
    def get_current_shifts_info(self) -> str:
        """Возвращает текущую информацию о сменах для контекста ИИ"""
        data = self.load_shifts()
        if not data or not data.get('shifts'):
            return "Информация о расписании смен недоступна."
        
        shifts = data['shifts']
        
        # Сортируем смены по дате начала
        shifts_sorted = sorted(shifts, key=lambda x: datetime.strptime(x['start_date'], '%d.%m.%Y'))
        
        info_parts = [
            f"📅 АКТУАЛЬНОЕ РАСПИСАНИЕ СМЕН (обновлено: {data['last_updated'][:16]})",
            ""
        ]
        
        for shift in shifts_sorted:
            try:
                # Используем новую функцию для определения статуса
                shift_status, app_status = self.get_shift_status(shift, datetime.now())
                
                info_parts.extend([
                    f"• {shift['name']}: {shift['start_date']} - {shift['end_date']}",
                    f"  Статус смены: {shift_status}",
                    f"  Прием заявок: {app_status}",
                    ""
                ])
                
            except Exception as e:
                logger.error(f"Ошибка обработки смены {shift.get('name', 'Unknown')}: {e}")
                continue
        
        return "\n".join(info_parts)
    
    def get_shifts_for_query(self, query: str) -> str:
        """Возвращает информацию о сменах для запроса пользователя"""
        try:
            with open(self.shifts_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            # Проверяем, связан ли запрос с подачей заявок
            application_keywords = ['заявк', 'подач', 'подать', 'записат', 'регистр', 'поступ']
            is_about_applications = any(keyword in query.lower() for keyword in application_keywords)
            
            if is_about_applications:
                return self.get_available_shifts_for_application()
            
            # Обычный запрос - показываем все смены
            info_parts = [
                "📅 РАСПИСАНИЕ ОБРАЗОВАТЕЛЬНЫХ СМЕН НА 2025 ГОД",
                f"Обновлено: {data['last_updated']}",
                f"Сегодня: {datetime.now().strftime('%d.%m.%Y (%A)')}",
                ""
            ]
            
            for shift in data['shifts']:
                # Используем новую функцию для определения статуса
                shift_status, app_status = self.get_shift_status(shift, datetime.now())
                
                info_parts.append(f"🎓 {shift['name']}")
                info_parts.append(f"📅 Даты: {shift['start_date']} - {shift['end_date']}")
                info_parts.append(f"📊 Статус: {shift_status}")
                info_parts.append(f"📝 Заявки: {app_status}")
                info_parts.append("")
            
            return "\n".join(info_parts)
            
        except FileNotFoundError:
            return "❌ Информация о расписании временно недоступна"
        except Exception as e:
            logger.error(f"Ошибка получения информации о сменах: {e}")
            return "❌ Ошибка загрузки информации о сменах"
    
    def get_shift_status(self, shift: Dict, current_date: datetime) -> Tuple[str, str]:
        """Определяет статус смены и заявок на основе текущей даты"""
        try:
            start_date = datetime.strptime(shift['start_date'], '%d.%m.%Y').date()
            end_date = datetime.strptime(shift['end_date'], '%d.%m.%Y').date()
            current_date_only = current_date.date()
            
            # Определяем статус смены
            if current_date_only < start_date:
                if (start_date - current_date_only).days <= 30:
                    shift_status = "🔜 Скоро начнется"
                else:
                    shift_status = "📅 Запланирована"
            elif start_date <= current_date_only <= end_date:
                shift_status = "⚡ Активная смена"
            else:
                shift_status = "✅ Завершена"
            
            # Определяем статус заявок
            app_status = "❓ Информация уточняется"
            
            if shift.get('application_start_date') and shift.get('application_end_date'):
                try:
                    app_start = datetime.strptime(shift['application_start_date'], '%d.%m.%Y').date()
                    app_end = datetime.strptime(shift['application_end_date'], '%d.%m.%Y').date()
                    
                    if current_date_only < app_start:
                        app_status = f"🔜 Скоро откроется ({shift['application_start_date']})"
                    elif app_start <= current_date_only <= app_end:
                        app_status = f"🟢 Прием открыт (до {shift['application_end_date']})"
                    else:
                        app_status = f"🔴 Прием закрыт (был до {shift['application_end_date']})"
                except ValueError:
                    pass
            elif shift.get('raw_status') == "Подачи нет":
                app_status = "🔴 Подача заявок закрыта"
            
            return shift_status, app_status
            
        except (ValueError, KeyError) as e:
            logger.warning(f"⚠️ Ошибка определения статуса для смены {shift.get('name', 'Unknown')}: {e}")
            return "❓ Статус неизвестен", "❓ Информация уточняется"
    
    def get_available_shifts_for_application(self) -> str:
        """Возвращает информацию о доступных для подачи заявок сменах"""
        try:
            with open(self.shifts_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            available_shifts = []
            upcoming_shifts = []
            
            for shift in data['shifts']:
                shift_status, app_status = self.get_shift_status(shift, datetime.now())
                
                # Собираем смены с открытыми заявками
                if "🟢" in app_status:  # Открытые заявки
                    available_shifts.append((shift, shift_status, app_status))
                elif "🟡" in app_status:  # Скоро откроются
                    upcoming_shifts.append((shift, shift_status, app_status))
            
            info_parts = [
                "📝 ИНФОРМАЦИЯ О ПОДАЧЕ ЗАЯВОК НА ОБРАЗОВАТЕЛЬНЫЕ СМЕНЫ",
                f"Актуально на: {datetime.now().strftime('%d.%m.%Y')}", 
                ""
            ]
            
            if available_shifts:
                info_parts.append("🟢 СЕЙЧАС ОТКРЫТ ПРИЕМ ЗАЯВОК:")
                info_parts.append("")
                
                for shift, shift_status, app_status in available_shifts:
                    info_parts.append(f"✅ {shift['name']}")
                    info_parts.append(f"📅 Даты смены: {shift['start_date']} - {shift['end_date']}")
                    info_parts.append(f"📝 {app_status}")
                    info_parts.append("")
            
            if upcoming_shifts:
                info_parts.append("🟡 СКОРО ОТКРОЕТСЯ ПРИЕМ ЗАЯВОК:")
                info_parts.append("")
                
                for shift, shift_status, app_status in upcoming_shifts:
                    info_parts.append(f"⏰ {shift['name']}")
                    info_parts.append(f"📅 Даты смены: {shift['start_date']} - {shift['end_date']}")
                    info_parts.append(f"📝 {app_status}")
                    info_parts.append("")
            
            if not available_shifts and not upcoming_shifts:
                info_parts.append("🔴 К сожалению, сейчас нет открытых смен для подачи заявок.")
                info_parts.append("")
                info_parts.append("📋 Все смены на 2025 год:")
                info_parts.append("")
                
                for shift in data['shifts']:
                    # Используем новую функцию для определения статуса
                    shift_status, app_status = self.get_shift_status(shift, datetime.now())
                    
                    info_parts.append(f"• {shift['name']}: {shift['start_date']} - {shift['end_date']}")
                    info_parts.append(f"  {app_status}")
                    info_parts.append("")
                
                info_parts.append("💡 Рекомендации:")
                info_parts.append("• Следите за обновлениями на сайте ndtp.by")
                info_parts.append("• Подготовьте проект заранее")
                info_parts.append("• При вопросах обращайтесь к консультанту через /help")
            
            return "\n".join(info_parts)
            
        except FileNotFoundError:
            return "❌ Информация о расписании временно недоступна"
        except Exception as e:
            logger.error(f"Ошибка получения доступных смен: {e}")
            return "❌ Ошибка загрузки информации о доступных сменах"

# Глобальный экземпляр парсера
schedule_parser = ScheduleParser()

# Функции для интеграции с основным ботом
async def get_schedule_context_async(query: str = "") -> str:
    """Асинхронно получает контекст о расписании смен"""
    try:
        # Обновляем данные если нужно
        await schedule_parser.update_schedule()
        
        # Возвращаем релевантную информацию
        if query:
            return schedule_parser.get_shifts_for_query(query)
        else:
            return schedule_parser.get_current_shifts_info()
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения контекста расписания: {e}")
        return "Временно недоступна информация о расписании смен."

def get_schedule_context(query: str = "") -> str:
    """Синхронно получает контекст о расписании смен"""
    try:
        # Используем сохраненные данные
        if query:
            return schedule_parser.get_shifts_for_query(query)
        else:
            return schedule_parser.get_current_shifts_info()
    except Exception as e:
        logger.error(f"❌ Ошибка получения контекста расписания: {e}")
        return "Временно недоступна информация о расписании смен."

async def force_update_schedule() -> bool:
    """Принудительно обновляет расписание"""
    return await schedule_parser.update_schedule(force=True)

# Функция для автоматического обновления
async def schedule_updater_loop(interval_hours: int = 6):
    """Цикл автоматического обновления расписания"""
    logger.info(f"🔄 Запущен цикл обновления расписания (каждые {interval_hours} часов)")
    
    while True:
        try:
            await schedule_parser.update_schedule()
            await asyncio.sleep(interval_hours * 3600)  # Ждем указанное количество часов
        except Exception as e:
            logger.error(f"❌ Ошибка в цикле обновления расписания: {e}")
            await asyncio.sleep(300)  # При ошибке ждем 5 минут и пробуем снова 