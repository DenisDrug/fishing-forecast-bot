import requests
import re
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
import traceback

from .config import config


class AIForecaster:
    """Класс для работы с Groq API"""

    SYSTEM_PROMPT = """Ты — опытный рыбак и ихтиолог. Проанализируй погодные данные и дай прогноз клева рыбы.

ПРОГНОЗ КЛЕВА:
- Отличный (5/5): Идеальные условия, рыба очень активна
- Хороший (4/5): Благоприятные условия, хорошие шансы на улов
- Средний (3/5): Обычные условия, рыба умеренно активна
- Слабый (2/5): Неблагоприятные условия, рыба пассивна
- Отсутствует (1/5): Очень плохие условия, клева почти нет

ФАКТОРЫ ВЛИЯНИЯ:
1. Давление: Стабильное (1013-1017 гПа) = хорошо, резкие изменения = плохо
2. Температура: 15-25°C = оптимально, резкие перепады = плохо
3. Ветер: Легкий (1-4 м/с) = хорошо, сильный (>6 м/с) = плохо
4. Осадки: Небольшой дождь = часто улучшает, ливень = плохо
5. Облачность: Переменная = хорошо

ФОРМАТ ОТВЕТА:
Название региона: [Регион]

📊 ОБЩАЯ ОЦЕНКА: [X]/5 - [Качество клева]
🎯 УВЕРЕННОСТЬ: [Y]%

📅 ПРОГНОЗ ПО ДНЯМ:
1. [Дата]: [Оценка]/5 - [Краткое обоснование]
2. [Дата]: [Оценка]/5 - [Краткое обоснование]
...

⚡ КЛЮЧЕВЫЕ ФАКТОРЫ:
• [Фактор 1]: [Влияние]
• [Фактор 2]: [Влияние]
...

💡 РЕКОМЕНДАЦИИ:
• [Рекомендация 1]
• [Рекомендация 2]

🎣 ЛУЧШИЙ ДЕНЬ ДЛЯ РЫБАЛКИ: [Дата] - [Причина]

Будь конкретным, используй данные из прогноза, объясняй причинно-следственные связи."""

    def __init__(self):
        self.api_key = config.GROQ_API_KEY
        self.api_url = config.GROQ_API_URL
        self.model = "mixtral-8x7b-32768"  # Бесплатная модель Groq

    def _create_user_prompt(self, region: str, weather_data: List[Dict[str, Any]]) -> str:
        """Создание промпта для ИИ на основе погодных данных"""
        weather_info = []

        for i, day in enumerate(weather_data, 1):
            date = datetime.fromisoformat(day['date']).strftime('%d.%m.%Y')
            weather_info.append(
                f"День {i} ({date}):\n"
                f"- Температура: {day['temperature']:.1f}°C (ощущается как {day['feels_like']:.1f}°C)\n"
                f"- Давление: {day['pressure']} гПа\n"
                f"- Влажность: {day['humidity']}%\n"
                f"- Ветер: {day['wind_speed']:.1f} м/с, направление: {day['wind_direction']}°\n"
                f"- Облачность: {day['cloudiness']}%\n"
                f"- Осадки: {day['precipitation']:.1f} мм\n"
                f"- Описание: {day['description']}\n"
            )

        user_prompt = (
            f"Регион: {region}\n"
            f"Количество дней: {len(weather_data)}\n"
            f"Текущая дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"ПОГОДНЫЕ ДАННЫЕ:\n{'-' * 40}\n"
            f"{''.join(weather_info)}\n"
            f"{'-' * 40}\n"
            f"Проанализируй эти данные и дай прогноз клева."
        )

        return user_prompt

    def _extract_forecast_quality(self, ai_response: str) -> Tuple[Optional[str], Optional[float]]:
        """Извлечение качества клева и уверенности из ответа ИИ"""
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

        except Exception as e:
            print(f"❌ Ошибка извлечения качества прогноза: {e}")
            return None, None

    def get_forecast(self, region: str, weather_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Получение прогноза клева от Groq API"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": self._create_user_prompt(region, weather_data)}
                ],
                "temperature": 0.3,
                "max_tokens": 1500
            }

            print(f"🤖 Запрашиваем прогноз у Groq для {region}")

            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=80
            )

            if response.status_code != 200:
                print(f"❌ Ошибка Groq API: {response.status_code}")
                print(f"Ответ: {response.text[:200]}")
                return self._get_fallback_forecast(region, weather_data)

            result = response.json()
            ai_response = result['choices'][0]['message']['content']

            quality, confidence = self._extract_forecast_quality(ai_response)

            print(f"✅ Получен прогноз от Groq. Качество: {quality}, Уверенность: {confidence}%")

            return {
                "ai_response": ai_response,
                "quality": quality,
                "confidence": confidence or 85.0
            }

        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка запроса к Groq API: {e}")
            return self._get_fallback_forecast(region, weather_data)
        except Exception as e:
            print(f"❌ Неожиданная ошибка при работе с Groq: {e}")
            traceback.print_exc()
            return self._get_fallback_forecast(region, weather_data)

    def _get_fallback_forecast(self, region: str, weather_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Резервный алгоритм на случай недоступности Groq API"""
        print(f"⚠️ Используем резервный алгоритм для {region}")

        scores = []

        for day in weather_data:
            score = 3.0

            if 1013 <= day['pressure'] <= 1017:
                score += 0.5
            elif day['pressure'] < 1000:
                score -= 1.0
            elif day['pressure'] > 1020:
                score -= 0.5

            if 15 <= day['temperature'] <= 25:
                score += 0.5
            elif day['temperature'] < 5 or day['temperature'] > 30:
                score -= 1.0

            if day['wind_speed'] > 6:
                score -= 0.5

            if 0.1 <= day['precipitation'] <= 5:
                score += 0.3
            elif day['precipitation'] > 10:
                score -= 0.5

            scores.append(max(1.0, min(5.0, score)))

        avg_score = sum(scores) / len(scores)

        if avg_score >= 4.5:
            quality = "Отличный"
        elif avg_score >= 3.5:
            quality = "Хороший"
        elif avg_score >= 2.5:
            quality = "Средний"
        elif avg_score >= 1.5:
            quality = "Слабый"
        else:
            quality = "Отсутствует"

        response_lines = [
            f"Название региона: {region}",
            "",
            f"📊 ОБЩАЯ ОЦЕНКА: {avg_score:.1f}/5 - {quality}",
            "🎯 УВЕРЕННОСТЬ: 70%",
            "",
            "📅 ПРОГНОЗ ПО ДНЯМ:"
        ]

        for i, (day, score) in enumerate(zip(weather_data, scores), 1):
            date = datetime.fromisoformat(day['date']).strftime('%d.%m')
            response_lines.append(
                f"{i}. {date}: {score:.1f}/5 - "
                f"Темп: {day['temperature']:.1f}°C, Давление: {day['pressure']} гПа"
            )

        response_lines.extend([
            "",
            "⚡ КЛЮЧЕВЫЕ ФАКТОРЫ:",
            "• Использован резервный алгоритм (Groq API недоступен)",
            "• Учитывались: давление, температура, ветер, осадки",
            "",
            "💡 РЕКОМЕНДАЦИИ:",
            "• Система Groq API временно недоступна",
            "• Прогноз рассчитан по упрощенному алгоритму",
            "",
            "⚠️ ВНИМАНИЕ: Это автоматический прогноз без анализа ИИ"
        ])

        ai_response = "\n".join(response_lines)

        return {
            "ai_response": ai_response,
            "quality": quality,
            "confidence": 70.0
        }


# Глобальный экземпляр ИИ-прогнозировщика
ai_forecaster = AIForecaster()