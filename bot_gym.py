import telebot
from telebot import types
import mysql.connector
from mysql.connector import Error
import pandas as pd
from datetime import datetime
import json
import logging
from config import BOT_TOKEN, DB_CONFIG, LOG_LEVEL, EXERCISES_FILE, NUMBERS_FILE, STATS_DIR

# Настройка логирования
logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)

# Создание бота
bot = telebot.TeleBot(BOT_TOKEN)

# Состояния пользователей
user_states = {}

# Константы состояний
class UserState:
    MAIN_MENU = "main_menu"
    CHOOSE_MUSCLE_GROUP = "choose_muscle_group"
    CHOOSE_EXERCISE = "choose_exercise"
    CHOOSE_REPS = "choose_reps"
    CHOOSE_WEIGHT = "choose_weight"
    EXERCISE_IN_PROGRESS = "exercise_in_progress"
    SUPERSET_CHOOSE_FIRST_EXERCISE = "superset_choose_first_exercise"
    SUPERSET_CHOOSE_SECOND_EXERCISE = "superset_choose_second_exercise"
    SUPERSET_FIRST_EXERCISE_REPS = "superset_first_exercise_reps"
    SUPERSET_FIRST_EXERCISE_WEIGHT = "superset_first_exercise_weight"
    SUPERSET_SECOND_EXERCISE_REPS = "superset_second_exercise_reps"
    SUPERSET_SECOND_EXERCISE_WEIGHT = "superset_second_exercise_weight"
    SUPERSET_IN_PROGRESS = "superset_in_progress"

# Загрузка данных из базы данных
def load_exercises_from_db():
    """Загружает упражнения из базы данных"""
    connection = get_db_connection()
    if not connection:
        return {}
    
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT muscle_group, exercise_name FROM exercises ORDER BY muscle_group, exercise_name")
        rows = cursor.fetchall()
        
        exercises = {}
        for muscle_group, exercise_name in rows:
            if muscle_group not in exercises:
                exercises[muscle_group] = []
            exercises[muscle_group].append(exercise_name)
        
        logger.info(f"Загружено упражнений из БД: {len(exercises)} групп")
        return exercises
        
    except Error as e:
        logger.error(f"Ошибка загрузки упражнений из БД: {e}")
        return {}
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def load_weights_from_db():
    """Загружает доступные веса из базы данных"""
    connection = get_db_connection()
    if not connection:
        return [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 17.5, 20.0, 22.5, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0]
    
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT weight FROM available_weights WHERE is_active = TRUE ORDER BY weight")
        rows = cursor.fetchall()
        
        weights = [float(row[0]) for row in rows]
        
        logger.info(f"Загружено весов из БД: {len(weights)}")
        return weights
        
    except Error as e:
        logger.error(f"Ошибка загрузки весов из БД: {e}")
        return [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 17.5, 20.0, 22.5, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0]
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def populate_default_weights():
    """Заполняет таблицу весов значениями по умолчанию, если она пуста"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Проверяем, есть ли уже веса в таблице
        cursor.execute("SELECT COUNT(*) FROM available_weights")
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Заполняем таблицу весами по умолчанию
            default_weights = [0.0, 1.0, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0, 7.5, 8.0, 9.0, 10.0, 11.0, 12.0, 12.5, 15.0, 17.0, 17.5, 18.0, 20.0, 21.5, 22.5, 23.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0, 65.0, 70.0, 75.0, 80.0, 85.0, 90.0]
            
            for weight in default_weights:
                cursor.execute("""
                    INSERT IGNORE INTO available_weights (weight) 
                    VALUES (%s)
                """, (weight,))
            
            connection.commit()
            logger.info(f"Заполнена таблица весов: {len(default_weights)} значений")
        
        return True
        
    except Error as e:
        logger.error(f"Ошибка заполнения таблицы весов: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Глобальные переменные для данных (будут загружены при запуске)
exercises_data = {}
weights_data = []

def initialize_data():
    """Инициализирует данные из базы данных"""
    global exercises_data, weights_data
    
    # Загружаем упражнения из БД
    exercises_data = load_exercises_from_db()
    
    # Заполняем таблицу весов значениями по умолчанию, если она пуста
    populate_default_weights()
    
    # Загружаем веса из БД
    weights_data = load_weights_from_db()
    
    logger.info(f"Инициализированы данные: {len(exercises_data)} групп упражнений, {len(weights_data)} весов")

# Подключение к базе данных
def get_db_connection():
    """Создает подключение к базе данных"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        logger.error(f"Ошибка подключения к базе данных: {e}")
        return None

