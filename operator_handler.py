import logging
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from enum import Enum
from aiogram import types, Bot
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

class UserStatus(Enum):
    NORMAL = "normal"
    WAITING_OPERATOR = "waiting_operator" 
    WITH_OPERATOR = "with_operator"
    RATING_OPERATOR = "rating_operator"

class OperatorState(StatesGroup):
    WAITING_OPERATOR = State()
    CONNECTED_TO_OPERATOR = State()
    RATING_OPERATOR = State()

class EscalationEngine:
    """Простой движок для анализа необходимости эскалации через уверенность ИИ"""
    
    @classmethod
    def analyze_escalation_need(cls, user_message: str, ai_confidence: float = 0.8) -> bool:
        """
        Анализирует необходимость эскалации запроса только по уверенности ИИ
        
        Returns:
            needs_escalation (bool)
        """
        # Если уверенность ИИ низкая - эскалируем
        if ai_confidence < 0.7:
            return True
        
        return False

class OperatorManager:
    """Простой менеджер операторов"""
    
    def __init__(self):
        # Упрощенная конфигурация операторов
        self.operators_config = {
            7148748755: {  # Реальный оператор
                "name": "Консультант Технопарка",
                "is_active": True,
                "rating": 5.0,
                "total_sessions": 0
            }
        }
        
    def get_active_operators(self) -> List[int]:
        """Получить список активных операторов"""
        active_operators = []
        
        for op_id, config in self.operators_config.items():
            if config["is_active"]:
                active_operators.append(op_id)
                logger.info(f"Оператор {op_id} активен")
                
        return active_operators
    
    def is_operator(self, user_id: int) -> bool:
        """Проверить, является ли пользователь оператором"""
        return user_id in self.operators_config
    
    def get_operator_info(self, operator_id: int) -> Optional[Dict]:
        """Получить информацию об операторе"""
        return self.operators_config.get(operator_id)

