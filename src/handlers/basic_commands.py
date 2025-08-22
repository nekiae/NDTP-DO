"""
Обработчики основных команд NDTP Bot
"""
import logging

from aiogram import Bot, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from ..core.config import config
from ..handlers.operator_handler import operator_handler, OperatorState, UserStatus

logger = logging.getLogger(__name__)


async def cmd_start(message: Message) -> None:
    """Стартовое приветствие по ролям: админ / оператор / пользователь"""
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    logger.info(f"🎯 Команда /start от пользователя {user_id} (@{username})")

    # Админ: отдельное приветствие и подсказки по функциям
    if config.is_admin(user_id):
        admin_text = (
            "🛠 Админ-панель Технопарка\n\n"
            "Доступные возможности:\n"
            "• /queue — очередь пользователей (принятие заявок доступно операторам)\n"
            "• /consultants_stats — сводная статистика по консультантам\n"
            "• /operators — список операторов\n"
            "• /notifications — статус системы уведомлений\n"
            "• /update_schedule, /update_documents — обновление данных\n\n"
            "Подсказка: используйте /help для теста эскалации в систему консультантов."
        )
        await message.answer(admin_text)
        return

    # Оператор: подробный гайд
    if operator_handler.operator_manager.is_operator(user_id):
        text = (
            "👋 Добро пожаловать в панель консультанта!\n\n"
            "Возможности:\n"
            "• Уведомления о новых запросах c кнопкой: ✅ Принять запрос\n"
            "• /queue — список очереди с возможностью принять заявку\n"
            "• /consultants_stats — агрегированная статистика\n"
            "• /operator_stats — ваша личная статистика\n"
            "• /end_session — завершить текущую сессию\n\n"
            "Во время сессии:\n"
            "• Сообщения пользователя приходят как пересланные (с корректной подписью)\n"
            "• Ваши ответы отправляются пользователю от имени консультанта\n"
        )
        await message.answer(text)
        return

    # Пользователь: обычное приветствие с меню
    await show_main_menu(message)