def init_database():
    """Инициализирует базу данных и создает таблицы"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Создание таблицы упражнений
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exercises (
                id INT AUTO_INCREMENT PRIMARY KEY,
                muscle_group VARCHAR(50) NOT NULL,
                exercise_name VARCHAR(100) NOT NULL,
                UNIQUE KEY unique_exercise (muscle_group, exercise_name)
            )
        """)
        
        # Создание таблицы статистики тренировок
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workout_stats (
                id INT AUTO_INCREMENT PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                date DATE NOT NULL,
                muscle_group VARCHAR(50) NOT NULL,
                exercise_name VARCHAR(100) NOT NULL,
                set_number INT NOT NULL,
                weight DECIMAL(5,2) NOT NULL,
                reps INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Создание таблицы суперсетов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS supersets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                date DATE NOT NULL,
                first_exercise_group VARCHAR(50) NOT NULL,
                first_exercise_name VARCHAR(100) NOT NULL,
                second_exercise_group VARCHAR(50) NOT NULL,
                second_exercise_name VARCHAR(100) NOT NULL,
                set_number INT NOT NULL,
                first_weight DECIMAL(5,2) NOT NULL,
                first_reps INT NOT NULL,
                second_weight DECIMAL(5,2) NOT NULL,
                second_reps INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Создание таблицы доступных весов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS available_weights (
                id INT AUTO_INCREMENT PRIMARY KEY,
                weight DECIMAL(5,2) NOT NULL UNIQUE,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        connection.commit()
        logger.info("База данных успешно инициализирована")
        return True
        
    except Error as e:
        logger.error(f"Ошибка инициализации базы данных: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Функции для работы с пользовательскими состояниями
def get_user_state(chat_id):
    """Получает состояние пользователя"""
    return user_states.get(chat_id, {})

def set_user_state(chat_id, state, data=None):
    """Устанавливает состояние пользователя"""
    if chat_id not in user_states:
        user_states[chat_id] = {}
    
    user_states[chat_id]['state'] = state
    if data:
        user_states[chat_id].update(data)

def clear_user_state(chat_id):
    """Очищает состояние пользователя"""
    if chat_id in user_states:
        del user_states[chat_id]

# Вспомогательные функции для клавиатур и маппингов
def create_main_menu_keyboard():
    """Создает главное меню"""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🏋️ Одиночное упражнение", callback_data="single_exercise"))
    keyboard.add(types.InlineKeyboardButton("💪 Суперсэт", callback_data="superset"))
    return keyboard

def build_muscle_groups_keyboard_and_state(chat_id):
    """Создает клавиатуру с группами мышц с короткими callback и сохраняет маппинг в состояние"""
    keyboard = types.InlineKeyboardMarkup()
    groups = list(exercises_data.keys())
    mg_map = {str(idx): group for idx, group in enumerate(groups)}
    # Сохраняем маппинг для пользователя
    set_user_state(chat_id, get_user_state(chat_id).get('state', UserState.MAIN_MENU), {'mg_map': mg_map})
    for idx, group in mg_map.items():
        keyboard.add(types.InlineKeyboardButton(group, callback_data=f"mg:{idx}"))
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))
    return keyboard

def build_exercises_keyboard_and_state(chat_id, muscle_group):
    """Создает клавиатуру с упражнениями с короткими callback и сохраняет маппинг в состояние"""
    keyboard = types.InlineKeyboardMarkup()
    exercises = exercises_data.get(muscle_group, [])
    ex_map = {str(idx): ex for idx, ex in enumerate(exercises)}
    # Сохраняем маппинг для пользователя
    set_user_state(chat_id, get_user_state(chat_id).get('state', UserState.MAIN_MENU), {'ex_map': ex_map})
    for idx, exercise in ex_map.items():
        keyboard.add(types.InlineKeyboardButton(exercise, callback_data=f"ex:{idx}"))
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_muscle_groups"))
    return keyboard

def create_reps_keyboard():
    """Создает клавиатуру с количеством повторений"""
    keyboard = types.InlineKeyboardMarkup()
    reps_options = [8, 10, 12, 15, 20, 25, 30]
    for i in range(0, len(reps_options), 3):
        row = []
        for j in range(3):
            if i + j < len(reps_options):
                reps = reps_options[i + j]
                row.append(types.InlineKeyboardButton(str(reps), callback_data=f"reps_{reps}"))
        keyboard.row(*row)
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_exercise"))
    return keyboard

def create_weights_keyboard():
    """Создает клавиатуру с весами"""
    keyboard = types.InlineKeyboardMarkup()
    
    # Используем веса из базы данных
    main_weights = weights_data[:16]  # Показываем первые 16 весов для удобства
    
    for i in range(0, len(main_weights), 4):
        row = []
        for j in range(4):
            if i + j < len(main_weights):
                weight = main_weights[i + j]
                row.append(types.InlineKeyboardButton(str(weight), callback_data=f"weight_{weight}"))
        keyboard.row(*row)
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_reps"))
    return keyboard

def create_continue_keyboard():
    """Создает клавиатуру для продолжения или завершения упражнения"""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("➕ Следующий подход", callback_data="next_set"))
    keyboard.add(types.InlineKeyboardButton("✅ Завершить упражнение", callback_data="finish_exercise"))
    return keyboard

