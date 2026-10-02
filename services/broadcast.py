"""Xabar tarqatish (broadcast)."""
import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup

from keyboards.inline import build

log = logging.getLogger(__name__)
_tasks: set[asyncio.Task] = set()


def parse_buttons(text: str) -> InlineKeyboardMarkup:
    """Format: har qator = bir qator tugma. 'Matn - https://url'; bir qatorda bir nechta: ' | ' bilan."""
    rows = []
    for line in text.strip().splitlines():
        row = []
        for part in line.split("|"):
            if " - " not in part:
                raise ValueError(f"Noto'g'ri format: {part.strip()}")
            title, url = part.rsplit(" - ", 1)
            title, url = title.strip(), url.strip()
            if not url.startswith(("http://", "https://", "tg://")) or not title:
                raise ValueError(f"Noto'g'ri havola: {part.strip()}")
            row.append((title, url))
        if row:
            rows.append(row)
    if not rows:
        raise ValueError("Tugma topilmadi")
    return build(rows)


async def _send(bot: Bot, uid: int, mode: str, src_chat: int, src_msg: int, markup) -> bool:
    for _ in range(3):
        try:
            if mode == "fwd":
                await bot.forward_message(uid, src_chat, src_msg)
            else:
                await bot.copy_message(uid, src_chat, src_msg, reply_markup=markup)
            return True
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except TelegramAPIError:
            return False
    return False


async def _run(bot: Bot, admin_id: int, user_ids: list[int], mode: str, src_chat: int, src_msg: int, markup):
    ok = fail = 0
    for uid in user_ids:
        if await _send(bot, uid, mode, src_chat, src_msg, markup):
            ok += 1
        else:
            fail += 1
        await asyncio.sleep(0.05)  # ~20 xabar/soniya (Telegram limiti 30)
    try:
        await bot.send_message(admin_id, f"✅ <b>Xabar yuborish yakunlandi</b>\n\n"
                                         f"📬 Yetkazildi: {ok}\n🚫 Xato/bloklagan: {fail}")
    except TelegramAPIError:
        pass


def start_broadcast(*args) -> None:
    t = asyncio.create_task(_run(*args))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
