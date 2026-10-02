"""Universal Downloader: TikTok, YouTube Shorts, Pinterest (suv belgisiz)."""
import re

from aiogram import F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message

import config
from filters import NotCommand
from middlewares import Ctx
from services import downloader as dl
from utils import h

URL_RE = re.compile(r"https?://(?:[\w-]+\.)?(?:tiktok\.com|youtube\.com|youtu\.be|pinterest\.[a-z.]+|pin\.it)/\S+", re.I)


def get_router() -> Router:
    r = Router(name="child_downloader")

    @r.message(CommandStart())
    async def start(m: Message, state: FSMContext, ctx: Ctx):
        await state.clear()
        text = (f"📥 Salom, <b>{h(m.from_user.full_name)}</b>!\n\n"
                "<b>TikTok</b>, <b>YouTube Shorts</b> yoki <b>Pinterest</b> havolasini yuboring — "
                "videoni suv belgisiz yuklab beraman.")
        if ctx.is_admin(m.from_user.id):
            text += "\n\n🛠 Boshqaruv: /admin"
        await m.answer(text)

    @r.message(StateFilter(None), F.text, NotCommand())
    async def handle(m: Message):
        match = URL_RE.search(m.text)
        if not match:
            await m.answer("❌ Havola topilmadi. TikTok, YouTube Shorts yoki Pinterest linkini yuboring.")
            return
        wait = await m.answer("⏳ Yuklanmoqda...")
        try:
            async with dl.workdir() as wd:
                video, info = await dl.download_video(match.group(0), wd)
                if video.stat().st_size > config.MAX_UPLOAD_BYTES:
                    await wait.edit_text("❌ Video 50MB dan katta, yuborib bo'lmaydi.")
                    return
                await m.answer_video(FSInputFile(video), caption="✅ Tayyor!", supports_streaming=True)
            await wait.delete()
        except dl.DownloadError as e:
            await wait.edit_text(f"❌ Yuklab bo'lmadi: {h(e)}")

    return r
