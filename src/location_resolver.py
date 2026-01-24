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
        """Ищет локацию через OpenWeather Geocoding API"""
        try:
            clean_query = self._clean_location_query(location_query)

            # Пробуем разные варианты запроса
            search_variants = []

            # 1. Оригинальный запрос
            search_variants.append(clean_query)

            # 2. Без окончания "е" (предположительный предложный падеж)
            if clean_query.lower().endswith('е'):
                base_form = clean_query[:-1] + 'а'  # "Лиде" -> "Лида"
                search_variants.append(base_form)

            # 3. Для популярных городов добавляем страны
            popular_with_country = {
                'лида': 'BY', 'гродно': 'BY', 'минск': 'BY',
                'москва': 'RU', 'санкт-петербург': 'RU',
                'киев': 'UA', 'вильнюс': 'LT'
            }

            query_lower = clean_query.lower()
            if query_lower in popular_with_country and not country_hint:
                country_hint = popular_with_country[query_lower]

            # Формируем поисковый запрос
            if country_hint:
                search_query = f"{clean_query},{country_hint}"
            else:
                search_query = clean_query

            params = {
                'q': search_query,
                'limit': 10,  # Больше результатов для лучшего поиска
                'appid': config.OPENWEATHER_API_KEY,
                'lang': 'ru'
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(self.geocoding_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()

                        if not data:
                            return None

                        # Ищем лучшее совпадение
                        best_match = self._find_best_match(data, clean_query)
                        if best_match:
                            return best_match

                        # Если не нашли, пробуем без страны
                        if country_hint:
                            params['q'] = clean_query
                            async with session.get(self.geocoding_url, params=params) as response2:
                                if response2.status == 200:
                                    data2 = await response2.json()
                                    return self._find_best_match(data2, clean_query) if data2 else None

                        return None
                    else:
                        return None

        except Exception as e:
            logger.error(f"Ошибка геокодинга: {e}")
            return None

    def _find_best_match(self, results: list, original_query: str) -> Optional[Dict]:
        """Находит лучшее совпадение среди результатов геокодинга"""
        original_lower = original_query.lower()

        for result in results:
            local_names = result.get('local_names', {})

            # Проверяем русское название
            ru_name = local_names.get('ru', '').lower()

            # Проверяем английское название
            en_name = result.get('name', '').lower()

            # Проверяем похожесть
            if (original_lower in ru_name or
                    original_lower in en_name or
                    ru_name in original_lower or
                    en_name in original_lower):
                return self._format_location_result(result)

        # Если не нашли точного совпадения, берем первый результат
        if results:
            return self._format_location_result(results[0])

        return None

    def _clean_location_query(self, query: str) -> str:
        """Очищает запрос локации"""
        query = query.strip()

        # Убираем предлоги в начале
        stop_words_start = ['в', 'на', 'для', 'около', 'возле', 'рядом', 'по', 'у', 'с']
        words = query.split()

        # Если первое слово - предлог, убираем его
        if words and words[0].lower() in stop_words_start:
            words = words[1:]

        # Убираем предлоги в конце
        stop_words_end = ['на', 'в', 'для', 'по', 'у', 'с']
        if words and words[-1].lower() in stop_words_end:
            words = words[:-1]

        if not words:
            return query

        result = ' '.join(words)

        # Возвращаем как есть - геокодинг сам разберется
        return result

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
        # Очищаем запрос от "Беларусь", "Россия" и т.д.
        clean_query = self._clean_location_query(location_query)

        # Убираем названия стран из запроса
        country_words = ['беларусь', 'белоруссия', 'россия', 'украина', 'польша',
                         'литва', 'латвия', 'эстония', 'казахстан']
        query_words = clean_query.split()
        filtered_words = [w for w in query_words if w.lower() not in country_words]
        clean_query = ' '.join(filtered_words) if filtered_words else clean_query

        # Для популярных городов - добавляем страну автоматически
        popular_cities = {
            'лида': 'BY', 'гродно': 'BY', 'минск': 'BY', 'брест': 'BY',
            'гомель': 'BY', 'витебск': 'BY', 'могилев': 'BY',
            'москва': 'RU', 'санкт-петербург': 'RU', 'сочи': 'RU',
            'киев': 'UA', 'львов': 'UA', 'одесса': 'UA',
            'вильнюс': 'LT', 'каунас': 'LT', 'клайпеда': 'LT'
        }

        city_lower = clean_query.lower()
        if city_lower in popular_cities:
            country_hint = popular_cities[city_lower]
            result = await self.resolve_location(clean_query, country_hint)
            if result:
                return result

        # Пробуем страны по порядку
        country_hints = ['BY', 'RU', 'UA', 'LT', 'LV', 'PL', 'EE', 'MD', 'KZ']

        for country in country_hints:
            result = await self.resolve_location(clean_query, country)
            if result:
                logger.info(f"Найдено с подсказкой страны {country}: {result.get('local_name')}")
                return result

        # Пробуем без подсказки страны
        return await self.resolve_location(clean_query)