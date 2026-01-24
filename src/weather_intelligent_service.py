# src/weather_intelligent_service.py
import aiohttp
import logging
from typing import Dict, Optional, List
from src.config import config

logger = logging.getLogger(__name__)


class IntelligentWeatherService:
    def __init__(self):
        self.base_url = config.OPENWEATHER_API_URL

    async def get_weather_forecast(self, location: str, days: int = 1) -> Optional[Dict]:
        """Получает прогноз погоды для локации"""
        try:
            params = {
                'q': location,
                'appid': config.OPENWEATHER_API_KEY,
                'units': 'metric',
                'lang': 'ru',
                'cnt': days * 8  # 8 запросов в день
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._format_weather_response(data, location, days)
                    else:
                        logger.error(f"Ошибка API погоды: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"Ошибка получения погоды: {e}")
            return None

    def _format_weather_response(self, data: Dict, location: str, days: int) -> Dict:
        """Форматирует ответ о погоде"""
        if not data or 'list' not in data:
            return None

        city = data['city']['name']
        country = data['city']['country']

        # Формируем прогноз по дням
        forecast_by_day = {}

        for item in data['list'][:days * 8]:  # Берем только нужное количество периодов
            date = item['dt_txt'].split()[0]

            if date not in forecast_by_day:
                forecast_by_day[date] = {
                    'temp_min': item['main']['temp'],
                    'temp_max': item['main']['temp'],
                    'pressure': [item['main']['pressure']],
                    'humidity': [item['main']['humidity']],
                    'wind_speed': [item['wind']['speed']],
                    'weather': [item['weather'][0]['description']],
                    'clouds': [item['clouds']['all']],
                    'precipitation': item.get('rain', {}).get('3h', 0) + item.get('snow', {}).get('3h', 0)
                }
            else:
                day_data = forecast_by_day[date]
                day_data['temp_min'] = min(day_data['temp_min'], item['main']['temp'])
                day_data['temp_max'] = max(day_data['temp_max'], item['main']['temp'])
                day_data['pressure'].append(item['main']['pressure'])
                day_data['humidity'].append(item['main']['humidity'])
                day_data['wind_speed'].append(item['wind']['speed'])
                day_data['weather'].append(item['weather'][0]['description'])
                day_data['clouds'].append(item['clouds']['all'])
                day_data['precipitation'] += item.get('rain', {}).get('3h', 0) + item.get('snow', {}).get('3h', 0)

        # Форматируем ответ
        formatted_response = {
            'location': f"{city}, {country}",
            'days': days,
            'forecast': []
        }

        for date, day_data in list(forecast_by_day.items())[:days]:
            formatted_response['forecast'].append({
                'date': date,
                'temp_min': round(day_data['temp_min'], 1),
                'temp_max': round(day_data['temp_max'], 1),
                'pressure': round(sum(day_data['pressure']) / len(day_data['pressure']) * 0.750064, 1),
                'humidity': round(sum(day_data['humidity']) / len(day_data['humidity'])),
                'wind_speed': round(sum(day_data['wind_speed']) / len(day_data['wind_speed']), 1),
                'weather': max(set(day_data['weather']), key=day_data['weather'].count),
                'clouds': round(sum(day_data['clouds']) / len(day_data['clouds'])),
                'precipitation': round(day_data['precipitation'], 1)
            })

        return formatted_response