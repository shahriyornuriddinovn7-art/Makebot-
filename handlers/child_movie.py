"""Kodli Kino Bot: kino qo'shish, kanalga avto-post, kod bo'yicha yuborish."""
import re

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import db
from filters import IsAdmin, NotCommand
from keyboards import inline as kb
from middlewares import Ctx
from states import MovieStates
from utils import h, safe_edit

# (kalit, so'rov matni)
FIELDS = [
    ("title", "🎬 Kino <b>nomini</b> kiriting:"),
    ("year", "📅 <b>Yilini</b> kiriting (masalan: 2024):"),
    ("quality", "🖥 <b>Sifatini</b> kiriting (masalan: 1080p):"),
    ("country", "🗽 <b>Davlatini</b> kiriting:"),
    ("language", "🇺🇿 <b>Tilini</b> kiriting (masalan: O'zbek tilida):"),
    ("genres", "🍿 <b>Janrlarini</b> vergul bilan kiriting (masalan: Jangari, Drama):"),
    ("code", "🔢 <b>Kino kodini</b> kiriting (yoki <code>auto</code> — avtomatik raqam):"),
]


def hashtags(genres: str) -> str:
    tags = []
    for g in re.split(r"[,\n#]+", genres):
        g = re.sub(r"\W+", "_", g.strip(), flags=re.UNICODE).strip("_")
        if g:
            tags.append("#" + g)
    return " ".join(tags)


def post_text(mv: dict, bot_username: str) -> str:
    """Kanalga tashlanadigan post — aynan talab qilingan struktura."""
    return (f"🎬 {h(mv['title'])}\n"
            f"📅 Yili: {h(mv['year'])}\n"
            f"🖥 Sifati: {h(mv['quality'])}\n"
            f"🗽 Davlati: {h(mv['country'])}\n"
            f"🇺🇿 Tili: {h(mv['language'])}\n"
            f"🍿 Janri: {h(hashtags(mv['genres']))}\n"
            f"✅ Filmni ko'rish uchun << {h(mv['code'])} ⬆️ kodini @{bot_username} ga yuboring 🍿")


def caption(mv: dict) -> str:
    return (f"🎬 <b>{h(mv['title'])}</b>\n📅 Yili: {h(mv['year'])}\n🖥 Sifati: {h(mv['quality'])}\n"
            f"🗽 Davlati: {h(mv['country'])}\n🇺🇿 Tili: {h(mv['language'])}\n🍿 Janri: {h(hashtags(mv['genres']))}")


