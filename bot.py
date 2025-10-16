import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2
from config import BOT_TOKEN, DB_CONFIG
from datetime import date
import calendar
from datetime import datetime, timedelta

bot = telebot.TeleBot(BOT_TOKEN)

# Подключение к базе
conn = psycopg2.connect(**DB_CONFIG)
cursor = conn.cursor()

# Состояния пользователя
user_state = {}

# ================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ================================

def ensure_state(chat_id):
    """Создаёт состояние для пользователя, если его нет."""
    if chat_id not in user_state:
        user_state[chat_id] = {}
    return user_state[chat_id]

def get_muscle_groups():
    cursor.execute("SELECT id, name FROM gym.muscle_groups ORDER BY name;")
    return cursor.fetchall()

def get_exercises_by_group(group_id):
    cursor.execute("SELECT id, name FROM gym.exercises WHERE muscle_group_id = %s ORDER BY name;", (group_id,))
    return cursor.fetchall()

def build_keyboard(items, callback_prefix, back_callback=None):
    kb = InlineKeyboardMarkup()
    for item_id, name in items:
        kb.add(InlineKeyboardButton(name, callback_data=f"{callback_prefix}:{item_id}"))
    if back_callback:
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data=back_callback))
    return kb

def build_grid_keyboard(labels, callback_prefix, back_callback=None, columns=3, extra_buttons=None):
    kb = InlineKeyboardMarkup()
    row = []
    for label in labels:
        row.append(InlineKeyboardButton(str(label), callback_data=f"{callback_prefix}:{label}"))
        if len(row) == columns:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
    if extra_buttons:
        kb.row(*extra_buttons)
    if back_callback:
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data=back_callback))
    return kb

def ensure_weight_exists(weight_value):
    if weight_value is None:
        return None
    cursor.execute("INSERT INTO gym.weights (weight_kg) VALUES (%s) ON CONFLICT DO NOTHING;", (weight_value,))
    conn.commit()
    return weight_value

def ensure_reps_exists(reps_count):
    if reps_count is None:
        return None
    cursor.execute("INSERT INTO gym.repetitions (reps_count) VALUES (%s) ON CONFLICT DO NOTHING;", (reps_count,))
    conn.commit()
    return reps_count

def get_all_reps():
    cursor.execute("SELECT reps_count FROM gym.repetitions ORDER BY reps_count;")
    return [row[0] for row in cursor.fetchall()]

def get_all_weights():
    cursor.execute("SELECT weight_kg FROM gym.weights ORDER BY weight_kg;")
    return [float(row[0]) for row in cursor.fetchall()]

def show_groups_menu(call, send_new=False):
    groups = get_muscle_groups()
    plus_btn = InlineKeyboardButton("➕", callback_data="add_group")
    kb = build_keyboard(groups, "muscle", "main_menu")
    kb.row(plus_btn)
    if send_new:
        bot.send_message(call.message.chat.id, "Выберите группу мышц:", reply_markup=kb)
    else:
        bot.edit_message_text(
            "Выберите группу мышц:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb
        )

def show_exercises_menu(call, send_new=False):
    state = ensure_state(call.message.chat.id)
    exercises = get_exercises_by_group(state["muscle_group_id"])
    plus_btn = InlineKeyboardButton("➕", callback_data="add_exercise")
    kb = build_keyboard(exercises, "exercise", "single")
    kb.row(plus_btn)
    if send_new:
        bot.send_message(call.message.chat.id, "Выберите упражнение:", reply_markup=kb)
    else:
        bot.edit_message_text(
            "Выберите упражнение:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb
        )

def show_reps_menu(call, send_new=False):
    chat_id = call.message.chat.id
    reps = get_all_reps()
    plus_btn = InlineKeyboardButton("➕", callback_data="add_reps_menu")
    kb = build_grid_keyboard(reps, "reps", back_callback="exercise_back", columns=4, extra_buttons=[plus_btn])
    current_set = ensure_state(chat_id).get("set_number", 1)
    if send_new:
        bot.send_message(chat_id, f"Подход {current_set}: выберите количество повторений:", reply_markup=kb)
    else:
        bot.edit_message_text(f"Подход {current_set}: выберите количество повторений:", chat_id, call.message.message_id, reply_markup=kb)

