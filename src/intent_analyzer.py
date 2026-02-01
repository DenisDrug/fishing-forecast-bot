# src/intent_analyzer.py
import re
from typing import Dict, Tuple, Optional
import logging
from src.morph_analyzer import MorphAnalyzer

logger = logging.getLogger(__name__)


class IntentAnalyzer:
    def __init__(self):
        self.morph = MorphAnalyzer()
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
            ],
            'ai_question': [  # НОВОЕ: паттерны для AI-вопросов
                r'совет[ауы]?', r'подскажи(те)?', r'помоги(те)?', r'расскажи(те)?',
                r'объясни(те)?', r'что.*посоветуешь', r'как.*лучше', r'что.*лучше',
                r'на\s+что.*ловить', r'какую.*наживку', r'какие.*снасти',
                r'техник[ау]', r'способ[ауы]?', r'метод[ауы]?', r'рекомендац',
                r'посоветуй(те)?', r'дай.*совет', r'как\s+ловить', r'как\s+поймать',
                r'нажив[аок]', r'снаст[ьи]', r'приман[аок]', r'удоч[аок]',
                r'крюч[аок]', r'леск[ау]', r'катушк[ауи]', r'воблер[ауы]?',
                r'блесн[ауы]?', r'прикорм[аок]', r'фидер[ауы]?', r'спиннинг[ауы]?',
                r'поплав[аок]'
            ]
        }

        # Ключевые слова для AI-вопросов
        self.ai_keywords = [
            'совет', 'подскажи', 'помоги', 'расскажи', 'объясни',
            'посоветуй', 'рекомендац', 'как лучше', 'что лучше',
            'на что ловить', 'какую наживку', 'какие снасти',
            'техник', 'способ', 'метод', 'дай совет'
        ]

        # Вопросительные слова
        self.question_words = ['как', 'что', 'почему', 'где', 'когда',
                               'зачем', 'какой', 'какая', 'какие', 'чем']

        # Известные города
        self.known_cities = [
            'лида', 'минск', 'москва', 'гомель', 'брест',
            'витебск', 'гродно', 'могилев', 'могилёв',
            'санкт-петербург', 'спб', 'питер'
        ]

    def is_ai_question(self, text: str) -> Tuple[bool, Dict]:
        """Определяет, является ли запрос AI-вопросом и извлекает контекст"""
        text_lower = text.lower().strip()

        result = {
            'is_ai': False,
            'reason': '',
            'location': None,
            'is_question': '?' in text_lower or any(text_lower.startswith(w) for w in self.question_words),
            'has_ai_keyword': False
        }

        # 1. Проверяем явные AI-триггеры (самый высокий приоритет)
        for keyword in self.ai_keywords:
            if keyword in text_lower:
                result['is_ai'] = True
                result['reason'] = f'AI keyword: {keyword}'
                result['has_ai_keyword'] = True
                break

        # 2. Проверяем паттерны AI-вопросов
        if not result['is_ai']:
            if self._contains_any(text_lower, self.patterns['ai_question']):
                result['is_ai'] = True
                result['reason'] = 'AI pattern match'

        # 3. Вопросительные слова в начале
        if not result['is_ai']:
            for question_word in self.question_words:
                if text_lower.startswith(question_word):
                    # Но не "что завтра" или "что сегодня" - это прогноз
                    if not (question_word == 'что' and any(
                            word in text_lower for word in ['завтра', 'сегодня', 'послезавтра'])):
                        result['is_ai'] = True
                        result['reason'] = f'Question word: {question_word}'
                        break

        # 4. Знак вопроса и не одно слово
        if not result['is_ai'] and '?' in text_lower:
            words = text_lower.split()
            if len(words) > 1:
                result['is_ai'] = True
                result['reason'] = 'Question mark with multiple words'

        # Извлекаем город для контекста
        result['location'] = self._extract_location(text)

        # 5. Специальный случай: город + длинный вопрос
        if not result['is_ai'] and result['location']:
            city_in_text = any(city in text_lower for city in self.known_cities)
            if city_in_text and len(text_lower.split()) > 3:
                # Проверяем, не просто ли это "Город завтра"
                if not any(pattern in text_lower for pattern in [' завтра', ' сегодня', ' послезавтра']):
                    result['is_ai'] = True
                    result['reason'] = 'City with detailed question'

        logger.info(f"AI анализ '{text}': {result}")
        return result['is_ai'], result

    def analyze_with_context(self, text: str, user_id: int, user_context: dict = None) -> Dict:
        """Анализирует запрос с учетом контекста пользователя"""
        base_result = self.analyze(text)

        # Добавляем информацию о AI-вопросе
        is_ai, ai_info = self.is_ai_question(text)
        base_result.update({
            'is_ai_question': is_ai,
            'ai_reason': ai_info['reason'],
            'has_ai_keyword': ai_info['has_ai_keyword']
        })

        # Добавляем контекст пользователя
        if user_context:
            base_result['has_context'] = True
            base_result['context_location'] = user_context.get('last_region')
            base_result['context_date'] = user_context.get('last_request_date')

            # Если у пользователя есть контекст и это follow-up вопрос
            if user_context.get('last_region') and self._is_followup_question(text):
                base_result['is_followup'] = True
                base_result['followup_context'] = user_context['last_region']

        return base_result

    def _is_followup_question(self, text: str) -> bool:
        """Определяет, является ли вопрос follow-up"""
        followup_keywords = [
            'река', 'озеро', 'водоем', 'водохранилище', 'пруд', 'затон',
            'насадк', 'приманк', 'наживк', 'прикормк',
            'снаст', 'удочк', 'спининг', 'фидер', 'поплав',
            'щук', 'окун', 'лещ', 'карп', 'плотв', 'карась', 'сом', 'судак',
            'где ловить', 'место', 'совет', 'рекомендац', 'как ловить',
            'время', 'час', 'утро', 'вечер', 'день', 'ночь',
            'глубин', 'течени', 'берег', 'залив', 'плес'
        ]

        text_lower = text.lower()
        return any(keyword in text_lower for keyword in followup_keywords)

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
        # Сначала удаляем общие фразы, которые мешают
        remove_phrases = [
            'на эти дни', 'в эти дни', 'на днях',
            'будет в', 'какой в', 'какая в'
        ]

        clean_text = text.lower()
        for phrase in remove_phrases:
            clean_text = clean_text.replace(phrase, ' ')
        # Инициализируем морфологический анализатор
        try:
            from src.morph_analyzer import MorphAnalyzer
            morph = MorphAnalyzer()
            use_morph = True
        except ImportError:
            use_morph = False

        # Убираем служебные слова
        text_lower = text.lower()
        remove_words = {
            'какая', 'какой', 'какое', 'какие', 'скажи', 'подскажи', 'покажи',
            'расскажи', 'погода', 'погоду', 'погодка', 'погодку', 'будет',
            'есть', 'дай', 'дайте', 'хочу', 'нужно', 'надо', 'можно',
            'посмотри', 'пожалуйста', 'а', 'и', 'или', 'но', 'что', 'как',
            'где', 'когда', 'зачем', 'почему', 'сколько'
        }

        # Слова которые могут быть в конце (на, в, для)
        end_words = {'на', 'в', 'для', 'по', 'у', 'с', 'за', 'из', 'от', 'до'}

        # Разбиваем текст
        words = text.split()
        result_words = []

        for word in words:
            clean_word = word.strip(' ,.!?;:').lower()

            # Пропускаем служебные слова
            if clean_word in remove_words:
                continue

            # Сохраняем оригинал (с заглавной)
            result_words.append(word.strip(' ,.!?;:'))

        if not result_words:
            return None

        # Объединяем
        cleaned_text = ' '.join(result_words)

        # Убираем "на", "в" и т.д. в конце
        last_word = cleaned_text.split()[-1].lower() if cleaned_text.split() else ''
        if last_word in end_words:
            cleaned_text = ' '.join(cleaned_text.split()[:-1])

        # Если осталось одно слово - проверяем что оно с заглавной
        final_words = cleaned_text.split()
        if len(final_words) == 1:
            word = final_words[0]
            if word and word[0].isupper():
                # Нормализуем падеж если есть морфология
                if use_morph:
                    return morph.to_nominative(word)
                return word

        # Ищем паттерн "в [город]"
        match = re.search(r'в\s+([А-ЯЁ][а-яё\-]+)', cleaned_text, re.IGNORECASE)
        if match:
            location = match.group(1)
            if location.lower() not in remove_words:
                # Нормализуем падеж если есть морфология
                if use_morph:
                    return morph.to_nominative(location)
                return location

        # Ищем просто слово с заглавной
        for word in final_words:
            if word and word[0].isupper():
                # Пропускаем если это короткое слово или междометие
                if len(word) <= 2 or word.lower() in ['ах', 'ох', 'эх', 'ух']:
                    continue

                # Нормализуем падеж если есть морфология
                if use_morph:
                    return morph.to_nominative(word)
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


def analyze_with_weather_context(self, text: str, last_weather_data: dict = None) -> dict:
    """Анализирует запрос с учетом последних погодных данных"""
    result = self.analyze(text)

    if last_weather_data:
        result['has_weather_context'] = True
        result['weather_data'] = {
            'location': last_weather_data.get('location'),
            'temperature': last_weather_data.get('temp'),
            'conditions': last_weather_data.get('conditions'),
            'days': last_weather_data.get('days', 1)
        }

    # Определяем, нужна ли погода для ответа
    result['needs_weather_data'] = self._needs_weather_for_response(text)

    return result


def _needs_weather_for_response(self, text: str) -> bool:
    """Определяет, нужны ли погодные данные для ответа"""
    text_lower = text.lower()

    weather_dependent_phrases = [
        'клев', 'клюет', 'ловится', 'прогноз.*рыб',
        'на что ловить', 'какая рыба', 'совет.*погод',
        'в такую погоду', 'при такой температуре',
        'завтра.*рыба', 'сегодня.*рыба'
    ]

    for phrase in weather_dependent_phrases:
        if re.search(phrase, text_lower):
            return True

    return False