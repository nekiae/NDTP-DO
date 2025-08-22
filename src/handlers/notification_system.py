import json
import logging
import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from aiogram import Bot

logger = logging.getLogger(__name__)

class NotificationSystem:
    """Система уведомлений о расписании смен"""
    
    def __init__(self):
        self.subscriptions_file = "notification_subscriptions.json"
        self.schedule_hash_file = "schedule_hash.json"
        self.bot = None
        
    def set_bot(self, bot: Bot):
        """Устанавливает экземпляр бота для отправки уведомлений"""
        self.bot = bot
    
    def load_subscriptions(self) -> Dict[str, List[int]]:
        """Загружает подписки пользователей"""
        try:
            with open(self.subscriptions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"schedule_updates": [], "application_reminders": []}
    
    def save_subscriptions(self, subscriptions: Dict[str, List[int]]):
        """Сохраняет подписки пользователей"""
        try:
            with open(self.subscriptions_file, 'w', encoding='utf-8') as f:
                json.dump(subscriptions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения подписок: {e}")
    
    def load_schedule_hash(self) -> Dict:
        """Загружает хеш расписания для отслеживания изменений"""
        try:
            with open(self.schedule_hash_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def save_schedule_hash(self, hash_data: Dict):
        """Сохраняет хеш расписания"""
        try:
            with open(self.schedule_hash_file, 'w', encoding='utf-8') as f:
                json.dump(hash_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения хеша расписания: {e}")
    
    def is_subscribed(self, user_id: int, notification_type: str) -> bool:
        """Проверяет, подписан ли пользователь на уведомления"""
        subscriptions = self.load_subscriptions()
        return user_id in subscriptions.get(notification_type, [])
    
    def subscribe_user(self, user_id: int, notification_type: str) -> bool:
        """Подписывает пользователя на уведомления"""
        try:
            subscriptions = self.load_subscriptions()
            
            if notification_type not in subscriptions:
                subscriptions[notification_type] = []
            
            if user_id not in subscriptions[notification_type]:
                subscriptions[notification_type].append(user_id)
                self.save_subscriptions(subscriptions)
                logger.info(f"✅ Пользователь {user_id} подписан на {notification_type}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка подписки пользователя {user_id}: {e}")
            return False
    
    def unsubscribe_user(self, user_id: int, notification_type: str) -> bool:
        """Отписывает пользователя от уведомлений"""
        try:
            subscriptions = self.load_subscriptions()
            
            if notification_type in subscriptions and user_id in subscriptions[notification_type]:
                subscriptions[notification_type].remove(user_id)
                self.save_subscriptions(subscriptions)
                logger.info(f"✅ Пользователь {user_id} отписан от {notification_type}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка отписки пользователя {user_id}: {e}")
            return False
    
    def get_user_subscriptions(self, user_id: int) -> Dict[str, bool]:
        """Получает все подписки пользователя"""
        subscriptions = self.load_subscriptions()
        return {
            "schedule_updates": user_id in subscriptions.get("schedule_updates", []),
            "application_reminders": user_id in subscriptions.get("application_reminders", [])
        }
    
    def generate_schedule_hash(self, shifts_data: Dict) -> str:
        """Генерирует хеш для отслеживания изменений в расписании"""
        import hashlib
        
        # Создаем строку из ключевых данных расписания
        hash_data = []
        
        if shifts_data and "shifts" in shifts_data:
            for shift in shifts_data["shifts"]:
                shift_str = f"{shift.get('name', '')}-{shift.get('start_date', '')}-{shift.get('end_date', '')}-{shift.get('application_start_date', '')}-{shift.get('application_end_date', '')}-{shift.get('raw_status', '')}"
                hash_data.append(shift_str)
        
        combined_data = "|".join(sorted(hash_data))
        return hashlib.sha256(combined_data.encode()).hexdigest()[:16]  # Используем первые 16 символов SHA256
    
    def check_schedule_changes(self, new_shifts_data: Dict) -> Optional[Dict]:
        """Проверяет изменения в расписании"""
        try:
            old_hash_data = self.load_schedule_hash()
            new_hash = self.generate_schedule_hash(new_shifts_data)
            
            old_hash = old_hash_data.get("hash", "")
            
            if new_hash != old_hash:
                # Расписание изменилось
                changes = {
                    "has_changes": True,
                    "old_hash": old_hash,
                    "new_hash": new_hash,
                    "timestamp": datetime.now().isoformat(),
                    "details": self._analyze_changes(old_hash_data.get("shifts", {}), new_shifts_data.get("shifts", []))
                }
                
                # Сохраняем новый хеш
                new_hash_data = {
                    "hash": new_hash,
                    "timestamp": datetime.now().isoformat(),
                    "shifts": {shift["name"]: shift for shift in new_shifts_data.get("shifts", [])}
                }
                self.save_schedule_hash(new_hash_data)
                
                return changes
            
            return {"has_changes": False}
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки изменений расписания: {e}")
            return None
    
    def _analyze_changes(self, old_shifts: Dict, new_shifts: List[Dict]) -> List[str]:
        """Анализирует конкретные изменения в расписании"""
        changes = []
        
        try:
            new_shifts_dict = {shift["name"]: shift for shift in new_shifts}
            
            # Проверяем новые смены
            for shift_name, shift_data in new_shifts_dict.items():
                if shift_name not in old_shifts:
                    changes.append(f"➕ Добавлена новая смена: {shift_name}")
                else:
                    old_shift = old_shifts[shift_name]
                    
                    # Проверяем изменения дат приема заявок
                    if (old_shift.get("application_start_date") != shift_data.get("application_start_date") or
                        old_shift.get("application_end_date") != shift_data.get("application_end_date")):
                        if shift_data.get("application_start_date") and shift_data.get("application_end_date"):
                            changes.append(f"📅 {shift_name}: обновлены даты приема заявок ({shift_data['application_start_date']} - {shift_data['application_end_date']})")
                    
                    # Проверяем изменения статуса
                    if old_shift.get("raw_status") != shift_data.get("raw_status"):
                        changes.append(f"📊 {shift_name}: изменен статус на '{shift_data.get('raw_status', 'Неизвестно')}'")
            
            # Проверяем удаленные смены
            for shift_name in old_shifts:
                if shift_name not in new_shifts_dict:
                    changes.append(f"➖ Удалена смена: {shift_name}")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка анализа изменений: {e}")
            changes.append("❓ Произошли изменения в расписании (детали недоступны)")
        
        return changes
    
    async def send_schedule_update_notification(self, changes: Dict):
        """Отправляет уведомления о изменениях в расписании"""
        if not self.bot or not changes.get("has_changes"):
            return
        
        subscriptions = self.load_subscriptions()
        subscribers = subscriptions.get("schedule_updates", [])
        
        if not subscribers:
            return
        
        # Формируем текст уведомления
        message_parts = [
            "🔔 Обновление расписания смен!",
            "",
            "📅 В расписании смен произошли изменения:"
        ]
        
        details = changes.get("details", [])
        if details:
            for detail in details[:5]:  # Максимум 5 изменений
                message_parts.append(f"• {detail}")
            
            if len(details) > 5:
                message_parts.append(f"• ... и еще {len(details) - 5} изменений")
        else:
            message_parts.append("• Обновлена информация о сменах")
        
        message_parts.extend([
            "",
            "📱 Используйте /calendar для просмотра актуального расписания",
            "",
            "🔕 Чтобы отписаться от уведомлений, используйте команду /calendar и нажмите на кнопку управления уведомлениями"
        ])
        
        message = "\n".join(message_parts)
        
        # Отправляем уведомления
        success_count = 0
        for user_id in subscribers:
            try:
                await self.bot.send_message(user_id, message)
                success_count += 1
                await asyncio.sleep(0.1)  # Небольшая задержка между отправками
            except Exception as e:
                logger.warning(f"⚠️ Не удалось отправить уведомление пользователю {user_id}: {e}")
        
        logger.info(f"📬 Отправлено уведомлений о расписании: {success_count}/{len(subscribers)}")
    
    async def check_application_deadlines(self):
        """Проверяет приближающиеся дедлайны подачи заявок"""
        if not self.bot:
            return
        
        try:
            from schedule_parser import ScheduleParser
            parser = ScheduleParser()
            shifts_data = parser.load_shifts()
            
            if not shifts_data or "shifts" not in shifts_data:
                return
            
            current_date = date.today()
            subscriptions = self.load_subscriptions()
            subscribers = subscriptions.get("application_reminders", [])
            
            if not subscribers:
                return
            
            notifications = []
            
            for shift in shifts_data["shifts"]:
                app_start = shift.get("application_start_date")
                app_end = shift.get("application_end_date")
                
                if not app_start or not app_end:
                    continue
                
                try:
                    app_start_date = datetime.strptime(app_start, "%d.%m.%Y").date()
                    app_end_date = datetime.strptime(app_end, "%d.%m.%Y").date()
                    
                    # Проверяем, начинается ли прием заявок сегодня
                    if app_start_date == current_date:
                        notifications.append({
                            "type": "application_start",
                            "shift": shift["name"],
                            "date": app_start,
                            "end_date": app_end
                        })
                    
                    # Проверяем, заканчивается ли прiem заявок завтра
                    elif app_end_date == current_date + timedelta(days=1):
                        notifications.append({
                            "type": "application_end_tomorrow",
                            "shift": shift["name"],
                            "date": app_end
                        })
                    
                    # Проверяем, заканчивается ли прием заявок сегодня
                    elif app_end_date == current_date:
                        notifications.append({
                            "type": "application_end_today",
                            "shift": shift["name"],
                            "date": app_end
                        })
                        
                except ValueError:
                    continue
            
            # Отправляем уведомления
            for notification in notifications:
                await self._send_deadline_notification(notification, subscribers)
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки дедлайнов: {e}")
    
    async def _send_deadline_notification(self, notification: Dict, subscribers: List[int]):
        """Отправляет уведомление о дедлайне"""
        if notification["type"] == "application_start":
            message = (
                f"🚀 Сегодня открывается прием заявок!\n\n"
                f"📚 Смена: {notification['shift']}\n"
                f"📅 Прием заявок: с {notification['date']} по {notification['end_date']}\n\n"
                f"⏰ Не упустите возможность подать заявку!\n"
                f"📱 Используйте /calendar для получения подробной информации"
            )
        elif notification["type"] == "application_end_tomorrow":
            message = (
                f"⏰ Завтра заканчивается прием заявок!\n\n"
                f"📚 Смена: {notification['shift']}\n"
                f"📅 Последний день подачи: {notification['date']}\n\n"
                f"🏃‍♂️ Поспешите подать заявку, если еще не сделали этого!\n"
                f"📱 Используйте /calendar для получения подробной информации"
            )
        elif notification["type"] == "application_end_today":
            message = (
                f"🔥 Сегодня последний день приема заявок!\n\n"
                f"📚 Смена: {notification['shift']}\n"
                f"📅 Прием заканчивается: {notification['date']}\n\n"
                f"⚡ Это последний шанс подать заявку!\n"
                f"📱 Используйте /calendar для получения подробной информации"
            )
        else:
            return
        
        success_count = 0
        for user_id in subscribers:
            try:
                await self.bot.send_message(user_id, message)
                success_count += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.warning(f"⚠️ Не удалось отправить уведомление о дедлайне пользователю {user_id}: {e}")
        
        logger.info(f"📬 Отправлено уведомлений о дедлайне ({notification['type']}): {success_count}/{len(subscribers)}")

# Глобальный экземпляр системы уведомлений
notification_system = NotificationSystem() 