"""Musiqa & Instagram Downloader: qidiruv + audio, Reels video + audio."""
import re

from aiogram import F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

import config
from filters import NotCommand
from keyboards import inline as kb
from middlewares import Ctx
from services import downloader as dl
from utils import fmt_duration, h

IG_RE = re.compile(r"https?://(?:www\.)?instagram\.com/\S+", re.I)
URL_RE = re.compile(r"https?://\S+", re.I)


def get_router() -> Router:
    r = Router(name="child_music")

    @r.message(CommandStart())
    async def start(m: Message, state: FSMContext, ctx: Ctx):
        await state.clear()
        text = (f"🎵 Salom, <b>{h(m.from_user.full_name)}</b>!\n\n"
                "• Qo'shiq <b>nomi</b> yoki matnini yozing — audio topib beraman.\n"
                "• <b>Instagram Reels</b> havolasini yuboring — video (suv belgisiz) va undagi musiqani alohida yuklayman.")
        if ctx.is_admin(m.from_user.id):
            text += "\n\n🛠 Boshqaruv: /admin"
        await m.answer(text)

    @r.message(StateFilter(None), F.text, NotCommand())
    async def text_handler(m: Message):
        text = m.text.strip()
        link = IG_RE.search(text)
        if link:
            return await reels(m, link.group(0))
        if URL_RE.search(text):
            await m.answer("❌ Hozircha faqat Instagram havolalari qo'llab-quvvatlanadi. Qo'shiq nomini yozing yoki Reels linkini yuboring.")
            return
        await search(m, text)

    async def reels(m: Message, url: str):
        wait = await m.answer("⏳ Yuklanmoqda...")
        try:
            async with dl.workdir() as wd:
                video, info = await dl.download_video(url, wd)
                if video.stat().st_size > config.MAX_UPLOAD_BYTES:
                    await wait.edit_text("❌ Video 50MB dan katta.")
                    return
                await m.answer_video(FSInputFile(video), caption="🎬 Video (suv belgisiz)", supports_streaming=True)
                audio = await dl.extract_audio(video, wd)
                if audio:
                    await m.answer_audio(FSInputFile(audio), title=(info.get("title") or "Instagram audio")[:60],
                                         caption="🎵 Videodagi musiqa")
                else:
                    await m.answer("ℹ️ Videodan audio ajratib bo'lmadi (ffmpeg yo'q yoki audio treki mavjud emas).")
            await wait.delete()
        except dl.DownloadError as e:
            await wait.edit_text(f"❌ Yuklab bo'lmadi: {h(e)}\n\n(Instagram ba'zan cookies talab qiladi — COOKIES_FILE ga qarang.)")

    async def search(m: Message, query: str):
        wait = await m.answer("🔎 Qidirilmoqda...")
        try:
            items = await dl.search_music(query, 8)
        except dl.DownloadError as e:
            await wait.edit_text(f"❌ Qidiruvda xatolik: {h(e)}")
            return
        if not items:
            await wait.edit_text("😕 Hech narsa topilmadi. Boshqacha yozib ko'ring.")
            return
        rows = [[(f"🎵 {(it.get('title') or '?')[:48]} [{fmt_duration(it.get('duration'))}]", f"mus:{it['id']}")]
                for it in items]
        await wait.edit_text(f"🔎 <b>{h(query)}</b> bo'yicha natijalar:", reply_markup=kb.build(rows))

    @r.callback_query(F.data.startswith("mus:"))
    async def download(c: CallbackQuery):
        vid = c.data.split(":", 1)[1]
        await c.answer("⏳ Yuklanmoqda...")
        wait = await c.message.answer("⏳ Audio tayyorlanmoqda...")
        try:
            async with dl.workdir() as wd:
                f, info = await dl.download_audio(f"https://www.youtube.com/watch?v={vid}", wd)
                if f.stat().st_size > config.MAX_UPLOAD_BYTES:
                    await wait.edit_text("❌ Fayl 50MB dan katta.")
                    return
                await c.message.answer_audio(FSInputFile(f), title=(info.get("title") or "")[:60],
                                             performer=(info.get("uploader") or info.get("channel") or "")[:60],
                                             duration=int(info.get("duration") or 0) or None)
            await wait.delete()
        except dl.DownloadError as e:
            await wait.edit_text(f"❌ Yuklab bo'lmadi: {h(e)}")

    return r
