-- Сброс схемы (при необходимости)
DROP TABLE IF EXISTS gym.supersets CASCADE;
DROP TABLE IF EXISTS gym.workout_stats CASCADE;
DROP TABLE IF EXISTS gym.exercises CASCADE;
DROP TABLE IF EXISTS gym.muscle_groups CASCADE;
DROP TABLE IF EXISTS gym.weights CASCADE;
DROP TABLE IF EXISTS gym.repetitions CASCADE;

-- =============================
-- 1. Таблица: muscle_groups
-- =============================
CREATE TABLE gym.muscle_groups (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- =============================
-- 2. Таблица: exercises (ссылка на muscle_groups)
-- =============================
CREATE TABLE gym.exercises (
    id SERIAL PRIMARY KEY,
    muscle_group_id INT NOT NULL REFERENCES gym.muscle_groups(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    name TEXT NOT NULL,
    UNIQUE (muscle_group_id, name)
);

-- =============================
-- 3. Таблица: weights (справочник весов)
-- =============================
CREATE TABLE gym.weights (
    weight_kg NUMERIC(6,2) PRIMARY KEY
);

INSERT INTO gym.weights (weight_kg) VALUES
(1.0), (2.0), (2.5), (3.0), (5.0), (7.5), (10.0), (12.5), (15.0), (20.0);

-- =============================
-- 4. Таблица: repetitions (справочник повторений)
-- =============================
CREATE TABLE gym.repetitions (
    reps_count SMALLINT PRIMARY KEY CHECK (reps_count > 0)
);

INSERT INTO gym.repetitions (reps_count) VALUES
(1), (2), (5), (8), (10), (12), (15), (20), (25);

-- =============================
-- 5. Таблица: workout_stats (ссылка на exercises)
-- =============================
CREATE TABLE gym.workout_stats (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    date DATE NOT NULL,
    exercise_id INT REFERENCES gym.exercises(id) ON UPDATE CASCADE ON DELETE SET NULL,
    set_number SMALLINT NOT NULL CHECK (set_number > 0),
    weight_kg NUMERIC(6,2),
    reps_count SMALLINT CHECK (reps_count > 0),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_workout_stats_chat_date ON gym.workout_stats (chat_id, date);
CREATE INDEX idx_workout_stats_exercise ON gym.workout_stats (exercise_id);

-- =============================
-- 6. Таблица: supersets (ссылки на exercises)
-- =============================
CREATE TABLE gym.supersets (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    date DATE NOT NULL,
    first_exercise_id INT REFERENCES gym.exercises(id) ON UPDATE CASCADE ON DELETE SET NULL,
    second_exercise_id INT REFERENCES gym.exercises(id) ON UPDATE CASCADE ON DELETE SET NULL,
    set_number SMALLINT NOT NULL CHECK (set_number > 0),
    first_weight_kg NUMERIC(6,2),
    first_reps_count SMALLINT CHECK (first_reps_count > 0),
    second_weight_kg NUMERIC(6,2),
    second_reps_count SMALLINT CHECK (second_reps_count > 0),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_supersets_chat_date ON gym.supersets (chat_id, date);
CREATE INDEX idx_supersets_first_second ON gym.supersets (first_exercise_id, second_exercise_id);

-- =============================
-- 7. Примерные данные: группы и упражнения
-- =============================
INSERT INTO gym.muscle_groups (name) VALUES
('Грудь'), ('Спина'), ('Ноги'), ('Плечи'), ('Бицепс'), ('Трицепс'), ('Пресс');

-- Привязанные упражнения
INSERT INTO gym.exercises (muscle_group_id, name)
SELECT g.id, e.name
FROM (VALUES
    ('Грудь', 'Жим лёжа'),
    ('Спина', 'Тяга горизонтального блока'),
    ('Ноги', 'Приседания со штангой'),
    ('Плечи', 'Жим гантелей сидя'),
    ('Бицепс', 'Подъём штанги на бицепс'),
    ('Трицепс', 'Французский жим лёжа'),
    ('Пресс', 'Скручивания'),
    ('Спина', 'Тяга верхнего блока'),
    ('Грудь', 'Отжимания на брусьях')
) AS e(group_name, name)
JOIN gym.muscle_groups g ON g.name = e.group_name
ON CONFLICT (muscle_group_id, name) DO NOTHING;;

-- =============================
-- 8. Примеры workout_stats
-- =============================
INSERT INTO gym.workout_stats (chat_id, date, exercise_id, set_number, weight_kg, reps_count)
SELECT 5873737, '2025-10-15', ex.id, 1, 10.0, 10
FROM gym.exercises ex JOIN gym.muscle_groups g ON g.id = ex.muscle_group_id
WHERE g.name = 'Грудь' AND ex.name = 'Жим лёжа';

INSERT INTO gym.workout_stats (chat_id, date, exercise_id, set_number, weight_kg, reps_count)
SELECT 5873737, '2025-10-15', ex.id, 2, 15.0, 2
FROM gym.exercises ex JOIN gym.muscle_groups g ON g.id = ex.muscle_group_id
WHERE g.name = 'Грудь' AND ex.name = 'Жим лёжа';

INSERT INTO gym.workout_stats (chat_id, date, exercise_id, set_number, weight_kg, reps_count)
SELECT 5873737, '2025-10-15', ex.id, 1, NULL, 20
FROM gym.exercises ex JOIN gym.muscle_groups g ON g.id = ex.muscle_group_id
WHERE g.name = 'Пресс' AND ex.name = 'Скручивания';

-- =============================
-- 9. Примеры supersets
-- =============================
INSERT INTO gym.supersets (
    chat_id, date, first_exercise_id, second_exercise_id,
    set_number, first_weight_kg, first_reps_count, second_weight_kg, second_reps_count
)
SELECT 5873737, '2025-10-15', ex1.id, ex2.id, 1, 10.0, 10, 3.0, 10
FROM gym.exercises ex1 JOIN gym.muscle_groups g1 ON g1.id = ex1.muscle_group_id,
     gym.exercises ex2 JOIN gym.muscle_groups g2 ON g2.id = ex2.muscle_group_id
WHERE g1.name = 'Бицепс' AND ex1.name = 'Подъём штанги на бицепс'
  AND g2.name = 'Трицепс' AND ex2.name = 'Французский жим лёжа';

INSERT INTO gym.supersets (
    chat_id, date, first_exercise_id, second_exercise_id,
    set_number, first_weight_kg, first_reps_count, second_weight_kg, second_reps_count
)
SELECT 5873737, '2025-10-16', ex1.id, ex2.id, 1, 15.0, 10, NULL, 20
FROM gym.exercises ex1 JOIN gym.muscle_groups g1 ON g1.id = ex1.muscle_group_id,
     gym.exercises ex2 JOIN gym.muscle_groups g2 ON g2.id = ex2.muscle_group_id
WHERE g1.name = 'Спина' AND ex1.name = 'Тяга верхнего блока'
  AND g2.name = 'Грудь' AND ex2.name = 'Отжимания на брусьях';