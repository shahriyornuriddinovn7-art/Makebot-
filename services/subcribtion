"""Majburiy obuna (Check Join) tekshiruvi."""
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from database import db

JOIN_TEXT = ("❗️ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling</b>, "
             "so'ng «✅ Tekshirish» tugmasini bosing.")


async def get_missing(bot: Bot, bot_pk: int, user_id: int) -> list[dict]:
    """Foydalanuvchi obuna bo'lmagan kanallar ro'yxati."""
    missing = []
    for ch in await db.list_channels(bot_pk):
        try:
            m = await bot.get_chat_member(ch["chat_id"], user_id)
        except TelegramAPIError:
            continue  # bot kanalda admin emas / kanal o'chgan -> tekshiruvni o'tkazib yuboramiz
        if m.status in ("left", "kicked") or (m.status == "restricted" and getattr(m, "is_member", True) is False):
            missing.append(ch)
    return missing