def show_weight_menu(call, send_new=False):
    chat_id = call.message.chat.id
    weights = [f"{w:.2f}".rstrip('0').rstrip('.') for w in get_all_weights()]
    plus_btn = InlineKeyboardButton("➕", callback_data="add_weight_menu")
    no_weight_btn = InlineKeyboardButton("⚪ Без веса", callback_data="no_weight")
    kb = build_grid_keyboard(weights, "w", back_callback="reps_back", columns=4, extra_buttons=[plus_btn, no_weight_btn])
    current_set = ensure_state(chat_id).get("set_number", 1)
    if send_new:
        bot.send_message(chat_id, f"Подход {current_set}: выберите вес (кг):", reply_markup=kb)
    else:
        bot.edit_message_text(f"Подход {current_set}: выберите вес (кг):", chat_id, call.message.message_id, reply_markup=kb)

def main_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🏋️‍♂️ Одиночное упражнение", callback_data="single"))
    kb.add(InlineKeyboardButton("🔥 Суперсет", callback_data="superset"))
    kb.add(InlineKeyboardButton("📊 Статистика", callback_data="stats"))
    return kb

# ================================
# START
# ================================

@bot.message_handler(commands=["start"])
def start(message):
    ensure_state(message.chat.id)
    print(f"/start от {message.chat.id}")
    bot.send_message(message.chat.id, "Выберите режим:", reply_markup=main_menu())

# ================================
# ОДИНОЧНОЕ УПРАЖНЕНИЕ
# ================================

@bot.callback_query_handler(func=lambda call: call.data == "single")
def single_mode(call):
    state = ensure_state(call.message.chat.id)
    state["mode"] = "single"
    print(f"Режим single выбран chat={call.message.chat.id}")
    show_groups_menu(call)

@bot.callback_query_handler(func=lambda call: call.data == "superset")
def superset_mode(call):
    state = ensure_state(call.message.chat.id)
    state.clear()
    state["mode"] = "superset"
    state["set_number"] = 1
    print(f"Режим superset выбран chat={call.message.chat.id}")
    show_groups_menu_superset(call, step=1)

def show_groups_menu_superset(call, step, send_new=False):
    groups = get_muscle_groups()
    plus_btn = InlineKeyboardButton("➕", callback_data="add_group")
    prefix = "s1_muscle" if step == 1 else "s2_muscle"
    kb = build_keyboard(groups, prefix, "main_menu")
    kb.row(plus_btn)
    text = "Выберите группу мышц для первого упражнения:" if step == 1 else "Выберите группу мышц для второго упражнения:"
    if send_new:
        bot.send_message(call.message.chat.id, text, reply_markup=kb)
    else:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

def show_exercises_menu_superset(call, step, send_new=False):
    state = ensure_state(call.message.chat.id)
    group_id = state["s1_muscle_group_id"] if step == 1 else state["s2_muscle_group_id"]
    exercises = get_exercises_by_group(group_id)
    plus_btn = InlineKeyboardButton("➕", callback_data="add_exercise")
    prefix = "s1_ex" if step == 1 else "s2_ex"
    kb = build_keyboard(exercises, prefix, "single")
    kb.row(plus_btn)
    text = "Выберите первое упражнение:" if step == 1 else "Выберите второе упражнение:"
    if send_new:
        bot.send_message(call.message.chat.id, text, reply_markup=kb)
    else:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

