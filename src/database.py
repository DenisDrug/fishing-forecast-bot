import psycopg2
import psycopg2.extras
from datetime import datetime
import json
from typing import List, Dict, Any, Optional
import traceback

from .config import config


class Database:
    """Класс для работы с PostgreSQL"""

    def __init__(self):
        self.conn = None
        self.connect()
        self.init_tables()

    def connect(self):
        """Подключение к PostgreSQL"""
        try:
            self.conn = psycopg2.connect(
                host=config.DB_HOST,
                port=config.DB_PORT,
                database=config.DB_NAME,
                user=config.DB_USER,
                password=config.DB_PASSWORD
            )
            self.conn.autocommit = True
            print(f"✅ Подключено к PostgreSQL: {config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}")
        except Exception as e:
            print(f"❌ Ошибка подключения к PostgreSQL: {e}")
            raise

    def init_tables(self):
        """Создание таблиц если их нет"""
        try:
            with self.conn.cursor() as cursor:
                # Таблица пользователей
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS fishing_users (
                        id SERIAL PRIMARY KEY,
                        telegram_id BIGINT UNIQUE NOT NULL,
                        username VARCHAR(100),
                        first_name VARCHAR(100),
                        last_name VARCHAR(100),
                        first_launch_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        total_requests INTEGER DEFAULT 0,
                        last_request_date TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Таблица истории запросов
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS fishing_forecasts (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES fishing_users(id) ON DELETE CASCADE,
                        region VARCHAR(100) NOT NULL,
                        request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        weather_data JSONB,
                        ai_response TEXT,
                        forecast_quality VARCHAR(20),
                        confidence REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Индексы для оптимизации
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_fishing_users_telegram_id 
                    ON fishing_users(telegram_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_fishing_forecasts_user_id 
                    ON fishing_forecasts(user_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_fishing_forecasts_request_date 
                    ON fishing_forecasts(request_date DESC)
                """)

                print("✅ Таблицы инициализированы в PostgreSQL")

        except Exception as e:
            print(f"❌ Ошибка инициализации таблиц: {e}")
            traceback.print_exc()

    def save_user(self, user_data: Dict[str, Any]) -> int:
        """Сохранение или обновление пользователя"""
        try:
            with self.conn.cursor() as cursor:
                # Проверяем существующего пользователя
                cursor.execute(
                    "SELECT id FROM fishing_users WHERE telegram_id = %s",
                    (user_data['telegram_id'],)
                )
                existing = cursor.fetchone()

                if existing:
                    user_id = existing[0]
                    # Обновляем существующего пользователя
                    cursor.execute("""
                        UPDATE fishing_users SET
                            username = COALESCE(%s, username),
                            first_name = COALESCE(%s, first_name),
                            last_name = COALESCE(%s, last_name),
                            last_request_date = CURRENT_TIMESTAMP
                        WHERE telegram_id = %s
                    """, (
                        user_data.get('username'),
                        user_data.get('first_name'),
                        user_data.get('last_name'),
                        user_data['telegram_id']
                    ))
                else:
                    # Создаем нового пользователя
                    cursor.execute("""
                        INSERT INTO fishing_users 
                        (telegram_id, username, first_name, last_name, first_launch_date, last_request_date)
                        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        RETURNING id
                    """, (
                        user_data['telegram_id'],
                        user_data.get('username'),
                        user_data.get('first_name'),
                        user_data.get('last_name')
                    ))
                    user_id = cursor.fetchone()[0]
                    print(f"👤 Создан новый пользователь: {user_data['telegram_id']}")

                return user_id

        except Exception as e:
            print(f"❌ Ошибка сохранения пользователя: {e}")
            traceback.print_exc()
            raise

    def save_forecast_request(self, forecast_data: Dict[str, Any]) -> int:
        """Сохранение запроса прогноза"""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO fishing_forecasts 
                    (user_id, region, request_date, weather_data, ai_response, forecast_quality, confidence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    forecast_data['user_id'],
                    forecast_data['region'],
                    forecast_data['request_date'],
                    json.dumps(forecast_data['weather_data']),
                    forecast_data['ai_response'],
                    forecast_data.get('forecast_quality'),
                    forecast_data.get('confidence')
                ))

                forecast_id = cursor.fetchone()[0]

                # Обновляем статистику пользователя
                cursor.execute("""
                    UPDATE fishing_users SET
                        total_requests = total_requests + 1,
                        last_request_date = %s
                    WHERE id = %s
                """, (forecast_data['request_date'], forecast_data['user_id']))

                print(f"📊 Сохранен прогноз #{forecast_id} для пользователя {forecast_data['user_id']}")
                return forecast_id

        except Exception as e:
            print(f"❌ Ошибка сохранения прогноза: {e}")
            traceback.print_exc()
            raise

    def get_user_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Получение истории запросов пользователя"""
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        id, region, request_date, 
                        SUBSTRING(ai_response FROM 1 FOR 100) as response_preview,
                        forecast_quality, confidence
                    FROM fishing_forecasts 
                    WHERE user_id = %s
                    ORDER BY request_date DESC
                    LIMIT %s
                """, (user_id, limit))

                history = []
                for row in cursor.fetchall():
                    history.append({
                        'id': row['id'],
                        'region': row['region'],
                        'date': row['request_date'],
                        'response_preview': row['response_preview'],
                        'quality': row['forecast_quality'],
                        'confidence': row['confidence']
                    })

                return history

        except Exception as e:
            print(f"❌ Ошибка получения истории: {e}")
            return []

    def get_user_stats(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получение статистики пользователя"""
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        telegram_id, username, first_launch_date, 
                        total_requests, last_request_date
                    FROM fishing_users 
                    WHERE id = %s
                """, (user_id,))

                row = cursor.fetchone()
                if row:
                    return {
                        'user_id': row['telegram_id'],
                        'username': row['username'],
                        'first_launch': row['first_launch_date'],
                        'total_requests': row['total_requests'],
                        'last_request': row['last_request_date']
                    }
                return None

        except Exception as e:
            print(f"❌ Ошибка получения статистики: {e}")
            return None

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получение пользователя по Telegram ID"""
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT id, telegram_id, username, first_name, total_requests
                    FROM fishing_users 
                    WHERE telegram_id = %s
                """, (telegram_id,))

                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None

        except Exception as e:
            print(f"❌ Ошибка получения пользователя: {e}")
            return None

    def close(self):
        """Закрытие соединения с БД"""
        if self.conn:
            self.conn.close()
            print("🔌 Соединение с PostgreSQL закрыто")


# Глобальный экземпляр базы данных
db = Database()