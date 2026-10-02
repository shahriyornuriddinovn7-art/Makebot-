"""Multitenancy BotManager: ko'plab child botni bitta jarayonda, async rejimda yurgizadi."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramUnauthorizedError

from database import db
from handlers.child_builder import build_child_dispatcher
from middlewares import Ctx

log = logging.getLogger(__name__)


@dataclass
class Running:
    bot: Bot
    dp: Dispatcher
    task: asyncio.Task


class BotManager:
    def __init__(self) -> None:
        self.running: dict[int, Running] = {}

    def is_running(self, pk: int) -> bool:
        return pk in self.running

    async def start_bot(self, pk: int) -> bool:
        if pk in self.running:
            return True
        row = await db.get_bot(pk)
        if not row or row["status"] != "active":
            return False
        bot = Bot(token=row["token"], default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        try:
            me = await bot.get_me()
        except TelegramUnauthorizedError:
            log.warning("Bot #%s tokeni yaroqsiz — nofaol qilindi", pk)
            await db.set_bot_status(pk, "inactive")
            await bot.session.close()
            return False
        except Exception as e:
            log.error("Bot #%s ishga tushmadi: %s", pk, e)
            await bot.session.close()
            return False
        await db.update_bot_meta(pk, me.username or "", me.full_name)
        ctx = Ctx(bot_pk=pk, bot_type=row["bot_type"], owner_id=row["owner_id"],
                  admin_ids={row["owner_id"]}, username=me.username or "")
        dp = build_child_dispatcher(ctx)
        task = asyncio.create_task(self._poll(pk, bot, dp), name=f"child-bot-{pk}")
        self.running[pk] = Running(bot, dp, task)
        log.info("Bot #%s (@%s, %s) ishga tushdi", pk, me.username, row["bot_type"])
        return True

    async def _poll(self, pk: int, bot: Bot, dp: Dispatcher) -> None:
        try:
            await dp.start_polling(bot, handle_signals=False, close_bot_session=False,
                                   allowed_updates=dp.resolve_used_update_types())
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Bot #%s polling to'xtadi", pk)

    async def stop_bot(self, pk: int) -> None:
        rb = self.running.pop(pk, None)
        if not rb:
            return
        with contextlib.suppress(Exception):
            await asyncio.wait_for(rb.dp.stop_polling(), timeout=15)
        rb.task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await rb.task
        with contextlib.suppress(Exception):
            await rb.bot.session.close()
        log.info("Bot #%s to'xtatildi", pk)

    async def restart_bot(self, pk: int) -> bool:
        await self.stop_bot(pk)
        return await self.start_bot(pk)

    async def start_all(self) -> None:
        for row in await db.active_bots():
            await self.start_bot(row["id"])
            await asyncio.sleep(0.2)

    async def stop_all(self) -> None:
        await asyncio.gather(*(self.stop_bot(pk) for pk in list(self.running)), return_exceptions=True)


manager = BotManager()
