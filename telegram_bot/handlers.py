"""
Обработчики команд и сообщений.
"""
from __future__ import annotations

import json
import logging
import pathlib
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

import claude_client as cc
from config import TELEGRAM_CHANNEL_ID, ADMIN_IDS

logger = logging.getLogger(__name__)

# ────────────────────────── Персистентное хранилище ──────────────────────

POSTS_FILE = pathlib.Path(__file__).parent / "posts.json"


def _load_posts() -> dict[int, str]:
    """Загружает посты из файла при старте."""
    if POSTS_FILE.exists():
        try:
            raw = json.loads(POSTS_FILE.read_text(encoding="utf-8"))
            return {int(k): v for k, v in raw.items()}
        except Exception as e:
            logger.warning("Не удалось загрузить posts.json: %s", e)
    return {}


def _save_posts() -> None:
    """Сохраняет посты на диск."""
    try:
        POSTS_FILE.write_text(
            json.dumps(channel_posts, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.error("Не удалось сохранить posts.json: %s", e)


# Загружаем при импорте модуля
channel_posts: dict[int, str] = _load_posts()
logger.info("Загружено постов из файла: %d", len(channel_posts))


# ────────────────────────── Вспомогательные ──────────────────────────────


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def admin_only(func):
    """Декоратор: только для администраторов."""
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user or not is_admin(user.id):
            await update.message.reply_text(
                "⛔ Эта команда доступна только администраторам бота."
            )
            return
        return await func(update, ctx)
    wrapper.__name__ = func.__name__
    return wrapper


async def _send_long(update: Update, text: str):
    """Отправляет длинное сообщение, разбивая на части по 4096 символов."""
    MAX = 4096
    for i in range(0, len(text), MAX):
        await update.message.reply_text(text[i : i + MAX])


# ────────────────────────── Команды ──────────────────────────────────────


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Приветствие и список команд."""
    text = (
        "👋 Привет! Я бот-ассистент для вашего Telegram-канала с поддержкой Claude AI.\n\n"
        "📋 *Доступные команды:*\n\n"
        "🔹 /post `<тема>` — создать пост на тему\n"
        "🔹 /save `<текст>` — сохранить текст поста для анализа\n"
        "🔹 /analyze `<ID>` — анализ поста по ID\n"
        "🔹 /improve `<ID> | <инструкции>` — улучшить пост\n"
        "🔹 /reply `<ID> | <комментарий>` — сгенерировать ответ на комментарий\n"
        "🔹 /publish `<текст>` — опубликовать пост в канале\n"
        "🔹 /summary — анализ последних сохранённых постов\n"
        "🔹 /ask `<вопрос>` — задать вопрос Claude\n"
        "🔹 /posts — список сохранённых постов\n"
        "🔹 /help — эта справка\n\n"
        "💡 *Как добавить пост для анализа:*\n"
        "  • Переслать сообщение из канала сюда\n"
        "  • Или: `/save текст поста`"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, ctx)


@admin_only
async def cmd_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Сохраняет текст поста вручную: /save <текст>"""
    text = " ".join(ctx.args)
    if not text:
        await update.message.reply_text(
            "❌ Укажите текст поста после команды.\n\n"
            "Пример:\n`/save Это текст поста из канала, который хочу проанализировать`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Используем message_id текущего сообщения как ключ
    post_id = update.message.message_id
    channel_posts[post_id] = text
    _save_posts()
    await update.message.reply_text(
        f"✅ Текст сохранён с ID `{post_id}`\n\n"
        f"Используйте:\n"
        f"• `/analyze {post_id}` — анализ\n"
        f"• `/improve {post_id}` — улучшить\n"
        f"• `/improve {post_id} | сделай живее` — улучшить с инструкцией",
        parse_mode=ParseMode.MARKDOWN,
    )


@admin_only
async def cmd_post(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Генерирует пост на заданную тему."""
    raw = " ".join(ctx.args)
    if not raw:
        await update.message.reply_text(
            "❌ Укажите тему. Пример:\n`/post Советы по продуктивности`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Поддержка стиля через «|»
    parts = raw.split("|", 1)
    topic = parts[0].strip()
    style = parts[1].strip() if len(parts) > 1 else ""

    await update.message.reply_text("✍️ Генерирую пост, подождите…")
    try:
        post = cc.create_post(topic, style)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка Claude: {e}")
        return

    # Кнопки для действий с постом
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📤 Опубликовать", callback_data=f"publish|{post[:200]}"),
            InlineKeyboardButton("♻️ Перегенерировать", callback_data=f"regen|{topic}|{style}"),
        ]
    ])
    await update.message.reply_text(
        f"📝 *Сгенерированный пост:*\n\n{post}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


@admin_only
async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Анализирует сохранённый пост по message_id."""
    if not ctx.args:
        await update.message.reply_text(
            "❌ Укажите ID сообщения. Пример:\n`/analyze 42`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        msg_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом.")
        return

    post_text = channel_posts.get(msg_id)
    if not post_text:
        await update.message.reply_text(
            f"❌ Пост #{msg_id} не найден. Перешлите мне сообщение из канала, чтобы сохранить его."
        )
        return

    await update.message.reply_text("🔍 Анализирую пост…")
    try:
        analysis = cc.analyze_post(post_text)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка Claude: {e}")
        return

    await _send_long(update, f"📊 *Анализ поста #{msg_id}:*\n\n{analysis}")


@admin_only
async def cmd_improve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Улучшает пост. Синтаксис: /improve <id> | <инструкции>"""
    raw = " ".join(ctx.args)
    if not raw:
        await update.message.reply_text(
            "❌ Укажите ID и (опционально) инструкции:\n`/improve 42 | Сделай более живым`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    parts = raw.split("|", 1)
    try:
        msg_id = int(parts[0].strip())
    except ValueError:
        await update.message.reply_text("❌ Первый аргумент — числовой ID поста.")
        return

    instructions = parts[1].strip() if len(parts) > 1 else ""
    post_text = channel_posts.get(msg_id)
    if not post_text:
        await update.message.reply_text(f"❌ Пост #{msg_id} не найден.")
        return

    await update.message.reply_text("✏️ Улучшаю пост…")
    try:
        improved = cc.improve_post(post_text, instructions)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка Claude: {e}")
        return

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📤 Опубликовать улучшенный", callback_data=f"publish|{improved[:200]}"),
    ]])
    await update.message.reply_text(
        f"✅ *Улучшенный пост:*\n\n{improved}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


@admin_only
async def cmd_reply(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Генерирует ответ на комментарий. Синтаксис: /reply <id> | <текст комментария>"""
    raw = " ".join(ctx.args)
    parts = raw.split("|", 1)
    if len(parts) < 2:
        await update.message.reply_text(
            "❌ Синтаксис:\n`/reply <ID поста> | <текст комментария>`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        msg_id = int(parts[0].strip())
    except ValueError:
        await update.message.reply_text("❌ Первый аргумент — числовой ID поста.")
        return

    comment = parts[1].strip()
    post_text = channel_posts.get(msg_id, "(пост не найден, отвечаю на комментарий без контекста)")

    await update.message.reply_text("💬 Генерирую ответ…")
    try:
        reply = cc.generate_reply(post_text, comment)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка Claude: {e}")
        return

    await update.message.reply_text(f"💬 *Предлагаемый ответ:*\n\n{reply}", parse_mode=ParseMode.MARKDOWN)


@admin_only
async def cmd_publish(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Публикует текст напрямую в канал."""
    text = " ".join(ctx.args)
    if not text:
        await update.message.reply_text(
            "❌ Укажите текст поста. Пример:\n`/publish Привет, канал!`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        sent = await ctx.bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=text)
        channel_posts[sent.message_id] = text
        await update.message.reply_text(
            f"✅ Пост опубликован в канале!\nID сообщения: `{sent.message_id}`",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка публикации: {e}")


@admin_only
async def cmd_summary(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Сводный анализ всех сохранённых постов."""
    if not channel_posts:
        await update.message.reply_text(
            "❌ Нет сохранённых постов. Перешлите сообщения из канала."
        )
        return

    await update.message.reply_text(f"📊 Анализирую {len(channel_posts)} постов…")
    try:
        summary = cc.summarize_posts(list(channel_posts.values()))
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка Claude: {e}")
        return

    await _send_long(update, f"📈 *Сводный анализ канала:*\n\n{summary}")


@admin_only
async def cmd_ask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Произвольный вопрос Claude."""
    question = " ".join(ctx.args)
    if not question:
        await update.message.reply_text("❌ Укажите вопрос после команды.")
        return

    await update.message.reply_text("🤔 Думаю…")
    try:
        answer = cc.answer_question(question)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка Claude: {e}")
        return

    await _send_long(update, answer)


@admin_only
async def cmd_posts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Список сохранённых постов."""
    if not channel_posts:
        await update.message.reply_text("📭 Нет сохранённых постов.")
        return

    lines = []
    for mid, text in list(channel_posts.items())[-20:]:  # последние 20
        preview = text[:80].replace("\n", " ")
        lines.append(f"🔹 ID `{mid}`: {preview}…")

    await update.message.reply_text(
        f"📋 *Сохранённые посты ({len(channel_posts)}):*\n\n" + "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


# ────────────────────────── Автообработка сообщений ─────────────────────


async def handle_channel_post(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Автоматически сохраняет новые посты из канала."""
    msg = update.channel_post
    if msg and msg.text:
        channel_posts[msg.message_id] = msg.text
        _save_posts()
        logger.info("Сохранён пост из канала #%d (%d символов)", msg.message_id, len(msg.text))


def _is_forwarded(msg) -> bool:
    """Проверяет все возможные признаки пересланного сообщения."""
    return bool(
        getattr(msg, "forward_origin", None)       # новый API (PTB v20+)
        or getattr(msg, "forward_from_chat", None)  # старый API: из канала/группы
        or getattr(msg, "forward_from", None)       # старый API: от пользователя
        or getattr(msg, "forward_sender_name", None)# скрытый отправитель
        or getattr(msg, "forward_date", None)       # дата оригинала (устаревший, но рабочий)
    )


async def handle_forwarded(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Сохраняет любое пересланное сообщение."""
    msg = update.message
    if not msg:
        return

    if not msg.text:
        await msg.reply_text(
            "⚠️ Пересланное сообщение не содержит текста.\n"
            "Для анализа поста с фото используйте `/save` и вставьте текст вручную."
        )
        return

    # Пробуем достать оригинальный message_id из forward_origin
    fwd = getattr(msg, "forward_origin", None)
    src_id = getattr(fwd, "message_id", None) or msg.message_id

    channel_posts[src_id] = msg.text
    _save_posts()
    logger.info("Сохранён пересланный пост: src_id=%d, len=%d", src_id, len(msg.text))

    await msg.reply_text(
        f"✅ Пост сохранён с ID `{src_id}`\n\n"
        f"Используйте:\n"
        f"• `/analyze {src_id}` — анализ\n"
        f"• `/improve {src_id}` — улучшить\n"
        f"• `/improve {src_id} | сделай живее` — улучшить с инструкцией",
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения: пересланные или свободный ввод."""
    msg = update.message
    if not msg or not msg.text:
        return

    user = msg.from_user
    if not user:
        return

    # Пересланные сообщения — сохраняем (проверяем все возможные атрибуты)
    if _is_forwarded(msg):
        await handle_forwarded(update, ctx)
        return

    # Обычные сообщения — только для админов
    if not is_admin(user.id):
        return

    # Свободный текст от админа → спрашиваем Claude
    await update.message.reply_text("🤔 Думаю…")
    try:
        answer = cc.answer_question(msg.text)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка Claude: {e}")
        return
    await _send_long(update, answer)


# ────────────────────────── Callback кнопки ──────────────────────────────


async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на inline-кнопки."""
    query = update.callback_query
    await query.answer()

    data = query.data or ""

    if data.startswith("publish|"):
        text = data[8:]
        try:
            sent = await ctx.bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=text)
            channel_posts[sent.message_id] = text
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(
                f"✅ Пост опубликован! ID: `{sent.message_id}`",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            await query.message.reply_text(f"❌ Ошибка публикации: {e}")

    elif data.startswith("regen|"):
        parts = data.split("|", 2)
        topic = parts[1] if len(parts) > 1 else ""
        style = parts[2] if len(parts) > 2 else ""
        await query.message.reply_text("✍️ Перегенерирую пост…")
        try:
            post = cc.create_post(topic, style)
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("📤 Опубликовать", callback_data=f"publish|{post[:200]}"),
                InlineKeyboardButton("♻️ Ещё раз", callback_data=f"regen|{topic}|{style}"),
            ]])
            await query.message.reply_text(
                f"📝 *Новый вариант:*\n\n{post}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        except Exception as e:
            await query.message.reply_text(f"❌ Ошибка Claude: {e}")