def get_router() -> Router:
    r = Router(name="child_movie")

    async def send_movie(bot: Bot, chat_id: int, mv: dict, ctx: Ctx):
        try:
            if mv["file_type"] == "document":
                await bot.send_document(chat_id, mv["file_id"], caption=caption(mv))
            else:
                await bot.send_video(chat_id, mv["file_id"], caption=caption(mv))
            await db.inc_views(mv["id"])
        except TelegramAPIError:
            await bot.send_message(chat_id, "❌ Kinoni yuborishda xatolik. Keyinroq urinib ko'ring.")

    # --------------------------------------------------------- foydalanuvchi
    @r.message(CommandStart())
    async def start(m: Message, command: CommandObject, state: FSMContext, bot: Bot, ctx: Ctx):
        await state.clear()
        if command.args and command.args.startswith("m_"):
            mv = await db.get_movie_by_code(ctx.bot_pk, command.args[2:])
            if mv:
                await send_movie(bot, m.chat.id, mv, ctx)
                return
        text = f"🎬 Salom, <b>{h(m.from_user.full_name)}</b>!\n\nKino <b>kodini</b> yuboring — men uni darhol jo'nataman. 🍿"
        if ctx.is_admin(m.from_user.id):
            text += "\n\n🛠 Boshqaruv: /admin"
        await m.answer(text)

    @r.message(StateFilter(None), F.text, NotCommand())
    async def by_code(m: Message, bot: Bot, ctx: Ctx):
        text = m.text.strip()
        mv = await db.get_movie_by_code(ctx.bot_pk, text)
        if mv:
            await send_movie(bot, m.chat.id, mv, ctx)
            return
        found = await db.search_movies(ctx.bot_pk, text)
        if found:
            rows = [[(f"🎬 {x['title']} • {x['code']}", f"mv:{x['id']}")] for x in found]
            await m.answer("🔎 Kod topilmadi, lekin shunga o'xshash kinolar bor:", reply_markup=kb.build(rows))
        else:
            await m.answer("❌ Bunday kodli kino topilmadi. Kodni tekshirib qayta yuboring.")

    @r.callback_query(F.data.startswith("mv:"))
    async def pick(c: CallbackQuery, bot: Bot, ctx: Ctx):
        mv = await db.get_movie(ctx.bot_pk, int(c.data.split(":")[1]))
        await c.answer()
        if mv:
            await send_movie(bot, c.from_user.id, mv, ctx)

    # -------------------------------------------------------------- admin
    @r.callback_query(F.data == "adm:movie_add", IsAdmin())
    async def add_start(c: CallbackQuery, state: FSMContext):
        await state.set_state(MovieStates.video)
        await safe_edit(c, "🎞 Kino <b>videosini</b> yuboring (video yoki fayl sifatida):", kb.cancel_to("adm:menu"))
        await c.answer()

    @r.message(MovieStates.video, F.video | F.document)
    async def got_video(m: Message, state: FSMContext):
        obj, ftype = (m.video, "video") if m.video else (m.document, "document")
        await state.update_data(file_id=obj.file_id, file_type=ftype, step=0)
        await state.set_state(MovieStates.fields)
        await m.answer(FIELDS[0][1])

    @r.message(MovieStates.video)
    async def bad_video(m: Message):
        await m.answer("❌ Iltimos, video yoki video-fayl yuboring.")

    @r.message(MovieStates.fields, F.text, NotCommand())
    async def got_field(m: Message, state: FSMContext, bot: Bot, ctx: Ctx):
        data = await state.get_data()
        step = data["step"]
        key = FIELDS[step][0]
        value = m.text.strip()
        if key == "code":
            if value.lower() == "auto":
                value = await db.next_code(ctx.bot_pk)
            elif not re.fullmatch(r"[\w-]{1,30}", value):
                await m.answer("❌ Kod faqat harf, raqam yoki '-' dan iborat bo'lishi kerak. Qayta kiriting:")
                return
            if await db.code_exists(ctx.bot_pk, value):
                await m.answer("❌ Bu kod band. Boshqa kod kiriting (yoki <code>auto</code>):")
                return
        data[key] = value
        step += 1
        if step < len(FIELDS):
            data["step"] = step
            await state.set_data(data)
            await m.answer(FIELDS[step][1])
            return

        data.pop("step", None)
        await state.clear()
        mid = await db.add_movie(ctx.bot_pk, data)
        mv = await db.get_movie(ctx.bot_pk, mid)
        report = f"✅ Kino saqlandi! Kod: <code>{h(mv['code'])}</code>"
        # ---- KANALGA AVTO-POST
        chan = await db.get_setting(ctx.bot_pk, "post_channel")
        if chan:
            try:
                await bot.send_message(int(chan), post_text(mv, ctx.username), reply_markup=kb.build(
                    [[("🤖 Kinoni botda ko'rish", f"https://t.me/{ctx.username}?start=m_{mv['code']}")]]))
                report += "\n📣 Kanalga e'lon joylandi."
            except TelegramAPIError as e:
                report += f"\n⚠️ Kanalga joylab bo'lmadi: {h(e.message if hasattr(e, 'message') else e)}"
        else:
            report += "\nℹ️ Post kanali ulanmagan (Admin → Post kanali)."
        await m.answer(report, reply_markup=kb.build([[("🎬 Yana qo'shish", "adm:movie_add")],
                                                      [("⬅️ Admin panel", "adm:menu")]]))

    # ---- post kanalini biriktirish / o'zgartirish
    @r.callback_query(F.data == "adm:movie_ch", IsAdmin())
    async def ch_menu(c: CallbackQuery, state: FSMContext, ctx: Ctx):
        await state.clear()
        title = await db.get_setting(ctx.bot_pk, "post_channel_title")
        text = "📣 <b>Kino post kanali</b>\n\nJoriy kanal: " + (f"<b>{h(title)}</b>" if title else "ulanmagan")
        rows = [[("✏️ Kanalni biriktirish / o'zgartirish", "adm:movie_ch_set")]]
        if title:
            rows.append([("🗑 Kanalni uzish", "adm:movie_ch_off")])
        rows.append([("⬅️ Admin panel", "adm:menu")])
        await safe_edit(c, text, kb.build(rows))
        await c.answer()

    @r.callback_query(F.data == "adm:movie_ch_set", IsAdmin())
    async def ch_set(c: CallbackQuery, state: FSMContext):
        await state.set_state(MovieStates.post_channel)
        await safe_edit(c, "📣 Kanal <b>@username</b> yoki <b>ID</b> yuboring.\nBot kanalda <b>admin</b> (post yozish huquqi bilan) bo'lishi shart.",
                        kb.cancel_to("adm:movie_ch"))
        await c.answer()

    @r.message(MovieStates.post_channel, F.text, NotCommand())
    async def ch_got(m: Message, state: FSMContext, bot: Bot, ctx: Ctx):
        raw = m.text.strip()
        if raw.startswith("https://t.me/"):
            raw = "@" + raw.rstrip("/").split("/")[-1]
        target = int(raw) if raw.lstrip("-").isdigit() else (raw if raw.startswith("@") else "@" + raw)
        try:
            chat = await bot.get_chat(target)
            me = await bot.get_chat_member(chat.id, bot.id)
        except TelegramAPIError:
            await m.answer("❌ Kanal topilmadi yoki bot u yerda yo'q.", reply_markup=kb.cancel_to("adm:movie_ch"))
            return
        if me.status not in ("administrator", "creator") or getattr(me, "can_post_messages", True) is False:
            await m.answer("❌ Botga kanalda admin va «xabar yozish» huquqini bering.", reply_markup=kb.cancel_to("adm:movie_ch"))
            return
        await db.set_setting(ctx.bot_pk, "post_channel", str(chat.id))
        await db.set_setting(ctx.bot_pk, "post_channel_title", chat.title or str(chat.id))
        await state.clear()
        await m.answer(f"✅ Post kanali: <b>{h(chat.title)}</b>", reply_markup=kb.back_admin())

    @r.callback_query(F.data == "adm:movie_ch_off", IsAdmin())
    async def ch_off(c: CallbackQuery, state: FSMContext, ctx: Ctx):
        await db.del_setting(ctx.bot_pk, "post_channel")
        await db.del_setting(ctx.bot_pk, "post_channel_title")
        await c.answer("Kanal uzildi")
        await ch_menu(c, state, ctx)

    # ---- kinolar ro'yxati / o'chirish
    @r.callback_query(F.data == "adm:movie_list", IsAdmin())
    async def movie_list(c: CallbackQuery, ctx: Ctx):
        movies = await db.list_movies(ctx.bot_pk, 15)
        rows = [[(f"🗑 {x['code']} • {x['title']} ({x['views']}👁)", f"adm:movie_del:{x['id']}")] for x in movies]
        rows.append([("⬅️ Admin panel", "adm:menu")])
        await safe_edit(c, "🗂 <b>So'nggi kinolar</b> (o'chirish uchun bosing):" if movies else "🗂 Kinolar yo'q.", kb.build(rows))
        await c.answer()

    @r.callback_query(F.data.startswith("adm:movie_del:"), IsAdmin())
    async def movie_del(c: CallbackQuery, ctx: Ctx):
        await db.delete_movie(ctx.bot_pk, int(c.data.split(":")[2]))
        await c.answer("🗑 O'chirildi")
        await movie_list(c, ctx)

    return r
