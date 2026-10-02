"""Kontekst + foydalanuvchini ro'yxatga olish + majburiy obuna + ban tekshiruvi."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from database import db
from keyboards import inline as kb
from services import subscription


@dataclass
class Ctx:
    """Har bir dispatcherga biriktirilgan bot konteksti."""
    bot_pk: int                # 0 = Maker Bot, aks holda bots.id
    bot_type: str              # 'maker' yoki BOT_TYPES kaliti
    owner_id: int
    admin_ids: set[int] = field(default_factory=set)
    username: str = ""

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


class ContextMiddleware(BaseMiddleware):
    def __init__(self, ctx: Ctx):
        self.ctx = ctx

    async def __call__(self, handler: Callable[[Any, dict], Awaitable[Any]], event: Any, data: dict) -> Any:
        data["ctx"] = self.ctx
        user = data.get("event_from_user")
        if isinstance(event, Message):
            chat = event.chat
        elif isinstance(event, CallbackQuery) and event.message:
            chat = event.message.chat
        else:
            chat = None
        # Faqat shaxsiy chatlar
        if user is None or user.is_bot or chat is None or chat.type != "private":
            return None

        row = await db.touch_user(self.ctx.bot_pk, user)
        is_admin = self.ctx.is_admin(user.id)
        if row["is_banned"] and not is_admin:
            return None

        # Majburiy obuna (adminlar va "check_sub" tugmasi bundan mustasno)
        is_check = isinstance(event, CallbackQuery) and event.data == "check_sub"
        if not is_admin and not is_check:
            missing = await subscription.get_missing(data["bot"], self.ctx.bot_pk, user.id)
            if missing:
                if isinstance(event, CallbackQuery):
                    await event.answer("❗️ Avval kanallarga obuna bo'ling", show_alert=True)
                await data["bot"].send_message(user.id, subscription.JOIN_TEXT,
                                               reply_markup=kb.join_kb(missing))
                return None
        return await handler(event, data)
