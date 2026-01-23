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

        system_prompt = """Ты полезный ассистент для рыболовов. Отвечай на вопросы о рыбалке, 
        давай советы по снастям, технике ловли, выбору места. Будь дружелюбным и полезным."""

        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            "temperature": 0.7,
            "max_tokens": 500
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