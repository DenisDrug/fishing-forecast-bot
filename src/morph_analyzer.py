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
            parses = self.morph.parse(word)
            if not parses:
                return word

            geo_parse = None
            for p in parses:
                if 'Geox' in str(p.tag):
                    geo_parse = p
                    break

            if not geo_parse:
                return word

            normal_form = geo_parse.normal_form
            if abs(len(normal_form) - len(word)) > 2:
                return word
            if word and word[0].isupper():
                return normal_form.capitalize()
            return normal_form
        except Exception:
            return word

    def normalize_toponym(self, word: str) -> str:
        """Нормализует топоним через парадигму (nomn), без костылей"""
        try:
            parses = self.morph.parse(word)
            if not parses:
                return word

            best_form = None
            best_score = -1

            for p in parses:
                tags = str(p.tag)
                if 'VERB' in tags or 'INFN' in tags:
                    continue
                if 'NOUN' not in tags and 'Geox' not in tags:
                    continue

                inflected = p.inflect({'nomn'})
                if not inflected:
                    continue
                candidate = inflected.word

                score = 0
                if 'Geox' in tags:
                    score += 5
                if abs(len(candidate) - len(word)) <= 2:
                    score += 2
                if candidate and word and candidate[0] == word[0].lower():
                    score += 1

                if score > best_score:
                    best_score = score
                    best_form = candidate

            if not best_form:
                return word

            if word and word[0].isupper():
                return best_form.capitalize()
            return best_form
        except Exception:
            return word
