from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters, CallbackQueryHandler
)
from datetime import datetime
import traceback

from .config import config
from .database import db
from .weather_service import weather_service
from .ai_forecaster import ai_forecaster


class FishingForecastBot:
    """Основной класс Telegram-бота"""

    def __init__(self):
        self.application = None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user

        # Сохраняем пользователя в БД
        user_data = {
            'telegram_id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name
        }

        user_id = db.save_user(user_data)

        # Получаем статистику пользователя
        stats = db.get_user_stats(user_id)

        # Формируем приветственное сообщение
        if stats and stats['total_requests'] > 0:
            # Для существующих пользователей
            welcome_msg = (
                f"🎣 Добро пожаловать обратно, {user.first_name}!\n\n"
                f"📊 Ваша статистика:\n"
                f"• Первый запуск: {stats['first_launch'].strftime('%d.%m.%Y')}\n"
                f"• Всего запросов: {stats['total_requests']}\n"
                f"• Последний запрос: {stats['last_request'].strftime('%d.%m.%Y %H:%M') if stats['last_request'] else 'Нет'}\n\n"
                f"Чтобы получить прогноз клева, просто напишите название региона или города.\n"
                f"Например: *Москва*, *Санкт-Петербург*, *Байкал*"
            )
        else:
            # Для новых пользователей
            welcome_msg = (
                f"🎣 Привет, {user.first_name}!\n\n"
                f"Я — *{config.BOT_NAME}*, бот для прогноза клева рыбы!\n\n"
                f"📈 **Что я умею:**\n"
                f"• Анализировать погоду на {config.FORECAST_DAYS} дней\n"
                f"• Прогнозировать клев рыбы с помощью ИИ\n"
                f"• Сохранять историю ваших запросов\n\n"
                f"📝 **Как пользоваться:**\n"
                f"Просто напишите название города или региона.\n"
                f"Например: *Москва* или *Санкт-Петербург*\n\n"
                f"🔍 **Доступные команды:**\n"
                f"/start - Запустить бота\n"
                f"/help - Помощь\n"
                f"/history - История запросов\n\n"
                f"*Напишите название города, чтобы начать!*"
            )

        keyboard = [
            [InlineKeyboardButton("📋 История запросов", callback_data="history")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            welcome_msg,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = (
            f"🎣 *{config.BOT_NAME}*\n\n"
            f"📖 **Руководство пользователя:**\n\n"
            f"🔍 **Основные команды:**\n"
            f"• Напишите название города - получить прогноз\n"
            f"• /history - История запросов\n"
            f"• /help - Эта справка\n"
            f"• /start - Перезапустить бота\n\n"
            f"📊 **Как работает прогноз:**\n"
            f"1. Я получаю погоду с OpenWeatherMap\n"
            f"2. Анализирую данные с помощью ИИ GROQ\n"
            f"3. Учитываю давление, температуру, ветер\n"
            f"4. Даю оценку клева по 5-балльной шкале\n\n"
            f"🎯 **Факторы влияния:**\n"
            f"• *Давление*: Стабильное = хорошо\n"
            f"• *Температура*: 15-25°C = оптимально\n"
            f"• *Ветер*: 1-4 м/с = хорошо\n"
            f"• *Осадки*: Легкий дождь = часто улучшает\n\n"
            f"*Удачной рыбалки!* 🎣"
        )

        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /history"""
        user = update.effective_user
        user_db = db.get_user_by_telegram_id(user.id)

        if not user_db:
            await update.message.reply_text(
                "📭 У вас еще нет истории запросов.\n"
                "Напишите название региона, чтобы получить первый прогноз!",
                parse_mode='Markdown'
            )
            return

        history = db.get_user_history(user_db['id'], limit=10)

        if not history:
            await update.message.reply_text(
                "📭 У вас еще нет истории запросов.\n"
                "Напишите название региона, чтобы получить первый прогноз!",
                parse_mode='Markdown'
            )
            return

        lines = [f"📚 *История ваших запросов:*\n"]

        for i, item in enumerate(history, 1):
            date_str = item['date'].strftime('%d.%m.%Y %H:%M')
            quality_emoji = {
                "Отличный": "🎣🎣🎣🎣🎣",
                "Хороший": "🎣🎣🎣🎣",
                "Средний": "🎣🎣🎣",
                "Слабый": "🎣🎣",
                "Отсутствует": "🎣"
            }.get(item['quality'], "🎣")

            lines.append(
                f"{i}. *{item['region']}*\n"
                f"   📅 {date_str}\n"
                f"   {quality_emoji} {item['quality'] or 'Не оценено'}\n"
                f"   🆔 #{item['id']}\n"
            )

        lines.append(f"\n📊 *Всего запросов:* {len(history)}")
        lines.append(f"👤 *ID пользователя:* {user.id}")
        lines.append("\n*Чтобы повторить запрос, просто напишите название региона*")

        history_text = "\n".join(lines)

        await update.message.reply_text(history_text, parse_mode='Markdown')

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений (запросов прогноза)"""
        user = update.effective_user
        region = update.message.text.strip()

        print(f"📨 Запрос от {user.id}: {region}")

        # Проверяем пользователя
        user_db = db.get_user_by_telegram_id(user.id)
        if not user_db:
            # Создаем пользователя если его нет
            user_data = {
                'telegram_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
            user_id = db.save_user(user_data)
        else:
            user_id = user_db['id']

        # Отправляем сообщение "обрабатывается"
        processing_msg = await update.message.reply_text(
            f"🎣 *Анализирую прогноз для {region}...*\n\n"
            f"1️⃣ Получаю данные погоды...\n"
            f"2️⃣ Анализирую с помощью ИИ...\n"
            f"3️⃣ Формирую прогноз клева...\n\n"
            f"*Это займет около 10-15 секунд*",
            parse_mode='Markdown'
        )

        try:
            # 1. Получаем прогноз погоды
            await processing_msg.edit_text(
                f"🎣 *Анализирую прогноз для {region}...*\n\n"
                f"✅ 1️⃣ Получаю данные погоды...\n"
                f"2️⃣ Анализирую с помощью ИИ...\n"
                f"3️⃣ Формирую прогноз клева...",
                parse_mode='Markdown'
            )

            weather_forecast = weather_service.get_forecast(region)

            if not weather_forecast or 'forecasts' not in weather_forecast:
                await processing_msg.edit_text(
                    f"❌ Не удалось получить прогноз погоды для *{region}*\n\n"
                    f"*Возможные причины:*\n"
                    f"• Регион указан неверно\n"
                    f"• Проблемы с интернет-соединением\n"
                    f"• Ошибка сервиса погоды\n\n"
                    f"Попробуйте другой регион или повторите позже.",
                    parse_mode='Markdown'
                )
                return

            # 2. Получаем прогноз клева от ИИ
            await processing_msg.edit_text(
                f"🎣 *Анализирую прогноз для {region}...*\n\n"
                f"✅ 1️⃣ Получаю данные погоды...\n"
                f"✅ 2️⃣ Анализирую с помощью ИИ...\n"
                f"3️⃣ Формирую прогноз клева...",
                parse_mode='Markdown'
            )

            forecast_result = ai_forecaster.get_forecast(region, weather_forecast['forecasts'])

            # 3. Сохраняем запрос в историю
            forecast_data = {
                'user_id': user_id,
                'region': region,
                'request_date': datetime.now(),
                'weather_data': weather_forecast['forecasts'],
                'ai_response': forecast_result["ai_response"],
                'forecast_quality': forecast_result["quality"],
                'confidence': forecast_result.get("confidence")
            }

            request_id = db.save_forecast_request(forecast_data)

            # 4. Формируем финальное сообщение
            weather_text = weather_service.format_weather_for_display(weather_forecast)
            ai_text = forecast_result["ai_response"]

            final_message = (
                f"🎣 *ПРОГНОЗ КЛЕВА ДЛЯ {region.upper()}*\n\n"
                f"{'=' * 40}\n"
                f"{weather_text}\n\n"
                f"{'=' * 40}\n"
                f"{ai_text}\n\n"
                f"{'=' * 40}\n"
                f"🆔 *ID запроса:* #{request_id}\n"
                f"📅 *Запрос обработан:* {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
                f"*Хорошей рыбалки!* 🎣"
            )

            # Отправляем результат
            await processing_msg.edit_text(
                final_message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )

            print(f"✅ Прогноз отправлен пользователю {user.id}")

        except Exception as e:
            print(f"❌ Ошибка при обработке запроса: {e}")
            traceback.print_exc()
            await processing_msg.edit_text(
                f"❌ *Произошла ошибка при обработке запроса*\n\n"
                f"*Детали:* {str(e)[:100]}...\n\n"
                f"Попробуйте еще раз или обратитесь к разработчику.",
                parse_mode='Markdown'
            )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик callback-запросов от inline-кнопок"""
        query = update.callback_query
        await query.answer()

        user = query.from_user
        data = query.data

        print(f"🔄 Callback от {user.id}: {data}")

        if data == "history":
            user_db = db.get_user_by_telegram_id(user.id)
            if user_db:
                history = db.get_user_history(user_db['id'], limit=10)
                if history:
                    lines = [f"📚 *История запросов:*\n"]

                    for i, item in enumerate(history, 1):
                        date_str = item['date'].strftime('%d.%m.%Y %H:%M')
                        lines.append(
                            f"{i}. *{item['region']}*\n"
                            f"   📅 {date_str}\n"
                            f"   🆔 #{item['id']}\n"
                        )

                    lines.append(f"\n📊 *Всего запросов:* {len(history)}")
                    history_text = "\n".join(lines)

                    await query.edit_message_text(
                        history_text,
                        parse_mode='Markdown'
                    )
                    return

        elif data == "help":
            help_text = (
                f"🎣 *{config.BOT_NAME}*\n\n"
                f"*Быстрая помощь:*\n\n"
                f"📝 **Как получить прогноз:**\n"
                f"Просто напишите название города\n\n"
                f"📊 **Команды:**\n"
                f"• /start - Главное меню\n"
                f"• /history - История\n"
                f"• /help - Помощь\n\n"
                f"*Примеры регионов:*\n"
                f"• Москва\n"
                f"• Санкт-Петербург\n"
                f"• Сочи\n"
                f"• Казань\n\n"
                f"*Удачи на рыбалке!* 🎣"
            )
            await query.edit_message_text(help_text, parse_mode='Markdown')

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Глобальный обработчик ошибок"""
        print(f"💥 Ошибка в боте: {context.error}")
        traceback.print_exc()

        try:
            if update and update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ *Произошла непредвиденная ошибка*\n\n"
                         "Попробуйте еще раз или обратитесь к разработчику.",
                    parse_mode='Markdown'
                )
        except:
            pass

    def setup_handlers(self, application: Application):
        """Настройка обработчиков команд"""
        # Команды
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("history", self.history_command))

        # Текстовые сообщения
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_message
        ))

        # Callback-запросы
        application.add_handler(CallbackQueryHandler(self.handle_callback))

        # Обработчик ошибок
        application.add_error_handler(self.error_handler)

    def run(self):
        """Запуск бота"""
        try:
            # Проверяем конфигурацию
            config.validate()

            # Создаем приложение
            self.application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

            # Настраиваем обработчики
            self.setup_handlers(self.application)

            # Запускаем бота
            print(f"🚀 Запускаю бота: {config.BOT_NAME}")
            print(f"🤖 Бот готов к работе!")
            print(f"📊 База данных: {config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}")

            self.application.run_polling(allowed_updates=Update.ALL_TYPES)

        except Exception as e:
            print(f"💥 Критическая ошибка при запуске бота: {e}")
            traceback.print_exc()
            if db.conn:
                db.close()