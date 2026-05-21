"""
Клиент для работы с Claude API.
Поддерживает: анализ, генерацию постов, ответы, редактирование.
"""
from __future__ import annotations

import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_MAX_TOKENS, CLAUDE_SYSTEM_PROMPT


client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _ask(prompt: str, system: str | None = None) -> str:
    """Базовый вызов Claude."""
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=CLAUDE_MAX_TOKENS,
        system=system or CLAUDE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ─────────────────────────── Публичные функции ───────────────────────────


def analyze_post(post_text: str) -> str:
    """Анализирует пост канала: тема, тон, сильные/слабые стороны, советы."""
    prompt = f"""Проанализируй следующий пост из Telegram-канала и дай подробный разбор:

--- ПОСТ ---
{post_text}
--- КОНЕЦ ПОСТА ---

Структура анализа:
1. 📌 Тема и ключевые идеи
2. 🎯 Целевая аудитория
3. ✅ Сильные стороны
4. ⚠️ Слабые стороны / что улучшить
5. 💡 Конкретные рекомендации
6. 📊 Оценка вовлечённости (1–10) с обоснованием"""
    return _ask(prompt)


def generate_reply(post_text: str, comment_text: str) -> str:
    """Генерирует ответ на комментарий под постом."""
    prompt = f"""Тебе нужно ответить от имени автора канала на комментарий.

--- ОРИГИНАЛЬНЫЙ ПОСТ ---
{post_text}
--- КОНЕЦ ПОСТА ---

--- КОММЕНТАРИЙ ---
{comment_text}
--- КОНЕЦ КОММЕНТАРИЯ ---

Напиши вежливый, информативный и дружелюбный ответ.
Ответ должен быть кратким (2–4 предложения), по существу.
Не начинай с «Здравствуйте» или похожих шаблонных фраз."""
    return _ask(prompt)


def create_post(topic: str, style_hint: str = "") -> str:
    """Создаёт новый пост для канала по заданной теме."""
    style_part = f"\nСтиль / дополнительные указания: {style_hint}" if style_hint else ""
    prompt = f"""Напиши пост для Telegram-канала на тему: «{topic}»{style_part}

Требования:
- Длина: 150–400 слов
- Живой, вовлекающий стиль
- Структура с абзацами, используй эмодзи умеренно
- Конец — призыв к действию или вопрос к читателям
- НЕ используй хэштеги"""
    return _ask(prompt)


def improve_post(post_text: str, instructions: str = "") -> str:
    """Улучшает существующий пост согласно инструкциям."""
    inst_part = f"\nИнструкции по улучшению: {instructions}" if instructions else ""
    prompt = f"""Улучши следующий пост для Telegram-канала.{inst_part}

--- ИСХОДНЫЙ ПОСТ ---
{post_text}
--- КОНЕЦ ПОСТА ---

Верни только улучшенный текст, без пояснений."""
    return _ask(prompt)


def summarize_posts(posts: list[str]) -> str:
    """Делает сводный анализ нескольких постов."""
    numbered = "\n\n".join(f"[{i+1}] {p}" for i, p in enumerate(posts))
    prompt = f"""Проанализируй подборку постов из Telegram-канала и дай общий отчёт.

--- ПОСТЫ ---
{numbered}
--- КОНЕЦ ---

Структура отчёта:
1. 🗂 Общая тематика канала
2. 📈 Качество контента (оценка 1–10)
3. 🔁 Повторяющиеся паттерны и приёмы
4. 📉 Проблемы и пробелы
5. 🚀 Топ-3 рекомендации для роста"""
    return _ask(prompt)


def answer_question(question: str, context: str = "") -> str:
    """Отвечает на произвольный вопрос администратора."""
    ctx_part = f"\nКонтекст:\n{context}\n" if context else ""
    return _ask(f"{ctx_part}\nВопрос: {question}")
