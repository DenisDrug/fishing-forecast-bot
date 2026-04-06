# src/morph_analyzer.py
import pymorphy3
from typing import Optional


class MorphAnalyzer:
    def __init__(self):
        self.morph = pymorphy3.MorphAnalyzer()

    def to_nominative(self, word: str) -> str:
        """Преобразует слово в именительный падеж"""
        try:
            parsed = self.morph.parse(word)[0]
            normal_form = parsed.normal_form

            # Если нормальная форма отличается от исходного слова
            if normal_form.lower() != word.lower():
                # Сохраняем оригинальный регистр
                if word[0].isupper():
                    return normal_form.capitalize()
                return normal_form

            return word
        except Exception:
            return word

    def is_city_name(self, word: str) -> bool:
        """Проверяет, может ли слово быть названием города"""
        try:
            parsed = self.morph.parse(word)[0]

            # Города обычно имеют тег 'Geox' (географическое название)
            tags = parsed.tag
            if 'Geox' in str(tags):
                return True

            # Или это существительное
            if 'NOUN' in str(tags):
                return True

            return False
        except Exception:
            return False

    def is_geographical_name(self, word: str) -> bool:
        """Проверяет, является ли слово географическим названием (Geox)"""
        try:
            parsed = self.morph.parse(word)[0]
            tags = parsed.tag
            return 'Geox' in str(tags)
        except Exception:
            return False

    def to_nominative_geo(self, word: str) -> str:
        """Безопасно нормализует топоним, избегая глагольных форм"""
        try:
            parsed = self.morph.parse(word)[0]
            tags = str(parsed.tag)
            normal_form = parsed.normal_form

            if 'VERB' in tags or 'INFN' in tags:
                return word

            if 'NOUN' in tags or 'Geox' in tags:
                if abs(len(normal_form) - len(word)) > 2:
                    return word
                if word and word[0].isupper():
                    return normal_form.capitalize()
                return normal_form

            return word
        except Exception:
            return word
