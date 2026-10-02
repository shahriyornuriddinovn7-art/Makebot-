"""Maker Bot kirish nuqtasi: python main.py"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
from bot_manager import manager
from database import db
from handlers import admin_core, common, maker, maker_admin
from middlewares import Ctx, ContextMiddleware


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.MAKER_TOKEN:
        sys.exit("❌ MAKER_BOT_TOKEN .env faylida ko'rsatilmagan.")
    if not config.ADMIN_IDS:
        logging.warning("ADMIN_IDS bo'sh — Maker admin paneliga hech kim kira olmaydi.")

    await db.connect()
    bot = Bot(config.MAKER_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.get_me()

    ctx = Ctx(bot_pk=0, bot_type="maker", owner_id=0, admin_ids=set(config.ADMIN_IDS), username=me.username or "")
    dp = Dispatcher(storage=MemoryStorage())
    mw = ContextMiddleware(ctx)
    dp.message.outer_middleware(mw)
    dp.callback_query.outer_middleware(mw)
    dp.include_router(common.get_router())
    dp.include_router(admin_core.get_router())
    dp.include_router(maker_admin.get_router())
    dp.include_router(maker.get_router())

    await manager.start_all()  # saqlangan barcha aktiv child botlarni qayta ishga tushiradi
    logging.info("Maker bot @%s ishga tushdi", me.username)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await manager.stop_all()
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
