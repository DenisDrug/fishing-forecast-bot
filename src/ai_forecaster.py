import requests
import re
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
import traceback

from .config import config


class AIForecaster:
    """Класс для работы с Google Gemini API"""

    # Промпт остается тот же
    SYSTEM_PROMPT = """Ты — опытный рыбак и ихтиолог. Проанализируй погодные данные и дай прогноз клева рыбы.

    ПРОГНОЗ КЛЕВА:
    - Отличный (5/5): Идеальные условия
    - Хороший (4/5): Благоприятные условия
    - Средний (3/5): Обычные условия
    - Слабый (2/5): Неблагоприятные условия
    - Отсутствует (1/5): Очень плохие условия

    ФАКТОРЫ ВЛИЯНИЯ:
    1. Давление: Стабильное (1013-1017 гПа) = хорошо
    2. Температура: 15-25°C = оптимально
    3. Ветер: Легкий (1-4 м/с) = хорошо
    4. Осадки: Небольшой дождь = часто улучшает

    ФОРМАТ ОТВЕТА:
    Название региона: [Регион]
    📊 ОБЩАЯ ОЦЕНКА: [X]/5 - [Качество]
    🎯 УВЕРЕННОСТЬ: [Y]%
    📅 ПРОГНОЗ ПО ДНЯМ: [далее по дням]
    ⚡ КЛЮЧЕВЫЕ ФАКТОРЫ: [факторы]
    💡 РЕКОМЕНДАЦИИ: [рекомендации]
    🎣 ЛУЧШИЙ ДЕНЬ: [Дата] - [Причина]
    
    Твоя задача:
        1. Оценить вероятность клёва по шкале от 1 до 10.
        2. Объяснить, какие факторы влияют на прогноз.
        3. Дать рекомендации:
           — какую рыбу лучше ловить;
           — на какие снасти и приманки;
           — в каких местах водоёма искать рыбу.
        
        Отвечай кратко, понятно, без лишней воды.
        Если данных недостаточно — укажи, что именно нужно уточнить.
    """

    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"

    def _create_user_prompt(self, region: str, weather_data: List[Dict[str, Any]]) -> str:
        """Создание промпта для Gemini"""
        weather_info = []

        for i, day in enumerate(weather_data, 1):
            date = datetime.fromisoformat(day['date']).strftime('%d.%m.%Y')
            weather_info.append(
                f"День {i} ({date}):\n"
                f"- Температура: {day['temperature']:.1f}°C\n"
                f"- Давление: {day['pressure']} гПа\n"
                f"- Влажность: {day['humidity']}%\n"
                f"- Ветер: {day['wind_speed']:.1f} м/с\n"
                f"- Облачность: {day['cloudiness']}%\n"
                f"- Осадки: {day['precipitation']:.1f} мм\n"
                f"- Описание: {day['description']}\n"
            )

        return (
            f"Регион: {region}\n"
            f"Количество дней: {len(weather_data)}\n"
            f"Текущая дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"ПОГОДНЫЕ ДАННЫЕ:\n{'-' * 40}\n"
            f"{''.join(weather_info)}\n"
            f"{'-' * 40}\n"
            f"Проанализируй и дай прогноз клева."
        )

    def _extract_forecast_quality(self, ai_response: str) -> Tuple[Optional[str], Optional[float]]:
        """Извлечение качества прогноза"""
        try:
            quality_match = re.search(r'ОБЩАЯ ОЦЕНКА:\s*(\d)/5', ai_response, re.IGNORECASE)
            confidence_match = re.search(r'УВЕРЕННОСТЬ:\s*(\d+)%', ai_response, re.IGNORECASE)

            quality_map = {
                '5': 'Отличный',
                '4': 'Хороший',
                '3': 'Средний',
                '2': 'Слабый',
                '1': 'Отсутствует'
            }

            quality = None
            confidence = None

            if quality_match:
                score = quality_match.group(1)
                quality = quality_map.get(score, 'Средний')

            if confidence_match:
                confidence = float(confidence_match.group(1))

            return quality, confidence
        except:
            return None, None

    def get_forecast(self, region: str, weather_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Получение прогноза от Gemini API"""
        try:
            # Формируем полный промпт
            full_prompt = f"{self.SYSTEM_PROMPT}\n\n{self._create_user_prompt(region, weather_data)}"

            # Подготавливаем запрос к Gemini API
            params = {"key": self.api_key}

            payload = {
                "contents": [{
                    "parts": [{"text": full_prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 1500,
                }
            }

            print(f"🤖 Запрашиваем прогноз у Gemini для {region}")

            # Отправляем запрос
            response = requests.post(
                self.api_url,
                params=params,
                json=payload,
                timeout=30
            )

            if response.status_code != 200:
                print(f"❌ Ошибка Gemini API: {response.status_code}")
                return self._get_fallback_forecast(region, weather_data)

            result = response.json()

            # Парсинг ответа Gemini
            if 'candidates' in result and result['candidates']:
                ai_response = result['candidates'][0]['content']['parts'][0]['text']
            else:
                print(f"❌ Неверный формат ответа Gemini")
                return self._get_fallback_forecast(region, weather_data)

            # Извлекаем качество
            quality, confidence = self._extract_forecast_quality(ai_response)

            print(f"✅ Получен прогноз от Gemini. Качество: {quality}")

            return {
                "ai_response": ai_response,
                "quality": quality,
                "confidence": confidence or 85.0
            }

        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка запроса к Gemini API: {e}")
            return self._get_fallback_forecast(region, weather_data)
        except Exception as e:
            print(f"❌ Ошибка при работе с Gemini: {e}")
            traceback.print_exc()
            return self._get_fallback_forecast(region, weather_data)

    def _get_fallback_forecast(self, region: str, weather_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Резервный алгоритм (оставить без изменений)"""
        # Ваш существующий резервный алгоритм
        print(f"⚠️ Используем резервный алгоритм для {region}")
        # ... ваш существующий код ...

ai_forecaster = AIForecaster()