class OperatorHandler:
    """Упрощенный класс для обработки эскалации к операторам"""
    
    def __init__(self):
        self.waiting_queue: Dict[int, Dict] = {}  # Очередь ожидания
        self.active_sessions: Dict[int, Dict] = {}  # Активные сессии
        self.user_states: Dict[int, UserStatus] = {}  # Статусы пользователей
        self.session_history: Dict[int, List] = {}  # История сессий
        
        self.operator_manager = OperatorManager()
        self.escalation_engine = EscalationEngine()
        
    def get_user_status(self, user_id: int) -> UserStatus:
        """Получить статус пользователя"""
        return self.user_states.get(user_id, UserStatus.NORMAL)
    
    def set_user_status(self, user_id: int, status: UserStatus):
        """Установить статус пользователя"""
        self.user_states[user_id] = status
        logger.info(f"Пользователь {user_id} изменил статус на {status.value}")
    
    async def analyze_message_for_escalation(self, message: str, ai_confidence: float = 0.8) -> Dict:
        """Анализировать сообщение на необходимость эскалации"""
        needs_escalation = self.escalation_engine.analyze_escalation_need(message, ai_confidence)
        
        return {
            "needs_escalation": needs_escalation,
            "confidence": ai_confidence,
            "reason": "low_ai_confidence" if needs_escalation else "confident_response"
        }
    
    async def escalate_to_operator(self, user_id: int, message: types.Message, 
                                 auto_escalation: bool = False, bot=None) -> bool:
        """Эскалировать запрос к оператору"""
        
        if self.get_user_status(user_id) != UserStatus.NORMAL:
            return False
            
        # Добавляем в очередь
        queue_position = len(self.waiting_queue) + 1
        self.waiting_queue[user_id] = {
            "user_id": user_id,
            "username": message.from_user.username or "Пользователь",
            "first_name": message.from_user.first_name or "",
            "chat_id": message.chat.id,
            "request_time": datetime.now(),
            "original_message": message.text,
            "queue_position": queue_position,
            "auto_escalation": auto_escalation,
            "message_history": []
        }
        
        self.set_user_status(user_id, UserStatus.WAITING_OPERATOR)
        
        # Уведомляем операторов
        await self._notify_available_operators(user_id, bot)
        
        return True
    
    async def _notify_available_operators(self, user_id: int, bot=None):
        """Уведомить доступных операторов о новом запросе"""
        if user_id not in self.waiting_queue:
            logger.warning(f"Пользователь {user_id} не найден в очереди ожидания")
            return
            
        request_info = self.waiting_queue[user_id]
        active_operators = self.operator_manager.get_active_operators()
        
        logger.info(f"🔍 Поиск активных операторов для пользователя {user_id}")
        logger.info(f"📋 Найдено активных операторов: {len(active_operators)} - {active_operators}")
        
        if not active_operators:
            logger.warning("❌ Нет активных операторов")
            return
        
        notification_text = (
            f"📝 **Новый запрос**\n\n"
            f"👤 **Пользователь:** {request_info['first_name']}\n"
            f"📱 Username: @{request_info['username']}\n"
            f"⏰ **Время:** {request_info['request_time'].strftime('%H:%M:%S')}\n"
            f"📋 **Позиция в очереди:** {request_info['queue_position']}\n\n"
            f"💬 **Запрос:**\n_{request_info['original_message']}_"
        )
        
        # Создаем инлайн-кнопки
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принять запрос", 
                    callback_data=f"accept_request_{user_id}"
                )
            ]
        ])
        
        # Отправляем уведомления операторам
        if bot:
            logger.info(f"📤 Отправка уведомлений {len(active_operators)} операторам")
            for operator_id in active_operators:
                try:
                    logger.info(f"📨 Отправка уведомления оператору {operator_id}...")
                    await bot.send_message(
                        operator_id, 
                        notification_text,
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
                    logger.info(f"✅ Уведомление успешно отправлено оператору {operator_id}")
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки уведомления оператору {operator_id}: {e}")
        else:
            logger.error("❌ Объект bot не передан!")
    
    def add_user_message_to_history(self, user_id: int, message: str, timestamp: datetime = None):
        """Добавить сообщение пользователя в историю"""
        if timestamp is None:
            timestamp = datetime.now()
            
        message_entry = {
            'text': message,
            'timestamp': timestamp,
            'type': 'user'
        }
        
        # Добавляем в очередь ожидания если пользователь там
        if user_id in self.waiting_queue:
            if 'message_history' not in self.waiting_queue[user_id]:
                self.waiting_queue[user_id]['message_history'] = []
            
            self.waiting_queue[user_id]['message_history'].append(message_entry)
            
            # Ограничиваем историю последними 5 сообщениями
            if len(self.waiting_queue[user_id]['message_history']) > 5:
                self.waiting_queue[user_id]['message_history'] = \
                    self.waiting_queue[user_id]['message_history'][-5:]
    
    async def accept_request(self, operator_id: int, user_id: int, bot: Bot) -> Tuple[bool, str]:
        """Принять запрос оператором"""
        
        if not self.operator_manager.is_operator(operator_id):
            return False, "Вы не являетесь оператором системы"
        
        if user_id not in self.waiting_queue:
            return False, "Запрос не найден в очереди"
        
        # Создаем активную сессию
        request_info = self.waiting_queue.pop(user_id)
        
        operator_config = self.operator_manager.get_operator_info(operator_id)
        
        self.active_sessions[user_id] = {
            **request_info,
            "operator_id": operator_id,
            "operator_name": operator_config["name"],
            "connection_time": datetime.now(),
            "last_activity": datetime.now(),
            "session_messages": [],
            "session_id": f"session_{user_id}_{int(datetime.now().timestamp())}"
        }
        
        # Меняем статус пользователя
        self.set_user_status(user_id, UserStatus.WITH_OPERATOR)
        
        # Перенумеровываем очередь
        await self._reorder_queue()
        
        # Уведомляем пользователя
        try:
            end_session_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Завершить консультацию", callback_data="end_user_session")]
            ])
            
            await bot.send_message(
                request_info["chat_id"],
                f"✅ Консультант подключился к диалогу!\n\n"
                f"📞 Теперь вы общаетесь напрямую с нашим специалистом\n"
                f"💬 Можете задать все интересующие вас вопросы\n\n"
                f"⏰ Время подключения: {datetime.now().strftime('%H:%M')}",
                reply_markup=end_session_keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователя {user_id}: {e}")
        
        # Уведомляем консультанта с кнопкой завершения
        try:
            operator_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔚 Завершить сессию", callback_data=f"operator_end_session_{user_id}")]
            ])
            
            await bot.send_message(
                operator_id,
                f"✅ Вы подключились к пользователю!\n\n"
                f"👤 Пользователь: {request_info['first_name']}\n"
                f"💬 Исходный запрос: {request_info['original_message']}\n\n"
                f"📞 Сессия активна. Все ваши сообщения будут переданы пользователю.",
                reply_markup=operator_keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления консультанта {operator_id}: {e}")
        
        return True, f"Подключен к пользователю {request_info['first_name']}"
    
    async def _reorder_queue(self):
        """Перенумеровать очередь после изменений"""
        sorted_queue = sorted(
            self.waiting_queue.items(), 
            key=lambda x: x[1]["request_time"]
        )
        
        for i, (user_id, request_info) in enumerate(sorted_queue, 1):
            self.waiting_queue[user_id]["queue_position"] = i
    
    async def forward_user_message(self, user_id: int, message: types.Message, bot: Bot) -> bool:
        """Переслать сообщение пользователя оператору"""
        if user_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[user_id]
        operator_id = session["operator_id"]
        
        # Сохраняем сообщение в истории сессии
        session["session_messages"].append({
            "from": "user",
            "text": message.text or "[медиа]",
            "timestamp": datetime.now(),
            "message_type": "text" if message.text else "media"
        })
        
        session["last_activity"] = datetime.now()
        
        try:
            # Пересылаем оператору
            prefix = f"💬 {session['first_name']}:"
            
            if message.text:
                await bot.send_message(operator_id, f"{prefix} {message.text}")
            elif message.photo:
                await bot.send_photo(operator_id, message.photo[-1].file_id, 
                                   caption=f"{prefix} [фото]")
            elif message.document:
                await bot.send_document(operator_id, message.document.file_id,
                                      caption=f"{prefix} [документ]")
            elif message.voice:
                await bot.send_voice(operator_id, message.voice.file_id,
                                   caption=f"{prefix} [голосовое сообщение]")
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка пересылки сообщения оператору {operator_id}: {e}")
            return False
    
    async def forward_operator_message(self, operator_id: int, message_text: str, bot: Bot) -> Tuple[bool, str]:
        """Переслать сообщение оператора пользователю"""
        
        # Найти активную сессию для оператора
        user_session = None
        
        for user_id, session in self.active_sessions.items():
            if session["operator_id"] == operator_id:
                user_session = session
                break
        
        if not user_session:
            return False, "Активная сессия не найдена"
        
        # Сохраняем в истории
        user_session["session_messages"].append({
            "from": "operator",
            "text": message_text,
            "timestamp": datetime.now(),
            "message_type": "text"
        })
        
        user_session["last_activity"] = datetime.now()
        
        try:
            await bot.send_message(
                user_session["chat_id"],
                message_text
            )
            return True, "Сообщение отправлено пользователю"
            
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения пользователю: {e}")
            return False, f"Ошибка отправки: {e}"
    
    async def end_session(self, user_id: int, bot: Bot, reason: str = "завершена") -> bool:
        """Завершить сессию с оператором"""
        if user_id not in self.active_sessions:
            return False
        
        session = self.active_sessions.pop(user_id)
        operator_id = session["operator_id"]
        
        # Сохраняем в историю
        session_duration = datetime.now() - session["connection_time"]
        session["end_time"] = datetime.now()
        session["duration"] = session_duration.total_seconds()
        session["end_reason"] = reason
        
        self.session_history[user_id] = self.session_history.get(user_id, [])
        self.session_history[user_id].append(session)
        
        # Переводим в режим оценки
        self.set_user_status(user_id, UserStatus.RATING_OPERATOR)
        
        # Отправляем форму оценки
        try:
            rating_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data=f"rate_5_{operator_id}"),
                    InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data=f"rate_4_{operator_id}")
                ],
                [
                    InlineKeyboardButton(text="⭐⭐⭐", callback_data=f"rate_3_{operator_id}"),
                    InlineKeyboardButton(text="⭐⭐", callback_data=f"rate_2_{operator_id}")
                ],
                [
                    InlineKeyboardButton(text="⭐", callback_data=f"rate_1_{operator_id}"),
                    InlineKeyboardButton(text="Пропустить", callback_data="rate_skip")
                ]
            ])
            
            await bot.send_message(
                session["chat_id"],
                f"📞 Сессия с консультантом {reason}.\n\n"
                f"⏱ Продолжительность: {int(session_duration.total_seconds() // 60)} мин\n"
                f"💬 Сообщений: {len(session['session_messages'])}\n\n"
                f"⭐ Пожалуйста, оцените качество консультации:",
                reply_markup=rating_keyboard
            )
            
        except Exception as e:
            logger.error(f"Ошибка отправки формы оценки: {e}")
            self.set_user_status(user_id, UserStatus.NORMAL)
        
        return True
    
    async def rate_operator(self, user_id: int, operator_id: int, rating: int, bot: Bot) -> bool:
        """Оценить работу оператора"""
        if self.get_user_status(user_id) != UserStatus.RATING_OPERATOR:
            return False
        
        # Сохраняем оценку
        if user_id in self.session_history:
            last_session = self.session_history[user_id][-1]
            last_session["user_rating"] = rating
            last_session["rating_time"] = datetime.now()
        
        # Обновляем рейтинг оператора
        operator_config = self.operator_manager.operators_config.get(operator_id)
        if operator_config:
            total_sessions = operator_config["total_sessions"]
            current_rating = operator_config["rating"]
            
            # Вычисляем новый рейтинг
            new_rating = ((current_rating * total_sessions) + rating) / (total_sessions + 1)
            operator_config["rating"] = round(new_rating, 2)
            operator_config["total_sessions"] += 1
        
        # Возвращаем в нормальный статус
        self.set_user_status(user_id, UserStatus.NORMAL)
        
        # Благодарим за оценку
        try:
            rating_text = "⭐" * rating if rating > 0 else "Спасибо за обратную связь"
            await bot.send_message(
                self.active_sessions.get(user_id, {}).get("chat_id") or user_id,
                f"✅ Спасибо за оценку: {rating_text}\n\n"
                f"Ваше мнение поможет нам улучшить качество обслуживания!\n"
                f"Если у вас есть другие вопросы, обращайтесь в любое время."
            )
        except Exception as e:
            logger.error(f"Ошибка отправки благодарности: {e}")
        
        return True
    
    async def cancel_waiting(self, user_id: int, bot: Bot) -> Tuple[bool, str]:
        """Отменить ожидание оператора"""
        if user_id not in self.waiting_queue:
            return False, "Вы не находитесь в очереди ожидания"
        
        self.waiting_queue.pop(user_id)
        self.set_user_status(user_id, UserStatus.NORMAL)
        
        # Перенумеровываем очередь
        await self._reorder_queue()
        
        return True, "Ожидание отменено"
    
    def get_queue_info(self) -> Dict:
        """Получить информацию о текущей очереди"""
        total_waiting = len(self.waiting_queue)
        total_active = len(self.active_sessions)
        active_operators = len(self.operator_manager.get_active_operators())
        
        return {
            "waiting_count": total_waiting,
            "active_sessions": total_active,
            "active_operators": active_operators,
            "queue_details": list(self.waiting_queue.values())
        }

# Создаем глобальный экземпляр
operator_handler = OperatorHandler()

def get_operator_handler() -> OperatorHandler:
    """Получить экземпляр обработчика операторов"""
    return operator_handler 