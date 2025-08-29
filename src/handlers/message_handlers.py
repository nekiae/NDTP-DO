"""
Обработчики сообщений NDTP Bot
"""
import asyncio
import logging
import time

from aiogram import Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message,InlineKeyboardButton, InlineKeyboardMarkup

from src.services.parsers.lists_parser import search_name_in_lists
from src.utils.helpers import shorten_document_name
from ..core.config import config
from ..core.constants import get_system_prompt
from ..handlers.operator_handler import operator_handler
from src.core.constants import UserStatus
from ..services.deepseek_client import deepseek_client
from ..services.context_service import get_enhanced_context

logger = logging.getLogger(__name__)




async def handle_text_message(message: Message, state: FSMContext, bot: Bot) -> None:
    """
    Главный обработчик текстовых сообщений
    
    Маршрутизирует сообщения в зависимости от статуса пользователя
    """
    user_id = message.from_user.id
    current_state = await state.get_state()

    # Исключаем операторов из этого обработчика
    if operator_handler.operator_manager.is_operator(user_id):
        logger.warning(
            f"⚠️ ВНИМАНИЕ: Сообщение оператора {user_id} попало в обработчик пользователей!"
        )
        return

    # Исключаем специальные состояния модулей
    if _is_special_module_state(message, current_state):
        return

    logger.info(f"📝 Получено сообщение от пользователя {user_id}: '{message.text}'")

    # Проверяем статус пользователя
    user_status = operator_handler.get_user_status(user_id)
    logger.info(f"👤 Статус пользователя {user_id}: {user_status}")

    # Маршрутизация по статусу
    if user_status == UserStatus.WAITING_OPERATOR:
        await _handle_waiting_operator(message, user_id)
    elif user_status == UserStatus.WITH_OPERATOR:
        await _handle_with_operator(message, user_id, bot)
    elif user_status == UserStatus.RATING_OPERATOR:
        await _handle_rating_required(message)
    elif current_state == UserStatus.SEARCHING_LISTS:
        await _handle_lists_search(message, state)
    else:
        # Обычная обработка сообщения с использованием ИИ
        await _handle_ai_response(message, bot)


def _is_special_module_state(message: Message, current_state: str) -> bool:
    """Проверка специальных состояний модулей"""
    # Исключаем команду /quiz и состояния квиза
    if config.enable_quiz and (
        message.text == "/quiz" or 
        (current_state and current_state.startswith("QuizState"))
    ):
        return True

    # Исключаем команду /brainstorm и состояния брейншторма  
    if config.enable_brainstorm and (
        message.text == "/brainstorm" or
        (current_state and current_state.startswith("BrainstormState"))
    ):
        return True

    return False


async def _handle_waiting_operator(message: Message, user_id: int) -> None:
    """Обработка сообщений от пользователей, ожидающих консультанта"""
    logger.info(
        f"⏳ Пользователь {user_id} ожидает консультанта - добавляем сообщение в историю"
    )
    # Добавляем сообщение в историю для консультанта
    operator_handler.add_user_message_to_history(user_id, message.text)
    await message.answer(
        "⏳ Ваш запрос уже передан консультанту. Пожалуйста, ожидайте подключения."
    )


async def _handle_with_operator(message: Message, user_id: int, bot: Bot) -> None:
    """Обработка сообщений от пользователей, подключенных к консультанту"""
    logger.info(
        f"💬 Пользователь {user_id} общается с консультантом - пересылаем сообщение"
    )
    # Пересылаем сообщение консультанту
    success = await operator_handler.forward_user_message(user_id, message, bot)
    if not success:
        await message.answer("❌ Ошибка пересылки сообщения консультанту")


async def _handle_rating_required(message: Message) -> None:
    """Обработка сообщений когда требуется оценка"""
    await message.answer(
        "⭐ Пожалуйста, сначала оцените работу консультанта, используя кнопки выше."
    )