# Обработчики команд
@bot.message_handler(commands=['start'])
def start_command(message):
    """Обработчик команды /start"""
    chat_id = message.chat.id
    set_user_state(chat_id, UserState.MAIN_MENU)
    
    welcome_text = """
🏋️ Добро пожаловать в Gym Bot!

Этот бот поможет вам отслеживать ваши тренировки в спортзале.

Выберите режим тренировки:
"""
    
    bot.send_message(chat_id, welcome_text, reply_markup=create_main_menu_keyboard())

@bot.message_handler(commands=['help'])
def help_command(message):
    """Обработчик команды /help"""
    help_text = """
📖 Помощь по использованию бота:

🏋️ Одиночное упражнение - записывайте упражнения по одному
💪 Суперсэт - записывайте два упражнения, выполняемые поочередно

Для начала работы используйте команду /start
"""
    bot.send_message(message.chat.id, help_text)

# Обработчики callback-ов
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """Обработчик всех callback-ов"""
    chat_id = call.message.chat.id
    user_state = get_user_state(chat_id)
    current_state = user_state.get('state', UserState.MAIN_MENU)
    
    try:
        if call.data == "single_exercise":
            handle_single_exercise_start(call)
        elif call.data == "superset":
            handle_superset_start(call)
        elif call.data.startswith("muscle_group_"):
            handle_muscle_group_selection(call)
        elif call.data.startswith("exercise_"):
            handle_exercise_selection(call)
        elif call.data.startswith("reps_"):
            handle_reps_selection(call)
        elif call.data.startswith("weight_"):
            handle_weight_selection(call)
        elif call.data == "next_set":
            handle_next_set(call)
        elif call.data == "finish_exercise":
            handle_finish_exercise(call)
        elif call.data == "back_to_main":
            handle_back_to_main(call)
        elif call.data == "back_to_muscle_groups":
            handle_back_to_muscle_groups(call)
        elif call.data == "back_to_exercise":
            handle_back_to_exercise(call)
        elif call.data == "back_to_reps":
            handle_back_to_reps(call)
            
    except Exception as e:
        logger.error(f"Ошибка обработки callback: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте снова.")

