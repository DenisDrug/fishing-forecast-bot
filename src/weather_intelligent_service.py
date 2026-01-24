# src/weather_intelligent_service.py
import aiohttp
import logging
from typing import Dict, Optional, List
from src.config import config
from src.location_resolver import LocationResolver

logger = logging.getLogger(__name__)


class IntelligentWeatherService:
    def __init__(self):
        self.base_url = config.OPENWEATHER_API_URL
        self.location_resolver = LocationResolver()

    async def get_weather_forecast(self, location_query: str, days: int = 1) -> Optional[Dict]:
        """Получает прогноз погоды для любой локации"""
        try:
            # Пробуем с подсказками стран
            resolved = await self.location_resolver.resolve_with_country_hints(location_query)

            if not resolved:
                # Если не нашли через геокодинг, пробуем прямой запрос по названию
                logger.warning(f"Геокодинг не нашел: {location_query}, пробуем прямой запрос")
                return await self._try_direct_city_query(location_query, days)

            lat = resolved['lat']
            lon = resolved['lon']

            logger.info(f"Найдена локация: {resolved.get('local_name')} ({lat}, {lon})")

            # Запрашиваем погоду по координатам
            params = {
                'lat': lat,
                'lon': lon,
                'appid': config.OPENWEATHER_API_KEY,
                'units': 'metric',
                'lang': 'ru',
                'cnt': days * 8
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._format_weather_response(data, resolved, days)
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка Weather API {response.status}: {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Ошибка получения погоды: {e}")
            return None

    async def _try_direct_city_query(self, location_query: str, days: int) -> Optional[Dict]:
        """Прямой запрос по названию города (fallback)"""
        try:
            params = {
                'q': location_query,
                'appid': config.OPENWEATHER_API_KEY,
                'units': 'metric',
                'lang': 'ru',
                'cnt': days * 8
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Создаем минимальный resolved_location
                        resolved = {
                            'name': data['city']['name'],
                            'local_name': data['city']['name'],
                            'country': data['city']['country']
                        }
                        return self._format_weather_response(data, resolved, days)
                    else:
                        return None
        except:
            return None

    def _format_weather_response(self, data: Dict, resolved_location: Dict, days: int) -> Dict:
        """Форматирует ответ о погоде с использованием найденной локации"""
        if not data or 'list' not in data:
            return None

        # Берем city из ответа API (английское название)
        city = data['city']['name']
        country = data['city']['country']

        # Используем русское название из resolved_location если есть
        russian_name = resolved_location.get('local_name', city)

        # Форматируем отображаемое название
        country_names = {'BY': 'Беларусь', 'RU': 'Россия', 'UA': 'Украина',
                         'LT': 'Литва', 'LV': 'Латвия', 'PL': 'Польша',
                         'EE': 'Эстония', 'MD': 'Молдова', 'KZ': 'Казахстан'}
        country_display = country_names.get(country, country)

        # Остальной код БЕЗ ИЗМЕНЕНИЙ
        forecast_by_day = {}

        for item in data['list'][:days * 8]:
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

        # Форматируем ответ с русским названием
        formatted_response = {
            'location': f"{russian_name}, {country_display}",
            'original_location': f"{city}, {country}",
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