"""Har bir child bot uchun alohida Dispatcher yig'adi (bot turiga qarab)."""
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from handlers import (admin_core, child_anon, child_downloader, child_edu, child_gemini,
                      child_image, child_movie, child_music, common)
from middlewares import Ctx, ContextMiddleware

TYPE_ROUTERS = {
    "movie": child_movie.get_router,
    "music": child_music.get_router,
    "gemini": child_gemini.get_router,
    "image": child_image.get_router,
    "edu": child_edu.get_router,
    "downloader": child_downloader.get_router,
    "anon": child_anon.get_router,
}


def build_child_dispatcher(ctx: Ctx) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    mw = ContextMiddleware(ctx)
    dp.message.outer_middleware(mw)
    dp.callback_query.outer_middleware(mw)
    # Routerlar har safar yangidan yaratiladi (bitta Router ikki parentga ulanolmaydi)
    dp.include_router(common.get_router())
    dp.include_router(admin_core.get_router())
    dp.include_router(TYPE_ROUTERS[ctx.bot_type]())
    return dp
