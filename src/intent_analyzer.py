# src/intent_analyzer.py
import re
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class IntentAnalyzer:
    def __init__(self):
        # Паттерны для определения намерений
        self.patterns = {
            'weather': [
                r'погод[ауе]', r'температур[ау]', r'давлени[ея]', r'ветер',
                r'влажност[ьи]', r'осадк[ио]', r'облачност[ьи]',
                r'солн[еце]', r'дожд[ья]', r'снег', r'туман'
            ],
            'fishing_forecast': [
                r'клев[ау]?', r'клюет', r'ловится', r'рыб[ауы]',
                r'прогноз.*клев', r'клев.*прогноз',
                r'мирн[аой]', r'хищн[аой][к]?', r'поймат[ься]',
                r'будет.*рыба', r'рыба.*будет', r'ловить.*завтра',
                r'как.*клюет', r'что.*по.*рыбе', r'какой.*клев'
            ],
            'location': [
                r'в\s+([А-ЯЁ][а-яё\-]+(?:\s+[А-ЯЁ][а-яё\-]+)*)',  # "в Москве"
                r'на\s+([А-ЯЁ][а-яё\-]+(?:\s+[А-ЯЁ][а-яё\-]+)*)',  # "на Байкале"
                r'для\s+([А-ЯЁ][а-яё\-]+(?:\s+[А-ЯЁ][а-яё\-]+)*)',  # "для Лиды"
                r'([А-ЯЁ][а-яё\-]+(?:\s+[А-ЯЁ][а-яё\-]+)*)\s+район',  # "Лидский район"
            ],
            'time_period': [
                r'сегодня', r'завтра', r'послезавтра',
                r'на\s+ближайшие?\s+(\d+)\s+дн[еяя]',
                r'на\s+(\d+)\s+дн[еяя]',
                r'на\s+недел[юе]', r'на\s+выходные',
                r'в\s+субботу', r'в\s+воскресенье'
            ]
        }

    def analyze(self, text: str) -> Dict:
        """Анализирует запрос пользователя"""
        text_lower = text.lower()

        result = {
            'intent': None,  # 'weather', 'fishing_forecast', 'general_question'
            'location': None,
            'time_period': None,
            'days': 1,
            'is_question': '?' in text_lower
        }

        # Определяем намерение
        if self._contains_any(text_lower, self.patterns['fishing_forecast']):
            result['intent'] = 'fishing_forecast'
        elif self._contains_any(text_lower, self.patterns['weather']):
            result['intent'] = 'weather'

        # Извлекаем локацию
        result['location'] = self._extract_location(text)

        # Извлекаем период времени
        time_info = self._extract_time_period(text_lower)
        result['time_period'] = time_info['period']
        result['days'] = time_info['days']

        # Если намерение не определено, но есть локация - вероятно погода
        if not result['intent'] and result['location']:
            result['intent'] = 'weather'

        # Если намерение все еще не определено - общий вопрос
        if not result['intent']:
            result['intent'] = 'general_question'

        logger.info(f"Анализ запроса '{text}': {result}")
        return result

    def _contains_any(self, text: str, patterns: list) -> bool:
        """Проверяет, содержит ли текст любой из паттернов"""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _extract_location(self, text: str) -> Optional[str]:
        """Извлекает название локации из текста"""
        # Паттерн для названий городов/регионов (слово с заглавной буквы)
        location_patterns = [
            r'в\s+([А-ЯЁ][а-яё\-]+(?:\s+[А-ЯЁ][а-яё\-]+)*)',
            r'на\s+([А-ЯЁ][а-яё\-]+(?:\s+[А-ЯЁ][а-яё\-]+)*)',
            r'для\s+([А-ЯЁ][а-яё\-]+(?:\s+[А-ЯЁ][а-яё\-]+)*)',
            r'([А-ЯЁ][а-яё\-]+(?:\s+[А-ЯЁ][а-яё\-]+)*)\s+район',
        ]

        for pattern in location_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        # Если явного указания нет, ищем просто название города
        # (слово с заглавной буквы, не в начале предложения)
        words = text.split()
        for i, word in enumerate(words):
            if i > 0 and word[0].isupper() and len(word) > 2:
                # Проверяем что это не день недели или месяц
                if word.lower() not in ['сегодня', 'завтра', 'послезавтра',
                                        'понедельник', 'вторник', 'среда',
                                        'четверг', 'пятница', 'суббота', 'воскресенье']:
                    return word

        return None

    def _extract_time_period(self, text: str) -> Dict:
        """Извлекает информацию о периоде времени"""
        result = {'period': 'today', 'days': 1}

        if 'завтра' in text:
            result['period'] = 'tomorrow'
            result['days'] = 1
        elif 'послезавтра' in text:
            result['period'] = 'day_after_tomorrow'
            result['days'] = 2
        elif 'недел' in text:
            result['period'] = 'week'
            result['days'] = 7
        elif 'выходн' in text:
            result['period'] = 'weekend'
            result['days'] = 2

        # Ищем указание количества дней
        days_match = re.search(r'на\s+ближайшие?\s+(\d+)\s+дн[еяя]', text)
        if days_match:
            result['days'] = min(int(days_match.group(1)), 10)  # максимум 10 дней
            result['period'] = f'{result["days"]}_days'

        days_match2 = re.search(r'на\s+(\d+)\s+дн[еяя]', text)
        if days_match2:
            result['days'] = min(int(days_match2.group(1)), 10)
            result['period'] = f'{result["days"]}_days'

        return result