from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters, CallbackQueryHandler
)
from datetime import datetime, timedelta
import re
import traceback
import requests

from .ai_chat_handler import handle_ai_chat, handle_ai_json_chat
from .config import config
from .database import db
from .weather_service import weather_service
from .ai_forecaster import ai_forecaster

from .intent_analyzer import IntentAnalyzer
from .weather_intelligent_service import IntelligentWeatherService
from .intelligent_fishing_forecaster import IntelligentFishingForecaster
from typing import Dict, Any
from src.geoip import GeoIPService, logger
from src.location_resolver import LocationResolver
import logging



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
        self.user_context = {}
        self.last_weather_data = {}  # {user_id: weather_data}
        self.intent_analyzer = IntentAnalyzer()

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
           # parse_mode='Markdown',
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

        await update.message.reply_text(help_text)

    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /history"""
        user = update.effective_user
        user_db = db.get_user_by_telegram_id(user.id)

        if not user_db:
            await update.message.reply_text(
                "📭 У вас еще нет истории запросов.\n"
                "Напишите название региона, чтобы получить первый прогноз!",
                #parse_mode='Markdown'
            )
            return

        history = db.get_user_history(user_db['id'], limit=10)

        if not history:
            await update.message.reply_text(
                "📭 У вас еще нет истории запросов.\n"
                "Напишите название региона, чтобы получить первый прогноз!",
                #parse_mode='Markdown'
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

        await update.message.reply_text(history_text)

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
        message_text = update.message.text.strip()
        user_id = update.effective_user.id

        # Определяем тип запроса
        intent_analyzer = IntentAnalyzer()
        analysis = intent_analyzer.analyze(message_text)
        text_lower = message_text.lower()

        # 1. Прогноз клева
        if analysis.get('intent') == 'fishing_forecast':
            await self._handle_fishing_request(update, analysis, message_text)
            return

        # 2. Погода
        if analysis.get('location') and analysis.get('intent') == 'weather':
            await self._handle_weather_request(update, analysis)
            return

        # 3. Общие вопросы к ИИ
        if '?' in message_text.lower() or analysis.get('intent') == 'general_question':
            await self._handle_ai_chat(update, message_text, analysis)
            return

        # 4. Непонятно
        help_text = "🎣 Напишите название города для прогноза или задайте вопрос о рыбалке."
        await update.message.reply_text(help_text)

    async def _handle_ai_chat(self, update: Update, question: str, analysis: Dict):
        """Обработка AI-вопросов с учетом погодного контекста"""
        user_id = update.effective_user.id

        try:
            # Отправляем сообщение "думаю"
            thinking_msg = await update.message.reply_text("🤔 Думаю над ответом...")

            # Проверяем, нужны ли погодные данные для ответа
            needs_weather = self._question_needs_weather(question)

            # Получаем последние погодные данные пользователя
            last_weather = self.user_context.get(user_id, {}).get('last_weather')

            # Формируем запрос с максимальным контекстом
            enhanced_question = question

            # Если вопрос про клев/рыбалку и есть погодный контекст
            if needs_weather and last_weather:
                location = last_weather.get('location', '')
                weather_context = (
                    f"\n\nКОНТЕКСТ ПОГОДЫ (последний запрос пользователя):\n"
                    f"Место: {location}\n"
                    f"Температура: {last_weather.get('temp', 'Н/Д')}°C\n"
                    f"Условия: {last_weather.get('conditions', 'Н/Д')}\n"
                    f"Давление: {last_weather.get('pressure', 'Н/Д')} мм рт.ст.\n"
                    f"Ветер: {last_weather.get('wind_speed', 'Н/Д')} м/с\n"
                    f"Дата: {last_weather.get('date', 'Н/Д')}\n"
                )
                enhanced_question = question + weather_context

            # Если есть указание города в анализе, добавляем его
            elif analysis.get('location'):
                location = analysis.get('location')
                enhanced_question = f"{question} [Место: {location}]"

            # Получаем ответ от ИИ
            ai_response = await handle_ai_chat(enhanced_question)

            # Удаляем сообщение "думаю"
            await thinking_msg.delete()

            # Отправляем ответ
            await update.message.reply_text(ai_response)

            # Сохраняем в историю
            await self._save_to_history(
                user_id=user_id,
                query=question,
                intent='ai_chat',
                response=ai_response[:500] if len(ai_response) > 500 else ai_response
            )

        except Exception as e:
            logging.error(f"Ошибка ИИ-чата: {e}")
            fallback_response = (
                "🤖 К сожалению, не могу ответить прямо сейчас.\n\n"
                "Вы можете:\n"
                "• Запросить прогноз клева для города\n"
                "• Попробовать задать вопрос позже\n"
                "• Уточнить свой запрос"
            )
            await update.message.reply_text(fallback_response)

    def _question_needs_weather(self, question: str) -> bool:
        """Определяет, нужны ли погодные данные для ответа на вопрос"""
        text_lower = question.lower()

        weather_keywords = [
            'клев', 'клюет', 'ловить', 'рыбалк', 'ловится',
            'на что ловить', 'какая рыба', 'в такую погоду',
            'при такой температуре', 'завтра.*рыба', 'сегодня.*рыба',
            'прогноз.*рыб', 'по клеву', 'клев.*будет'
        ]

        return any(keyword in text_lower for keyword in weather_keywords)

    async def _handle_ai_chat_with_weather_context(self, update: Update, question: str, weather_data: dict):
        """Обработка AI-вопросов с конкретными погодными данными"""
        user_id = update.effective_user.id

        try:
            thinking_msg = await update.message.reply_text("🤔 Анализирую с учетом погоды...")

            # Формируем запрос с полным погодным контекстом
            location = weather_data.get('location', 'этом месте')
            enhanced_question = f"""
    ТЕКУЩИЕ ПОГОДНЫЕ УСЛОВИЯ ДЛЯ {location.upper()}:
    • Температура: {weather_data.get('temperature', 'Н/Д')}°C
    • Погода: {weather_data.get('conditions', 'Н/Д')}
    • Давление: {weather_data.get('pressure', 'Н/Д')} мм рт.ст.
    • Ветер: {weather_data.get('wind', 'Н/Д')} м/с
    • Влажность: {weather_data.get('humidity', 'Н/Д')}%
    • Дата: {weather_data.get('timestamp', datetime.now().strftime('%d.%m.%Y'))}

    ВОПРОС ПОЛЬЗОВАТЕЛЯ: {question}

    ДАЙ ОТВЕТ С УЧЕТОМ ЭТИХ ПОГОДНЫХ УСЛОВИЙ!
    """

            ai_response = await handle_ai_chat(enhanced_question)
            await thinking_msg.delete()
            await update.message.reply_text(ai_response)

        except Exception as e:
            logging.error(f"Ошибка AI с погодным контекстом: {e}")
            await update.message.reply_text("❌ Не удалось проанализировать с учетом погоды.")

    def _format_simple_weather_for_ai(self, weather_data: dict, is_tomorrow: bool = False) -> str:
        """Краткая сводка погоды для ИИ с учетом 'завтра'"""
        if not weather_data.get('forecast'):
            return "Нет данных"

        # Выбираем правильный день: 0=сегодня, 1=завтра
        day_index = 1 if is_tomorrow else 0

        if day_index < len(weather_data['forecast']):
            day = weather_data['forecast'][day_index]
            return (
                f"Дата: {day.get('date', '')}\n"
                f"Погода: {day.get('weather', '')}\n"
                f"Температура: {day.get('temp_min', '?')}...{day.get('temp_max', '?')}°C\n"
                f"Ветер: {day.get('wind_speed', '?')} м/с\n"
                f"Давление: {day.get('pressure', '?')} мм рт.ст."
            )
        else:
            # Fallback: берем первый доступный день
            day = weather_data['forecast'][0]
            return f"Погода: {day.get('weather', '')}, Температура: {day.get('temp_min', '?')}...{day.get('temp_max', '?')}°C"

    def _parse_ai_fishing_response(self, ai_response: str, location: str, is_tomorrow: bool = False) -> str:
        """Парсит ответ ИИ и форматирует в читаемый вид"""
        try:
            # Пытаемся извлечь JSON
            import json
            import re

            # Ищем JSON в ответе
            json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                # Если нет JSON, создаем fallback
                data = {
                    "overall_score": 5,
                    "peaceful_score": 5,
                    "predator_score": 5,
                    "brief_comment": "Средний клев при текущих условиях."
                }

            # Форматируем звездочками
            def score_to_stars(score):
                full_stars = int(score / 2)  # 10 баллов = 5 звезд
                return "⭐" * full_stars + "☆" * (5 - full_stars)

            # Красивый формат
            date_text = "ЗАВТРА" if is_tomorrow else "СЕГОДНЯ"

            response = (
                f"🎣 *ПРОГНОЗ КЛЕВА ДЛЯ {location.upper()} {date_text}*\n\n"
                f"📊 *ОЦЕНКА КЛЕВА:*\n"
                f"• Общий клев: {data.get('overall_score', 5)}/10 {score_to_stars(data.get('overall_score', 5))}\n"
                f"• Мирная рыба: {data.get('peaceful_score', 5)}/10 {score_to_stars(data.get('peaceful_score', 5))}\n"
                f"• Хищная рыба: {data.get('predator_score', 5)}/10 {score_to_stars(data.get('predator_score', 5))}\n\n"
                f"💬 *КОММЕНТАРИЙ:*\n{data.get('brief_comment', '')}\n\n"
                f"📍 *МЕСТО:* {location}\n"
                f"📅 *ДАТА:* {date_text.lower()}\n"
                f"🎯 *ТОЧНОСТЬ:* анализ на основе реальных погодных данных"
            )

            return response

        except Exception as e:
            logging.error(f"Ошибка парсинга ответа ИИ: {e}")
            return f"🎣 *ПРОГНОЗ КЛЕВА ДЛЯ {location}*\n\n📊 К сожалению, не удалось получить оценку.\n\nПопробуйте запросить прогноз клева с указанием города."

    async def _handle_integrated_fishing_forecast(self, update: Update, location: str, days: int = 1,
                                                  is_tomorrow: bool = False):
        """ИСПРАВЛЕННЫЙ: Интегрированный прогноз клева - всегда правильный город и дата"""
        user_id = update.effective_user.id
        message_text = update.message.text
        message_lower = message_text.lower()

        print(f"=== DEBUG _handle_integrated_fishing_forecast ===")
        print(f"Входные данные: location='{location}', days={days}, is_tomorrow={is_tomorrow}")
        print(f"Полный текст: '{message_text}'")

        # ===== ИСПРАВЛЕНИЕ 1: ОПРЕДЕЛЯЕМ НАСТОЯЩИЙ ГОРОД =====
        final_city = location

        # Список слов, которые НЕ являются городами
        NOT_CITIES = {'на', 'в', 'для', 'по', 'у', 'с', 'за', 'из', 'от', 'о'}

        # Если location - это служебное слово (на, в, для и т.д.)
        if location.lower() in NOT_CITIES:
            print(f"DEBUG: Получен служебный город '{location}', ищем настоящий...")

            # Вариант А: Ищем город в текущем сообщении
            words = message_text.split()
            for word in words:
                word_clean = word.strip('.,!?;:').lower()

                # Пропускаем служебные слова
                if word_clean in NOT_CITIES or word_clean in ['завтра', 'сегодня', 'клев', 'будет', 'какой', 'какая']:
                    continue

                if len(word_clean) > 2:  # Минимум 3 буквы для города
                    # Проверяем, может это уже сохраненный город в другом падеже
                    if word[0].isupper():  # С заглавной - вероятно город
                        final_city = word.strip('.,!?;:')
                        print(f"DEBUG: Нашли город в тексте: '{final_city}'")
                        break

            # Вариант Б: Если не нашли в тексте, берем из контекста
            if final_city.lower() in NOT_CITIES and user_id in self.user_context:
                final_city = self.user_context[user_id].get('last_region', '')
                if final_city:
                    print(f"DEBUG: Взяли город из контекста (last_region): '{final_city}'")

            # Вариант В: Если все еще нет, ищем last_city
            if final_city.lower() in NOT_CITIES and user_id in self.user_context:
                final_city = self.user_context[user_id].get('last_city', '')
                if final_city:
                    print(f"DEBUG: Взяли город из контекста (last_city): '{final_city}'")

        # ===== ИСПРАВЛЕНИЕ 2: Проверяем, что город валидный =====
        if not final_city or final_city.lower() in NOT_CITIES:
            print(f"DEBUG: Не удалось определить город (final_city='{final_city}')")
            await update.message.reply_text(
                "❌ Не указан город. Примеры правильных запросов:\n"
                "• 'Клев в Лиде завтра'\n"
                "• 'Какой клев завтра в Минске'\n"
                "• 'Прогноз клева для Ошмян'\n"
                "• 'Лида' (бот сам поймет, что нужен прогноз клева)"
            )
            return

        # ===== ИСПРАВЛЕНИЕ 3: ОПРЕДЕЛЯЕМ ДАТУ =====
        # Переопределяем is_tomorrow на основе текста сообщения
        is_tomorrow = 'завтра' in message_lower
        date_text = "ЗАВТРА" if is_tomorrow else "СЕГОДНЯ"

        # Корректируем days для "завтра"
        forecast_days = 2 if is_tomorrow else 1

        print(
            f"DEBUG РЕЗУЛЬТАТ: city='{final_city}', tomorrow={is_tomorrow}, date='{date_text}', forecast_days={forecast_days}")

        # ===== ОСНОВНАЯ ЛОГИКА =====
        await update.message.reply_text(f"🎣 Анализирую клев в {final_city} {date_text.lower()}...")

        try:
            # Получаем погоду
            weather_data = await self.weather_service.get_weather_forecast(final_city, forecast_days)

            if not weather_data:
                await update.message.reply_text(f"❌ Не удалось получить данные для '{final_city}'.")
                return

            # Формируем УПРОЩЕННЫЙ промпт для ИИ
            weather_summary = self._format_simple_weather_for_ai(weather_data, is_tomorrow)

            ai_prompt = f"""
    Ты — рыболовный эксперт. Проанализируй клев рыбы.

    МЕСТО: {final_city}
    ДАТА: {date_text}

    ПОГОДНЫЕ УСЛОВИЯ:
    {weather_summary}

    ДАЙ ОЦЕНКУ КЛЕВА ОТ 1 ДО 10:
    1. Общая оценка клева (1-10)
    2. Оценка для мирной рыбы (1-10)
    3. Оценка для хищной рыбы (1-10)

    ОТВЕЧАЙ ТОЛЬКО В JSON ФОРМАТЕ:
    {{
      "overall_score": число от 1 до 10,
      "peaceful_score": число от 1 до 10,
      "predator_score": число от 1 до 10,
      "comment": "короткий комментарий 10-15 слов о клеве"
    }}

    НИКАКИХ ДРУГИХ ТЕКСТОВ, ТОЛЬКО JSON!
    """

            # Получаем ответ от ИИ
            thinking_msg = await update.message.reply_text("🤔 Анализирую с помощью ИИ...")
            ai_response = await handle_ai_json_chat(ai_prompt)
            await thinking_msg.delete()

            # Парсим JSON ответ (используем улучшенный парсер)
            forecast = self._parse_ai_fishing_response_improved(ai_response, final_city, date_text)

            # Отправляем УПРОЩЕННЫЙ ответ
            await update.message.reply_text(forecast, parse_mode='Markdown')

        except Exception as e:
            logging.error(f"Ошибка прогноза клева: {e}", exc_info=True)
            await update.message.reply_text("❌ Ошибка анализа. Попробуйте позже.")

    # ===== ДОБАВИТЬ ЭТОТ МЕТОД В КЛАСС =====
    def _parse_ai_fishing_response_improved(self, ai_response: str, city: str, date: str) -> str:
        """УЛУЧШЕННЫЙ парсер ответа ИИ"""
        try:
            import json
            import re

            print(f"DEBUG _parse_ai_fishing_response: raw response length={len(ai_response)}")
            print(f"DEBUG: Первые 200 символов: {ai_response[:200]}")

            # Ищем JSON в ответе (более надежный поиск)
            json_match = re.search(r'\{[^{}]*\}', ai_response)
            if not json_match:
                # Пробуем найти любой JSON
                json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)

            if json_match:
                json_str = json_match.group()
                print(f"DEBUG: Найден JSON: {json_str}")
                data = json.loads(json_str)
            else:
                print(f"DEBUG: JSON не найден, создаем fallback")
                data = {
                    'overall_score': 5,
                    'peaceful_score': 5,
                    'predator_score': 5,
                    'comment': 'Средний клев при текущих условиях.'
                }

            # Функция для звездочек
            def get_stars(score):
                try:
                    score_num = int(score)
                    full = min(int(score_num / 2), 5)
                    return '⭐' * full + '☆' * (5 - full)
                except:
                    return '⭐⭐⭐☆☆'

            # КРАСИВЫЙ ФОРМАТ ОТВЕТА
            return (
                f"🎣 *ПРОГНОЗ КЛЕВА*\n\n"
                f"📍 *МЕСТО:* {city}\n"
                f"📅 *ДАТА:* {date}\n\n"
                f"📊 *ОЦЕНКА КЛЕВА:*\n"
                f"• Общий: {data.get('overall_score', 5)}/10 {get_stars(data.get('overall_score', 5))}\n"
                f"• Мирная рыба: {data.get('peaceful_score', 5)}/10 {get_stars(data.get('peaceful_score', 5))}\n"
                f"• Хищная рыба: {data.get('predator_score', 5)}/10 {get_stars(data.get('predator_score', 5))}\n\n"
                f"💬 *КОММЕНТАРИЙ:*\n{data.get('comment', data.get('brief_comment', 'Анализ завершен.'))}\n\n"
                f"🎯 *АНАЛИЗ НА ОСНОВЕ РЕАЛЬНЫХ ПОГОДНЫХ ДАННЫХ*"
            )

        except Exception as e:
            print(f"DEBUG: Ошибка парсинга: {e}")
            return f"🎣 *ПРОГНОЗ КЛЕВА ДЛЯ {city} {date}*\n\n✅ Анализ завершен.\n\n📍 *МЕСТО:* {city}\n📅 *ДАТА:* {date}"

    def _format_weather_for_ai(self, weather_data: dict) -> str:
        """Форматирует погодные данные для промпта ИИ"""
        summary = []

        if 'forecast' in weather_data:
            for day in weather_data['forecast']:
                summary.append(
                    f"{day.get('date', '')}: {day.get('weather', '')}, "
                    f"Температура: {day.get('temp_min', '')}...{day.get('temp_max', '')}°C, "
                    f"Ветер: {day.get('wind_speed', '')} м/с, "
                    f"Давление: {day.get('pressure', '')} мм рт.ст."
                )

        return "\n".join(summary) if summary else "Нет данных о погоде"

    def _format_integrated_response(self, location: str, weather_data: dict, ai_response: str) -> str:
        """Форматирует итоговый ответ"""
        # Краткая сводка погоды
        if 'forecast' in weather_data and weather_data['forecast']:
            first_day = weather_data['forecast'][0]
            weather_summary = (
                f"🌤️ *Погода в {location}:*\n"
                f"• {first_day.get('weather', 'Нет данных')}\n"
                f"• Температура: {first_day.get('temp_min', '?')}...{first_day.get('temp_max', '?')}°C\n"
                f"• Ветер: {first_day.get('wind_speed', '?')} м/с\n"
                f"• Давление: {first_day.get('pressure', '?')} мм рт.ст.\n\n"
            )
        else:
            weather_summary = f"🌤️ *Погода в {location}:* данные получены\n\n"

        return f"{weather_summary}🎣 *Прогноз клева (анализ ИИ):*\n\n{ai_response}"

    async def _handle_weather_request(self, update: Update, analysis: Dict):
        user_id = update.effective_user.id
        message_text = update.message.text
        location = analysis.get('location')
        days = analysis.get('days', 1)
        time_period = analysis.get('time_period')
        start_offset = self._get_time_period_offset(time_period)

        print(f"DEBUG: Извлечена локация: '{location}' из '{update.message.text}'")

        # СПЕЦИАЛЬНАЯ ПРОВЕРКА: исправляем неправильно извлеченные города
        invalid_words = ['на', 'в', 'для', 'по', 'у', 'с', 'за', 'какой', 'какая', 'эти', 'дни']

        if location and location.lower() in invalid_words:
            # Пытаемся извлечь город из исходного текста другим способом
            location = self._extract_city_from_query(update.message.text)

        if not location or len(location) < 2:  # Минимум 2 буквы для города
            await update.message.reply_text(
                "❌ Не удалось определить город. Укажите название явно, например: 'Лида' или 'Погода в Лиде'")
            return

        location = self.location_resolver._clean_location_query(location)
        location = self.location_resolver._convert_to_nominative(location)
        await update.message.reply_text(f"🌤️ Ищу '{location}'...")

        # Используем улучшенный резолвер с учетом страны пользователя
        resolved = await self.location_resolver.resolve_location_for_user(location, user_id)
        requested_days = max(days + start_offset, 1)

        if resolved:
            # Получаем погоду по координатам
            weather_data = await self.weather_service.get_weather_forecast_by_coords(
                resolved['lat'], resolved['lon'], requested_days
            )
        else:
            # Fallback: пробуем получить прогноз напрямую по названию
            weather_data = await self.weather_service.get_weather_forecast(location, requested_days)

        if not weather_data:
            await update.message.reply_text(f"❌ Не удалось найти '{location}'...")
            return

        full_weather_data = weather_data
        weather_data = self._slice_weather_forecast(full_weather_data, start_offset, days)

        if not weather_data or not weather_data.get('forecast'):
            await update.message.reply_text(f"❌ Не удалось подобрать прогноз по дате.")
            return

        self._store_weather_context(user_id, location, weather_data, full_weather_data)

        # Форматируем ответ
        response = self._format_weather_response(weather_data)
        await update.message.reply_text(response)

    async def _extract_city_from_query(self, text: str) -> str:
        """ИЗВЛЕКАЕТ ГОРОД, ИГНОРИРУЯ 'на', 'в' и т.д."""
        text_lower = text.lower()

        # Список слов, которые НЕ являются городами
        NOT_CITIES = {
            'на', 'в', 'для', 'по', 'у', 'с', 'за', 'из', 'от', 'о',
            'какой', 'какая', 'какое', 'какие', 'будет', 'клев',
            'клюет', 'ловится', 'прогноз', 'погода', 'завтра',
            'сегодня', 'послезавтра', 'эти', 'дни', 'дня', 'а', 'и'
        }

        # Разбиваем текст на слова
        words = text.split()

        # Ищем первое "нормальное" слово (не предлог, не служебное)
        for word in words:
            word_clean = word.strip('.,!?;:')
            word_clean_lower = word_clean.lower()

            # Пропускаем служебные слова
            if word_clean_lower in NOT_CITIES or len(word_clean) < 2:
                continue

            # Это может быть город!
            return word_clean

        return ""

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
        time_period = analysis.get('time_period')
        start_offset = self._get_time_period_offset(time_period)

        if not location and user_id in self.user_context:
            location = self.user_context[user_id].get('last_weather_location') or self.user_context[user_id].get('last_region')

        # Если нет локации - уточняем
        if not location:
            await update.message.reply_text(
                "Для прогноза клева укажите место. Например: 'Какой клев в Лиде?' или 'Будет ли рыба клевать завтра в Москве?'"
            )
            return

        thinking_msg = await update.message.reply_text(f"🎣 Анализирую условия для рыбалки в {location}...")

        # Получаем погоду для анализа (используем кэш, если подходит)
        requested_days = max(days + start_offset, 1)
        weather_data = self._get_cached_weather(user_id, location, requested_days)

        if not weather_data:
            weather_data = await self.weather_service.get_weather_forecast(location, requested_days)

        if not weather_data:
            await update.message.reply_text(
                f"❌ Не удалось получить данные для '{location}'. Проверьте название места."
            )
            return

        weather_data = self._slice_weather_forecast(weather_data, start_offset, days)

        if not weather_data or not weather_data.get('forecast'):
            await update.message.reply_text(
                f"❌ Не удалось подобрать прогноз по дате для '{location}'."
            )
            return

        # Сохраняем контекст погоды
        self._store_weather_context(user_id, location, weather_data)

        # Получаем прогноз клева от ИИ
        forecast = await self.fishing_forecaster.analyze_fishing_conditions(
            weather_data,
            original_query
        )

        # Форматируем ответ
        response = f"🎣 *Прогноз клева для {weather_data.get('location', location)}*\n\n{forecast}"
        await update.message.reply_text(response)
        try:
            await thinking_msg.delete()
        except Exception as exc:
            logging.debug("Failed to delete forecast analysis message: %s", exc)


        # Сохраняем в историю
        await self._save_to_history(user_id, original_query, 'fishing_forecast', response)

    def _get_time_period_offset(self, time_period: str) -> int:
        """Возвращает сдвиг дней для периода времени"""
        if time_period == 'tomorrow':
            return 1
        if time_period == 'day_after_tomorrow':
            return 2
        return 0

    def _normalize_location_name(self, name: str) -> str:
        """Нормализует название локации для сравнения"""
        if not name:
            return ''
        return re.sub(r'[^a-zа-я0-9]+', '', name.lower())

    def _get_cached_weather(self, user_id: int, location: str, min_days: int) -> Dict:
        """Возвращает кэш погоды, если он подходит под запрос"""
        context = self.user_context.get(user_id, {})
        cached_weather = context.get('last_weather_full')
        cached_location = context.get('last_weather_location')
        cached_time = context.get('last_weather_timestamp')

        if not cached_weather or not cached_location or not cached_time:
            return None

        if self._normalize_location_name(cached_location) != self._normalize_location_name(location):
            return None

        if datetime.now() - cached_time > timedelta(minutes=30):
            return None

        cached_days = cached_weather.get('days')
        if cached_days is None:
            cached_days = len(cached_weather.get('forecast', []))

        if cached_days < min_days:
            return None

        return cached_weather

    def _slice_weather_forecast(self, weather_data: Dict, start_offset_days: int, days: int) -> Dict:
        """Обрезает прогноз по дате и количеству дней"""
        if not weather_data or 'forecast' not in weather_data:
            return weather_data

        forecasts = weather_data.get('forecast', [])
        if not forecasts:
            return weather_data

        try:
            sorted_forecasts = sorted(
                forecasts,
                key=lambda item: datetime.fromisoformat(item['date']).date()
            )
        except Exception:
            sorted_forecasts = forecasts

        try:
            first_date = datetime.fromisoformat(sorted_forecasts[0]['date']).date()
            start_date = first_date + timedelta(days=start_offset_days)
            filtered = [
                day for day in sorted_forecasts
                if datetime.fromisoformat(day['date']).date() >= start_date
            ][:max(days, 1)]
        except Exception:
            filtered = sorted_forecasts[:max(days, 1)]

        if not filtered:
            return weather_data

        sliced = dict(weather_data)
        sliced['forecast'] = filtered
        sliced['days'] = len(filtered)
        return sliced

    def _store_weather_context(self, user_id: int, location: str, weather_data: Dict, full_weather_data: Dict = None):
        """Сохраняет погодный контекст для последующих запросов"""
        if user_id not in self.user_context:
            self.user_context[user_id] = {}

        full_data = full_weather_data or weather_data
        first_day = weather_data.get('forecast', [{}])[0] if weather_data else {}
        normalized_location = weather_data.get('location', location)

        self.user_context[user_id].update({
            'last_weather_full': full_data,
            'last_weather_location': normalized_location,
            'last_weather_days': full_data.get('days') if full_data else None,
            'last_weather_timestamp': datetime.now(),
            'last_city': normalized_location,
            'last_region': normalized_location,
            'last_request_date': datetime.now(),
            'last_weather': {
                'location': normalized_location,
                'temp': first_day.get('temp_min'),
                'conditions': first_day.get('weather'),
                'pressure': first_day.get('pressure'),
                'wind_speed': first_day.get('wind_speed'),
                'humidity': first_day.get('humidity'),
                'days': weather_data.get('days', 1),
                'date': first_day.get('date'),
                'timestamp': datetime.now()
            }
        })

        if hasattr(self, 'last_weather_data'):
            self.last_weather_data[user_id] = {
                'location': normalized_location,
                'temperature': first_day.get('temp_min'),
                'conditions': first_day.get('weather'),
                'pressure': first_day.get('pressure'),
                'wind': first_day.get('wind_speed'),
                'humidity': first_day.get('humidity'),
                'forecast_days': weather_data.get('days', 1),
                'timestamp': datetime.now()
            }

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
        """Определяет, является ли запрос вопросом для ИИ"""
        text_lower = text.lower().strip()

        # 1. Явные запросы к ИИ (ВЫСШИЙ ПРИОРИТЕТ)
        ai_triggers = [
            "совет", "подскажи", "помоги", "расскажи", "объясни",
            "что посоветуешь", "как лучше", "что лучше",
            "на что ловить", "какую наживку", "какие снасти",
            "техник", "способ", "метод", "рекомендац", "посоветуй",
            "дай совет", "подскажите", "помогите"
        ]

        # Проверяем триггеры - если есть, сразу к ИИ
        for trigger in ai_triggers:
            if trigger in text_lower:
                logging.info(f"🤖 AI-триггер найден: '{trigger}' в тексте '{text}'")
                return True

        # 2. Вопросительные слова в начале (даже без знака ?)
        question_starts = ["как", "что", "почему", "где", "когда", "зачем", "какой", "какая"]
        for start in question_starts:
            if text_lower.startswith(start):
                logging.info(f"🤖 Вопросительное слово в начале: '{start}'")
                return True

        # 3. Знак вопроса + не одно слово
        if '?' in text and len(text_lower.split()) > 1:
            logging.info(f"🤖 Знак вопроса в тексте")
            return True

        # 4. Запросы про конкретные элементы рыбалки
        fishing_specific = ["наживк", "снаст", "приманк", "удил", "крючк", "леск", "катушк", "воблер", "блесн"]
        if any(term in text_lower for term in fishing_specific):
            logging.info(f"🤖 Специфичный рыболовный термин")
            return True

        # 5. Комбинация: содержит город И вопрос
        known_cities = ["лида", "минск", "москва", "гомель", "брест", "витебск", "гродно"]
        city_in_text = any(city in text_lower for city in known_cities)

        if city_in_text:
            # Если есть город И длинный текст (>3 слов) - вероятно, вопрос с контекстом
            word_count = len(text_lower.split())
            if word_count > 3:
                # Проверяем, не просто ли это "Город завтра/сегодня"
                if not (word_count == 2 and any(word in text_lower for word in ["завтра", "сегодня", "послезавтра"])):
                    logging.info(f"🤖 Комбинация: город + длинный текст")
                    return True

        logging.info(f"❌ Не распознан как AI-вопрос: '{text}'")
        return False

    async def _handle_followup_question(self, update: Update, user_id: int, question: str):
        """Обработка follow-up вопросов после прогноза"""
        processing_msg = await update.message.reply_text(
            f"🤔 *Анализирую ваш вопрос...*\n\n"
            f"Учитываю контекст предыдущего прогноза для *{self.user_context[user_id]['last_region']}*",
            #parse_mode='Markdown'
        )

        try:
            # Подготавливаем контекст для ИИ
            last_forecast_text = self.user_context[user_id].get('last_forecast_summary', '')
            last_region = self.user_context[user_id]['last_region']

            # Отправляем вопрос в ИИ с контекстом
            ai_response = await self._ask_ai_with_context(last_region, last_forecast_text, question)

            await processing_msg.edit_text(
                ai_response,
                #parse_mode='Markdown',
                disable_web_page_preview=True
            )

            print(f"✅ Ответ на follow-up вопрос отправлен пользователю {user_id}")

        except Exception as e:
            print(f"❌ Ошибка при обработке follow-up вопроса: {e}")
            traceback.print_exc()
            await processing_msg.edit_text(
                f"❌ *Не удалось обработать вопрос*\n\n"
                f"Попробуйте задать вопрос иначе или запросите новый прогноз.",
                #parse_mode='Markdown'
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
                "model": "openai/gpt-oss-120b",
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
            #parse_mode='Markdown'
        )

        try:
            # 1. Получаем прогноз погоды
            await processing_msg.edit_text(
                f"🎣 *Анализирую прогноз для {region}...*\n\n"
                f"✅ 1️⃣ Получаю данные погоды...\n"
                f"2️⃣ Анализирую с помощью ИИ...\n"
                f"3️⃣ Формирую прогноз клева...",
                #parse_mode='Markdown'
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
                    #parse_mode='Markdown'
                )
                return

            # 2. Получаем прогноз клева от ИИ
            await processing_msg.edit_text(
                f"🎣 *Анализирую прогноз для {region}...*\n\n"
                f"✅ 1️⃣ Получаю данные погоды...\n"
                f"✅ 2️⃣ Анализирую с помощью ИИ...\n"
                f"3️⃣ Формирую прогноз клева...",
                #parse_mode='Markdown'
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
                #parse_mode='Markdown',
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
                #parse_mode='Markdown'
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
                    #parse_mode='Markdown'
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
