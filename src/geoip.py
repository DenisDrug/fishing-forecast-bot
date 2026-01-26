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
        """Определяет страну пользователя - ПРИНУДИТЕЛЬНО СНГ"""
        # ПРИНУДИТЕЛЬНО возвращаем Беларусь для всех русскоязычных
        return 'BY'  # Или 'RU' в зависимости от целевой аудитории

        # Отключил сложную логику - просто возвращаем BY

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