def handle_single_exercise_start(call):
    """Обработчик начала одиночного упражнения"""
    chat_id = call.message.chat.id
    set_user_state(chat_id, UserState.CHOOSE_MUSCLE_GROUP)
    
    text = "🏋️ Выберите группу мышц:"
    bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=build_muscle_groups_keyboard_and_state(chat_id))
    bot.answer_callback_query(call.id)

def handle_superset_start(call):
    """Обработчик начала суперсэта"""
    chat_id = call.message.chat.id
    set_user_state(chat_id, UserState.SUPERSET_CHOOSE_FIRST_EXERCISE)
    
    text = "💪 Суперсэт\n\nВыберите первое упражнение:"
    bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=build_muscle_groups_keyboard_and_state(chat_id))
    bot.answer_callback_query(call.id)

def handle_muscle_group_selection(call):
    """Обработчик выбора группы мышц"""
    chat_id = call.message.chat.id
    # Поддержка коротких и старых callback
    if call.data.startswith("mg:"):
        idx = call.data.split(":", 1)[1]
        muscle_group = get_user_state(chat_id).get('mg_map', {}).get(idx)
    else:
        muscle_group = call.data.replace("muscle_group_", "")
    user_state = get_user_state(chat_id)
    current_state = user_state.get('state')
    
    if current_state == UserState.CHOOSE_MUSCLE_GROUP:
        set_user_state(chat_id, UserState.CHOOSE_EXERCISE, {'muscle_group': muscle_group})
        text = f"🏋️ Выберите упражнение для группы '{muscle_group}':"
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=build_exercises_keyboard_and_state(chat_id, muscle_group))
    elif current_state == UserState.SUPERSET_CHOOSE_FIRST_EXERCISE:
        set_user_state(chat_id, UserState.SUPERSET_CHOOSE_FIRST_EXERCISE, {'first_muscle_group': muscle_group})
        text = f"💪 Суперсэт\n\nВыберите первое упражнение для группы '{muscle_group}':"
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=build_exercises_keyboard_and_state(chat_id, muscle_group))
    elif current_state == UserState.SUPERSET_CHOOSE_SECOND_EXERCISE:
        set_user_state(chat_id, UserState.SUPERSET_CHOOSE_SECOND_EXERCISE, {'second_muscle_group': muscle_group})
        text = f"💪 Суперсэт\n\nВыберите второе упражнение для группы '{muscle_group}':"
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=build_exercises_keyboard_and_state(chat_id, muscle_group))
    
    bot.answer_callback_query(call.id)

def handle_exercise_selection(call):
    """Обработчик выбора упражнения"""
    chat_id = call.message.chat.id
    # Поддержка коротких и старых callback
    if call.data.startswith("ex:"):
        idx = call.data.split(":", 1)[1]
        exercise = get_user_state(chat_id).get('ex_map', {}).get(idx)
    else:
        exercise = call.data.replace("exercise_", "")
    user_state = get_user_state(chat_id)
    current_state = user_state.get('state')
    
    if current_state == UserState.CHOOSE_EXERCISE:
        muscle_group = user_state.get('muscle_group')
        set_user_state(chat_id, UserState.CHOOSE_REPS, {
            'muscle_group': muscle_group,
            'exercise': exercise,
            'sets': []
        })
        text = f"🏋️ {muscle_group} - {exercise}\n\nВыберите количество повторений:"
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=create_reps_keyboard())
    elif current_state == UserState.SUPERSET_CHOOSE_FIRST_EXERCISE:
        first_muscle_group = user_state.get('first_muscle_group')
        set_user_state(chat_id, UserState.SUPERSET_CHOOSE_SECOND_EXERCISE, {
            'first_muscle_group': first_muscle_group,
            'first_exercise': exercise
        })
        text = f"💪 Суперсэт\n\nПервое упражнение: {first_muscle_group} - {exercise}\n\nВыберите второе упражнение:"
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=build_muscle_groups_keyboard_and_state(chat_id))
    elif current_state == UserState.SUPERSET_CHOOSE_SECOND_EXERCISE:
        second_muscle_group = user_state.get('second_muscle_group')
        first_muscle_group = user_state.get('first_muscle_group')
        first_exercise = user_state.get('first_exercise')
        set_user_state(chat_id, UserState.SUPERSET_FIRST_EXERCISE_REPS, {
            'first_muscle_group': first_muscle_group,
            'first_exercise': first_exercise,
            'second_muscle_group': second_muscle_group,
            'second_exercise': exercise,
            'sets': []
        })
        text = f"💪 Суперсэт\n\n1️⃣ {first_muscle_group} - {first_exercise}\n2️⃣ {second_muscle_group} - {exercise}\n\nВыберите количество повторений для первого упражнения:"
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=create_reps_keyboard())
    
    bot.answer_callback_query(call.id)

