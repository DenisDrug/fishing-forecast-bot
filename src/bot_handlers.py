from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters, CallbackQueryHandler
)
from datetime import datetime, timedelta
import traceback
import requests

from .ai_chat_handler import handle_ai_chat
from .config import config
from .database import db
from .weather_service import weather_service
from .ai_forecaster import ai_forecaster

from .intent_analyzer import IntentAnalyzer
from .weather_intelligent_service import IntelligentWeatherService
from .intelligent_fishing_forecaster import IntelligentFishingForecaster
from .ai_chat_handler import handle_ai_chat
from typing import Dict, Any
from src.geoip import GeoIPService, logger
from src.location_resolver import LocationResolver


class FishingForecastBot:
    """Основной класс Telegram-бота с поддержкой диалога"""

    def __init__(self):
        self.application = None
        self.user_context = {}  # Храним контекст пользователей: {user_id: {last_region, last_forecast, last_request_date}}
        self.intent_analyzer = IntentAnalyzer()
        self.weather_service = IntelligentWeatherService()
        self.fishing_forecaster = IntelligentFishingForecaster()
        self.geoip_service = GeoIPService()
        self.location_resolver = LocationResolver()

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        user_id = user.id

        # Очищаем старый контекст при новом старте
        if user_id in self.user_context:
            del self.user_context[user_id]

        # Сохраняем пользователя в БД
        user_data = {
            'telegram_id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name
        }

        user_db_id = db.save_user(user_data)
        stats = db.get_user_stats(user_db_id)

        # Формируем приветственное сообщение
        if stats and stats['total_requests'] > 0:
            welcome_msg = (
                f"🎣 Добро пожаловать обратно, {user.first_name}!\n\n"
                f"📊 Ваша статистика:\n"
                f"• Первый запуск: {stats['first_launch'].strftime('%d.%m.%Y')}\n"
                f"• Всего запросов: {stats['total_requests']}\n"
                f"• Последний запрос: {stats['last_request'].strftime('%d.%m.%Y %H:%M') if stats['last_request'] else 'Нет'}\n\n"
                f"*Новый функционал:* Теперь можно задавать уточняющие вопросы!\n"
                f"1. Запросите прогноз для региона\n"
                f"2. Затем спросите про конкретный водоем, насадки или виды рыб\n\n"
                f"Например: *Москва*, затем *Река Москва*, затем *Какие насадки?*"
            )
        else:
            welcome_msg = (
                f"🎣 Привет, {user.first_name}!\n\n"
                f"Я — *{config.BOT_NAME}*, твой умный помощник для рыбалки!\n\n"
                f"📈 **Что я умею:**\n"
                f"• Анализировать погоду на {config.FORECAST_DAYS} дней\n"
                f"• Прогнозировать клев рыбы с помощью ИИ\n"
                f"• Поддерживать диалог - задавайте уточняющие вопросы!\n\n"
                f"🎯 **Новый функционал:**\n"
                f"1. Запросите прогноз для региона (например: *Москва*)\n"
                f"2. Затем можете уточнить:\n"
                f"   • Конкретный водоем (река, озеро)\n"
                f"   • Виды рыб\n"
                f"   • Насадки и снасти\n"
                f"   • Места ловли\n\n"
                f"*Напишите название города, чтобы начать!*"
            )

        keyboard = [
            [InlineKeyboardButton("📋 История запросов", callback_data="history")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")],
            [InlineKeyboardButton("🎣 Пример диалога", callback_data="example_dialog")]
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
            f"🎣 *{config.BOT_NAME} - Умный рыболовный помощник*\n\n"
            f"📖 **Как работает диалог:**\n\n"
            f"1️⃣ **ШАГ 1: Запрос прогноза**\n"
            f"Напишите название региона или города\n"
            f"*Пример:* Москва, Санкт-Петербург, Лида\n\n"
            f"2️⃣ **ШАГ 2: Уточняющие вопросы**\n"
            f"После получения прогноза можете спросить:\n"
            f"• *Конкретный водоем:* Река Неман, Озеро Белое\n"
            f"• *Виды рыб:* Где ловить щуку? Как поймать окуня?\n"
            f"• *Насадки и снасти:* Какие насадки? Какие снасти использовать?\n"
            f"• *Места ловли:* Где лучше ловить? Какие места?\n\n"
            f"🔍 **Пример диалога:**\n"
            f"Вы: Москва\n"
            f"Бот: Прогноз для Москвы...\n"
            f"Вы: Река Москва\n"
            f"Бот: Для реки Москва рекомендую...\n"
            f"Вы: Какие насадки для леща?\n"
            f"Бот: Для леща используйте...\n\n"
            f"📊 **Факторы влияния на клев:**\n"
            f"• *Давление:* Стабильное (760-763 мм рт.ст.) = хорошо\n"
            f"• *Температура:* 15-25°C = оптимально\n"
            f"• *Ветер:* 1-4 м/с = хорошо\n"
            f"• *Осадки:* Легкий дождь = часто улучшает\n\n"
            f"*Удачной рыбалки и интересных диалогов!* 🎣"
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

    def _is_followup_question(self, text: str) -> bool:
        """Определяет, является ли сообщение follow-up вопросом"""
        followup_keywords = [
            'река', 'озеро', 'водоем', 'водохранилище', 'пруд', 'затон',
            'насадк', 'приманк', 'наживк', 'прикормк',
            'снаст', 'удочк', 'спининг', 'фидер', 'поплав',
            'щук', 'окун', 'лещ', 'карп', 'плотв', 'карась', 'сом', 'судак', 'голавль', 'жерех',
            'где ловить', 'место', 'совет', 'рекомендац', 'как ловить',
            'время', 'час', 'утро', 'вечер', 'день', 'ночь',
            'глубин', 'течени', 'берег', 'залив', 'плес'
        ]

        text_lower = text.lower()
        return any(keyword in text_lower for keyword in followup_keywords)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Интеллектуальный обработчик сообщений"""
        user = update.effective_user
        user_id = user.id
        message_text = update.message.text.strip()

        print(f"📨 Сообщение от {user.id}: {message_text}")

        # Анализируем намерение пользователя
        analysis = self.intent_analyzer.analyze(message_text)

        # Обрабатываем в зависимости от намерения
        if analysis['intent'] == 'weather':
            await self._handle_weather_request(update, analysis)

        elif analysis['intent'] == 'fishing_forecast':
            await self._handle_fishing_request(update, analysis, message_text)

        elif analysis['intent'] == 'general_question':
            await self._handle_general_question(update, message_text)

        else:
            await update.message.reply_text(
                "Не совсем понял ваш запрос. Вы можете спросить о погоде или прогнозе клева.")

    async def _handle_weather_request(self, update: Update, analysis: Dict):
        user_id = update.effective_user.id
        message_text = update.message.text
        location = analysis.get('location')
        days = analysis.get('days', 1)

        print(f"DEBUG: Извлечена локация: '{location}' из '{update.message.text}'")

        if not location:
            await update.message.reply_text("Для прогноза погоды укажите место...")
            return

        await update.message.reply_text(f"🌤️ Ищу '{location}'...")

        # Используем улучшенный резолвер с учетом страны пользователя
        resolved = await self.location_resolver.resolve_location_for_user(location, user_id)

        if not resolved:
            await update.message.reply_text(f"❌ Не удалось найти '{location}'...")
            return

        # Получаем погоду по координатам
        weather_data = await self.weather_service.get_weather_forecast_by_coords(
            resolved['lat'], resolved['lon'], days
        )

        if not weather_data:
            await update.message.reply_text(f"❌ Не удалось получить прогноз...")
            return

        # Форматируем ответ
        response = self._format_weather_response(weather_data)
        await update.message.reply_text(response, parse_mode="Markdown")

    async def _ask_for_clarification(self, update: Update, original_query: str,
                                     locations: list, days: int):
        """Спрашивает уточнение при нескольких возможных локациях"""
        message = f"Найдено несколько мест по запросу '{original_query}':\n\n"

        for i, loc in enumerate(locations[:5], 1):  # Показываем первые 5
            country = loc.get('country', '')
            state = loc.get('state', '')
            name = loc.get('local_name', loc.get('name', 'Неизвестно'))

            message += f"{i}. {name}"
            if state:
                message += f", {state}"
            if country:
                message += f" ({country})"
            message += "\n"

        message += "\nУточните, какое место вас интересует? Например: '1' или 'Лида, Беларусь'"

        # Сохраняем контекст для follow-up
        context_data = {
            'possible_locations': locations,
            'original_query': original_query,
            'days': days,
            'action': 'weather_clarify'
        }
        self.user_context[update.effective_user.id] = context_data

        await update.message.reply_text(message)

    async def _handle_fishing_request(self, update: Update, analysis: Dict, original_query: str):
        """Обработка запроса прогноза клева"""
        user_id = update.effective_user.id
        location = analysis.get('location')
        days = analysis.get('days', 1)

        # Если нет локации - уточняем
        if not location:
            await update.message.reply_text(
                "Для прогноза клева укажите место. Например: 'Какой клев в Лиде?' или 'Будет ли рыба клевать завтра в Москве?'"
            )
            return

        await update.message.reply_text(f"🎣 Анализирую условия для рыбалки в {location}...")

        # Получаем погоду для анализа
        weather_data = await self.weather_service.get_weather_forecast(location, days)

        if not weather_data:
            await update.message.reply_text(
                f"❌ Не удалось получить данные для '{location}'. Проверьте название места."
            )
            return

        # Получаем прогноз клева от ИИ
        forecast = await self.fishing_forecaster.analyze_fishing_conditions(
            weather_data,
            original_query
        )

        # Форматируем ответ
        response = f"🎣 *Прогноз клева для {location}*\n\n{forecast}"
        await update.message.reply_text(response)

        # Сохраняем в историю
        await self._save_to_history(user_id, original_query, 'fishing_forecast', response)

    async def _handle_general_question(self, update: Update, question: str):
        """Обработка общих вопросов о рыбалке"""
        await update.message.reply_text("🤔 Думаю над ответом...")
        ai_response = await handle_ai_chat(question)
        await update.message.reply_text(ai_response)

    def _format_weather_response(self, weather_data: Dict) -> str:
        """Форматирует ответ о погоде"""
        location = weather_data['location']
        days = weather_data['days']

        response = f"🌤️ *Прогноз погоды для {location}*\n\n"

        for day in weather_data['forecast']:
            emoji = self._get_weather_emoji(day['weather'])
            response += f"📅 *{day['date']}* {emoji}\n"
            response += f"• {day['weather'].capitalize()}\n"
            response += f"• Температура: {day['temp_min']}°C...{day['temp_max']}°C\n"
            response += f"• Давление: {day['pressure']} мм рт.ст.\n"
            response += f"• Влажность: {day['humidity']}%\n"
            response += f"• Ветер: {day['wind_speed']} м/с\n"
            if day['precipitation'] > 0:
                response += f"• Осадки: {day['precipitation']} мм\n"
            response += "\n"

        return response

    def _get_weather_emoji(self, weather_description: str) -> str:
        """Возвращает эмодзи для погоды"""
        weather_lower = weather_description.lower()

        if 'ясно' in weather_lower or 'солн' in weather_lower:
            return "☀️"
        elif 'облач' in weather_lower:
            return "☁️"
        elif 'дожд' in weather_lower or 'лив' in weather_lower:
            return "🌧️"
        elif 'снег' in weather_lower:
            return "❄️"
        elif 'туман' in weather_lower:
            return "🌫️"
        elif 'гроз' in weather_lower:
            return "⛈️"
        else:
            return "🌤️"

    def _is_ai_question(self, text: str) -> bool:
        """Определяет, является ли сообщение вопросом для ИИ"""
        logger.debug(f"Анализируем текст: {text}")
        text_lower = text.lower()

        # Если начинается с вопросительных слов И НЕ содержит указание на город
        question_starters = {'какая', 'какой', 'какое', 'какие', 'как', 'что',
                             'почему', 'зачем', 'когда', 'где', 'сколько'}

        first_word = text_lower.split()[0] if text_lower.split() else ''

        # Если начинается с вопросительного слова И содержит "погод" или "клев"
        # то это запрос погоды, а не ИИ-вопрос
        if first_word in question_starters:
            if 'погод' in text_lower or 'клев' in text_lower or 'рыб' in text_lower:
                return False
            return True

        # Обычные вопросы с "?"
        if '?' in text_lower:
            return True

        # Запросы советов
        advice_words = {'совет', 'подскажи', 'помоги', 'расскажи', 'объясни', 'посоветуй'}
        if any(word in text_lower for word in advice_words):
            return True

        return False

    async def _handle_followup_question(self, update: Update, user_id: int, question: str):
        """Обработка follow-up вопросов после прогноза"""
        processing_msg = await update.message.reply_text(
            f"🤔 *Анализирую ваш вопрос...*\n\n"
            f"Учитываю контекст предыдущего прогноза для *{self.user_context[user_id]['last_region']}*",
            parse_mode='Markdown'
        )

        try:
            # Подготавливаем контекст для ИИ
            last_forecast_text = self.user_context[user_id].get('last_forecast_summary', '')
            last_region = self.user_context[user_id]['last_region']

            # Отправляем вопрос в ИИ с контекстом
            ai_response = await self._ask_ai_with_context(last_region, last_forecast_text, question)

            await processing_msg.edit_text(
                ai_response,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )

            print(f"✅ Ответ на follow-up вопрос отправлен пользователю {user_id}")

        except Exception as e:
            print(f"❌ Ошибка при обработке follow-up вопроса: {e}")
            traceback.print_exc()
            await processing_msg.edit_text(
                f"❌ *Не удалось обработать вопрос*\n\n"
                f"Попробуйте задать вопрос иначе или запросите новый прогноз.",
                parse_mode='Markdown'
            )

    async def _ask_ai_with_context(self, region: str, forecast_summary: str, question: str) -> str:
        """Запрос к Groq API с учетом контекста предыдущего прогноза"""
        try:
            headers = {
                "Authorization": f"Bearer {config.GROQ_API_KEY}",
                "Content-Type": "application/json"
            }

            prompt = f"""Ты — эксперт-рыболов и гид по рыбалке. Ранее ты дал прогноз клева для региона: {region}

КОНТЕКСТ ПРЕДЫДУЩЕГО ПРОГНОЗА (основные моменты):
{forecast_summary[:800]}...

ВОПРОС ПОЛЬЗОВАТЕЛЯ: {question}

ТВОЯ ЗАДАЧА:
1. Ответить на вопрос В КОНТЕКСТЕ ранее данного прогноза для {region}
2. Если вопрос про конкретный водоем - дать рекомендации именно для этого типа водоема
3. Дать конкретные практические советы
4. Сохранять дружелюбный тон опытного рыбака

ФОРМАТ ОТВЕТА:
🎯 ОТВЕТ НА ВОПРОС: [краткий заголовок]

📝 РЕКОМЕНДАЦИИ:
• [Конкретный совет 1]
• [Конкретный совет 2]
• [Конкретный совет 3]

📍 ДЛЯ РЕГИОНА {region.upper()}:
[Специфика для данного региона]

🐟 ПРИМЕЧАНИЕ:
[Дополнительные замечания или предупреждения]

💡 СОВЕТ ЭКСПЕРТА:
[Фишка или лайфхак от опытного рыбака]"""

            payload = {
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 1200
            }

            response = requests.post(
                config.GROQ_API_URL,
                headers=headers,
                json=payload,
                timeout=45
            )

            if response.status_code == 200:
                result = response.json()
                answer = result['choices'][0]['message']['content']

                # Добавляем призыв продолжать диалог
                answer += "\n\n💬 *Можете задать еще вопросы про насадки, места ловли или конкретные виды рыб!*"

                return answer
            else:
                return self._get_fallback_followup_response(region, question)

        except Exception as e:
            print(f"❌ Ошибка запроса к Groq API: {e}")
            return self._get_fallback_followup_response(region, question)

    def _get_fallback_followup_response(self, region: str, question: str) -> str:
        """Резервный ответ на follow-up вопрос"""
        return (
            f"🎯 *Ответ на вопрос о {region}*\n\n"
            f"📝 К сожалению, ИИ временно недоступен для углубленного анализа.\n\n"
            f"💡 *Общие рекомендации:*\n"
            f"• Для водоемов в районе {region} учитывайте местные особенности\n"
            f"• Консультируйтесь с местными рыболовами\n"
            f"• Экспериментируйте с разными насадками\n\n"
            f"*Запросите новый прогноз для получения актуальных данных.*"
        )

    async def _handle_region_request(self, update: Update, user_id: int, region: str):
        """Обработка нового запроса региона"""
        # Проверяем пользователя
        user_db = db.get_user_by_telegram_id(user_id)
        if not user_db:
            user_data = {
                'telegram_id': user_id,
                'username': update.effective_user.username,
                'first_name': update.effective_user.first_name,
                'last_name': update.effective_user.last_name
            }
            user_db_id = db.save_user(user_data)
        else:
            user_db_id = user_db['id']

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
                'user_id': user_db_id,
                'region': region,
                'request_date': datetime.now(),
                'weather_data': weather_forecast['forecasts'],
                'ai_response': forecast_result["ai_response"],
                'forecast_quality': forecast_result["quality"],
                'confidence': forecast_result.get("confidence")
            }

            request_id = db.save_forecast_request(forecast_data)

            # 4. Сохраняем контекст для follow-up вопросов
            self.user_context[user_id] = {
                'last_region': region,
                'last_forecast_summary': forecast_result["ai_response"][:500],  # Сохраняем краткое содержание
                'last_request_date': datetime.now()
            }

            # 5. Формируем финальное сообщение
            weather_text = weather_service.format_weather_for_display(weather_forecast)
            ai_text = forecast_result["ai_response"]

            final_message = (
                f"🎣 *ПРОГНОЗ КЛЕВА ДЛЯ {region.upper()}*\n\n"
                f"{'=' * 40}\n"
                f"{weather_text}\n\n"
                f"{'=' * 40}\n"
                f"{ai_text}\n\n"
                f"{'=' * 40}\n"
                f"💬 *Теперь можете задать уточняющие вопросы!*\n"
                f"• Конкретный водоем (река, озеро)\n"
                f"• Виды рыб\n"
                f"• Насадки и снасти\n"
                f"• Места ловли\n\n"
                f"🆔 *ID запроса:* #{request_id}\n"
                f"📅 *Запрос обработан:* {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
                f"*Хорошей рыбалки!* 🎣"
            )

            await processing_msg.edit_text(
                final_message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )

            print(f"✅ Прогноз отправлен пользователю {user_id}")

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

        if data == "history":
            user_db = db.get_user_by_telegram_id(user.id)
            if user_db:
                history = db.get_user_history(user_db['id'], limit=10)
                if history:
                    lines = [f"📚 *История запросов:*\n"]
                    for i, item in enumerate(history, 1):
                        date_str = item['date'].strftime('%d.%m.%Y %H:%M')
                        lines.append(f"{i}. *{item['region']}*\n   📅 {date_str}\n")
                    lines.append(f"\n📊 *Всего запросов:* {len(history)}")
                    await query.edit_message_text("\n".join(lines), parse_mode='Markdown')
                    return

        elif data == "help":
            help_text = (
                f"🎣 *Быстрая помощь:*\n\n"
                f"📝 **Новый диалоговый режим:**\n"
                f"1. Запросите прогноз для региона\n"
                f"2. Задавайте уточняющие вопросы\n\n"
                f"💡 **Примеры вопросов:**\n"
                f"• Река [название] (после прогноза)\n"
                f"• Какие насадки для [вид рыбы]?\n"
                f"• Где лучше ловить [вид рыбы]?\n"
                f"• Какие снасти использовать?\n\n"
                f"*Попробуйте начать с запроса любого города!*"
            )
            await query.edit_message_text(help_text, parse_mode='Markdown')

        elif data == "example_dialog":
            example = (
                f"🎣 *Пример умного диалога:*\n\n"
                f"👤 *Вы:* Москва\n"
                f"🤖 *Бот:* Прогноз для Москвы...\n\n"
                f"👤 *Вы:* Река Москва\n"
                f"🤖 *Бот:* Для реки Москва рекомендую...\n\n"
                f"👤 *Вы:* Где ловить щуку?\n"
                f"🤖 *Бот:* Щуку на реке Москва лучше искать...\n\n"
                f"👤 *Вы:* Какие воблеры использовать?\n"
                f"🤖 *Бот:* Для щуки подойдут воблеры...\n\n"
                f"*Попробуйте такой диалог с ботом!* 🎣"
            )
            await query.edit_message_text(example, parse_mode='Markdown')

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
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("history", self.history_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        application.add_handler(CallbackQueryHandler(self.handle_callback))
        application.add_error_handler(self.error_handler)

    def run(self):
        """Запуск бота"""
        try:
            config.validate()
            self.application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
            self.setup_handlers(self.application)
            print(f"🚀 Запускаю бота: {config.BOT_NAME}")
            print(f"🤖 Бот готов к работе с поддержкой диалога!")
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)
        except Exception as e:
            print(f"💥 Критическая ошибка: {e}")
            traceback.print_exc()
            if db.conn:
                db.close()

    async def _save_to_history(self, user_id: int, query: str, intent: str, response: str):
        """Сохраняет запрос в историю"""
        try:
            # Импортируем здесь чтобы избежать циклических импортов
            from src.database import save_to_history as db_save_history

            # Обрезаем длинный ответ
            truncated_response = response[:500] + "..." if len(response) > 500 else response

            await db_save_history(
                user_id=user_id,
                query=query,
                intent=intent,
                response=truncated_response
            )
            print(f"📊 Сохранен запрос #{user_id} типа '{intent}'")

        except Exception as e:
            print(f"❌ Ошибка сохранения в историю: {e}")
            # Не падаем, просто логируем ошибку