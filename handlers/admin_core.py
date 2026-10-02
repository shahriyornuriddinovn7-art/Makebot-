"""Maker Bot va barcha child botlar uchun UMUMIY admin panel:
statistika, majburiy obuna, API kalitlar, broadcast."""
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import config
from database import db
from filters import IsAdmin, NotCommand
from keyboards import inline as kb
from middlewares import Ctx
from services import ai
from services.broadcast import parse_buttons, start_broadcast
from states import AdminStates
from utils import h, mask_key, safe_edit


def get_router() -> Router:
    r = Router(name="admin_core")
    r.message.filter(IsAdmin())
    r.callback_query.filter(IsAdmin())

    # ------------------------------------------------------------ menu
    @r.message(Command("admin"))
    async def cmd_admin(m: Message, state: FSMContext, ctx: Ctx):
        await state.clear()
        await m.answer("🛠 <b>Admin panel</b>", reply_markup=kb.admin_menu(ctx.bot_type))

    @r.callback_query(F.data == "adm:menu")
    async def cb_menu(c: CallbackQuery, state: FSMContext, ctx: Ctx):
        await state.clear()
        await safe_edit(c, "🛠 <b>Admin panel</b>", kb.admin_menu(ctx.bot_type))
        await c.answer()

    # ------------------------------------------------------ statistika
    @r.callback_query(F.data == "adm:stats")
    async def cb_stats(c: CallbackQuery, ctx: Ctx):
        users = await db.count_users(ctx.bot_pk)
        today = await db.count_new_users_today(ctx.bot_pk)
        text = f"📊 <b>Statistika</b>\n\n👥 Foydalanuvchilar: <b>{users}</b>\n🆕 Bugun qo'shilgan: <b>{today}</b>\n"
        if ctx.bot_type == "maker":
            by_type = await db.bots_by_type()
            total = sum(by_type.values())
            text += f"\n🤖 Yaratilgan botlar: <b>{total}</b>\n"
            for key, title in config.BOT_TYPES.items():
                text += f"   • {title}: {by_type.get(key, 0)}\n"
        elif ctx.bot_type == "movie":
            text += f"🎬 Kinolar: <b>{await db.count_movies(ctx.bot_pk)}</b>\n"
        await safe_edit(c, text, kb.back_admin())
        await c.answer()

    # ------------------------------------------------ majburiy obuna
    async def render_channels(c: CallbackQuery, ctx: Ctx):
        chans = await db.list_channels(ctx.bot_pk)
        lines = [f"{i}. {h(ch['title'])} — {('@' + ch['username']) if ch['username'] else 'private'}"
                 for i, ch in enumerate(chans, 1)]
        text = "📢 <b>Majburiy obuna kanallari</b>\n\n" + ("\n".join(lines) if lines else "Hozircha kanal yo'q.")
        await safe_edit(c, text, kb.channels_kb(chans))

    @r.callback_query(F.data == "adm:ch")
    async def cb_channels(c: CallbackQuery, state: FSMContext, ctx: Ctx):
        await state.clear()
        await render_channels(c, ctx)
        await c.answer()

    @r.callback_query(F.data == "adm:cha")
    async def cb_ch_add(c: CallbackQuery, state: FSMContext):
        await state.set_state(AdminStates.add_channel)
        await safe_edit(c, "📢 Kanal <b>@username</b> yoki <b>ID</b> (-100...) yuboring.\n\n"
                           "⚠️ Bot avval o'sha kanalga <b>admin</b> qilib qo'shilgan bo'lishi shart.",
                        kb.cancel_to("adm:ch"))
        await c.answer()

    @r.message(AdminStates.add_channel, F.text, NotCommand())
    async def ch_add(m: Message, state: FSMContext, bot: Bot, ctx: Ctx):
        raw = m.text.strip()
        if raw.startswith("https://t.me/"):
            raw = "@" + raw.rstrip("/").split("/")[-1]
        target = int(raw) if raw.lstrip("-").isdigit() else (raw if raw.startswith("@") else "@" + raw)
        try:
            chat = await bot.get_chat(target)
            me = await bot.get_chat_member(chat.id, bot.id)
        except TelegramAPIError:
            await m.answer("❌ Kanal topilmadi yoki bot u yerda yo'q. Botni kanalga admin qiling va qayta urinib ko'ring.",
                           reply_markup=kb.cancel_to("adm:ch"))
            return
        if chat.type == "private" or me.status not in ("administrator", "creator"):
            await m.answer("❌ Bot bu kanalda <b>admin</b> emas. Avval admin qiling.", reply_markup=kb.cancel_to("adm:ch"))
            return
        invite = None
        if not chat.username:
            try:
                invite = await bot.export_chat_invite_link(chat.id)
            except TelegramAPIError:
                pass
        await db.add_channel(ctx.bot_pk, chat.id, chat.username, chat.title or str(chat.id), invite)
        await state.clear()
        await m.answer(f"✅ <b>{h(chat.title)}</b> majburiy obunaga qo'shildi.", reply_markup=kb.back_admin())

    @r.callback_query(F.data.startswith("adm:chd:"))
    async def cb_ch_del(c: CallbackQuery, ctx: Ctx):
        await db.del_channel(ctx.bot_pk, int(c.data.split(":")[2]))
        await c.answer("🗑 O'chirildi")
        await render_channels(c, ctx)

    @r.callback_query(F.data == "adm:cht")
    async def cb_ch_test(c: CallbackQuery, bot: Bot, ctx: Ctx):
        chans = await db.list_channels(ctx.bot_pk)
        if not chans:
            await c.answer("Kanal yo'q", show_alert=True)
            return
        lines = []
        for ch in chans:
            try:
                me = await bot.get_chat_member(ch["chat_id"], bot.id)
                ok = me.status in ("administrator", "creator")
            except TelegramAPIError:
                ok = False
            lines.append(f"{'✅' if ok else '⚠️ bot admin emas —'} {h(ch['title'])}")
        await safe_edit(c, "🔍 <b>Tekshiruv natijasi</b>\n\n" + "\n".join(lines), kb.channels_kb(chans))
        await c.answer()

    # ------------------------------------------------------ API kalitlar
    async def render_keys(c_or_m, ctx: Ctx):
        provs = config.API_PROVIDERS.get(ctx.bot_type, [])
        stored = {p: await db.get_key(ctx.bot_pk, p) for p, _ in provs}
        lines = [f"{'✅' if stored[p] else '❌'} <b>{n}</b>: " + (f"<code>{mask_key(stored[p])}</code>" if stored[p] else "ulanmagan")
                 for p, n in provs]
        text = "🔑 <b>API kalitlar</b>\n\n" + "\n".join(lines) + "\n\nKalit ulanishi bilan modul <b>darhol</b> ishga tushadi."
        markup = kb.keys_kb(provs, stored)
        if isinstance(c_or_m, CallbackQuery):
            await safe_edit(c_or_m, text, markup)
        else:
            await c_or_m.answer(text, reply_markup=markup)

    @r.callback_query(F.data == "adm:keys")
    async def cb_keys(c: CallbackQuery, state: FSMContext, ctx: Ctx):
        await state.clear()
        await render_keys(c, ctx)
        await c.answer()

    @r.callback_query(F.data.startswith("adm:key:"))
    async def cb_key_set(c: CallbackQuery, state: FSMContext, ctx: Ctx):
        provider = c.data.split(":")[2]
        if provider not in dict(config.API_PROVIDERS.get(ctx.bot_type, [])):
            await c.answer("Noma'lum provider", show_alert=True)
            return
        await state.set_state(AdminStates.set_key)
        await state.update_data(provider=provider)
        await safe_edit(c, f"🔑 <b>{provider}</b> API kalitini yuboring.\n(Xavfsizlik uchun xabar o'chiriladi.)",
                        kb.cancel_to("adm:keys"))
        await c.answer()

    @r.callback_query(F.data.startswith("adm:keyd:"))
    async def cb_key_del(c: CallbackQuery, ctx: Ctx):
        await db.del_key(ctx.bot_pk, c.data.split(":")[2])
        await c.answer("🗑 Kalit o'chirildi")
        await render_keys(c, ctx)

    @r.message(AdminStates.set_key, F.text, NotCommand())
    async def key_input(m: Message, state: FSMContext, ctx: Ctx):
        provider = (await state.get_data()).get("provider")
        key = m.text.strip()
        try:
            await m.delete()
        except TelegramAPIError:
            pass
        wait = await m.answer("⏳ Kalit tekshirilmoqda...")
        ok, err = True, ""
        if provider == "gemini":
            ok, err = await ai.validate_gemini(key)
        elif provider == "openai" or (provider == "image" and key.startswith("sk-")):
            ok, err = await ai.validate_openai(key)
        elif len(key) < 8:
            ok, err = False, "Kalit juda qisqa"
        if not ok:
            await wait.edit_text(f"❌ Kalit ishlamadi: {h(err)}\n\nBoshqa kalit yuboring yoki bekor qiling.",
                                 reply_markup=kb.cancel_to("adm:keys"))
            return
        await db.set_key(ctx.bot_pk, provider, key)
        await state.clear()
        await wait.edit_text("✅ Kalit ulandi — modul <b>darhol faollashdi</b>!", reply_markup=kb.build(
            [[("🔑 API kalitlar", "adm:keys")], [("⬅️ Admin panel", "adm:menu")]]))

    # ------------------------------------------------------ broadcast
    @r.callback_query(F.data == "adm:bc")
    async def cb_bc(c: CallbackQuery, state: FSMContext):
        await state.clear()
        await safe_edit(c, "✉️ <b>Xabar yuborish</b>\n\nRejimni tanlang:", kb.bc_mode_kb())
        await c.answer()

    @r.callback_query(F.data.startswith("adm:bcm:"))
    async def cb_bc_mode(c: CallbackQuery, state: FSMContext):
        await state.set_state(AdminStates.bc_wait_msg)
        await state.update_data(mode=c.data.split(":")[2])
        await safe_edit(c, "📝 Yuboriladigan xabarni jo'nating (matn, rasm, video, fayl — istalgan turdagi).",
                        kb.cancel_to("adm:menu"))
        await c.answer()

    @r.message(AdminStates.bc_wait_msg, NotCommand())
    async def bc_msg(m: Message, state: FSMContext, ctx: Ctx):
        data = await state.get_data()
        await state.update_data(src_chat=m.chat.id, src_msg=m.message_id)
        if data["mode"] == "fwd":
            await state.set_state(AdminStates.bc_confirm)
            await ask_confirm(m, state, ctx)
        else:
            await state.set_state(AdminStates.bc_wait_buttons)
            await m.answer("🔘 Inline tugma qo'shasizmi?\n\nFormat:\n<code>Matn - https://link.uz</code>\n"
                           "Bir qatorda bir nechta: <code>A - https://a.uz | B - https://b.uz</code>\n\n"
                           "Tugma kerak bo'lmasa /skip yuboring.")

    @r.message(AdminStates.bc_wait_buttons, F.text)
    async def bc_buttons(m: Message, state: FSMContext, ctx: Ctx):
        if m.text.strip() != "/skip":
            try:
                parse_buttons(m.text)
            except ValueError as e:
                await m.answer(f"❌ {h(e)}\nQayta yuboring yoki /skip.")
                return
            await state.update_data(buttons=m.text)
        await state.set_state(AdminStates.bc_confirm)
        await ask_confirm(m, state, ctx)

    async def ask_confirm(m: Message, state: FSMContext, ctx: Ctx):
        data = await state.get_data()
        markup = parse_buttons(data["buttons"]) if data.get("buttons") else None
        mode = data["mode"]
        if mode == "copy":  # ko'rib chiqish uchun adminga nusxa
            try:
                await m.bot.copy_message(m.chat.id, data["src_chat"], data["src_msg"], reply_markup=markup)
            except TelegramAPIError:
                pass
        total = len(await db.user_ids(ctx.bot_pk))
        await m.answer(f"👆 Shu xabar <b>{total}</b> ta foydalanuvchiga "
                       f"({'forward' if mode == 'fwd' else 'oddiy'} rejimda) yuborilsinmi?",
                       reply_markup=kb.bc_confirm_kb())

    @r.callback_query(F.data == "adm:bcgo", AdminStates.bc_confirm)
    async def cb_bc_go(c: CallbackQuery, state: FSMContext, bot: Bot, ctx: Ctx):
        data = await state.get_data()
        await state.clear()
        markup = parse_buttons(data["buttons"]) if data.get("buttons") else None
        users = await db.user_ids(ctx.bot_pk)
        start_broadcast(bot, c.from_user.id, users, data["mode"], data["src_chat"], data["src_msg"], markup)
        await safe_edit(c, f"🚀 Yuborish boshlandi ({len(users)} ta). Tugagach hisobot keladi.", kb.back_admin())
        await c.answer()

    return r
