import logging
from datetime import datetime
from typing import Dict, List
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

logger = logging.getLogger(__name__)

# Глобальная переменная для LLM
brainstorm_llm = None

# Состояния FSM для брейншторма
class BrainstormState(StatesGroup):
    PICK_DIRECTION = State()    # Выбор направления
    ACTIVE = State()           # Активный диалог вопрос-ответ

# Направления обучения НДТ (взято с официального сайта https://ndtp.by/educational_directions/)
DIRECTIONS = {
    "aerospace": {
        "id": "aerospace",
        "name": "Авиакосмические технологии",
        "emoji": "🚀",
        "tags": ["авиация", "космос", "дроны", "спутники", "летательные аппараты"],
        "description": "Изучение авиации и космических технологий"
    },
    "architecture": {
        "id": "architecture",
        "name": "Архитектура и дизайн",
        "emoji": "🏗️",
        "tags": ["архитектура", "дизайн", "проектирование", "креативность"],
        "description": "Создание архитектурных проектов и дизайн-решений"
    },
    "biotechnology": {
        "id": "biotechnology",
        "name": "Биотехнологии",
        "emoji": "🧬",
        "tags": ["лаборатория", "анализ", "исследования", "генетика", "биология"],
        "description": "Исследования в области биологии и медицины"
    },
    "vr_ar": {
        "id": "vr_ar",
        "name": "Виртуальная и дополненная реальность",
        "emoji": "🥽",
        "tags": ["VR", "AR", "виртуальная реальность", "дополненная реальность", "3D"],
        "description": "Разработка VR/AR приложений и технологий"
    },
    "green_chemistry": {
        "id": "green_chemistry",
        "name": "Зелёная химия",
        "emoji": "🌿",
        "tags": ["экология", "химия", "устойчивое развитие", "зеленые технологии"],
        "description": "Экологически безопасные химические процессы"
    },
    "environmental": {
        "id": "environmental",
        "name": "Инженерная экология",
        "emoji": "🌱",
        "tags": ["экология", "мониторинг", "очистка", "устойчивое развитие"],
        "description": "Экологические технологии и охрана окружающей среды"
    },
    "infosecurity": {
        "id": "infosecurity",
        "name": "Информационная безопасность",
        "emoji": "🔒",
        "tags": ["кибербезопасность", "защита данных", "сетевые технологии", "криптография"],
        "description": "Защита информации и компьютерных систем"
    },
    "ict": {
        "id": "ict",
        "name": "Информационные и компьютерные технологии",
        "emoji": "💻",
        "tags": ["программирование", "алгоритмы", "разработка", "веб", "мобильные приложения"],
        "description": "Программирование и разработка программного обеспечения"
    },
    "laser": {
        "id": "laser",
        "name": "Лазерные технологии",
        "emoji": "⚡",
        "tags": ["лазер", "оптика", "обработка материалов", "точность"],
        "description": "Изучение и применение лазерных технологий"
    },
    "automotive": {
        "id": "automotive",
        "name": "Машины и двигатели. Автомобилестроение",
        "emoji": "🚗",
        "tags": ["автомобили", "двигатели", "механика", "конструирование"],
        "description": "Конструирование автомобилей и двигателей"
    },
    "nano": {
        "id": "nano",
        "name": "Наноиндустрия и нанотехнологии",
        "emoji": "🔬",
        "tags": ["наноматериалы", "микроскопия", "инновации", "молекулярный уровень"],
        "description": "Изучение наноматериалов и нанотехнологий"
    },
    "natural_resources": {
        "id": "natural_resources",
        "name": "Природные ресурсы",
        "emoji": "🌍",
        "tags": ["природные ресурсы", "геология", "экология", "устойчивое развитие"],
        "description": "Изучение и рациональное использование природных ресурсов"
    },
    "robotics": {
        "id": "robotics",
        "name": "Робототехника",
        "emoji": "🤖",
        "tags": ["конструирование", "сенсоры", "программирование", "механика", "автоматизация"],
        "description": "Конструирование и программирование роботов"
    },
    "electronics": {
        "id": "electronics",
        "name": "Электроника и связь",
        "emoji": "📡",
        "tags": ["электроника", "связь", "радио", "микроэлектроника"],
        "description": "Разработка электронных устройств и систем связи"
    },
    "energy_future": {
        "id": "energy_future",
        "name": "Энергетика будущего",
        "emoji": "⚡",
        "tags": ["возобновляемые источники", "энергоэффективность", "батареи", "зеленая энергия"],
        "description": "Альтернативные источники энергии и энергосбережение"
    }
}

