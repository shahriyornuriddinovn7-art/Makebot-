"""Gemini AI Chatbot. Kalit /admin orqali ulanishi bilan darhol ishlaydi."""
from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database import db
from filters import NotCommand
from middlewares import Ctx
from services import ai
from utils import chunk_text, h

SYSTEM = ("Sen professional AI yordamchisan. Foydalanuvchi qaysi tilda yozsa, shu tilda "
          "aniq, tushunarli va chuqur javob ber.")


def get_router() -> Router:
    r = Router(name="child_gemini")

    @r.message(CommandStart())
    async def start(m: Message, state: FSMContext, ctx: Ctx):
        await state.clear()
        text = f"🤖 Salom, <b>{h(m.from_user.full_name)}</b>! Menga istalgan savolingizni yozing.\n\n/clear — suhbatni tozalash"
        if not await db.get_key(ctx.bot_pk, "gemini"):
            text += "\n\n⚠️ AI hali faol emas — bot egasi API kalit ulashi kerak."
        if ctx.is_admin(m.from_user.id):
            text += "\n🛠 Boshqaruv: /admin"
        await m.answer(text)

    @r.message(Command("clear"))
    async def clear(m: Message, state: FSMContext):
        await state.clear()
        await m.answer("🧹 Suhbat tozalandi.")

    @r.message(StateFilter(None), F.text, NotCommand())
    async def chat(m: Message, state: FSMContext, ctx: Ctx):
        key = await db.get_key(ctx.bot_pk, "gemini")
        if not key:
            await m.answer(ai.NO_KEY_TEXT)
            return
        hist = (await state.get_data()).get("hist", [])
        hist.append(("user", m.text))
        await m.bot.send_chat_action(m.chat.id, "typing")
        try:
            answer = await ai.gemini_chat(key, hist[-14:], SYSTEM)
        except ai.AIError as e:
            await m.answer(f"⚠️ AI xatosi: {h(e)}")
            return
        hist.append(("model", answer))
        await state.update_data(hist=hist[-14:])
        for part in chunk_text(answer):
            await m.answer(part, parse_mode=None)

    return r
