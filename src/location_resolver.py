# src/location_resolver.py
import aiohttp
import logging
from typing import Dict, Optional
from src.config import config

logger = logging.getLogger(__name__)


class LocationResolver:
    def __init__(self):
        self.geocoding_url = "http://api.openweathermap.org/geo/1.0/direct"

    async def resolve_location(self, location_query: str, country_hint: str = None) -> Optional[Dict]:
        """
        Ищет локацию через OpenWeather Geocoding API
        Поддерживает русские названия городов, районов, областей
        """
        try:
            # Очищаем запрос
            clean_query = self._clean_location_query(location_query)

            # Формируем запрос к геокодеру
            if country_hint:
                search_query = f"{clean_query},{country_hint}"
            else:
                search_query = clean_query

            params = {
                'q': search_query,
                'limit': 5,  # Берем несколько результатов
                'appid': config.OPENWEATHER_API_KEY,
                'lang': 'ru'  # Для русских названий
            }

            logger.info(f"Geocoding search: {search_query}")

            async with aiohttp.ClientSession() as session:
                async with session.get(self.geocoding_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()

                        if not data or len(data) == 0:
                            logger.warning(f"Локация не найдена: {clean_query}")
                            return None

                        # Выбираем лучший результат
                        best_match = self._select_best_match(data, clean_query)
                        return best_match
                    else:
                        error_text = await response.text()
                        logger.error(f"Geocoding API error {response.status}: {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Ошибка геокодинга: {e}")
            return None

    def _clean_location_query(self, query: str) -> str:
        """Очищает запрос локации от лишних слов"""
        # Убираем предлоги и общие слова, но сохраняем структуру
        words = query.strip().split()

        # Если запрос короткий (1-2 слова), убираем предлоги
        if len(words) <= 3:
            stop_words = {'в', 'на', 'для', 'около', 'возле', 'рядом', 'по', 'у'}
            cleaned = [w for w in words if w.lower() not in stop_words]
            return ' '.join(cleaned)

        return query.strip()

    def _select_best_match(self, results: list, original_query: str) -> Dict:
        """Выбирает лучший результат из найденных"""
        original_lower = original_query.lower()

        for result in results:
            # Проверяем русское название
            local_names = result.get('local_names', {})
            ru_name = local_names.get('ru', '').lower()

            # Проверяем английское название
            en_name = result.get('name', '').lower()

            # Проверяем полное название (город + регион)
            state = result.get('state', '').lower()
            full_name = f"{en_name} {state}".strip().lower()

            # Ищем лучшее соответствие
            if original_lower in ru_name or original_lower in full_name:
                return self._format_location_result(result)

        # Если точного совпадения нет, берем первый результат
        return self._format_location_result(results[0])

    def _format_location_result(self, result: Dict) -> Dict:
        """Форматирует результат геокодинга"""
        local_names = result.get('local_names', {})

        return {
            'name': result.get('name', ''),  # Английское название
            'local_name': local_names.get('ru', result.get('name', '')),  # Русское название
            'lat': result.get('lat'),
            'lon': result.get('lon'),
            'country': result.get('country', ''),
            'state': result.get('state', ''),  # Регион/область
            'type': self._get_location_type(result)
        }

    def _get_location_type(self, result: Dict) -> str:
        """Определяет тип локации"""
        # OpenWeather возвращает тип в local_names или можно определить по названию
        if 'район' in result.get('state', '').lower():
            return 'district'
        elif any(word in result.get('name', '').lower() for word in ['city', 'town', 'village']):
            return 'settlement'
        else:
            return 'unknown'

    async def get_coordinates(self, location_query: str) -> Optional[tuple]:
        """Возвращает координаты (lat, lon) для запроса"""
        resolved = await self.resolve_location(location_query)
        if resolved:
            return (resolved['lat'], resolved['lon'])
        return None

    async def resolve_with_country_hints(self, location_query: str) -> Optional[Dict]:
        """Пробует найти локацию с разными подсказками по странам"""
        # Популярные страны для рыбалки
        country_hints = ['BY', 'RU', 'UA', 'LT', 'LV', 'PL', 'EE', 'MD', 'KZ']

        for country in country_hints:
            result = await self.resolve_location(location_query, country)
            if result:
                logger.info(f"Found with country hint {country}: {result['local_name']}")
                return result

        # Пробуем без подсказки страны
        return await self.resolve_location(location_query)