def show_reps_menu_superset(call, which, send_new=False):
    chat_id = call.message.chat.id
    reps = get_all_reps()
    plus_btn = InlineKeyboardButton("➕", callback_data="add_reps_menu")
    prefix = "sreps1" if which == 1 else "sreps2"
    kb = build_grid_keyboard(reps, prefix, columns=4, extra_buttons=[plus_btn])
    current_set = ensure_state(chat_id).get("set_number", 1)
    which_text = "первого" if which == 1 else "второго"
    ensure_state(chat_id)["awaiting_superset"] = "first_reps" if which == 1 else "second_reps"
    if send_new:
        bot.send_message(chat_id, f"Суперсет {current_set}: выберите повторения для {which_text} упражнения:", reply_markup=kb)
    else:
        bot.edit_message_text(f"Суперсет {current_set}: выберите повторения для {which_text} упражнения:", chat_id, call.message.message_id, reply_markup=kb)

def show_weight_menu_superset(call, which, send_new=False):
    chat_id = call.message.chat.id
    weights = [f"{w:.2f}".rstrip('0').rstrip('.') for w in get_all_weights()]
    plus_btn = InlineKeyboardButton("➕", callback_data="add_weight_menu")
    no_weight_btn = InlineKeyboardButton("⚪ Без веса", callback_data="sno_weight1" if which == 1 else "sno_weight2")
    prefix = "sw1" if which == 1 else "sw2"
    kb = build_grid_keyboard(weights, prefix, columns=4, extra_buttons=[plus_btn, no_weight_btn])
    current_set = ensure_state(chat_id).get("set_number", 1)
    which_text = "первого" if which == 1 else "второго"
    ensure_state(chat_id)["awaiting_superset"] = "first_weight" if which == 1 else "second_weight"
    if send_new:
        bot.send_message(chat_id, f"Суперсет {current_set}: выберите вес для {which_text} упражнения:", reply_markup=kb)
    else:
        bot.edit_message_text(f"Суперсет {current_set}: выберите вес для {which_text} упражнения:", chat_id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("muscle:"))
def choose_exercise(call):
    state = ensure_state(call.message.chat.id)
    group_id = int(call.data.split(":")[1])
    state["muscle_group_id"] = group_id
    cursor.execute("SELECT name FROM gym.muscle_groups WHERE id = %s", (group_id,))
    group_name = cursor.fetchone()[0]
    print(f"Выбрана группа: {group_name} (id={group_id}) chat={call.message.chat.id}")
    show_exercises_menu(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith("s1_muscle:"))
def s1_choose_group(call):
    state = ensure_state(call.message.chat.id)
    gid = int(call.data.split(":")[1])
    state["s1_muscle_group_id"] = gid
    cursor.execute("SELECT name FROM gym.muscle_groups WHERE id = %s", (gid,))
    gname = cursor.fetchone()[0]
    print(f"Superset: выбрана группа 1: {gname} (id={gid}) chat={call.message.chat.id}")
    show_exercises_menu_superset(call, step=1)

@bot.callback_query_handler(func=lambda call: call.data.startswith("s2_muscle:"))
def s2_choose_group(call):
    state = ensure_state(call.message.chat.id)
    gid = int(call.data.split(":")[1])
    state["s2_muscle_group_id"] = gid
    cursor.execute("SELECT name FROM gym.muscle_groups WHERE id = %s", (gid,))
    gname = cursor.fetchone()[0]
    print(f"Superset: выбрана группа 2: {gname} (id={gid}) chat={call.message.chat.id}")
    show_exercises_menu_superset(call, step=2)

@bot.callback_query_handler(func=lambda call: call.data.startswith("s1_ex:"))
def s1_choose_ex(call):
    state = ensure_state(call.message.chat.id)
    ex_id = int(call.data.split(":")[1])
    state["s1_exercise_id"] = ex_id
    cursor.execute("SELECT name FROM gym.exercises WHERE id = %s", (ex_id,))
    ex_name = cursor.fetchone()[0]
    state["s1_exercise_name"] = ex_name
    print(f"Superset: выбрано упражнение 1: {ex_name} chat={call.message.chat.id}")
    show_groups_menu_superset(call, step=2)

