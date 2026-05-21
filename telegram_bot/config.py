"""
Конфигурация бота.
Загружает переменные окружения из .env файла.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL_ID: str = os.environ["TELEGRAM_CHANNEL_ID"]

# Anthropic / Claude
ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-opus-4-7")

# Администраторы бота
_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = [
    int(uid.strip()) for uid in _raw_admins.split(",") if uid.strip().isdigit()
]

# Параметры Claude
CLAUDE_MAX_TOKENS: int = int(os.getenv("CLAUDE_MAX_TOKENS", "4096"))
CLAUDE_SYSTEM_PROMPT: str = """Ты — умный ассистент для управления Telegram-каналом.
Ты умеешь:
- Анализировать контент постов и давать подробный разбор
- Писать ответы на комментарии в стиле канала
- Создавать новые посты на заданную тему
- Улучшать и редактировать существующие тексты
- Оценивать качество и вовлечённость аудитории

Пиши ясно, по-русски, если пользователь пишет по-русски.
Будь конкретен и полезен."""
