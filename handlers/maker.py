"""Maker Bot: foydalanuvchi tomoni (bot yaratish, botlarim, AI yordamchi)."""
import re

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import config
from bot_manager import manager
from database import db
from filters import NotCommand
from keyboards import inline as kb
from middlewares import Ctx
from services import ai
from states import MakerStates
from utils import chunk_text, h, safe_edit

TOKEN_RE = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{30,}$")
HELP = ("ℹ️ <b>Yordam</b>\n\n1. @BotFather da yangi bot yarating va tokenni oling.\n"
        "2. «➕ Bot yaratish» → bot turini tanlang → tokenni yuboring.\n"
        "3. Bot bir zumda ishga tushadi. Uni boshqarish uchun o'z botingizda <code>/admin</code> yuboring.")


async def _check_token(token: str):
    tb = Bot(token)
    try:
        return await tb.get_me()
    finally:
        await tb.session.close()


def get_router() -> Router:
    r = Router(name="maker")

    @r.message(CommandStart())
    async def start(m: Message, state: FSMContext, ctx: Ctx):
        await state.clear()
        await m.answer(f"👋 Salom, <b>{h(m.from_user.full_name)}</b>!\n\n"
                       "Men <b>Bot Yaratuvchi</b>man. Token yuboring — men sizga tayyor botni bir zumda ishga tushiraman:\n"
                       "🎬 Kino • 🎵 Musiqa • 🤖 AI • 🎨 Logo • 🎓 Ta'lim • 📥 Downloader • 🕶 Anonim chat",
                       reply_markup=kb.maker_menu(ctx.is_admin(m.from_user.id)))

    @r.callback_query(F.data == "mk:menu")
    async def menu(c: CallbackQuery, state: FSMContext, ctx: Ctx):
        await state.clear()
        await safe_edit(c, "🏠 <b>Asosiy menyu</b>", kb.maker_menu(ctx.is_admin(c.from_user.id)))
        await c.answer()

    @r.callback_query(F.data == "mk:help")
    async def help_(c: CallbackQuery):
        await safe_edit(c, HELP, kb.build([[("⬅️ Orqaga", "mk:menu")]]))
        await c.answer()

    # --------------------------------------------------------- yaratish
    @r.callback_query(F.data == "mk:create")
    async def create(c: CallbackQuery, state: FSMContext):
        await state.clear()
        await safe_edit(c, "🤖 <b>Qaysi turdagi bot yaratamiz?</b>", kb.bot_types_kb())
        await c.answer()

    @r.callback_query(F.data.startswith("mk:type:"))
    async def pick_type(c: CallbackQuery, state: FSMContext):
        btype = c.data.split(":")[2]
        if btype not in config.BOT_TYPES:
            await c.answer("Noma'lum tur", show_alert=True)
            return
        await state.set_state(MakerStates.token)
        await state.update_data(btype=btype)
        await safe_edit(c, f"{config.BOT_TYPES[btype]}\n\n🔑 @BotFather dan olingan <b>bot tokenini</b> yuboring:",
                        kb.cancel_to("mk:create"))
        await c.answer()

    @r.message(MakerStates.token, F.text, NotCommand())
    async def got_token(m: Message, state: FSMContext, ctx: Ctx):
        token = m.text.strip()
        try:
            await m.delete()  # token chatda qolmasin
        except TelegramAPIError:
            pass
        if not TOKEN_RE.match(token):
            await m.answer("❌ Token formati noto'g'ri. Qayta yuboring.", reply_markup=kb.cancel_to("mk:create"))
            return
        uid = m.from_user.id
        if await db.get_bot_by_token(token):
            await m.answer("❌ Bu token allaqachon ulangan.", reply_markup=kb.cancel_to("mk:create"))
            return
        if not ctx.is_admin(uid) and await db.count_bots(uid) >= config.MAX_BOTS_PER_USER:
            await m.answer(f"❌ Siz maksimal {config.MAX_BOTS_PER_USER} ta bot yarata olasiz.")
            return
        try:
            me = await _check_token(token)
        except Exception:
            await m.answer("❌ Token yaroqsiz (Telegram rad etdi). Tekshirib qayta yuboring.",
                           reply_markup=kb.cancel_to("mk:create"))
            return
        btype = (await state.get_data())["btype"]
        pk = await db.add_bot(token, me.id, me.username, me.full_name, btype, uid)
        await state.clear()
        ok = await manager.start_bot(pk)
        if not ok:
            await m.answer("⚠️ Bot saqlandi, lekin ishga tushmadi. «🤖 Botlarim» orqali qayta urinib ko'ring.")
            return
        extra = {"gemini": "\n🔑 AI ishlashi uchun /admin → API kalitlar bo'limida Gemini kalitini ulang.",
                 "image": "\n🔑 Ishlashi uchun /admin → API kalitlar bo'limida kalitni ulang.",
                 "movie": "\n🎬 /admin → «Post kanali» va «Kino qo'shish» bo'limlarini sozlang.",
                 "edu": "\n🔑 AI funksiyalari uchun /admin → Gemini kalitini ulang."}.get(btype, "")
        await m.answer(f"✅ <b>Bot ishga tushdi!</b>\n\n{config.BOT_TYPES[btype]}\n👉 https://t.me/{me.username}\n\n"
                       f"Boshqaruv: botingizda <code>/admin</code> yuboring.{extra}",
                       reply_markup=kb.maker_menu(ctx.is_admin(uid)))

    # ----------------------------------------------------------- botlarim
    async def render_my(c: CallbackQuery):
        bots = await db.list_bots(owner_id=c.from_user.id, limit=20)
        if not bots:
            await safe_edit(c, "📭 Sizda hali bot yo'q.", kb.build([[("➕ Bot yaratish", "mk:create")],
                                                                    [("⬅️ Orqaga", "mk:menu")]]))
            return
        rows = [[(f"{kb.STATUS_ICON.get(b['status'], '•')} @{b['username']} • {config.BOT_TYPES[b['bot_type']].split(' ', 1)[1]}",
                  f"mk:b:{b['id']}")] for b in bots]
        rows.append([("⬅️ Orqaga", "mk:menu")])
        await safe_edit(c, "🤖 <b>Sizning botlaringiz</b>", kb.build(rows))

    @r.callback_query(F.data == "mk:my")
    async def my_bots(c: CallbackQuery):
        await render_my(c)
        await c.answer()

    async def own_bot(c: CallbackQuery, pk: int):
        b = await db.get_bot(pk)
        if not b or b["owner_id"] != c.from_user.id:
            await c.answer("Topilmadi", show_alert=True)
            return None
        return b

    async def render_bot(c: CallbackQuery, b: dict):
        text = (f"{kb.STATUS_ICON[b['status']]} <b>@{h(b['username'])}</b>\n{config.BOT_TYPES[b['bot_type']]}\n"
                f"Holat: <b>{b['status']}</b>\n👥 Foydalanuvchilar: {await db.count_users(b['id'])}")
        rows = []
        if b["status"] == "active":
            rows.append([("⏸ To'xtatish", f"mk:bt:{b['id']}")])
        elif b["status"] == "inactive":
            rows.append([("▶️ Yoqish", f"mk:bt:{b['id']}")])
        else:
            text += "\n\n⛔ Bot administrator tomonidan bloklangan."
        rows.append([("🗑 O'chirish", f"mk:bd:{b['id']}")])
        rows.append([("⬅️ Orqaga", "mk:my")])
        await safe_edit(c, text, kb.build(rows))

    @r.callback_query(F.data.startswith("mk:b:"))
    async def bot_detail(c: CallbackQuery):
        b = await own_bot(c, int(c.data.split(":")[2]))
        if b:
            await render_bot(c, b)
            await c.answer()

    @r.callback_query(F.data.startswith("mk:bt:"))
    async def bot_toggle(c: CallbackQuery):
        b = await own_bot(c, int(c.data.split(":")[2]))
        if not b or b["status"] == "blocked":
            return
        if b["status"] == "active":
            await db.set_bot_status(b["id"], "inactive")
            await manager.stop_bot(b["id"])
        else:
            await db.set_bot_status(b["id"], "active")
            if not await manager.start_bot(b["id"]):
                await c.answer("⚠️ Ishga tushmadi (token yaroqsizmi?)", show_alert=True)
        await render_bot(c, await db.get_bot(b["id"]))
        await c.answer()

    @r.callback_query(F.data.startswith("mk:bd:"))
    async def bot_del_ask(c: CallbackQuery):
        b = await own_bot(c, int(c.data.split(":")[2]))
        if b:
            await safe_edit(c, f"⚠️ <b>@{h(b['username'])}</b> va barcha ma'lumotlari (token, kinolar, foydalanuvchilar) "
                               "butunlay o'chiriladi. Davom etasizmi?",
                            kb.build([[("✅ Ha, o'chirish", f"mk:bdy:{b['id']}"), ("❌ Yo'q", f"mk:b:{b['id']}")]]))
            await c.answer()

    @r.callback_query(F.data.startswith("mk:bdy:"))
    async def bot_del(c: CallbackQuery):
        b = await own_bot(c, int(c.data.split(":")[2]))
        if b:
            await manager.stop_bot(b["id"])
            await db.delete_bot(b["id"])
            await c.answer("🗑 O'chirildi")
            await render_my(c)

    # -------------------------------------------------------- AI yordamchi
    @r.callback_query(F.data == "mk:ai")
    async def ai_start(c: CallbackQuery, state: FSMContext):
        if not (await db.get_key(0, "gemini") or await db.get_key(0, "openai")):
            await c.answer("⚠️ AI hali ulanmagan (admin API kalit qo'shishi kerak).", show_alert=True)
            return
        await state.set_state(MakerStates.ai_chat)
        await state.update_data(hist=[])
        await safe_edit(c, "🧠 <b>AI yordamchi</b> yoqildi. Savolingizni yozing.\nChiqish: /stop",
                        kb.build([[("⬅️ Chiqish", "mk:menu")]]))
        await c.answer()

    @r.message(Command("stop"), StateFilter(MakerStates.ai_chat))
    async def ai_stop(m: Message, state: FSMContext, ctx: Ctx):
        await state.clear()
        await m.answer("🏠 Asosiy menyu", reply_markup=kb.maker_menu(ctx.is_admin(m.from_user.id)))

    @r.message(MakerStates.ai_chat, F.text, NotCommand())
    async def ai_msg(m: Message, state: FSMContext):
        hist = (await state.get_data()).get("hist", [])
        hist.append(("user", m.text))
        await m.bot.send_chat_action(m.chat.id, "typing")
        try:
            answer = await ai.chat_with_keys(0, hist[-12:], system="Sen foydalanuvchi tilida aniq javob beradigan AI yordamchisan.")
        except ai.AIError as e:
            await m.answer(f"⚠️ {h(e)}")
            return
        hist.append(("model", answer))
        await state.update_data(hist=hist[-12:])
        for part in chunk_text(answer):
            await m.answer(part, parse_mode=None)

    return r
