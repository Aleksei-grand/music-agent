"""
Генератор уникальных ID (аналог ULID)
"""
import uuid
from datetime import datetime


def generate_id() -> str:
    """Генерация уникального ID"""
    return str(uuid.uuid4()).replace("-", "")


def generate_ulid() -> str:
    """Генерация ULID-подобного ID с временной меткой"""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    random_part = str(uuid.uuid4()).replace("-", "")[:16]
    return f"{timestamp}{random_part}"
