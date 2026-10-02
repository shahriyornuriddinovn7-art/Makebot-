"""Check Join tugmasi (Maker va child botlar uchun umumiy)."""
from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from middlewares import Ctx
from services.subscription import get_missing


def get_router() -> Router:
    r = Router(name="common")

    @r.callback_query(F.data == "check_sub")
    async def check_sub(c: CallbackQuery, bot: Bot, ctx: Ctx):
        if await get_missing(bot, ctx.bot_pk, c.from_user.id):
            await c.answer("❌ Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
            return
        await c.answer("✅ Obuna tasdiqlandi!")
        try:
            await c.message.delete()
        except Exception:
            pass
        await bot.send_message(c.from_user.id, "✅ Rahmat! Endi botdan foydalanishingiz mumkin. /start ni bosing.")

    return r
  
