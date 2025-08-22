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

def register_operator_handlers(dp, bot):
    """Регистрирует обработчики операторов в диспетчере"""
    from aiogram import F
    from aiogram.filters import Command
    
    logger.info("📋 Регистрация обработчиков операторов...")
    
    # Обработчик команды для связи с оператором
    @dp.message(Command("help"))
    async def help_command(message: types.Message):
        """Команда связи с консультантом"""
        user_id = message.from_user.id
        
        # Проверяем текущий статус пользователя
        status = operator_handler.get_user_status(user_id)
        
        if status == UserStatus.WAITING_OPERATOR:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить ожидание", callback_data="cancel_waiting")]
            ])
            await message.answer(
                "⏳ Вы уже находитесь в очереди на консультацию.\n"
                "Пожалуйста, ожидайте подключения консультанта.",
                reply_markup=keyboard
            )
            return
        
        elif status == UserStatus.WITH_OPERATOR:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Завершить консультацию", callback_data="end_user_session")]
            ])
            await message.answer(
                "💬 Вы сейчас общаетесь с консультантом.\n"
                "Можете продолжить диалог или завершить сессию.",
                reply_markup=keyboard
            )
            return
        
        # Предлагаем связаться с оператором
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👨‍💼 Связаться с консультантом", callback_data="request_operator")]
        ])
        
        await message.answer(
            "🤝 **Нужна помощь консультанта?**\n\n"
            "Наши специалисты готовы ответить на ваши вопросы\n"
            "о поступлении и обучении в Национальном детском технопарке.\n\n"
            "💡 *Обычно консультанты отвечают в течение нескольких минут*",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    # Обработчик callback для запроса оператора
    @dp.callback_query(F.data == "request_operator")
    async def request_operator_callback(callback: types.CallbackQuery):
        """Обработка запроса на связь с оператором"""
        await callback.answer()
        
        user_id = callback.from_user.id
        success = await operator_handler.escalate_to_operator(
            user_id, callback.message, auto_escalation=False, bot=bot
        )
        
        if success:
            queue_info = operator_handler.get_queue_info()
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить ожидание", callback_data="cancel_waiting")]
            ])
            
            await callback.message.edit_text(
                f"✅ **Запрос отправлен консультантам!**\n\n"
                f"📋 Ваше место в очереди: **{queue_info['waiting_count']}**\n"
                f"👥 Активных сессий: {queue_info['active_sessions']}\n"
                f"🟢 Доступных консультантов: {queue_info['active_operators']}\n\n"
                f"⏰ Ожидаемое время ответа: **2-5 минут**\n"
                f"💬 Можете написать дополнительные вопросы - они будут переданы консультанту",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text(
                "❌ Извините, сейчас нет доступных консультантов.\n"
                "Попробуйте обратиться позже."
            )
    
    # Обработчик принятия запроса оператором
    @dp.callback_query(F.data.startswith("accept_request_"))
    async def accept_request_callback(callback: types.CallbackQuery):
        """Принятие запроса оператором"""
        await callback.answer()
        
        try:
            user_id = int(callback.data.split("_")[-1])
            operator_id = callback.from_user.id
            
            success, message_text = await operator_handler.accept_request(
                operator_id, user_id, bot
            )
            
            if success:
                await callback.message.edit_text(
                    f"✅ {message_text}\n\n"
                    f"📞 Сессия активна. Все ваши сообщения будут переданы пользователю."
                )
            else:
                await callback.message.edit_text(f"❌ {message_text}")
                
        except Exception as e:
            logger.error(f"Ошибка принятия запроса: {e}")
            await callback.message.edit_text("❌ Ошибка при подключении к пользователю")
    
    # Обработчик отмены ожидания
    @dp.callback_query(F.data == "cancel_waiting")
    async def cancel_waiting_callback(callback: types.CallbackQuery):
        """Отмена ожидания оператора"""
        await callback.answer()
        
        user_id = callback.from_user.id
        success, message_text = await operator_handler.cancel_waiting(user_id, bot)
        
        if success:
            await callback.message.edit_text(
                f"✅ {message_text}\n\n"
                f"Если у вас останутся вопросы, вы всегда можете обратиться к нам снова!"
            )
        else:
            await callback.message.edit_text(f"❌ {message_text}")
    
    # Обработчик завершения сессии пользователем
    @dp.callback_query(F.data == "end_user_session")
    async def end_user_session_callback(callback: types.CallbackQuery):
        """Завершение сессии пользователем"""
        await callback.answer()
        
        user_id = callback.from_user.id
        success = await operator_handler.end_session(
            user_id, bot, reason="завершена пользователем"
        )
        
        if success:
            await callback.message.edit_text(
                "📞 Сессия с консультантом завершена.\n\n"
                "Спасибо за обращение! Если у вас появятся новые вопросы, "
                "мы всегда готовы помочь."
            )
        else:
            await callback.message.edit_text(
                "❌ Активная сессия не найдена"
            )
    
    # Обработчик завершения сессии оператором
    @dp.callback_query(F.data.startswith("operator_end_session_"))
    async def operator_end_session_callback(callback: types.CallbackQuery):
        """Завершение сессии оператором"""
        await callback.answer()
        
        try:
            user_id = int(callback.data.split("_")[-1])
            success = await operator_handler.end_session(
                user_id, bot, reason="завершена консультантом"
            )
            
            if success:
                await callback.message.edit_text(
                    "✅ Сессия завершена.\n\n"
                    "Пользователю отправлена форма для оценки качества консультации."
                )
            else:
                await callback.message.edit_text("❌ Активная сессия не найдена")
                
        except Exception as e:
            logger.error(f"Ошибка завершения сессии: {e}")
            await callback.message.edit_text("❌ Ошибка при завершении сессии")
    
    # Обработчики оценки
    @dp.callback_query(F.data.startswith("rate_"))
    async def rate_operator_callback(callback: types.CallbackQuery):
        """Обработка оценки оператора"""
        await callback.answer()
        
        user_id = callback.from_user.id
        
        if callback.data == "rate_skip":
            operator_handler.set_user_status(user_id, UserStatus.NORMAL)
            await callback.message.edit_text(
                "✅ Спасибо за обратную связь!\n\n"
                "Если у вас есть другие вопросы, обращайтесь в любое время."
            )
            return
        
        try:
            parts = callback.data.split("_")
            rating = int(parts[1])
            operator_id = int(parts[2])
            
            success = await operator_handler.rate_operator(
                user_id, operator_id, rating, bot
            )
            
            if success:
                rating_text = "⭐" * rating
                await callback.message.edit_text(
                    f"✅ Спасибо за оценку: {rating_text}\n\n"
                    f"Ваше мнение поможет нам улучшить качество обслуживания!\n"
                    f"Если у вас есть другие вопросы, обращайтесь в любое время."
                )
            else:
                await callback.message.edit_text("❌ Ошибка сохранения оценки")
                
        except Exception as e:
            logger.error(f"Ошибка обработки оценки: {e}")
            await callback.message.edit_text("❌ Ошибка при обработке оценки")
    
    # Обработчик сообщений от пользователей в сессии
    @dp.message(F.text)
    async def handle_user_messages(message: types.Message):
        """Обработка сообщений пользователей"""
        user_id = message.from_user.id
        status = operator_handler.get_user_status(user_id)
        
        # Если пользователь ожидает оператора, добавляем сообщение в историю
        if status == UserStatus.WAITING_OPERATOR:
            operator_handler.add_user_message_to_history(
                user_id, message.text, message.date
            )
        
        # Если пользователь в сессии с оператором, пересылаем сообщение
        elif status == UserStatus.WITH_OPERATOR:
            success = await operator_handler.forward_user_message(
                user_id, message, bot
            )
            if not success:
                await message.answer(
                    "❌ Ошибка передачи сообщения консультанту. "
                    "Попробуйте переподключиться."
                )
    
    # Обработчик сообщений от операторов
    @dp.message(F.text)
    async def handle_operator_messages(message: types.Message):
        """Обработка сообщений от операторов"""
        operator_id = message.from_user.id
        
        # Проверяем, является ли отправитель оператором
        if not operator_handler.operator_manager.is_operator(operator_id):
            return
        
        # Пересылаем сообщение пользователю
        success, result_message = await operator_handler.forward_operator_message(
            operator_id, message.text, bot
        )
        
        if not success:
            await message.answer(f"❌ {result_message}")
    
    logger.info("✅ Обработчики операторов зарегистрированы")
