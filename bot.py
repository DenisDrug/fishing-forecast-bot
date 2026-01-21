#!/usr/bin/env python3
"""
🎣 Telegram Bot: Прогноз клева рыбы
Автор: Denis Bre
Версия: 1.0.0
"""


import sys
import os

# Добавляем src в путь для импортов
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.bot_handlers import FishingForecastBot


def main():
    """Основная функция запуска"""
    print("🎣" * 20)
    print("    Fishing Forecast Bot")
    print("    PostgreSQL Version")
    print("🎣" * 20)
    print()

    try:
        # Создаем и запускаем бота
        bot = FishingForecastBot()
        bot.run()

    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()