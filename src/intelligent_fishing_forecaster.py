# src/intelligent_fishing_forecaster.py
import aiohttp
import logging
import math
from datetime import datetime
from typing import Dict, Optional
from src.config import config

logger = logging.getLogger(__name__)


class IntelligentFishingForecaster:
    def __init__(self):
        self.groq_url = config.GROQ_API_URL

    async def analyze_fishing_conditions(self, weather_data: Dict, user_query: str) -> str:
        """Анализирует условия для рыбалки с учетом запроса пользователя"""
        if not config.GROQ_API_KEY:
            return self._backup_fishing_forecast(weather_data)

        try:
            prompt = self._create_fishing_prompt(weather_data, user_query)

            headers = {
                "Authorization": f"Bearer {config.GROQ_API_KEY}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "openai/gpt-oss-120b",
                "messages": [
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 800
            }

            timeout = aiohttp.ClientTimeout(total=20)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.groq_url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"].strip()
                    else:
                        logger.error(f"Groq API error: {response.status}")
                        return self._backup_fishing_forecast(weather_data)

        except Exception as e:
            logger.error(f"Ошибка анализа ИИ: {e}")
            return self._backup_fishing_forecast(weather_data)

    def _create_fishing_prompt(self, weather_data: Dict, user_query: str) -> str:
        """Создает промпт для ИИ на основе погоды и запроса"""
        location = weather_data.get('location', 'неизвестное место')
        days = weather_data.get('days', 1)

        prompt = f"""
        Пользователь спрашивает: "{user_query}"

        Прогноз погоды для {location} на {days} день/дней:
        """

        for day in weather_data.get('forecast', []):
            moon_info = self._get_moon_phase_info(day.get('date'))
            prompt += f"""
        Дата: {day.get('date', 'N/A')}
        Температура: {day.get('temp_min')}°C...{day.get('temp_max')}°C
        Давление: {day.get('pressure')} мм рт.ст.
        Влажность: {day.get('humidity')}%
        Ветер: {day.get('wind_speed')} м/с
        Погода: {day.get('weather')}
        Облачность: {day.get('clouds')}%
        Осадки: {day.get('precipitation', 0)} мм
        Луна: {moon_info}
        """

        prompt += """

        Проанализируй эти погодные условия и дай прогноз клева рыбы:
        1. Общая оценка клева (от 1 до 10)
        2. Прогноз по мирной рыбе (лещ, плотва, карась, карп)
        3. Прогноз по хищной рыбе (щука, окунь, судак)
        4. Лучшее время суток для рыбалки
        5. Рекомендации по снастям и наживке
        6. Конкретные советы для указанного периода

        Учитывай:
        - Стабильность атмосферного давления
        - Температуру воды (примерно на 2-3°C ниже температуры воздуха)
        - Фазу луны и освещенность
        - Сезонные особенности
        - Влияние ветра и осадков

        Отвечай на русском языке, будь конкретным и практичным.
        """

        return prompt

    def _get_moon_phase_info(self, date_str: str) -> str:
        """Возвращает фазу луны и освещенность для даты"""
        if not date_str:
            return "неизвестно"

        try:
            date = datetime.fromisoformat(date_str).date()
        except ValueError:
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                return "неизвестно"

        known_new_moon = datetime(2000, 1, 6).date()
        days_since = (date - known_new_moon).days
        synodic_month = 29.53058867
        phase = days_since % synodic_month

        if phase < 1.84566:
            phase_name = "Новолуние"
        elif phase < 5.53699:
            phase_name = "Растущий серп"
        elif phase < 9.22831:
            phase_name = "Первая четверть"
        elif phase < 12.91963:
            phase_name = "Растущая луна"
        elif phase < 16.61096:
            phase_name = "Полнолуние"
        elif phase < 20.30228:
            phase_name = "Убывающая луна"
        elif phase < 23.99361:
            phase_name = "Последняя четверть"
        elif phase < 27.68493:
            phase_name = "Стареющий серп"
        else:
            phase_name = "Новолуние"

        illumination = (1 - math.cos(2 * math.pi * phase / synodic_month)) / 2
        illumination_percent = int(round(illumination * 100))

        return f"{phase_name}, освещенность {illumination_percent}%"

    def _get_system_prompt(self) -> str:
        """Возвращает системный промпт для ИИ"""
        return """Ты опытный ихтиолог и рыболов с 20-летним стажем. 
        Ты анализируешь погодные условия и даешь точные прогнозы клева рыбы.
        Ты учитываешь все факторы: температуру, давление, ветер, влажность, сезон, время суток.
        Ты даешь практические советы, которые действительно работают.
        Ты специализируешься на пресноводной рыбе средней полосы."""

    def _backup_fishing_forecast(self, weather_data: Dict) -> str:
        """Резервный алгоритм прогноза клева"""
        location = weather_data.get('location', 'данной местности')

        return f"""
🎣 *Прогноз клева для {location}* (резервный алгоритм)

*Общая оценка:* 5/10 - средний клев

*Мирная рыба (лещ, плотва, карась):*
• Вероятность клева: 40%
• Лучшее время: утро (6-9 часов)
• Рекомендуемая наживка: мотыль, червь

*Хищная рыба (щука, окунь):*
• Вероятность клева: 60%
• Лучшее время: день (11-15 часов)
• Рекомендуемые приманки: блесны, воблеры

*Общие рекомендации:*
• Используйте чувствительные снасти
• Экспериментируйте с глубиной ловли
• Ищите рыбу вблизи водной растительности

_Для более точного прогноза укажите конкретный водоем (река, озеро, пруд)._
"""