def handle_reps_selection(call):
    """Обработчик выбора повторений"""
    chat_id = call.message.chat.id
    reps = int(call.data.replace("reps_", ""))
    user_state = get_user_state(chat_id)
    current_state = user_state.get('state')
    
    if current_state == UserState.CHOOSE_REPS:
        set_user_state(chat_id, UserState.CHOOSE_WEIGHT, {'current_reps': reps})
        text = f"🏋️ {user_state.get('muscle_group')} - {user_state.get('exercise')}\nПовторения: {reps}\n\nВыберите вес:"
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=create_weights_keyboard())
    elif current_state == UserState.SUPERSET_FIRST_EXERCISE_REPS:
        set_user_state(chat_id, UserState.SUPERSET_FIRST_EXERCISE_WEIGHT, {'first_reps': reps})
        first_muscle_group = user_state.get('first_muscle_group')
        first_exercise = user_state.get('first_exercise')
        text = f"💪 Суперсэт\n\n1️⃣ {first_muscle_group} - {first_exercise}\nПовторения: {reps}\n\nВыберите вес для первого упражнения:"
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=create_weights_keyboard())
    elif current_state == UserState.SUPERSET_SECOND_EXERCISE_REPS:
        set_user_state(chat_id, UserState.SUPERSET_SECOND_EXERCISE_WEIGHT, {'second_reps': reps})
        second_muscle_group = user_state.get('second_muscle_group')
        second_exercise = user_state.get('second_exercise')
        text = f"💪 Суперсэт\n\n2️⃣ {second_muscle_group} - {second_exercise}\nПовторения: {reps}\n\nВыберите вес для второго упражнения:"
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=create_weights_keyboard())
    
    bot.answer_callback_query(call.id)