async def show_main_menu(message: Message) -> None:
    """Показать главное меню пользователю"""
    welcome_text = (
        "👋 Добро пожаловать в бот Национального детского технопарка!\n\n"
        "🤖 Я ваш интеллектуальный помощник. Выберите интересующую вас тему:"
    )

    keyboard_rows = [
        [
            InlineKeyboardButton(text="🏫 О технопарке", callback_data="info_about"),
            InlineKeyboardButton(
                text="📚 Направления обучения", callback_data="info_programs"
            ),
        ],
        [InlineKeyboardButton(text="📝 Поступление", callback_data="info_admission")],
    ]

    # Добавляем модули если они доступны
    if config.enable_brainstorm:
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="🧠 Брейншторм идей", callback_data="start_brainstorm"
                )
            ]
        )

    if config.enable_calendar:
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="📅 Календарь смен", callback_data="show_calendar"
                )
            ]
        )

    if config.enable_lists:
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="📋 Проверить списки", callback_data="check_lists"
                )
            ]
        )

    if config.enable_quiz:
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="🎯 Квиз: подбор направления", callback_data="start_quiz"
                )
            ]
        )

    keyboard_rows.append(
        [
            InlineKeyboardButton(
                text="👨‍💼 Связаться с консультантом",
                callback_data="request_consultant",
            )
        ]
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await message.answer(welcome_text, reply_markup=keyboard)


async def cmd_menu(message: Message) -> None:
    """Главное меню (аналог callback back_to_menu)"""
    await show_main_menu(message)


async def cmd_help(message: Message, state: FSMContext, bot: Bot) -> None:
    """Запрос помощи от консультанта"""
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    logger.info(
        f"🆘 Команда /help от пользователя {user_id} (@{username}) - запрос консультанта"
    )

    # Используем API для эскалации к оператору
    success = await operator_handler.escalate_to_operator(
        user_id, message, auto_escalation=False, bot=bot
    )

    if success:
        await state.set_state(OperatorState.WAITING_OPERATOR)
        queue_info = operator_handler.get_queue_info()
        position = len(
            [u for u in queue_info["queue_details"] if u["user_id"] == user_id]
        )

        await message.answer(
            "📞 Ваш запрос передан консультанту.\n"
            "Пожалуйста, ожидайте подключения.\n\n"
            f"📋 Ваша позиция в очереди: {position}\n"
            "⏰ Среднее время ожидания: 3-5 минут\n\n"
            "Вы можете отменить ожидание командой /cancel"
        )
    else:
        await message.answer(
            "❌ Не удалось подключиться к системе операторов. Попробуйте позже."
        )


async def cmd_status(message: Message) -> None:
    """Показать статус пользователя"""
    user_id = message.from_user.id
    user_status = operator_handler.get_user_status(user_id)

    logger.info(
        f"ℹ️ Запрос статуса от пользователя {user_id}, статус: {user_status.value}"
    )

    # Определяем текст статуса
    status_descriptions = {
        UserStatus.NORMAL: "🟢 Обычный режим - можете задавать вопросы",
        UserStatus.WAITING_OPERATOR: "⏳ Ожидаете подключения консультанта",
        UserStatus.WITH_OPERATOR: "💬 Общаетесь с консультантом",
        UserStatus.RATING_OPERATOR: "⭐ Необходимо оценить работу консультанта",
    }

    status_text = (
        f"ℹ️ Ваш статус: {status_descriptions.get(user_status, 'Неизвестно')}\n\n"
    )

    # Дополнительная информация в зависимости от статуса
    if (
        user_status == UserStatus.WAITING_OPERATOR
        and user_id in operator_handler.waiting_queue
    ):
        request_info = operator_handler.waiting_queue[user_id]
        status_text += (
            f"📋 Информация о запросе:\n"
            f"⏰ Время запроса: {request_info['request_time'].strftime('%H:%M:%S')}\n"
            f"📍 Позиция в очереди: {request_info['queue_position']}\n\n"
        )
    elif (
        user_status == UserStatus.WITH_OPERATOR
        and user_id in operator_handler.active_sessions
    ):
        session_info = operator_handler.active_sessions[user_id]
        operator_info = operator_handler.operator_manager.get_operator_info(
            session_info["operator_id"]
        )
        status_text += (
            f"👨‍💼 Консультант: {operator_info['name']}\n"
            f"⏰ Начало сессии: {session_info['start_time'].strftime('%H:%M:%S')}\n"
            f"📝 Сообщений: {session_info.get('message_count', 0)}\n\n"
        )

    # Дополнительная информация о системе
    queue_info = operator_handler.get_queue_info()
    status_text += (
        f"📊 Статус системы:\n"
        f"⏳ В очереди ожидания: {queue_info['waiting_count']}\n"
        f"💬 Активные сессии: {queue_info['active_sessions']}\n"
        f"👨‍💼 Операторов онлайн: {queue_info['active_operators']}\n\n"
        f"Команды: /help - запросить консультанта, /cancel - отмена"
    )

    await message.answer(status_text)


async def cmd_cancel(message: Message, state: FSMContext, bot: Bot) -> None:
    """Отмена текущей операции"""
    user_id = message.from_user.id
    current_state = await state.get_state()
    user_status = operator_handler.get_user_status(user_id)

    logger.info(
        f"🚫 Команда /cancel от пользователя {user_id}, статус: {user_status.value}"
    )

    # Отмена ожидания оператора или активной сессии
    if user_status == UserStatus.WAITING_OPERATOR:
        success, msg = await operator_handler.cancel_waiting(user_id, bot)
        if success:
            await state.clear()
            await message.answer(
                "❌ Ожидание консультанта отменено. Чем еще могу помочь?"
            )
        else:
            await message.answer(f"❌ {msg}")
    elif user_status == UserStatus.WITH_OPERATOR:
        success = await operator_handler.end_session(
            user_id, bot, "завершена пользователем"
        )
        if success:
            await state.clear()
            await message.answer(
                "❌ Сессия с консультантом завершена. Чем еще могу помочь?"
            )
        else:
            await message.answer("❌ Ошибка завершения сессии")
    elif user_status == UserStatus.RATING_OPERATOR:
        # Пропускаем оценку и завершаем
        operator_handler.set_user_status(user_id, UserStatus.NORMAL)
        await state.clear()
        await message.answer("❌ Оценка пропущена. Чем еще могу помочь?")
    elif current_state is not None:
        await state.clear()
        await message.answer("❌ Операция отменена. Чем еще могу помочь?")
    else:
        await message.answer("❌ Нечего отменять.")


async def handle_request_consultant(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обработка кнопки 'Связаться с консультантом'"""
    try:
        user = callback.from_user
        chat_id = callback.message.chat.id if callback.message else user.id
        
        # Эскалируем с явными атрибутами пользователя
        success = await operator_handler.escalate_to_operator(
            user.id,
            callback.message,
            auto_escalation=False,
            bot=bot,
            first_name=user.first_name or "",
            username=user.username or "",
            chat_id=chat_id,
            origin_message_id=None,
            original_message_override="Запрос консультации",
        )
        
        if success:
            await state.set_state(OperatorState.WAITING_OPERATOR)
            queue_info = operator_handler.get_queue_info()
            position = len(
                [u for u in queue_info["queue_details"] if u["user_id"] == user.id]
            )
            await callback.message.answer(
                "📞 Ваш запрос передан консультанту.\n"
                "Пожалуйста, ожидайте подключения.\n\n"
                f"📋 Ваша позиция в очереди: {position}\n"
                "⏰ Среднее время ожидания: 3-5 минут\n\n"
                "Вы можете отменить ожидание командой /cancel"
            )
        else:
            await callback.message.answer(
                "❌ Не удалось подключиться к системе операторов. Попробуйте позже."
            )
    finally:
        try:
            await callback.answer()
        except Exception as e:
            logger.error(f"❌ Ошибка при ответе на callback: {e}")


def register_basic_commands(dp, bot: Bot) -> None:
    """Регистрация базовых команд"""
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_menu, Command("menu"))
    dp.message.register(lambda msg, state: cmd_help(msg, state, bot), Command("help"))
    dp.message.register(cmd_status, Command("status"))
    dp.message.register(lambda msg, state: cmd_cancel(msg, state, bot), Command("cancel"))
    
    dp.callback_query.register(
        lambda cb, state: handle_request_consultant(cb, state, bot), 
        F.data == "request_consultant"
    )
    
    logger.info("✅ Базовые команды зарегистрированы")
