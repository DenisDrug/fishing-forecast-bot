# src/ai_chat_handler.py
import logging
import aiohttp
from .config import config

logger = logging.getLogger(__name__)


async def handle_ai_chat(question: str) -> str:
    """
    Обрабатывает общие вопросы пользователя через Groq API
    """
    if not config.GROQ_API_KEY:
        return "ИИ-функция временно недоступна."

    try:
        headers = {
            "Authorization": f"Bearer {config.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        SYSTEM_PROMPT = """Ты — эксперт-рыболов и гид в Telegram-боте "Прогноз клева рыбы".

        ВАЖНАЯ ИНФОРМАЦИЯ О БОТЕ:
        1. Бот имеет доступ к реальным погодным данным через OpenWeather API
        2. Бот может получать прогноз погоды на несколько дней
        3. Бот может анализировать условия для рыбалки на основе реальных данных
        4. Текущая дата: {current_date}

        ТВОИ ВОЗМОЖНОСТИ:
        • Давать советы по рыбалке, снастям, наживкам
        • Объяснять влияние погоды на клев рыбы
        • Рекомендовать технику ловли для разных условий
        • Отвечать на вопросы о рыбалке

        ЧТО НЕЛЬЗЯ ГОВОРИТЬ:
        ❌ "У меня нет доступа к погоде" - У БОТА ЕСТЬ доступ!
        ❌ "Я не могу дать прогноз" - Бот может через другие модули
        ❌ "Спросите где-то еще" - перенаправляй к функциям бота

        КАК ОТВЕЧАТЬ НА ЗАПРОСЫ ПОГОДЫ:
        Если пользователь спрашивает про погоду или прогноз клева:
        1. Скажи, что бот может получить реальный прогноз
        2. Предложи написать просто название города
        3. Объясни, какие факторы влияют на клев

        ПРИМЕРЫ ОТВЕТОВ:
        Вопрос: "Какая погода в Москве?"
        Ответ: "Бот может получить актуальный прогноз погоды для Москвы. Просто напишите 'Москва' для получения данных на сегодня или 'Москва 3 дня' для трехдневного прогноза."

        Вопрос: "Какой клев в Витебске?"
        Ответ: "Для прогноза клева нужны реальные погодные данные. Напишите 'Витебск' и бот проанализирует условия для рыбалки с помощью ИИ на основе актуальной погоды."

        ТЕКУЩИЙ СЕЗОН: {current_season}

        ОТВЕЧАЙ КОНКРЕТНО И ПО ДЕЛУ. Не придумывай данные, если не уверен."""

        payload = {
            "model": "openai/gpt-oss-120b",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question}
            ],
            "temperature": 0.7,
            "max_tokens": 1200
        }

        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    answer = data["choices"][0]["message"]["content"].strip()
                    return answer
                else:
                    logger.error(f"Groq API error: {response.status}")
                    return "Извините, не могу ответить сейчас. Попробуйте позже."

    except Exception as e:
        logger.error(f"AI chat error: {e}")
        return "Произошла ошибка при обработке вопроса."


async def handle_ai_json_chat(prompt: str) -> str:
    """
    Обрабатывает запросы, где нужен строго JSON-ответ
    """
    if not config.GROQ_API_KEY:
        return '{"overall_score":5,"peaceful_score":5,"predator_score":5,"comment":"ИИ недоступен, средний клев."}'

    try:
        headers = {
            "Authorization": f"Bearer {config.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        system_prompt = (
            "Ты — эксперт-рыболов. Отвечай строго валидным JSON без лишнего текста, "
            "без пояснений и без форматирования."
        )

        payload = {
            "model": "openai/gpt-oss-120b",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 400
        }

        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    answer = data["choices"][0]["message"]["content"].strip()
                    return answer

                logger.error(f"Groq API error: {response.status}")
                return '{"overall_score":5,"peaceful_score":5,"predator_score":5,"comment":"Ответ недоступен."}'

    except Exception as e:
        logger.error(f"AI JSON chat error: {e}")
        return '{"overall_score":5,"peaceful_score":5,"predator_score":5,"comment":"Ошибка обработки ответа."}'

def get_current_season() -> str:
    """Определяет текущий сезон"""
    from datetime import datetime
    month = datetime.now().month

    if month in [12, 1, 2]:
        return "ЗИМА (декабрь-февраль): подледная рыбалка"
    elif month in [3, 4, 5]:
        return "ВЕСНА (март-май): нерестовый период"
    elif month in [6, 7, 8]:
        return "ЛЕТО (июнь-август): теплая вода"
    else:
        return "ОСЕНЬ (сентябрь-ноябрь): предзимний жор"