@bot.callback_query_handler(func=lambda call: call.data.startswith("s2_ex:"))
def s2_choose_ex(call):
    state = ensure_state(call.message.chat.id)
    ex_id = int(call.data.split(":")[1])
    state["s2_exercise_id"] = ex_id
    cursor.execute("SELECT name FROM gym.exercises WHERE id = %s", (ex_id,))
    ex_name = cursor.fetchone()[0]
    state["s2_exercise_name"] = ex_name
    print(f"Superset: выбрано упражнение 2: {ex_name} chat={call.message.chat.id}")
    show_reps_menu_superset(call, which=1)

@bot.callback_query_handler(func=lambda call: call.data.startswith("exercise:"))
def start_set(call):
    state = ensure_state(call.message.chat.id)
    ex_id = int(call.data.split(":")[1])
    state["exercise_id"] = ex_id
    cursor.execute("SELECT name FROM gym.exercises WHERE id = %s", (ex_id,))
    ex_name = cursor.fetchone()[0]
    state["exercise_name"] = ex_name
    state["set_number"] = state.get("set_number", 1)
    print(f"Выбрано упражнение: {ex_name} chat={call.message.chat.id}")
    show_reps_menu(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith("reps:"))
def choose_reps(call):
    state = ensure_state(call.message.chat.id)
    reps = int(call.data.split(":")[1])
    state["reps"] = reps
    ensure_reps_exists(reps)
    print(f"Выбраны повторения: {reps} chat={call.message.chat.id}")
    show_weight_menu(call)

@bot.callback_query_handler(func=lambda call: call.data in ["set_weight", "no_weight"])
def get_weight(call):
    state = ensure_state(call.message.chat.id)
    if call.data == "no_weight":
        state["weight"] = None
        return finish_set(call)
    show_weight_menu(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith("w:"))
def choose_weight(call):
    state = ensure_state(call.message.chat.id)
    weight = float(call.data.split(":")[1])
    state["weight"] = weight
    ensure_weight_exists(weight)
    print(f"Выбран вес: {weight} кг chat={call.message.chat.id}")
    finish_set(call)

def finish_superset(chat_id):
    state = ensure_state(chat_id)
    today = date.today()
    cursor.execute(
        """
        INSERT INTO gym.supersets (
            chat_id, date, first_exercise_id, second_exercise_id,
            set_number, first_weight_kg, first_reps_count, second_weight_kg, second_reps_count
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
        """,
        (
            chat_id,
            today,
            state["s1_exercise_id"],
            state["s2_exercise_id"],
            state.get("set_number", 1),
            state.get("s1_weight"),
            state["s1_reps"],
            state.get("s2_weight"),
            state["s2_reps"],
        ),
    )
    conn.commit()

@bot.callback_query_handler(func=lambda call: call.data.startswith("sreps1:"))
def s_choose_reps1(call):
    st = ensure_state(call.message.chat.id)
    st["s1_reps"] = int(call.data.split(":")[1])
    ensure_reps_exists(st["s1_reps"])
    print(f"Superset: повторения 1: {st['s1_reps']} chat={call.message.chat.id}")
    show_weight_menu_superset(call, which=1)

@bot.callback_query_handler(func=lambda call: call.data.startswith("sreps2:"))
def s_choose_reps2(call):
    st = ensure_state(call.message.chat.id)
    st["s2_reps"] = int(call.data.split(":")[1])
    ensure_reps_exists(st["s2_reps"])
    print(f"Superset: повторения 2: {st['s2_reps']} chat={call.message.chat.id}")
    show_weight_menu_superset(call, which=2)

@bot.callback_query_handler(func=lambda call: call.data.startswith("sw1:"))
def s_choose_weight1(call):
    st = ensure_state(call.message.chat.id)
    st["s1_weight"] = float(call.data.split(":")[1])
    ensure_weight_exists(st["s1_weight"])
    print(f"Superset: вес 1: {st['s1_weight']} chat={call.message.chat.id}")
    show_reps_menu_superset(call, which=2)

@bot.callback_query_handler(func=lambda call: call.data == "sno_weight1")
def s_no_weight1(call):
    st = ensure_state(call.message.chat.id)
    st["s1_weight"] = None
    print(f"Superset: без веса 1 chat={call.message.chat.id}")
    show_reps_menu_superset(call, which=2)

