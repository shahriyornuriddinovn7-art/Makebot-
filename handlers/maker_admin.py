"""Maker Bot admin paneli: yaratilgan botlarni boshqarish (aktiv/noaktiv, bloklash, o'chirish)."""
from aiogram import F, Router
from aiogram.types import CallbackQuery

import config
from bot_manager import manager
from database import db
from filters import IsAdmin
from keyboards import inline as kb
from utils import h, safe_edit

PAGE = 8


def get_router() -> Router:
    r = Router(name="maker_admin")
    r.callback_query.filter(IsAdmin())

    async def render_list(c: CallbackQuery, page: int):
        total = await db.count_bots()
        bots = await db.list_bots(limit=PAGE, offset=page * PAGE)
        rows = [[(f"{kb.STATUS_ICON.get(b['status'], '•')} @{b['username']} • {b['bot_type']}", f"adm:bot:{b['id']}")]
                for b in bots]
        nav = []
        if page > 0:
            nav.append(("⬅️", f"adm:bots:{page - 1}"))
        if (page + 1) * PAGE < total:
            nav.append(("➡️", f"adm:bots:{page + 1}"))
        if nav:
            rows.append(nav)
        rows.append([("⬅️ Admin panel", "adm:menu")])
        await safe_edit(c, f"🤖 <b>Yaratilgan botlar</b> (jami: {total})", kb.build(rows))

    @r.callback_query(F.data.startswith("adm:bots:"))
    async def bots_list(c: CallbackQuery):
        await render_list(c, int(c.data.split(":")[2]))
        await c.answer()

    async def render(c: CallbackQuery, pk: int):
        b = await db.get_bot(pk)
        if not b:
            await c.answer("Topilmadi", show_alert=True)
            return
        text = (f"{kb.STATUS_ICON[b['status']]} <b>@{h(b['username'])}</b> (#{b['id']})\n{config.BOT_TYPES[b['bot_type']]}\n"
                f"Egasi: <code>{b['owner_id']}</code>\nHolat: <b>{b['status']}</b> • "
                f"{'ishlayapti' if manager.is_running(pk) else 'to‘xtagan'}\n"
                f"👥 Foydalanuvchilar: {await db.count_users(pk)}\nYaratilgan: {b['created_at']}")
        rows = [[("⏸ Noaktiv qilish" if b["status"] == "active" else "▶️ Aktiv qilish", f"adm:bt:{pk}")],
                [("✅ Blokdan chiqarish" if b["status"] == "blocked" else "⛔ Bloklash", f"adm:bb:{pk}")],
                [("🗑 Token va botni o'chirish", f"adm:bd:{pk}")],
                [("⬅️ Ro'yxat", "adm:bots:0")]]
        await safe_edit(c, text, kb.build(rows))

    @r.callback_query(F.data.startswith("adm:bot:"))
    async def detail(c: CallbackQuery):
        await render(c, int(c.data.split(":")[2]))
        await c.answer()

    @r.callback_query(F.data.startswith("adm:bt:"))
    async def toggle(c: CallbackQuery):
        pk = int(c.data.split(":")[2])
        b = await db.get_bot(pk)
        if not b:
            return
        if b["status"] == "blocked":
            await c.answer("Bot bloklangan. Avval blokdan chiqaring.", show_alert=True)
            return
        if b["status"] == "active":
            await db.set_bot_status(pk, "inactive")
            await manager.stop_bot(pk)
        else:
            await db.set_bot_status(pk, "active")
            await manager.start_bot(pk)
        await render(c, pk)
        await c.answer()

    @r.callback_query(F.data.startswith("adm:bb:"))
    async def block(c: CallbackQuery):
        pk = int(c.data.split(":")[2])
        b = await db.get_bot(pk)
        if not b:
            return
        if b["status"] == "blocked":
            await db.set_bot_status(pk, "active")
            await manager.start_bot(pk)
        else:
            await db.set_bot_status(pk, "blocked")
            await manager.stop_bot(pk)
        await render(c, pk)
        await c.answer()

    @r.callback_query(F.data.startswith("adm:bd:"))
    async def del_ask(c: CallbackQuery):
        pk = int(c.data.split(":")[2])
        await safe_edit(c, f"⚠️ Bot #{pk} va uning tokeni/ma'lumotlari o'chiriladi. Ishonchingiz komilmi?",
                        kb.build([[("✅ Ha", f"adm:bdy:{pk}"), ("❌ Yo'q", f"adm:bot:{pk}")]]))
        await c.answer()

    @r.callback_query(F.data.startswith("adm:bdy:"))
    async def del_do(c: CallbackQuery):
        pk = int(c.data.split(":")[2])
        await manager.stop_bot(pk)
        await db.delete_bot(pk)
        await c.answer("🗑 O'chirildi")
        await render_list(c, 0)

    return r
