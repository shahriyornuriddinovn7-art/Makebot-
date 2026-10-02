"""Kichik yordamchi funksiyalar."""
import html

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup


def h(text) -> str:
    """HTML escape."""
    return html.escape(str(text if text is not None else ""), quote=False)


def chunk_text(text: str, size: int = 4000) -> list[str]:
    """Uzun matnni Telegram limitiga mos bo'laklarga bo'ladi."""
    text = text.strip()
    parts: list[str] = []
    while len(text) > size:
        cut = text.rfind("\n", 0, size)
        if cut < size // 2:
            cut = size
        parts.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        parts.append(text)
    return parts or ["(bo'sh)"]


def mask_key(key: str) -> str:
    return key[:4] + "…" + key[-4:] if len(key) > 10 else "***"


def fmt_duration(sec) -> str:
    try:
        sec = int(sec)
    except (TypeError, ValueError):
        return ""
    return f"{sec // 60}:{sec % 60:02d}"


async def safe_edit(c: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    """Xabarni tahrirlaydi; imkonsiz bo'lsa yangi xabar yuboradi."""
    try:
        await c.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as e:
        if "not modified" in str(e).lower():
            return
        await c.message.answer(text, reply_markup=markup)