@bot.callback_query_handler(func=lambda call: call.data.startswith("sw2:"))
def s_choose_weight2(call):
    st = ensure_state(call.message.chat.id)
    st["s2_weight"] = float(call.data.split(":")[1])
    ensure_weight_exists(st["s2_weight"])
    print(f"Superset: вес 2: {st['s2_weight']} chat={call.message.chat.id}")
    finish_superset(call.message.chat.id)
    current_set = st.get("set_number", 1)
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("➕ Следующий сет", callback_data="s_next_set"),
        InlineKeyboardButton("🏁 Закончить", callback_data="main_menu")
    )
    bot.edit_message_text(
        f"Суперсет {current_set} сохранён: 1) {st['s1_reps']} повт, вес {st.get('s1_weight') or 'нет'} кг; 2) {st['s2_reps']} повт, вес {st.get('s2_weight') or 'нет'} кг",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda call: call.data == "sno_weight2")
def s_no_weight2(call):
    st = ensure_state(call.message.chat.id)
    st["s2_weight"] = None
    print(f"Superset: без веса 2 chat={call.message.chat.id}")
    finish_superset(call.message.chat.id)
    current_set = st.get("set_number", 1)
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("➕ Следующий сет", callback_data="s_next_set"),
        InlineKeyboardButton("🏁 Закончить", callback_data="main_menu")
    )
    bot.edit_message_text(
        f"Суперсет {current_set} сохранён: 1) {st['s1_reps']} повт, вес {st.get('s1_weight') or 'нет'} кг; 2) {st['s2_reps']} повт, вес {st.get('s2_weight') or 'нет'} кг",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda call: call.data == "s_next_set")
def s_next_set(call):
    st = ensure_state(call.message.chat.id)
    st["set_number"] = st.get("set_number", 1) + 1
    print(f"Следующий сет суперсета: {st['set_number']} chat={call.message.chat.id}")
    show_reps_menu_superset(call, which=1)