# Системный промпт для фасилитатора брейншторма
def get_brainstorm_system_prompt(direction: Dict) -> str:
    """Генерирует системный промпт для выбранного направления"""
    return f"""Ты — фасилитатор брейншторма Национального детского технопарка. Помогаешь школьнику самостоятельно придумать идею проекта в направлении {direction['name']} {direction['emoji']}.

Твоя роль: задавать последовательно открытые, наводящие вопросы, чтобы пользователь САМ сформулировал идею проекта.

ПРАВИЛА:
• НЕ предлагай готовые идеи, решения, названия проектов, пошаговые планы
• НЕ делай выводов, не подводи итог
• После каждого ответа пользователя задавай следующий вопрос, который логично продолжает беседу
• Вопросы должны раскрывать проблемы, мотивацию, ресурсы ученика
• Если получишь assistant_control:"stop" — вежливо завершай сессию
• Если получишь assistant_control:"done" — поздравь и напомни зафиксировать идею

НАПРАВЛЕНИЕ: {direction['name']}
ОПИСАНИЕ: {direction['description']}
ТЕГИ: {', '.join(direction['tags'])}

Начни с открытого вопроса о том, что в этом направлении кажется пользователю интересным или важным."""

# Клавиатура с направлениями
def make_directions_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с направлениями обучения"""
    builder = InlineKeyboardBuilder()
    
    # Группируем направления по 3 в ряд
    directions_list = list(DIRECTIONS.items())
    for i in range(0, len(directions_list), 3):
        row = []
        for j in range(3):
            if i + j < len(directions_list):
                dir_id, dir_info = directions_list[i + j]
                text = f"{dir_info['emoji']} {dir_info['name']}"
                row.append(InlineKeyboardButton(text=text, callback_data=f"dir_{dir_id}"))
        builder.row(*row)
    
    # Кнопка выхода
    builder.row(InlineKeyboardButton(text="⏹ Выйти", callback_data="brainstorm_exit"))
    
    return builder.as_markup()

# Клавиатура действий во время брейншторма
def make_brainstorm_actions_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру действий во время брейншторма"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Я придумал(а) идею", callback_data="brainstorm_done"),
            InlineKeyboardButton(text="⏹ Выйти", callback_data="brainstorm_exit")
        ]
    ])

# Класс для работы с LLM (аналогично существующему в bot.py)
class BrainstormLLM:
    def __init__(self, api_key: str, api_url: str = "https://api.deepseek.com/v1/chat/completions"):
        self.api_key = api_key
        self.api_url = api_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def generate_question(self, direction: Dict, history: List[Dict]) -> str:
        """Генерирует следующий вопрос на основе истории диалога"""
        try:
            import aiohttp
            
            # Подготавливаем сообщения для API
            messages = [
                {"role": "system", "content": get_brainstorm_system_prompt(direction)}
            ]
            
            # Добавляем историю диалога (только user и assistant сообщения)
            for msg in history:
                if msg["role"] in ["user", "assistant"]:
                    messages.append(msg)
                elif msg["role"] == "assistant_control":
                    # Специальные команды управления
                    if msg["content"] == "stop":
                        return "Спасибо за брейншторм! Возвращайся, когда понадобится помощь с идеями."
                    elif msg["content"] == "done":
                        return "Отлично! Зафиксируй свою идею, пока она свежа. Желаю успехов в реализации проекта!"
            
            logger.info(f"🧠 Отправляем запрос к API с {len(messages)} сообщениями")
            
            # Отправляем запрос к API
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": "deepseek-chat",
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 200
                }
                
                logger.info(f"🧠 Payload: {payload}")
                
                async with session.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result["choices"][0]["message"]["content"]
                        logger.info(f"🧠 Получен ответ от API: {content[:50]}...")
                        return content
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Ошибка API: {response.status} - {error_text}")
                        return "Извините, произошла техническая ошибка. Попробуйте позже."
                        
        except Exception as e:
            logger.error(f"❌ Ошибка генерации вопроса: {e}")
            return "Извините, произошла ошибка. Попробуйте перезапустить брейншторм."

def init_brainstorm_llm(api_key: str):
    """Инициализация LLM для брейншторма"""
    global brainstorm_llm
    try:
        brainstorm_llm = BrainstormLLM(api_key)
        logger.info("✅ LLM для брейншторма инициализирован")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации LLM для брейншторма: {e}")
        brainstorm_llm = None

# Обработчики команд
def register_brainstorm_handlers(router: Router, bot):
    """Регистрирует обработчики брейншторма"""
    
    @router.message(Command("brainstorm"))
    async def cmd_brainstorm(message: Message, state: FSMContext):
        """Запуск брейншторма"""
        user_id = message.from_user.id
        username = message.from_user.username or "без username"
        logger.info(f"🧠 Команда /brainstorm от пользователя {user_id} (@{username})")
        
        # Проверяем доступность LLM
        if not brainstorm_llm:
            await message.answer("❌ Система брейншторма временно недоступна. Попробуйте позже.")
            return
        
        await message.answer(
            "🧠 **Брейншторм идей проектов**\n\n"
            "Я помогу тебе придумать идею проекта! Выбери направление, которое тебя интересует:\n\n"
            "💡 Как это работает:\n"
            "• Я буду задавать вопросы о твоих интересах\n"
            "• Ты отвечаешь, а я задаю следующий вопрос\n"
            "• В любой момент можешь сказать, что придумал идею\n"
            "• Никаких готовых решений — только твои мысли!",
            reply_markup=make_directions_keyboard()
        )
        await state.set_state(BrainstormState.PICK_DIRECTION)
    
    @router.callback_query(BrainstormState.PICK_DIRECTION, F.data.startswith("dir_"))
    async def handle_direction_pick(callback: CallbackQuery, state: FSMContext):
        """Обработка выбора направления"""
        user_id = callback.from_user.id
        direction_id = callback.data.replace("dir_", "")
        
        if direction_id not in DIRECTIONS:
            await callback.answer("❌ Неизвестное направление", show_alert=True)
            return
        
        direction = DIRECTIONS[direction_id]
        logger.info(f"🧠 Пользователь {user_id} выбрал направление: {direction['name']}")
        
        # Сохраняем выбранное направление
        await state.update_data(
            direction=direction,
            history=[],
            rounds=0,
            start_time=datetime.now().isoformat()
        )
        
        # Начинаем брейншторм
        await callback.message.edit_text(
            f"🎯 **{direction['name']} {direction['emoji']}**\n\n"
            f"Отлично! Давай поговорим о {direction['name'].lower()}.\n"
            f"Я буду задавать вопросы, а ты отвечай честно — это поможет найти интересную идею!"
        )
        
        # Переходим в активное состояние
        await state.set_state(BrainstormState.ACTIVE)
        
        # Генерируем первый вопрос
        await ask_next_question(callback.message, state)
        await callback.answer()
    
    @router.callback_query(BrainstormState.PICK_DIRECTION, F.data == "brainstorm_exit")
    async def handle_brainstorm_exit_from_pick(callback: CallbackQuery, state: FSMContext):
        """Выход из брейншторма на этапе выбора направления"""
        await callback.message.edit_text(
            "👋 Брейншторм отменен. Возвращайся, когда захочешь придумать идею проекта!"
        )
        await state.clear()
        await callback.answer()
    
    @router.message(BrainstormState.ACTIVE)
    async def handle_user_answer(message: Message, state: FSMContext):
        """Обработка ответа пользователя"""
        user_id = message.from_user.id
        data = await state.get_data()
        
        # Добавляем ответ пользователя в историю
        user_message = {"role": "user", "content": message.text}
        data["history"].append(user_message)
        data["rounds"] = data.get("rounds", 0) + 1
        
        await state.update_data(history=data["history"], rounds=data["rounds"])
        
        logger.info(f"🧠 Пользователь {user_id} ответил (раунд {data['rounds']}): {message.text[:50]}...")
        
        # Генерируем следующий вопрос
        await ask_next_question(message, state)
    
    @router.callback_query(BrainstormState.ACTIVE, F.data.in_(["brainstorm_done", "brainstorm_exit"]))
    async def handle_brainstorm_control(callback: CallbackQuery, state: FSMContext):
        """Обработка кнопок управления брейнштормом"""
        user_id = callback.from_user.id
        data = await state.get_data()
        
        if callback.data == "brainstorm_done":
            # Пользователь придумал идею
            logger.info(f"🧠 Пользователь {user_id} завершил брейншторм с идеей (раундов: {data.get('rounds', 0)})")
            
            # Добавляем команду завершения в историю
            data["history"].append({"role": "assistant_control", "content": "done"})
            
            # Генерируем финальное сообщение
            final_message = await brainstorm_llm.generate_question(data["direction"], data["history"])
            
            await callback.message.answer(
                final_message,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Новый брейншторм", callback_data="brainstorm_restart")],
                    [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_menu")]
                ])
            )
            
        else:
            # Пользователь выходит
            logger.info(f"🧠 Пользователь {user_id} вышел из брейншторма (раундов: {data.get('rounds', 0)})")
            
            # Добавляем команду остановки в историю
            data["history"].append({"role": "assistant_control", "content": "stop"})
            
            # Генерируем сообщение завершения
            exit_message = await brainstorm_llm.generate_question(data["direction"], data["history"])
            
            await callback.message.answer(
                exit_message,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Новый брейншторм", callback_data="brainstorm_restart")],
                    [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_menu")]
                ])
            )
        
        # Очищаем состояние
        await state.clear()
        await callback.answer()
    
    @router.callback_query(F.data == "brainstorm_restart")
    async def handle_brainstorm_restart(callback: CallbackQuery, state: FSMContext):
        """Перезапуск брейншторма"""
        await callback.message.edit_text(
            "🧠 **Брейншторм идей проектов**\n\n"
            "Выбери направление для нового брейншторма:",
            reply_markup=make_directions_keyboard()
        )
        await state.set_state(BrainstormState.PICK_DIRECTION)
        await callback.answer()

async def ask_next_question(message: Message, state: FSMContext):
    """Генерирует и отправляет следующий вопрос"""
    data = await state.get_data()
    
    if not brainstorm_llm:
        logger.error("❌ LLM не инициализирован")
        await message.answer("❌ Ошибка: LLM не инициализирован")
        return
    
    try:
        logger.info(f"🧠 Генерируем вопрос для направления: {data['direction']['name']}")
        logger.info(f"🧠 История диалога: {len(data['history'])} сообщений")
        
        # Генерируем вопрос
        question = await brainstorm_llm.generate_question(data["direction"], data["history"])
        
        if not question or question.strip() == "":
            logger.error("❌ Получен пустой ответ от API")
            await message.answer(
                "❌ Произошла ошибка при генерации вопроса. Попробуйте перезапустить брейншторм.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Перезапустить", callback_data="brainstorm_restart")],
                    [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_menu")]
                ])
            )
            await state.clear()
            return
        
        # Добавляем вопрос в историю
        assistant_message = {"role": "assistant", "content": question}
        data["history"].append(assistant_message)
        await state.update_data(history=data["history"])
        
        # Отправляем вопрос с кнопками действий
        await message.answer(
            question,
            reply_markup=make_brainstorm_actions_keyboard()
        )
        
        logger.info(f"🧠 Сгенерирован вопрос (раунд {data.get('rounds', 0) + 1}): {question[:50]}...")
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации вопроса: {e}")
        await message.answer(
            "❌ Произошла ошибка при генерации вопроса. Попробуйте перезапустить брейншторм.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Перезапустить", callback_data="brainstorm_restart")],
                [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_menu")]
            ])
        )
        await state.clear()

# Функция для получения статистики брейншторма
def get_brainstorm_stats() -> Dict:
    """Возвращает статистику использования брейншторма"""
    return {
        "available": brainstorm_llm is not None,
        "directions_count": len(DIRECTIONS),
        "directions": list(DIRECTIONS.keys())
    }

# Функция для добавления кнопки брейншторма в главное меню
def add_brainstorm_to_menu_keyboard(keyboard_rows: List[List[InlineKeyboardButton]]) -> List[List[InlineKeyboardButton]]:
    """Добавляет кнопку брейншторма в главное меню"""
    # Добавляем кнопку брейншторма в начало
    keyboard_rows.insert(0, [
        InlineKeyboardButton(text="🧠 Брейншторм идей", callback_data="start_brainstorm")
    ])
    return keyboard_rows

# Обработчик для кнопки брейншторма в главном меню
def register_brainstorm_menu_handler(router: Router):
    """Регистрирует обработчик кнопки брейншторма в главном меню"""
    
    @router.callback_query(F.data == "start_brainstorm")
    async def handle_start_brainstorm_from_menu(callback: CallbackQuery, state: FSMContext):
        """Запуск брейншторма из главного меню"""
        if not brainstorm_llm:
            await callback.answer("❌ Система брейншторма временно недоступна", show_alert=True)
            return
        
        await callback.message.edit_text(
            "🧠 **Брейншторм идей проектов**\n\n"
            "Я помогу тебе придумать идею проекта! Выбери направление, которое тебя интересует:\n\n"
            "💡 Как это работает:\n"
            "• Я буду задавать вопросы о твоих интересах\n"
            "• Ты отвечаешь, а я задаю следующий вопрос\n"
            "• В любой момент можешь сказать, что придумал идею\n"
            "• Никаких готовых решений — только твои мысли!",
            reply_markup=make_directions_keyboard()
        )
        await state.set_state(BrainstormState.PICK_DIRECTION)
        await callback.answer() 