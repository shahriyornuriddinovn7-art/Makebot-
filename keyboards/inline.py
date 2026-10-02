"""Barcha inline klaviaturalar."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import config


def build(rows) -> InlineKeyboardMarkup:
    """rows: [[(matn, qiymat), ...], ...]  qiymat http(s):// bilan boshlansa URL, aks holda callback_data."""
    def btn(b):
        text, val = b
        if val.startswith(("http://", "https://", "tg://")):
            return InlineKeyboardButton(text=text, url=val)
        return InlineKeyboardButton(text=text, callback_data=val)
    return InlineKeyboardMarkup(inline_keyboard=[[btn(b) for b in row] for row in rows])


# ---------------------------------------------------------------- umumiy
def join_kb(channels: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        link = ch.get("invite_link") or (f"https://t.me/{ch['username']}" if ch.get("username") else None)
        if link:
            rows.append([(f"📢 {ch['title']}", link)])
    rows.append([("✅ Tekshirish", "check_sub")])
    return build(rows)


def back_admin() -> InlineKeyboardMarkup:
    return build([[("⬅️ Admin panel", "adm:menu")]])


def cancel_to(data: str) -> InlineKeyboardMarkup:
    return build([[("❌ Bekor qilish", data)]])


# ------------------------------------------------------------- admin panel
def admin_menu(bot_type: str) -> InlineKeyboardMarkup:
    rows = [[("📊 Statistika", "adm:stats"), ("📢 Majburiy obuna", "adm:ch")],
            [("✉️ Xabar yuborish", "adm:bc")]]
    if bot_type in config.API_PROVIDERS:
        rows.append([("🔑 API kalitlar", "adm:keys")])
    if bot_type == "maker":
        rows.append([("🤖 Yaratilgan botlar", "adm:bots:0")])
    elif bot_type == "movie":
        rows.append([("🎬 Kino qo'shish", "adm:movie_add"), ("🗂 Kinolar", "adm:movie_list")])
        rows.append([("📣 Post kanali", "adm:movie_ch")])
    elif bot_type == "edu":
        rows.append([("📚 Kitob qo'shish", "adm:book_add")])
    return build(rows)


def channels_kb(channels: list[dict]) -> InlineKeyboardMarkup:
    rows = [[(f"🗑 {c['title']}", f"adm:chd:{c['id']}")] for c in channels]
    rows.append([("➕ Kanal qo'shish", "adm:cha"), ("🔍 Tekshirish", "adm:cht")])
    rows.append([("⬅️ Admin panel", "adm:menu")])
    return build(rows)


def keys_kb(providers, stored: dict) -> InlineKeyboardMarkup:
    rows = []
    for p, name in providers:
        row = [(f"🔑 {name}", f"adm:key:{p}")]
        if stored.get(p):
            row.append(("🗑", f"adm:keyd:{p}"))
        rows.append(row)
    rows.append([("⬅️ Admin panel", "adm:menu")])
    return build(rows)


def bc_mode_kb() -> InlineKeyboardMarkup:
    return build([[("📨 Oddiy (copy)", "adm:bcm:copy"), ("↪️ Forward", "adm:bcm:fwd")],
                  [("⬅️ Admin panel", "adm:menu")]])


def bc_confirm_kb() -> InlineKeyboardMarkup:
    return build([[("✅ Yuborish", "adm:bcgo"), ("❌ Bekor", "adm:menu")]])


# -------------------------------------------------------------- maker bot
def maker_menu(is_admin: bool) -> InlineKeyboardMarkup:
    rows = [[("➕ Bot yaratish", "mk:create")],
            [("🤖 Botlarim", "mk:my"), ("🧠 AI yordamchi", "mk:ai")],
            [("ℹ️ Yordam", "mk:help")]]
    if is_admin:
        rows.append([("🛠 Admin panel", "adm:menu")])
    return build(rows)


def bot_types_kb() -> InlineKeyboardMarkup:
    rows = [[(title, f"mk:type:{key}")] for key, title in config.BOT_TYPES.items()]
    rows.append([("⬅️ Orqaga", "mk:menu")])
    return build(rows)


STATUS_ICON = {"active": "🟢", "inactive": "🔴", "blocked": "⛔"}