def handle_weight_selection(call):
    """Обработчик выбора веса"""
    chat_id = call.message.chat.id
    weight = float(call.data.replace("weight_", ""))
    user_state = get_user_state(chat_id)
    current_state = user_state.get('state')
    
    if current_state == UserState.CHOOSE_WEIGHT:
        reps = user_state.get('current_reps')
        muscle_group = user_state.get('muscle_group')
        exercise = user_state.get('exercise')
        sets = user_state.get('sets', [])
        
        # Добавляем новый подход
        new_set = {'reps': reps, 'weight': weight}
        sets.append(new_set)
        
        set_user_state(chat_id, UserState.EXERCISE_IN_PROGRESS, {'sets': sets})
        
        # Формируем текст с результатами
        text = f"🏋️ {muscle_group} - {exercise}\n\n"
        for i, set_data in enumerate(sets, 1):
            text += f"Подход {i}: {set_data['reps']} повторений × {set_data['weight']} кг\n"
        
        text += "\nЧто делаем дальше?"
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=create_continue_keyboard())
        
    elif current_state == UserState.SUPERSET_FIRST_EXERCISE_WEIGHT:
        first_reps = user_state.get('first_reps')
        first_muscle_group = user_state.get('first_muscle_group')
        first_exercise = user_state.get('first_exercise')
        set_user_state(chat_id, UserState.SUPERSET_SECOND_EXERCISE_REPS, {'first_weight': weight})
        
        text = f"💪 Суперсэт\n\n1️⃣ {first_muscle_group} - {first_exercise}\nПовторения: {first_reps}, Вес: {weight} кг\n\nВыберите количество повторений для второго упражнения:"
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=create_reps_keyboard())
        
    elif current_state == UserState.SUPERSET_SECOND_EXERCISE_WEIGHT:
        second_reps = user_state.get('second_reps')
        second_muscle_group = user_state.get('second_muscle_group')
        second_exercise = user_state.get('second_exercise')
        first_muscle_group = user_state.get('first_muscle_group')
        first_exercise = user_state.get('first_exercise')
        first_reps = user_state.get('first_reps')
        first_weight = user_state.get('first_weight')
        sets = user_state.get('sets', [])
        
        # Добавляем новый подход суперсэта
        new_set = {
            'first_reps': first_reps,
            'first_weight': first_weight,
            'second_reps': second_reps,
            'second_weight': weight
        }
        sets.append(new_set)
        
        set_user_state(chat_id, UserState.SUPERSET_IN_PROGRESS, {'sets': sets})
        
        # Формируем текст с результатами
        text = f"💪 Суперсэт\n\n"
        for i, set_data in enumerate(sets, 1):
            text += f"Подход {i}:\n"
            text += f"1️⃣ {first_muscle_group} - {first_exercise}: {set_data['first_reps']} × {set_data['first_weight']} кг\n"
            text += f"2️⃣ {second_muscle_group} - {second_exercise}: {set_data['second_reps']} × {set_data['second_weight']} кг\n\n"
        
        text += "Что делаем дальше?"
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=create_continue_keyboard())
    
    bot.answer_callback_query(call.id)

def handle_next_set(call):
    """Обработчик следующего подхода"""
    chat_id = call.message.chat.id
    user_state = get_user_state(chat_id)
    current_state = user_state.get('state')
    
    if current_state == UserState.EXERCISE_IN_PROGRESS:
        muscle_group = user_state.get('muscle_group')
        exercise = user_state.get('exercise')
        set_user_state(chat_id, UserState.CHOOSE_REPS)
        text = f"🏋️ {muscle_group} - {exercise}\n\nВыберите количество повторений для следующего подхода:"
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=create_reps_keyboard())
    elif current_state == UserState.SUPERSET_IN_PROGRESS:
        first_muscle_group = user_state.get('first_muscle_group')
        first_exercise = user_state.get('first_exercise')
        set_user_state(chat_id, UserState.SUPERSET_FIRST_EXERCISE_REPS)
        text = f"💪 Суперсэт\n\nВыберите количество повторений для первого упражнения:\n1️⃣ {first_muscle_group} - {first_exercise}"
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=create_reps_keyboard())
    
    bot.answer_callback_query(call.id)

def handle_finish_exercise(call):
    """Обработчик завершения упражнения"""
    chat_id = call.message.chat.id
    user_state = get_user_state(chat_id)
    current_state = user_state.get('state')
    
    # Сохраняем данные в базу данных
    if current_state == UserState.EXERCISE_IN_PROGRESS:
        save_single_exercise_data(chat_id, user_state)
    elif current_state == UserState.SUPERSET_IN_PROGRESS:
        save_superset_data(chat_id, user_state)
    
    # Возвращаемся в главное меню
    clear_user_state(chat_id)
    set_user_state(chat_id, UserState.MAIN_MENU)
    
    text = "✅ Упражнение завершено!\n\nВыберите режим тренировки:"
    bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=create_main_menu_keyboard())
    bot.answer_callback_query(call.id, "Упражнение сохранено!")

def handle_back_to_main(call):
    """Обработчик возврата в главное меню"""
    chat_id = call.message.chat.id
    clear_user_state(chat_id)
    set_user_state(chat_id, UserState.MAIN_MENU)
    
    text = "🏋️ Выберите режим тренировки:"
    bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=create_main_menu_keyboard())
    bot.answer_callback_query(call.id)