@bot.callback_query_handler(func=lambda call: call.data == "add_reps_menu")
def add_reps_menu(call):
    candidates = [5, 8, 12, 16, 18, 25]
    kb = build_grid_keyboard(candidates, "add_reps", back_callback=None, columns=3)
    bot.edit_message_text("Добавить новое значение повторений:", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_reps:"))
def add_reps_value(call):
    value = int(call.data.split(":")[1])
    cursor.execute("INSERT INTO gym.repetitions (reps_count) VALUES (%s) ON CONFLICT DO NOTHING;", (value,))
    conn.commit()
    print(f"Добавлено значение повторений: {value}")
    st = ensure_state(call.message.chat.id)
    if st.get("mode") == "superset" and st.get("awaiting_superset") in ("first_reps", "second_reps"):
        which = 1 if st["awaiting_superset"] == "first_reps" else 2
        show_reps_menu_superset(call, which=which, send_new=True)
    else:
        show_reps_menu(call, send_new=True)

@bot.callback_query_handler(func=lambda call: call.data == "add_weight_menu")
def add_weight_menu(call):
    candidates = [1.25, 2.5, 5, 7.5, 12.5, 20]
    labels = [f"{c}" for c in candidates]
    kb = build_grid_keyboard(labels, "add_weight", back_callback=None, columns=3)
    bot.edit_message_text("Добавить новый вес (кг):", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_weight:"))
def add_weight_value(call):
    value = float(call.data.split(":")[1])
    cursor.execute("INSERT INTO gym.weights (weight_kg) VALUES (%s) ON CONFLICT DO NOTHING;", (value,))
    conn.commit()
    print(f"Добавлен вес: {value} кг")
    st = ensure_state(call.message.chat.id)
    if st.get("mode") == "superset" and st.get("awaiting_superset") in ("first_weight", "second_weight"):
        which = 1 if st["awaiting_superset"] == "first_weight" else 2
        show_weight_menu_superset(call, which=which, send_new=True)
    else:
        show_weight_menu(call, send_new=True)

def finish_set(call_or_msg):
    chat_id = call_or_msg.chat.id if hasattr(call_or_msg, "chat") else call_or_msg.message.chat.id
    state = ensure_state(chat_id)
    today = date.today()
    cursor.execute(
        """
        INSERT INTO gym.workout_stats (
            chat_id, date, exercise_id, set_number, weight_kg, reps_count
        ) VALUES (%s, %s, %s, %s, %s, %s);
        """,
        (
            chat_id,
            today,
            state["exercise_id"],
            state.get("set_number", 1),
            state.get("weight"),
            state["reps"],
        ),
    )
    conn.commit()
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("➕ Ещё подход", callback_data="next_set"),
        InlineKeyboardButton("🏁 Закончить", callback_data="main_menu")
    )
    current_set = state.get('set_number', 1)
    print(f"Сохранён подход chat={chat_id} упражнение_id={state['exercise_id']} сет={current_set} повт={state['reps']} вес={state.get('weight')}")
    bot.edit_message_text(
        f"Подход {current_set} сохранён: {state['reps']} повторений, вес: {state.get('weight') or 'нет'} кг",
        chat_id,
        call_or_msg.message.message_id if hasattr(call_or_msg, 'message') else call_or_msg.message_id,
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda call: call.data == "next_set")
def next_set(call):
    chat_id = call.message.chat.id
    state = ensure_state(chat_id)
    state["set_number"] = state.get("set_number", 1) + 1
    print(f"Следующий подход: {state['set_number']} chat={chat_id}")
    show_reps_menu(call)

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def back_to_main(call):
    ensure_state(call.message.chat.id)
    print(f"Возврат в главное меню chat={call.message.chat.id}")
    bot.edit_message_text("Выберите режим:", call.message.chat.id, call.message.message_id, reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "stats")
def stats_menu(call):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("📅 За день", callback_data="stats_day"),
        InlineKeyboardButton("🏷 По упражнению", callback_data="stats_exercise"),
    )
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="main_menu"))
    bot.edit_message_text("Что показать?", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "exercise_back")
def back_to_exercises(call):
    print(f"Назад к упражнениям chat={call.message.chat.id}")
    show_exercises_menu(call)

@bot.callback_query_handler(func=lambda call: call.data == "reps_back")
def back_to_reps(call):
    print(f"Назад к повторениям chat={call.message.chat.id}")
    show_reps_menu(call)

def build_calendar(chat_id, year, month):
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(year, month)
    kb = InlineKeyboardMarkup()
    prev_month = (datetime(year, month, 15) - timedelta(days=31)).replace(day=1)
    next_month = (datetime(year, month, 15) + timedelta(days=31)).replace(day=1)
    ru_months = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
        7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }
    kb.row(
        InlineKeyboardButton("◀️", callback_data=f"cal:{prev_month.year}:{prev_month.month}"),
        InlineKeyboardButton(f"{ru_months[month]} {year}", callback_data="noop"),
        InlineKeyboardButton("▶️", callback_data=f"cal:{next_month.year}:{next_month.month}")
    )
    cursor.execute(
        """
        SELECT DISTINCT date FROM (
            SELECT date FROM gym.workout_stats WHERE chat_id = %s AND date >= %s AND date < %s
            UNION ALL
            SELECT date FROM gym.supersets WHERE chat_id = %s AND date >= %s AND date < %s
        ) t
        """,
        (
            chat_id, datetime(year, month, 1).date(), (datetime(year, month, 1) + timedelta(days=32)).replace(day=1).date(),
            chat_id, datetime(year, month, 1).date(), (datetime(year, month, 1) + timedelta(days=32)).replace(day=1).date(),
        )
    )
    trained = {d[0].day for d in cursor.fetchall()}
    kb.row(*[InlineKeyboardButton(x, callback_data="noop") for x in ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]])
    for week in weeks:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="noop"))
            else:
                label = f"{day}{'⭐' if day in trained else ''}"
                row.append(InlineKeyboardButton(label, callback_data=f"day:{year}:{month}:{day}"))
        kb.row(*row)
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="stats"))
    return kb

