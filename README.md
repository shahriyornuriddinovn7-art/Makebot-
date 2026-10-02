# 🤖 Maker Bot — Bot yaratuvchi bot (aiogram 3.x)

Foydalanuvchi token yuboradi, bot turini tanlaydi — bot bir zumda ishga tushadi.
7 ta tur: Kino • Musiqa/Instagram • Gemini AI • Logo/Rasm AI • Ta'lim • Universal Downloader • Anonim chat.

## Ishga tushirish
```bash
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # MAKER_BOT_TOKEN va ADMIN_IDS ni to'ldiring
python main.py
```
Musiqa/Instagram audio ajratish uchun serverda **ffmpeg** o'rnatilgan bo'lishi kerak (`apt install ffmpeg`).
Docker: `docker build -t maker . && docker run --env-file .env -v $(pwd)/data:/app/data maker`

## Struktura
```
main.py            — Maker bot kirish nuqtasi
config.py          — .env, bot turlari, API provayderlar
database.py        — aiosqlite: users, bots, channels, movies, api_keys, settings + edu_* jadvallar
bot_manager.py     — Multitenancy: har child bot uchun alohida Dispatcher + polling task
middlewares.py     — Ctx, ro'yxatga olish, ban, majburiy obuna (Check Join)
handlers/
  maker.py         — Maker: bot yaratish, botlarim, AI yordamchi
  maker_admin.py   — Maker admin: botlarni aktiv/noaktiv, bloklash, o'chirish
  admin_core.py    — UMUMIY admin: statistika, kanallar, API kalit, broadcast (Maker + child)
  child_*.py       — 7 ta bot turi
  child_builder.py — bot turiga qarab dispatcher yig'adi
keyboards/inline.py, services/ (ai, image, downloader, subscription, broadcast)
```

## Muhim eslatmalar
- **Child bot admini** = bot egasi (`/admin`). **Maker admini** = `ADMIN_IDS`.
- AI/Logo botlari kalit ulangunicha «faol emas» deydi; kalit `/admin → 🔑 API kalitlar` orqali kiritilishi bilan **qayta ishga tushirmasdan** ishlaydi (kalit har so'rovda bazadan o'qiladi).
- Rasm kaliti `sk-...` bilan boshlansa OpenAI, aks holda Pollinations ishlatiladi.
- Majburiy obuna ishlashi uchun bot kanalda **admin** bo'lishi shart.
- Kino botda post kanali: `/admin → 📣 Post kanali`. Kino qo'shilganda post avtomatik tushadi.
- Instagram ko'pincha login talab qiladi: `cookies.txt` (Netscape format) tayyorlab `COOKIES_FILE` ga yo'lini yozing.
- Telegram Bot API fayl limiti: 50 MB.
- Anonim chat navbati xotirada saqlanadi (qayta ishga tushganda tozalanadi).
