import re
from datetime import datetime


def validate_region_name(region: str) -> bool:
    """Проверка валидности названия региона"""
    if not region or len(region.strip()) < 2:
        return False

    region = region.strip()

    # Проверка на допустимые символы
    if not re.match(r'^[a-zA-Zа-яА-ЯёЁ0-9\s\-\.\,]+$', region):
        return False

    # Проверка на спам (много повторяющихся символов)
    if re.search(r'(.)\1{10,}', region):
        return False

    return True


def format_timestamp(timestamp: datetime) -> str:
    """Форматирование времени"""
    now = datetime.now()
    delta = now - timestamp

    if delta.days == 0:
        if delta.seconds < 60:
            return "только что"
        elif delta.seconds < 3600:
            minutes = delta.seconds // 60
            return f"{minutes} мин назад"
        else:
            hours = delta.seconds // 3600
            return f"{hours} ч назад"
    elif delta.days == 1:
        return "вчера"
    elif delta.days < 7:
        return f"{delta.days} дн назад"
    else:
        return timestamp.strftime('%d.%m.%Y')