async def _handle_lists_search(message: Message, state: FSMContext) -> None:
    """Обработка поиска в списках участников"""
    try:
        query = message.text.strip()
        
        if not query:
            await message.answer(
                "❌ Пустой запрос\n\n"
                "Пожалуйста, напишите имя фамилия для поиска.\n\n"
                "📝 Пример: Анна Иванова"
            )
            return
        
        # Отправляем сообщение о начале поиска
        search_message = await message.answer(f"🔍 Поиск: {query}\n\nПроверяю списки участников...")
        
        # Выполняем поиск
        results = await search_name_in_lists(query, search_type='student_lists')
        
        # Очищаем состояние
        await state.clear()
        
        # Формируем ответ
        if not results:
            response_text = (
                f"❌ Результат поиска: '{query}'\n\n"
                "🔍 В списках участников технопарка совпадений не найдено.\n\n"
                "💡 Рекомендации:\n"
                "• Проверьте правильность написания\n"
                "• Попробуйте ввести только имя или фамилию\n"
                "• Обратитесь к консультанту для уточнения"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Поиск другого имени", callback_data="check_lists")],
                [InlineKeyboardButton(text="👨‍💼 Связаться с консультантом", callback_data="request_consultant")],
                [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_menu")]
            ])
        else:
            response_text = f"✅ Найдено: {len(results)} совпадений\n\n"
            response_text += f"👤 Поиск: {query}\n\n"
            
            # Группируем результаты по сменам
            shifts_data = {}
            for result in results:
                shift_name = result['shift']
                if shift_name not in shifts_data:
                    shifts_data[shift_name] = []
                shifts_data[shift_name].append(result)
            
            # Сортируем смены по году (новые сверху)
            def extract_year_from_shift(shift_name):
                import re
                # Ищем год в названии смены
                year_match = re.search(r'20\d{2}', shift_name)
                if year_match:
                    return int(year_match.group())
                
                # Если год не найден, определяем по месяцам
                months_order = {
                    'январь': 1, 'февраль': 2, 'март': 3, 'апрель': 4,
                    'май': 5, 'июнь': 6, 'июль': 7, 'август': 8, 
                    'сентябрь': 9, 'октябрь': 10, 'ноябрь': 11, 'декабрь': 12
                }
                
                shift_lower = shift_name.lower()
                for month, order in months_order.items():
                    if month in shift_lower:
                        # Предполагаем текущий год, если не указан
                        from datetime import datetime
                        current_year = datetime.now().year
                        return current_year * 100 + order  # Комбинируем год и месяц для сортировки
                
                return 0  # Неизвестные смены в конец
            
            # Сортируем по году/месяцу (новые сверху)
            sorted_shifts = sorted(shifts_data.items(), 
                                key=lambda x: extract_year_from_shift(x[0]), 
                                reverse=True)
            
            # Формируем список найденных смен
            for i, (shift_name, shift_results) in enumerate(sorted_shifts, 1):
                response_text += f"📋 {shift_name}\n"
                
                # Показываем сокращенные названия документов
                unique_docs = set()
                for result in shift_results:
                    doc_name = result['document']
                    # Применяем умное сокращение названий
                    short_name = shorten_document_name(doc_name)
                    unique_docs.add(short_name)
                
                for doc in sorted(unique_docs):
                    response_text += f"   ✓ {doc}\n"
                
                response_text += "\n"
            
            # Добавляем пояснение
            response_text += "💡 Данные найдены в официальных списках технопарка\n"
            
            # Если результатов много, обрезаем
            if len(response_text) > 3500:
                response_text = response_text[:3500] + "\n\n📄 *Показаны основные результаты*"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Поиск другого имени", callback_data="check_lists")],
                [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_menu")]
            ])
        
        # Обновляем сообщение с результатами
        await search_message.edit_text(response_text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"❌ Ошибка поиска в списках: {e}")
        await message.answer(
            "⚠️ Временная ошибка поиска\n\n"
            "Система поиска временно недоступна.\n"
            "Попробуйте позже или обратитесь к консультанту.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👨‍💼 Связаться с консультантом", callback_data="request_consultant")],
                [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_menu")]
            ])
        )
    await state.clear()


async def _handle_ai_response(message: Message, bot: Bot) -> None:
    """Обработка обычного сообщения с помощью ИИ"""
    user_id = message.from_user.id
    logger.info(
        f"🤖 Пользователь {user_id} (@{message.from_user.username}) спрашивает: "
        f"'{message.text[:50]}{'...' if len(message.text) > 50 else ''}'"
    )
    
    try:
        logger.info("🔍 Начинаем поиск в базе знаний...")
        
        # Запомним последнее пользовательское сообщение для возможной эскалации
        try:
            operator_handler.remember_user_message(message)
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении сообщения: {e}")

        # Получаем контекст из RAG системы
        context = await get_enhanced_context(message.text)
        logger.info(
            f"Получен контекст: {context[:200]}..."
            if len(context) > 200
            else f"Получен контекст: {context}"
        )

        # Подготовка сообщений для ИИ
        system_message = get_system_prompt()
        user_message = f"""
ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ:
{context}

ВОПРОС ПОЛЬЗОВАТЕЛЯ: {message.text}

Ответьте на вопрос пользователя, используя только информацию выше.
"""

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]

        logger.info("🚀 Отправляем стриминговый запрос к DeepSeek API...")

        # Отправляем начальное сообщение для редактирования
        sent_message = await message.answer("🤔 Думаю...")

        # Получение стримингового ответа
        await _process_streaming_response(message, sent_message, messages, bot)

    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}", exc_info=True)
        await message.answer(
            "😔 Произошла техническая ошибка.\n"
            "Пожалуйста, попробуйте позже или обратитесь к оператору: /help"
        )