@bot.callback_query_handler(func=lambda call: call.data == "stats_day")
def stats_day(call):
    today = datetime.today()
    kb = build_calendar(call.message.chat.id, today.year, today.month)
    bot.edit_message_text("Выберите день:", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("cal:"))
def stats_calendar_nav(call):
    _, y, m = call.data.split(":")
    y = int(y); m = int(m)
    kb = build_calendar(call.message.chat.id, y, m)
    bot.edit_message_text("Выберите день:", call.message.chat.id, call.message.message_id, reply_markup=kb)

def build_day_summary(chat_id, y, m, d):
    the_day = date(y, m, d)
    def format_weight_text(w):
        if w is None:
            return "нет кг"
        s = ("{:g}".format(w)).replace('.', ',')
        return f"{s} кг"
    def format_pair(reps, weight):
        reps_txt = f"{reps}" if reps is not None else "–"
        weight_txt = format_weight_text(weight)
        return f"{reps_txt} x {weight_txt}"
    cursor.execute(
        """
        SELECT mg.name AS group_name, ex.name AS ex_name, ws.set_number, ws.weight_kg, ws.reps_count, ws.created_at
        FROM gym.workout_stats ws
        JOIN gym.exercises ex ON ex.id = ws.exercise_id
        JOIN gym.muscle_groups mg ON mg.id = ex.muscle_group_id
        WHERE ws.chat_id = %s AND ws.date = %s
        ORDER BY ws.created_at
        """,
        (chat_id, the_day)
    )
    singles_rows = cursor.fetchall()
    singles_grouped = {}
    for gname, exname, set_no, w, r, created in singles_rows:
        key = (gname or "", exname or "")
        singles_grouped.setdefault(key, []).append((set_no, r, w))
    cursor.execute(
        """
        SELECT mg1.name, ex1.name, mg2.name, ex2.name, s.set_number,
               s.first_weight_kg, s.first_reps_count, s.second_weight_kg, s.second_reps_count, s.created_at
        FROM gym.supersets s
        JOIN gym.exercises ex1 ON ex1.id = s.first_exercise_id
        JOIN gym.muscle_groups mg1 ON mg1.id = ex1.muscle_group_id
        JOIN gym.exercises ex2 ON ex2.id = s.second_exercise_id
        JOIN gym.muscle_groups mg2 ON mg2.id = ex2.muscle_group_id
        WHERE s.chat_id = %s AND s.date = %s
        ORDER BY s.created_at
        """,
        (chat_id, the_day)
    )
    supers = cursor.fetchall()
    lines = [f"Статистика за {the_day.strftime('%d.%m.%Y')}:\n"]
    if singles_grouped:
        lines.append("Одиночные упражнения:")
        for (gname, exname), sets in singles_grouped.items():
            lines.append(f"- ({gname}) {exname}:")
            for set_no, r, w in sets:
                lines.append(f"{set_no}) {format_pair(r, w)}")
            lines.append("")
    if supers:
        lines.append("Суперсеты:\n")
        for g1, n1, g2, n2, set_no, w1, r1, w2, r2, created in supers:
            lines.append(f"- Сет {set_no}:")
            lines.append(f"1) ({g1}) {n1}: {format_pair(r1, w1)};")
            lines.append(f"2) ({g2}) {n2}: {format_pair(r2, w2)}")
    if not singles_grouped and not supers:
        lines.append("Нет данных за выбранный день.")
    return "\n".join(lines).rstrip()

@bot.callback_query_handler(func=lambda call: call.data.startswith("day:"))
def stats_day_pick(call):
    _, y, m, d = call.data.split(":")
    y = int(y); m = int(m); d = int(d)
    text = build_day_summary(call.message.chat.id, y, m, d)
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="stats_day"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "stats_exercise")
def stats_exercise_entry(call):
    st = ensure_state(call.message.chat.id)
    st["mode"] = "stats_exercise"
    groups = get_muscle_groups()
    kb = build_keyboard(groups, "stat_muscle", "stats")
    bot.edit_message_text("Выберите группу:", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("stat_muscle:"))
