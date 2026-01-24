# src/geoip.py
import aiohttp
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class GeoIPService:
    def __init__(self):
        self.ip_api_url = "http://ip-api.com/json/"
        # Кэш для хранения стран пользователей
        self.user_country_cache = {}

    async def get_user_country(self, user_id: int, ip_address: str = None) -> str:
        """Определяет страну пользователя"""
        # Проверяем кэш
        if user_id in self.user_country_cache:
            return self.user_country_cache[user_id]

        # Если есть IP - определяем по нему
        if ip_address:
            country = await self._get_country_by_ip(ip_address)
            if country:
                self.user_country_cache[user_id] = country
                return country

        # По умолчанию для русскоязычных пользователей
        default_country = 'BY'
        self.user_country_cache[user_id] = default_country

        return default_country

    async def _get_country_by_ip(self, ip_address: str) -> Optional[str]:
        """Определяет страну по IP через ip-api.com"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.ip_api_url}{ip_address}?fields=countryCode") as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('countryCode')
        except Exception as e:
            logger.error(f"GeoIP error: {e}")

        return None

    def set_user_country(self, user_id: int, country_code: str):
        """Устанавливает страну пользователя вручную"""
        self.user_country_cache[user_id] = country_code