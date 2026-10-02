"""Anonim Chat Bot: tasodifiy suhbatdosh topish va xabarlarni anonim uzatish."""
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import BaseFilter, Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards import inline as kb
from middlewares import Ctx

# bot_pk -> navbatdagi foydalanuvchilar / juftliklar (xotirada; restartda tozalanadi)
_queue: dict[int, list[int]] = {}
_pairs: dict[tuple[int, int], int] = {}

MENU = kb.build([[("🔎 Suhbatdosh topish", "an:find")]])
IN_CHAT = kb.build([[("⏭ Keyingisi", "an:next"), ("⛔ To'xtatish", "an:stop")]])


class InChat(BaseFilter):
    async def __call__(self, message: Message, ctx: Ctx) -> bool:
        return (ctx.bot_pk, message.from_user.id) in _pairs


async def _leave(bot: Bot, bot_pk: int, uid: int, notify_partner: bool = True) -> None:
    q = _queue.get(bot_pk, [])
    if uid in q:
        q.remove(uid)
    partner = _pairs.pop((bot_pk, uid), None)
    if partner is not None:
        _pairs.pop((bot_pk, partner), None)
        if notify_partner:
            try:
                await bot.send_message(partner, "🚪 Suhbatdosh chatni tark etdi.", reply_markup=MENU)
            except TelegramAPIError:
                pass


async def _find(bot: Bot, bot_pk: int, uid: int) -> str:
    if (bot_pk, uid) in _pairs:
        return "ℹ️ Siz allaqachon suhbatdasiz. /next yoki /stop."
    q = _queue.setdefault(bot_pk, [])
    if uid in q:
        return "⏳ Suhbatdosh qidirilmoqda..."
    while q:
        other = q.pop(0)
        if other == uid:
            continue
        _pairs[(bot_pk, uid)] = other
        _pairs[(bot_pk, other)] = uid
        try:
            await bot.send_message(other, "✅ Suhbatdosh topildi! Yozishingiz mumkin.\n/next — keyingisi, /stop — to'xtatish",
                                   reply_markup=IN_CHAT)
        except TelegramAPIError:
            _pairs.pop((bot_pk, uid), None)
            _pairs.pop((bot_pk, other), None)
            continue
        return "✅ Suhbatdosh topildi! Yozishingiz mumkin.\n/next — keyingisi, /stop — to'xtatish"
    q.append(uid)
    return "🔎 Suhbatdosh qidirilmoqda... Topilishi bilan xabar beraman."


def get_router() -> Router:
    r = Router(name="child_anon")

    @r.message(CommandStart())
    async def start(m: Message, state: FSMContext, bot: Bot, ctx: Ctx):
        await state.clear()
        await _leave(bot, ctx.bot_pk, m.from_user.id)
        text = ("🕶 <b>Anonim chat</b>ga xush kelibsiz!\nIsmingiz va profilingiz yashirin qoladi. "
                "Haqorat va noqonuniy kontent taqiqlanadi.")
        if ctx.is_admin(m.from_user.id):
            text += "\n\n🛠 Boshqaruv: /admin"
        await m.answer(text, reply_markup=MENU)

    @r.callback_query(F.data == "an:find")
    async def cb_find(c: CallbackQuery, bot: Bot, ctx: Ctx):
        await c.answer()
        await c.message.answer(await _find(bot, ctx.bot_pk, c.from_user.id))

    @r.callback_query(F.data == "an:next")
    async def cb_next(c: CallbackQuery, bot: Bot, ctx: Ctx):
        await c.answer()
        await _leave(bot, ctx.bot_pk, c.from_user.id)
        await c.message.answer(await _find(bot, ctx.bot_pk, c.from_user.id))

    @r.callback_query(F.data == "an:stop")
    async def cb_stop(c: CallbackQuery, bot: Bot, ctx: Ctx):
        await c.answer()
        await _leave(bot, ctx.bot_pk, c.from_user.id)
        await c.message.answer("⛔ Suhbat to'xtatildi.", reply_markup=MENU)

    @r.message(Command("find"))
    async def cmd_find(m: Message, bot: Bot, ctx: Ctx):
        await m.answer(await _find(bot, ctx.bot_pk, m.from_user.id))

    @r.message(Command("next"))
    async def cmd_next(m: Message, bot: Bot, ctx: Ctx):
        await _leave(bot, ctx.bot_pk, m.from_user.id)
        await m.answer(await _find(bot, ctx.bot_pk, m.from_user.id))

    @r.message(Command("stop"))
    async def cmd_stop(m: Message, bot: Bot, ctx: Ctx):
        await _leave(bot, ctx.bot_pk, m.from_user.id)
        await m.answer("⛔ Suhbat to'xtatildi.", reply_markup=MENU)

    @r.message(InChat())
    async def relay(m: Message, bot: Bot, ctx: Ctx):
        partner = _pairs.get((ctx.bot_pk, m.from_user.id))
        if partner is None:
            return
        if m.text and m.text.startswith("/"):
            return
        try:
            await m.copy_to(partner)  # forward emas — kimligi ko'rinmaydi
        except TelegramAPIError:
            await _leave(bot, ctx.bot_pk, m.from_user.id, notify_partner=False)
            await m.answer("⚠️ Suhbatdosh botni bloklagan. Chat yopildi.", reply_markup=MENU)

    @r.message(F.text, ~F.text.startswith("/"))
    async def idle(m: Message):
        await m.answer("Suhbatdosh topish uchun tugmani bosing 👇", reply_markup=MENU)

    return r
