import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Конфигурация приложения"""

    # Ключи API
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')

    # Настройки PostgreSQL
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 5432))
    DB_NAME = os.getenv('DB_NAME')
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')

    # Строка подключения к PostgreSQL
    DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    # Настройки API
    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
    OPENWEATHER_API_URL = "https://api.openweathermap.org/data/2.5/forecast"

    # Настройки приложения
    BOT_NAME = "🎣 Прогноз клева"
    BOT_VERSION = "1.0"
    FORECAST_DAYS = int(os.getenv('FORECAST_DAYS', 5))
    WEATHER_UNITS = os.getenv('WEATHER_UNITS', 'metric')
    LANGUAGE = os.getenv('LANGUAGE', 'ru')

    # Проверка обязательных переменных
    @classmethod
    def validate(cls):
        """Проверка конфигурации"""
        missing = []
        if not cls.TELEGRAM_BOT_TOKEN:
            missing.append('TELEGRAM_BOT_TOKEN')
        if not cls.OPENWEATHER_API_KEY:
            missing.append('OPENWEATHER_API_KEY')
        if not cls.GROQ_API_KEY:
            missing.append('GROQ_API_KEY')
        if not cls.DB_NAME:
            missing.append('DB_NAME')
        if not cls.DB_USER:
            missing.append('DB_USER')
        if not cls.DB_PASSWORD:
            missing.append('DB_PASSWORD')

        if missing:
            raise ValueError(f"Отсутствуют обязательные переменные окружения: {', '.join(missing)}")

        print(f"✅ Конфигурация загружена: {cls.BOT_NAME} v{cls.BOT_VERSION}")


config = Config()
