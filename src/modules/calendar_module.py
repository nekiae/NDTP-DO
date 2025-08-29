import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
import aiohttp
from bs4 import BeautifulSoup
import re

from src.core.config import config

from aiogram import F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

logger = logging.getLogger(__name__)

class CalendarModule:
    """Модуль календаря смен с документами"""
    
    def __init__(self):
        self.shifts_file = config.data_dir/"parsers"/"current_shifts.json"
        self.base_url = "https://ndtp.by"
        self.schedule_url = "https://ndtp.by/educational-shifts/schedule/"
        
    def load_shifts_data(self) -> Optional[Dict]:
        """Загружает данные о сменах"""
        try:
            with open(self.shifts_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки данных о сменах: {e}")
            return None
    
    def create_shifts_calendar(self, user_id: int = None) -> tuple[str, InlineKeyboardMarkup]:
        """Создает календарь смен с кнопками"""
        shifts_data = self.load_shifts_data()
        
        if not shifts_data or not shifts_data.get('shifts'):
            return (
                "❌ Информация о сменах временно недоступна.",
                InlineKeyboardMarkup(inline_keyboard=[])
            )
        
        text = (
            "📅 Выберите смену для просмотра подробной информации:\n\n"
            "💡 Нажмите на смену, чтобы увидеть даты, статус приема заявок и доступные документы."
        )
        
        # Создаем кнопки для смен
        keyboard_rows = []
        shifts = shifts_data['shifts']
        
        # Сортируем по номеру месяца
        shifts_sorted = sorted(shifts, key=lambda x: x.get('month_number', 0))
        
        # Группируем по 2 кнопки в ряд
        for i in range(0, len(shifts_sorted), 2):
            row = []
            
            # Первая кнопка в ряду
            shift1 = shifts_sorted[i]
            row.append(InlineKeyboardButton(
                text=f"🎓 {shift1['name']}",
                callback_data=f"calendar_shift_{shift1['month_number']}"
            ))
            
            # Вторая кнопка в ряду (если есть)
            if i + 1 < len(shifts_sorted):
                shift2 = shifts_sorted[i + 1]
                row.append(InlineKeyboardButton(
                    text=f"🎓 {shift2['name']}",
                    callback_data=f"calendar_shift_{shift2['month_number']}"
                ))
            
            keyboard_rows.append(row)
        
        # Добавляем кнопку управления уведомлениями
        keyboard_rows.append([
            InlineKeyboardButton(
                text="🔔 Настройки уведомлений",
                callback_data="notification_settings"
            )
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        return text, keyboard
    
    async def get_shift_details(self, month_number: int) -> tuple[str, InlineKeyboardMarkup]:
        """Получает детальную информацию о смене"""
        shifts_data = self.load_shifts_data()
        
        if not shifts_data:
            return (
                "❌ Ошибка загрузки данных о смене.",
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад к календарю", callback_data="back_to_calendar")]
                ])
            )
        
        # Находим смену по номеру месяца
        shift = None
        for s in shifts_data['shifts']:
            if s.get('month_number') == month_number:
                shift = s
                break
        
        if not shift:
            return (
                "❌ Смена не найдена.",
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад к календарю", callback_data="back_to_calendar")]
                ])
            )
        
        # Формируем информацию о смене
        text_parts = [
            f"📚 {shift['name']}",
            f"📅 Период смены: {shift['start_date']} - {shift['end_date']}"
        ]
        
        # Информация о приеме заявок
        if shift.get('application_start_date') and shift.get('application_end_date'):
            app_start = shift['application_start_date']
            app_end = shift['application_end_date']
            text_parts.append(f"📝 Прием заявок: с {app_start} по {app_end}")
            
            # Определяем статус приема заявок
            try:
                app_start_date = datetime.strptime(app_start, '%d.%m.%Y').date()
                app_end_date = datetime.strptime(app_end, '%d.%m.%Y').date()
                current_date = datetime.now().date()
                
                if current_date < app_start_date:
                    status = f"⏳ Прием откроется {app_start}"
                elif app_start_date <= current_date <= app_end_date:
                    status = "🟢 Прием заявок открыт!"
                else:
                    status = "🔴 Прием заявок закрыт"
                
                text_parts.append(f"📊 Статус: {status}")
            except Exception:
                text_parts.append(f"📊 Статус: {shift.get('raw_status', 'Уточняется')}")
        else:
            text_parts.append(f"📊 Статус: {shift.get('raw_status', 'Подача заявок закрыта')}")
        
        text_parts.append("")
        text_parts.append("📄 Доступные файлы:")
        
        text = "\n".join(text_parts)
        
        # Получаем реальные документы с сайта
        documents = await self.get_shift_documents_real(month_number)
        
        # Создаем клавиатуру с документами
        keyboard_rows = []
        
        # Добавляем кнопки для каждого документа
        for doc in documents:
            keyboard_rows.append([
                InlineKeyboardButton(
                    text=f"📄 {doc['title']}", 
                    url=doc['url']
                )
            ])
        
        # Если документы не найдены, добавляем общую ссылку
        if not documents:
            keyboard_rows.append([
                InlineKeyboardButton(
                    text="📊 Посмотреть документы на сайте", 
                    url=self.schedule_url
                )
            ])
        
        # Кнопка "Назад"
        keyboard_rows.append([
            InlineKeyboardButton(
                text="🔙 Назад к календарю", 
                callback_data="back_to_calendar"
            )
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        
        return text, keyboard
    
    async def get_shift_documents_real(self, month_number: int) -> List[Dict]:
        """Получает список документов для конкретной смены с сайта"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.schedule_url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"❌ Ошибка запроса: {response.status}")
                        return []
                    
                    html = await response.text()
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Ищем панель с нужной сменой
            panels = soup.find_all('div', class_='fusion-panel')
            
            shift_names = {
                1: "Январская", 2: "Февральская", 3: "Мартовская", 4: "Апрельская",
                5: "Майская", 6: "Июньская", 7: "Июльская", 8: "Августовская",
                9: "Сентябрьская", 10: "Октябрьская", 11: "Ноябрьская", 12: "Декабрьская"
            }
            
            target_shift_name = shift_names.get(month_number, "")
            documents = []
            
            for panel in panels:
                title_elem = panel.find('span', class_='fusion-toggle-heading')
                if not title_elem:
                    continue
                
                title_text = title_elem.get_text()
                if target_shift_name not in title_text:
                    continue
                
                # Ищем контент панели
                content = panel.find('div', class_='panel-body')
                if not content:
                    # Попробуем найти контент по другому селектору
                    content = panel.find('div', class_='fusion-toggle-content')
                
                if not content:
                    continue
                
                logger.info(f"🔍 Ищем документы для {target_shift_name} смены...")
                
                # Ищем все ссылки в контенте
                links = content.find_all('a', href=True)
                logger.info(f"📋 Найдено ссылок в панели: {len(links)}")
                
                for link in links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    # Пропускаем пустые ссылки
                    if not text or not href:
                        continue
                    
                    # Фильтруем ссылки на документы PDF и DOC
                    is_document = (
                        href.endswith('.pdf') or 
                        href.endswith('.doc') or 
                        href.endswith('.docx') or
                        any(keyword in text.lower() for keyword in [
                            'положение', 'список', 'состав', 'участник', 
                            'место', 'проведение', 'зачисл', 'смен', 'группа'
                        ])
                    )
                    
                    if is_document:
                        # Формируем полную ссылку
                        if href.startswith('/'):
                            full_url = self.base_url + href
                        elif href.startswith('http'):
                            full_url = href
                        else:
                            full_url = self.base_url + '/' + href
                        
                        # Очищаем название документа
                        clean_title = text.replace('\n', ' ').replace('\t', ' ')
                        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
                        
                        # Сокращаем название документа
                        short_title = self._shorten_document_title(clean_title)
                        
                        documents.append({
                            'title': short_title,
                            'url': full_url,
                            'type': self._classify_document(text)
                        })
                        
                        logger.info(f"📄 Найден документ: {short_title}")
                
                # Если нашли панель с нужной сменой, выходим
                if documents:
                    break
            
            logger.info(f"📄 Найдено документов для {target_shift_name} смены: {len(documents)}")
            return documents
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения документов: {e}")
            return []
    
    def _classify_document(self, title: str) -> str:
        """Классифицирует тип документа"""
        title_lower = title.lower()
        
        if 'положение' in title_lower:
            return 'regulation'
        elif 'список' in title_lower and 'участник' in title_lower:
            return 'participants_list'
        elif 'место' in title_lower and 'проведение' in title_lower:
            return 'venues'
        elif 'зачисл' in title_lower:
            return 'enrolled_list'
        else:
            return 'other'
    
    def _shorten_document_title(self, title: str) -> str:
        """Сокращает название документа для красивого отображения"""
        title_lower = title.lower()
        
        # Положение об образовательной смене - оставляем как есть
        if 'положение' in title_lower and 'образовательн' in title_lower:
            return "Положение об образовательной смене"
        
        # Список участников, допущенных ко второму этапу
        if ('список' in title_lower or 'состав' in title_lower) and \
           ('участник' in title_lower) and \
           ('допущ' in title_lower or 'втор' in title_lower or '2' in title):
            return "Список участников 2 этапа"
        
        # Места проведения - оставляем как есть
        if 'место' in title_lower and 'проведен' in title_lower:
            return "Места проведения"
        
        # Список зачисленных в НДТП
        if ('список' in title_lower or 'состав' in title_lower) and \
           ('зачислен' in title_lower or 'групп' in title_lower) and \
           ('технопарк' in title_lower or 'ндтп' in title_lower):
            return "Список зачисленных в НДТП"
        
        # Если ничего не подошло, оставляем оригинальное название, но укорачиваем
        if len(title) > 45:
            return title[:42] + "..."
        
        return title
    
    def get_shift_status_emoji(self, shift: Dict) -> str:
        """Возвращает эмодзи статуса смены"""
        try:
            if not shift.get('application_start_date'):
                return "📅"
            
            app_start = datetime.strptime(shift['application_start_date'], '%d.%m.%Y').date()
            app_end = datetime.strptime(shift['application_end_date'], '%d.%m.%Y').date()
            current_date = datetime.now().date()
            
            if current_date < app_start:
                return "⏳"
            elif app_start <= current_date <= app_end:
                return "🟢"
            else:
                return "🔴"
        except Exception:
            return "📅"

# Глобальный экземпляр модуля
calendar_module = CalendarModule()
def register_calendar_hadler(dp):
    
    @dp.callback_query(F.data == "back_to_calendar")
    @dp.callback_query(F.data == "show_calendar")
    async def handle_show_calendar(callback: CallbackQuery):
        """Показать календарь смен"""
        if not config.enable_calendar:
            await callback.answer("❌ Календарь смен временно недоступен", show_alert=True)
            return
        
        try:
            user_id = callback.from_user.id
            text, keyboard = get_calendar_interface(user_id)
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer()
        except Exception as e:
            logger.error(f"❌ Ошибка показа календаря: {e}")
            await callback.answer("❌ Ошибка загрузки календаря", show_alert=True)
    @dp.callback_query(F.data.startswith("calendar_shift_"))
    async def handle_calendar_shift(callback: CallbackQuery):
        """Показать информацию о конкретной смене"""
        if not config.enable_calendar:
            await callback.answer("❌ Календарь временно недоступен", show_alert=True)
            return
        
        try:
            month_number = int(callback.data.split("_")[2])
            text, keyboard = await get_shift_info(month_number)
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer()
        except (ValueError, IndexError) as e:
            logger.error(f"❌ Ошибка парсинга данных смены: {e}")
            await callback.answer("❌ Ошибка обработки запроса", show_alert=True)
        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о смене: {e}")
            await callback.answer("❌ Ошибка загрузки информации", show_alert=True)
    
    @dp.callback_query(F.data == "notification_settings")
    async def handle_notification_settings(callback: CallbackQuery):
        """Показать настройки уведомлений"""
        if not config.enable_calendar:
            await callback.answer("❌ Система уведомлений временно недоступна", show_alert=True)
            return
        
        try:
            user_id = callback.from_user.id
            text, keyboard = get_notification_settings_interface(user_id)
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer()
        except Exception as e:
            logger.error(f"❌ Ошибка показа настроек уведомлений: {e}")
            await callback.answer("❌ Ошибка загрузки настроек", show_alert=True)
# Функции для интеграции с ботом
def get_calendar_interface(user_id: int = None):
    """Возвращает интерфейс календаря"""
    return calendar_module.create_shifts_calendar(user_id)

async def get_shift_info(month_number: int):
    """Возвращает информацию о конкретной смене"""
    return await calendar_module.get_shift_details(month_number)

async def get_shift_documents_async(month_number: int):
    """Асинхронно получает документы смены"""
    return await calendar_module.get_shift_documents_real(month_number)

def get_notification_settings_interface(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Создает интерфейс настройки уведомлений"""
    from src.handlers.notification_system import notification_system
    
    # Получаем текущие подписки пользователя
    subscriptions = notification_system.get_user_subscriptions(user_id)
    
    text_parts = [
        "🔔 Настройки уведомлений",
        "",
        "Выберите типы уведомлений, которые хотите получать:",
        "",
        "📅 Обновления расписания - уведомления об изменениях в расписании смен (новые даты, документы, статусы)",
        "",
        "⏰ Напоминания о дедлайнах - уведомления о начале и окончании приема заявок на смены"
    ]
    
    text = "\n".join(text_parts)
    
    # Создаем кнопки с текущим статусом подписок
    schedule_emoji = "✅" if subscriptions["schedule_updates"] else "❌"
    reminders_emoji = "✅" if subscriptions["application_reminders"] else "❌"
    
    keyboard_rows = [
        [
            InlineKeyboardButton(
                text=f"{schedule_emoji} Обновления расписания",
                callback_data="toggle_notification_schedule_updates"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{reminders_emoji} Напоминания о дедлайнах", 
                callback_data="toggle_notification_application_reminders"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 Назад к календарю",
                callback_data="back_to_calendar"
            )
        ]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    return text, keyboard 