async def _process_streaming_response(
    original_message: Message, 
    sent_message: Message, 
    messages: list, 
    bot: Bot
) -> None:
    """Обработка стримингового ответа от ИИ"""
    response_text = ""
    last_update = 0
    last_typing_time = 0
    update_interval = 100  # Обновляем каждые 100 символов
    user_id = original_message.from_user.id

    try:
        async for chunk in deepseek_client.get_streaming_completion(
            messages, temperature=0.3
        ):
            if chunk:
                response_text += chunk
                current_time = time.time()

                # Обновляем сообщение каждые N символов И если прошло минимум 2 секунды
                if (
                    len(response_text) - last_update >= update_interval
                    and current_time - last_typing_time >= 2.0
                ):
                    await _update_message_safely(
                        bot, sent_message, response_text + " ▌"
                    )
                    last_update = len(response_text)
                    last_typing_time = current_time
                    await asyncio.sleep(1.0)

        # Финальное обновление без индикатора печатания
        if response_text:
            await _update_message_safely(bot, sent_message, response_text)
            logger.info(
                f"✅ Стриминговый ответ завершен: {len(response_text)} символов "
                f"для пользователя {user_id}"
            )
            
            # Показываем кнопку эскалации если нужно
            await _show_escalation_button_if_needed(original_message, response_text)
        else:
            await _update_message_safely(
                bot, sent_message,
                "😔 Извините, произошла ошибка при получении ответа.\n"
                "Попробуйте переформулировать вопрос или обратитесь к оператору: /help"
            )

    except Exception as streaming_error:
        logger.error(f"Ошибка стриминга: {streaming_error}")
        await _update_message_safely(
            bot, sent_message,
            "😔 Извините, произошла ошибка при обработке вашего запроса.\n"
            "Попробуйте переформулировать вопрос или обратитесь к оператору: /help"
        )


async def _update_message_safely(bot: Bot, message: Message, text: str) -> None:
    """Безопасное обновление сообщения с обработкой ошибок форматирования"""
    try:
        try:
            # Сначала пробуем с Markdown
            await bot.edit_message_text(
                text,
                chat_id=message.chat.id,
                message_id=message.message_id,
                parse_mode="Markdown",
            )
        except Exception:
            # Если ошибка markdown, пробуем без форматирования
            await bot.edit_message_text(
                text,
                chat_id=message.chat.id,
                message_id=message.message_id,
            )
    except Exception as e:
        # Игнорируем ошибки редактирования (например, если текст не изменился)
        logger.debug(f"Инфо: не удалось обновить сообщение с таймером: {e}")


async def _show_escalation_button_if_needed(message: Message, response_text: str) -> None:
    """Показать кнопку эскалации если ответ содержит предложение обратиться к оператору"""
    try:
        lower_text = response_text.lower()
        if ("/help" in lower_text) or ("обратит" in lower_text and "оператор" in lower_text):
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

            help_kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Связаться с консультантом",
                            callback_data="escalate_from_last",
                        )
                    ]
                ]
            )
            await message.answer(
                "Нужна помощь консультанта? Нажмите кнопку:",
                reply_markup=help_kb,
            )
    except Exception as kb_error:
        logger.debug(f"Не удалось показать кнопку эскалации: {kb_error}")


async def handle_media_message(message: Message, bot: Bot) -> None:
    """
    Обработка медиа сообщений с учетом статуса пользователя
    
    Args:
        message: Сообщение с медиа
        bot: Экземпляр бота
    """
    user_id = message.from_user.id

    # Исключаем операторов
    if operator_handler.operator_manager.is_operator(user_id):
        logger.info(f"📨 Медиа от оператора {user_id}")
        # Пересылаем медиа пользователю
        success = await operator_handler.forward_operator_media(user_id, message, bot)
        if not success:
            await message.answer("❌ Ошибка пересылки медиа")
        return

    user_status = operator_handler.get_user_status(user_id)
    logger.info(
        f"📎 Получено медиа от пользователя {user_id}, статус: {user_status}"
    )

    # Пользователь ожидает консультанта
    if user_status == UserStatus.WAITING_OPERATOR:
        await message.answer(
            "⏳ Ваш запрос уже передан консультанту. Пожалуйста, ожидайте подключения."
        )
        return

    # Пользователь подключен к консультанту
    if user_status == UserStatus.WITH_OPERATOR:
        logger.info(
            f"💬 Пересылаем медиа от пользователя {user_id} консультанту"
        )
        success = await operator_handler.forward_user_message(user_id, message, bot)
        if not success:
            await message.answer("❌ Ошибка пересылки медиа консультанту")
        return

    # Пользователь оценивает работу консультанта
    if user_status == UserStatus.RATING_OPERATOR:
        await message.answer(
            "⭐ Пожалуйста, сначала оцените работу консультанта, используя кнопки выше."
        )
        return

    # Обычный режим - медиа не поддерживается ИИ
    await message.answer(
        "🎤 Извините, обработка медиа временно недоступна.\n"
        "📝 Пожалуйста, отправьте ваш вопрос текстом или обратитесь к оператору: /help"
    )


def register_message_handlers(dp, bot: Bot) -> None:
    """Регистрация обработчиков сообщений"""
    # Текстовые сообщения
    dp.message.register(
        handle_text_message,
        F.text
    )
    

    dp.message.register(
        handle_media_message,
        F.audio, F.sticker, F.video, F.voice, F.document, F.photo
    )

    
    logger.info("✅ Обработчики сообщений зарегистрированы")