def stats_exercise_choose_group(call):
    st = ensure_state(call.message.chat.id)
    gid = int(call.data.split(":")[1])
    st["stat_group_id"] = gid
    exs = get_exercises_by_group(gid)
    kb = build_keyboard(exs, "stat_ex", "stats_exercise")
    bot.edit_message_text("Выберите упражнение:", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("stat_ex:"))
def stats_exercise_show(call):
    st = ensure_state(call.message.chat.id)
    ex_id = int(call.data.split(":")[1])
    since = (datetime.today() - timedelta(days=30)).date()
    cursor.execute(
        """
        SELECT ws.date, ws.reps_count, ws.weight_kg
        FROM gym.workout_stats ws
        WHERE ws.chat_id = %s AND ws.exercise_id = %s AND ws.date >= %s
        ORDER BY ws.date, ws.set_number
        """,
        (call.message.chat.id, ex_id, since)
    )
    rows = cursor.fetchall()
    num_sets = len(rows)
    avg_reps = round(sum([r[1] or 0 for r in rows]) / num_sets, 2) if num_sets else 0
    avg_weight = round(sum([(r[2] or 0.0) for r in rows]) / num_sets, 2) if num_sets else 0
    cursor.execute("SELECT name FROM gym.exercises WHERE id = %s", (ex_id,))
    ex_name = cursor.fetchone()[0]
    text = (
        f"Статистика за месяц по: {ex_name}\n"
        f"Подходов: {num_sets}\n"
        f"Средние повторы: {avg_reps}\n"
        f"Средний вес: {avg_weight} кг"
    )
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="stats_exercise"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "add_group")
def add_group_prompt(call):
    chat_id = call.message.chat.id
    state = ensure_state(chat_id)
    state["awaiting_input"] = "group"
    print(f"Запрос ввода новой группы chat={chat_id}")
    bot.send_message(chat_id, "Отправьте название новой группы мышц сообщением.")

@bot.callback_query_handler(func=lambda call: call.data == "add_exercise")
def add_exercise_prompt(call):
    chat_id = call.message.chat.id
    state = ensure_state(chat_id)
    state["awaiting_input"] = "exercise"
    print(f"Запрос ввода нового упражнения chat={chat_id}")
    bot.send_message(chat_id, "Отправьте название нового упражнения сообщением.")

@bot.message_handler(func=lambda m: ensure_state(m.chat.id).get("awaiting_input") in ("group", "exercise"))
def receive_new_names(message):
    chat_id = message.chat.id
    state = ensure_state(chat_id)
    text = (message.text or '').strip()
    if not text:
        bot.send_message(chat_id, "Пустое название. Отправьте корректный текст.")
        return
    if state["awaiting_input"] == "group":
        cursor.execute("INSERT INTO gym.muscle_groups (name) VALUES (%s) ON CONFLICT DO NOTHING RETURNING id;", (text,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("SELECT id FROM gym.muscle_groups WHERE name = %s;", (text,))
            row = cursor.fetchone()
        conn.commit()
        print(f"Добавлена/найдена группа: {text} id={row[0]} chat={chat_id}")
        dummy_call = type('obj', (), { 'message': message })()
        show_groups_menu(dummy_call, send_new=True)
    else:
        group_id = state.get("muscle_group_id")
        if not group_id:
            bot.send_message(chat_id, "Сначала выберите группу мышц.")
            return
        cursor.execute(
            "INSERT INTO gym.exercises (muscle_group_id, name) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
            (group_id, text)
        )
        conn.commit()
        print(f"Добавлено упражнение: {text} для группы_id {group_id} chat={chat_id}")
        dummy_call = type('obj', (), { 'message': message })()
        show_exercises_menu(dummy_call, send_new=True)
    state["awaiting_input"] = None

print("Бот запущен.")
bot.infinity_polling()