def handle_back_to_muscle_groups(call):
    """Обработчик возврата к выбору группы мышц"""
    chat_id = call.message.chat.id
    set_user_state(chat_id, UserState.CHOOSE_MUSCLE_GROUP)
    
    text = "🏋️ Выберите группу мышц:"
    bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=build_muscle_groups_keyboard_and_state(chat_id))
    bot.answer_callback_query(call.id)

def handle_back_to_exercise(call):
    """Обработчик возврата к выбору упражнения"""
    chat_id = call.message.chat.id
    user_state = get_user_state(chat_id)
    muscle_group = user_state.get('muscle_group')
    
    set_user_state(chat_id, UserState.CHOOSE_EXERCISE, {'muscle_group': muscle_group})
    
    text = f"🏋️ Выберите упражнение для группы '{muscle_group}':"
    bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=build_exercises_keyboard_and_state(chat_id, muscle_group))
    bot.answer_callback_query(call.id)

def handle_back_to_reps(call):
    """Обработчик возврата к выбору повторений"""
    chat_id = call.message.chat.id
    user_state = get_user_state(chat_id)
    muscle_group = user_state.get('muscle_group')
    exercise = user_state.get('exercise')
    
    set_user_state(chat_id, UserState.CHOOSE_REPS, {
        'muscle_group': muscle_group,
        'exercise': exercise,
        'sets': user_state.get('sets', [])
    })
    
    text = f"🏋️ {muscle_group} - {exercise}\n\nВыберите количество повторений:"
    bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=create_reps_keyboard())
    bot.answer_callback_query(call.id)

# Функции для сохранения данных
def save_single_exercise_data(chat_id, user_state):
    """Сохраняет данные одиночного упражнения в базу данных"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        muscle_group = user_state.get('muscle_group')
        exercise = user_state.get('exercise')
        sets = user_state.get('sets', [])
        current_date = datetime.now().date()
        
        for i, set_data in enumerate(sets, 1):
            cursor.execute("""
                INSERT INTO workout_stats (chat_id, date, muscle_group, exercise_name, set_number, weight, reps)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (chat_id, current_date, muscle_group, exercise, i, set_data['weight'], set_data['reps']))
        
        connection.commit()
        logger.info(f"Сохранены данные одиночного упражнения для пользователя {chat_id}")
        return True
        
    except Error as e:
        logger.error(f"Ошибка сохранения данных одиночного упражнения: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def save_superset_data(chat_id, user_state):
    """Сохраняет данные суперсэта в базу данных"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        first_muscle_group = user_state.get('first_muscle_group')
        first_exercise = user_state.get('first_exercise')
        second_muscle_group = user_state.get('second_muscle_group')
        second_exercise = user_state.get('second_exercise')
        sets = user_state.get('sets', [])
        current_date = datetime.now().date()
        
        for i, set_data in enumerate(sets, 1):
            cursor.execute("""
                INSERT INTO supersets (chat_id, date, first_exercise_group, first_exercise_name, 
                                     second_exercise_group, second_exercise_name, set_number, 
                                     first_weight, first_reps, second_weight, second_reps)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (chat_id, current_date, first_muscle_group, first_exercise, 
                  second_muscle_group, second_exercise, i, 
                  set_data['first_weight'], set_data['first_reps'],
                  set_data['second_weight'], set_data['second_reps']))
        
        connection.commit()
        logger.info(f"Сохранены данные суперсэта для пользователя {chat_id}")
        return True
        
    except Error as e:
        logger.error(f"Ошибка сохранения данных суперсэта: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Основная функция запуска бота
def main():
    """Основная функция для запуска бота"""
    logger.info("Запуск Gym Bot...")
    
    # Инициализация базы данных
    if not init_database():
        logger.error("Не удалось инициализировать базу данных")
        return
    
    # Инициализация данных из базы данных
    initialize_data()
    
    # Проверяем, что данные загружены
    if not exercises_data:
        logger.error("Не удалось загрузить упражнения из базы данных")
        return
    
    # Запуск бота
    try:
        logger.info("Бот запущен и готов к работе!")
        bot.polling(none_stop=True)
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")

if __name__ == "__main__":
    main()
