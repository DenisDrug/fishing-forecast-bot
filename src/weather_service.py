import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
import traceback

from .config import config


class WeatherService:
    """Сервис для работы с API погоды OpenWeatherMap"""

    def __init__(self):
        self.api_key = config.OPENWEATHER_API_KEY
        self.base_url = config.OPENWEATHER_API_URL
        self.units = config.WEATHER_UNITS
        self.lang = config.LANGUAGE

    def get_forecast(self, region: str, days: int = config.FORECAST_DAYS) -> Optional[Dict[str, Any]]:
        """Получение прогноза погоды на указанное количество дней"""
        try:
            params = {
                'q': region,
                'appid': self.api_key,
                'units': self.units,
                'lang': self.lang,
                'cnt': days * 8  # 8 прогнозов в день (каждые 3 часа)
            }

            print(f"🌤️ Запрашиваем погоду для: {region}")
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Группируем по дням
            daily_data = {}
            for item in data['list']:
                date = datetime.fromtimestamp(item['dt'])
                date_key = date.strftime('%Y-%m-%d')

                if date_key not in daily_data:
                    daily_data[date_key] = []
                daily_data[date_key].append(item)

            # Берем прогноз на каждый день (обычно дневной прогноз)
            forecasts = []
            for date_str, day_forecasts in sorted(daily_data.items())[:days]:
                # Выбираем прогноз на 12:00 (примерно середину дня)
                day_forecast = None
                for forecast in day_forecasts:
                    forecast_time = datetime.fromtimestamp(forecast['dt'])
                    if 10 <= forecast_time.hour <= 14:
                        day_forecast = forecast
                        break

                # Если нет прогноза на 12:00, берем первый
                if not day_forecast:
                    day_forecast = day_forecasts[0]

                # Парсим данные погоды
                main = day_forecast['main']
                weather = day_forecast['weather'][0]
                wind = day_forecast.get('wind', {})
                rain = day_forecast.get('rain', {}).get('3h', 0)
                snow = day_forecast.get('snow', {}).get('3h', 0)

                # Конвертируем давление из гПа в мм рт.ст.
                pressure_hpa = main.get('pressure', 1013)
                pressure_mmhg = round(pressure_hpa * 0.750062, 1)

                forecast_data = {
                    'date': datetime.fromtimestamp(day_forecast['dt']).isoformat(),
                    'temperature': main.get('temp', 0),
                    'feels_like': main.get('feels_like', 0),
                    'pressure': pressure_mmhg,  # мм рт.ст.
                    'humidity': main.get('humidity', 0),
                    'wind_speed': wind.get('speed', 0),
                    'wind_direction': wind.get('deg', 0),
                    'cloudiness': day_forecast.get('clouds', {}).get('all', 0),
                    'precipitation': rain + snow,
                    'description': weather['description'].capitalize(),
                    'icon': weather['icon']
                }
                forecasts.append(forecast_data)

            if forecasts:
                print(f"✅ Получен прогноз на {len(forecasts)} дней для {region}")
                return {
                    'region': region,
                    'forecasts': forecasts,
                    'last_updated': datetime.now().isoformat()
                }
            else:
                print(f"❌ Нет данных прогноза для {region}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка запроса к API погоды: {e}")
        except Exception as e:
            print(f"❌ Неожиданная ошибка при получении погоды: {e}")
            traceback.print_exc()

        return None

    def format_weather_for_display(self, weather_data: Dict[str, Any]) -> str:
        """Форматирование погоды для отображения"""
        if not weather_data or 'forecasts' not in weather_data:
            return "❌ Не удалось получить прогноз погоды"

        emoji_map = {
            '01': '☀️',  # clear sky
            '02': '⛅',  # few clouds
            '03': '☁️',  # scattered clouds
            '04': '☁️',  # broken clouds
            '09': '🌧️',  # shower rain
            '10': '🌦️',  # rain
            '11': '⛈️',  # thunderstorm
            '13': '❄️',  # snow
            '50': '🌫️',  # mist
        }

        lines = [f"🌍 **Регион:** {weather_data['region']}"]
        lines.append(f"📅 **Прогноз на {len(weather_data['forecasts'])} дней:**\n")

        for i, day in enumerate(weather_data['forecasts'], 1):
            date = datetime.fromisoformat(day['date'])
            day_name = date.strftime('%d.%m')
            icon_key = day['icon'][:2]
            emoji = emoji_map.get(icon_key, '⛅')

            wind_dir = self._get_wind_direction(day['wind_direction'])

            lines.append(
                f"**{day_name}** {emoji}\n"
                f"• {day['description']}\n"
                f"• Температура: {day['temperature']:.1f}°C\n"
                f"• Ощущается как: {day['feels_like']:.1f}°C\n"
                f"• Давление: {day['pressure']:.1f} мм рт.ст.\n"  # Изменено
                f"• Влажность: {day['humidity']}%\n"
                f"• Ветер: {day['wind_speed']:.1f} м/с ({wind_dir})\n"
                f"• Облачность: {day['cloudiness']}%\n"
                f"• Осадки: {day['precipitation']:.1f} мм\n"
            )

        return "\n".join(lines)

    def _get_wind_direction(self, degrees: int) -> str:
        """Определение направления ветра по градусам"""
        directions = ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ']
        index = round(degrees / 45) % 8
        return directions[index]


# Глобальный экземпляр погодного сервиса
weather_service = WeatherService()