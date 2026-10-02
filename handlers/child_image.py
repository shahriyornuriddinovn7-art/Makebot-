"""AI Logo & Tasvir yaratuvchi bot."""
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from database import db
from filters import NotCommand
from keyboards import inline as kb
from middlewares import Ctx
from services import ai
from services.image import generate_image
from utils import h

MODES = {"logo": "🏷 Logo", "avatar": "👤 Avatar", "image": "🖼 Rasm"}


def mode_kb(current: str):
    return kb.build([[((("✅ " if k == current else "") + v), f"img:mode:{k}") for k, v in MODES.items()]])


def get_router() -> Router:
    r = Router(name="child_image")

    @r.message(CommandStart())
    async def start(m: Message, state: FSMContext, ctx: Ctx):
        await state.clear()
        text = (f"🎨 Salom, <b>{h(m.from_user.full_name)}</b>!\n\nRejimni tanlang va yaratmoqchi bo'lgan narsangizni "
                "<b>matn bilan tasvirlab</b> yuboring (ingliz tilida aniqroq chiqadi).")
        if not await db.get_key(ctx.bot_pk, "image"):
            text += "\n\n⚠️ Modul hali faol emas — bot egasi API kalit ulashi kerak."
        if ctx.is_admin(m.from_user.id):
            text += "\n🛠 Boshqaruv: /admin"
        await m.answer(text, reply_markup=mode_kb("image"))

    @r.callback_query(F.data.startswith("img:mode:"))
    async def set_mode(c: CallbackQuery, state: FSMContext):
        mode = c.data.split(":")[2]
        await state.update_data(mode=mode)
        try:
            await c.message.edit_reply_markup(reply_markup=mode_kb(mode))
        except TelegramBadRequest:
            pass
        await c.answer(f"Rejim: {MODES[mode]}")

    @r.message(StateFilter(None), F.text, NotCommand())
    async def draw(m: Message, state: FSMContext, ctx: Ctx):
        key = await db.get_key(ctx.bot_pk, "image")
        if not key:
            await m.answer("⚠️ Modul hali faol emas. Bot egasi /admin → 🔑 API kalitlar orqali kalit ulashi kerak.")
            return
        mode = (await state.get_data()).get("mode", "image")
        wait = await m.answer("🎨 Chizilmoqda, bir oz kuting...")
        await m.bot.send_chat_action(m.chat.id, "upload_photo")
        try:
            img = await generate_image(key, m.text.strip(), mode)
        except ai.AIError as e:
            await wait.edit_text(f"❌ Xatolik: {h(e)}")
            return
        await m.answer_photo(BufferedInputFile(img, "image.png"), caption=f"✅ {MODES[mode]}")
        await wait.delete()

    return r
