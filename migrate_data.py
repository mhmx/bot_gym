#!/usr/bin/env python3
"""
Скрипт для миграции существующих данных из CSV файлов в MySQL базу данных
"""

import mysql.connector
from mysql.connector import Error
import pandas as pd
import os
from datetime import datetime
import logging
from config import DB_CONFIG, EXERCISES_FILE, STATS_DIR

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

def migrate_exercises():
    """Мигрирует упражнения из exercises.csv в базу данных"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        # Читаем CSV файл с упражнениями
        df = pd.read_csv(EXERCISES_FILE)
        
        cursor = connection.cursor()
        
        # Очищаем таблицу упражнений
        cursor.execute("DELETE FROM exercises")
        
        # Вставляем упражнения
        for _, row in df.iterrows():
            muscle_group = row['group']
            exercise_name = row['exercise']
            
            cursor.execute("""
                INSERT INTO exercises (muscle_group, exercise_name)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE exercise_name = VALUES(exercise_name)
            """, (muscle_group, exercise_name))
        
        connection.commit()
        logger.info(f"Успешно мигрированы упражнения: {len(df)} записей")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка миграции упражнений: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def migrate_weights():
    """Мигрирует веса из numbers.csv в базу данных"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        # Читаем CSV файл с весами
        df = pd.read_csv(NUMBERS_FILE)
        
        cursor = connection.cursor()
        
        # Очищаем таблицу весов
        cursor.execute("DELETE FROM available_weights")
        
        # Вставляем веса
        for _, row in df.iterrows():
            weight = row['Numbers']
            if pd.notna(weight):
                cursor.execute("""
                    INSERT INTO available_weights (weight)
                    VALUES (%s)
                """, (float(weight),))
        
        connection.commit()
        logger.info(f"Успешно мигрированы веса: {len(df)} записей")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка миграции весов: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def migrate_workout_stats():
    """Мигрирует статистику тренировок из CSV файлов в базу данных"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Очищаем таблицу статистики
        cursor.execute("DELETE FROM workout_stats")
        
        # Ищем все CSV файлы со статистикой
        if not os.path.exists(STATS_DIR):
            logger.warning(f"Директория {STATS_DIR} не найдена")
            return True
        
        migrated_count = 0
        
        for filename in os.listdir(STATS_DIR):
            if filename.endswith('_stats.csv'):
                filepath = os.path.join(STATS_DIR, filename)
                logger.info(f"Обрабатываем файл: {filepath}")
                
                try:
                    df = pd.read_csv(filepath)
                    
                    for _, row in df.iterrows():
                        chat_id = int(row['chat_id'])
                        date_str = row['date']
                        muscle_group = row['group']
                        exercise_name = row['exercise']
                        set_number = int(row['run'])
                        weight = float(row['weight'])
                        reps = int(row['reps'])
                        
                        # Парсим дату
                        try:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                        except ValueError:
                            logger.warning(f"Неверный формат даты: {date_str}")
                            continue
                        
                        cursor.execute("""
                            INSERT INTO workout_stats (chat_id, date, muscle_group, exercise_name, set_number, weight, reps)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (chat_id, date_obj, muscle_group, exercise_name, set_number, weight, reps))
                        
                        migrated_count += 1
                
                except Exception as e:
                    logger.error(f"Ошибка обработки файла {filepath}: {e}")
                    continue
        
        connection.commit()
        logger.info(f"Успешно мигрирована статистика тренировок: {migrated_count} записей")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка миграции статистики тренировок: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def verify_migration():
    """Проверяет успешность миграции"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Проверяем количество упражнений
        cursor.execute("SELECT COUNT(*) FROM exercises")
        exercises_count = cursor.fetchone()[0]
        logger.info(f"Количество упражнений в базе: {exercises_count}")
        
        # Проверяем количество весов
        cursor.execute("SELECT COUNT(*) FROM available_weights")
        weights_count = cursor.fetchone()[0]
        logger.info(f"Количество весов в базе: {weights_count}")
        
        # Проверяем количество записей статистики
        cursor.execute("SELECT COUNT(*) FROM workout_stats")
        stats_count = cursor.fetchone()[0]
        logger.info(f"Количество записей статистики в базе: {stats_count}")
        
        # Проверяем уникальных пользователей
        cursor.execute("SELECT COUNT(DISTINCT chat_id) FROM workout_stats")
        users_count = cursor.fetchone()[0]
        logger.info(f"Количество уникальных пользователей: {users_count}")
        
        # Показываем примеры данных
        cursor.execute("SELECT * FROM exercises LIMIT 5")
        exercises_sample = cursor.fetchall()
        logger.info("Примеры упражнений:")
        for exercise in exercises_sample:
            logger.info(f"  {exercise[1]} - {exercise[2]}")
        
        cursor.execute("SELECT * FROM workout_stats ORDER BY date DESC LIMIT 5")
        stats_sample = cursor.fetchall()
        logger.info("Последние записи статистики:")
        for stat in stats_sample:
            logger.info(f"  {stat[1]} | {stat[2]} | {stat[3]} - {stat[4]} | Подход {stat[5]} | {stat[6]}кг × {stat[7]} повторений")
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка проверки миграции: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def main():
    """Основная функция миграции"""
    logger.info("Начинаем миграцию данных...")
    
    # Инициализация базы данных
    if not init_database():
        logger.error("Не удалось инициализировать базу данных")
        return
    
    # Миграция упражнений
    logger.info("Мигрируем упражнения...")
    if not migrate_exercises():
        logger.error("Ошибка миграции упражнений")
        return
    
    # Миграция весов
    logger.info("Мигрируем веса...")
    if not migrate_weights():
        logger.error("Ошибка миграции весов")
        return
    
    # Миграция статистики тренировок
    logger.info("Мигрируем статистику тренировок...")
    if not migrate_workout_stats():
        logger.error("Ошибка миграции статистики тренировок")
        return
    
    # Проверка миграции
    logger.info("Проверяем результаты миграции...")
    if not verify_migration():
        logger.error("Ошибка проверки миграции")
        return
    
    logger.info("Миграция успешно завершена!")

if __name__ == "__main__":
    main()
