"""yt-dlp asosidagi yuklovchi (video, audio, qidiruv). Bloklovchi ishlar executor'da bajariladi."""
from __future__ import annotations

import asyncio
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import config

try:
    import yt_dlp
except ImportError:  # pragma: no cover
    yt_dlp = None

_sem = asyncio.Semaphore(config.MAX_PARALLEL_DOWNLOADS)


class DownloadError(Exception):
    pass


@asynccontextmanager
async def workdir():
    d = config.TEMP_DIR / uuid.uuid4().hex
    d.mkdir(parents=True, exist_ok=True)
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _opts(outdir: Path) -> dict:
    o = {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": 30, "retries": 3,
         "outtmpl": str(outdir / "%(id)s.%(ext)s"), "max_filesize": config.MAX_UPLOAD_BYTES,
         "restrictfilenames": True}
    if config.COOKIES_FILE and Path(config.COOKIES_FILE).exists():
        o["cookiefile"] = config.COOKIES_FILE
    return o


def _first_entry(info: dict) -> dict:
    if info and info.get("entries"):
        for e in info["entries"]:
            if e:
                return e
    return info


def _find_file(outdir: Path, prefer: tuple[str, ...] = ()) -> Path | None:
    files = [f for f in outdir.iterdir() if f.is_file() and not f.name.endswith((".part", ".ytdl"))]
    for ext in prefer:
        for f in files:
            if f.suffix.lower() == ext:
                return f
    return files[0] if files else None


def _video_sync(url: str, outdir: Path):
    o = _opts(outdir)
    o["format"] = "best[ext=mp4]/best"
    with yt_dlp.YoutubeDL(o) as ydl:
        info = _first_entry(ydl.extract_info(url, download=True))
    f = _find_file(outdir, (".mp4",))
    if not f:
        raise DownloadError("Video topilmadi yoki hajmi 50MB dan katta.")
    return f, info


def _audio_sync(target: str, outdir: Path):
    o = _opts(outdir)
    if shutil.which("ffmpeg"):
        o["format"] = "bestaudio/best"
        o["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
    else:
        o["format"] = "bestaudio[ext=m4a]/bestaudio"
    with yt_dlp.YoutubeDL(o) as ydl:
        info = _first_entry(ydl.extract_info(target, download=True))
    f = _find_file(outdir, (".mp3", ".m4a"))
    if not f:
        raise DownloadError("Audio topilmadi yoki hajmi 50MB dan katta.")
    return f, info


def _search_sync(query: str, n: int) -> list[dict]:
    o = {"quiet": True, "no_warnings": True, "extract_flat": True, "socket_timeout": 20}
    with yt_dlp.YoutubeDL(o) as ydl:
        info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
    return [e for e in (info or {}).get("entries", []) if e and e.get("id")]


async def _run(fn, *args):
    if yt_dlp is None:
        raise DownloadError("yt-dlp o'rnatilmagan (pip install yt-dlp).")
    async with _sem:
        try:
            return await asyncio.get_running_loop().run_in_executor(None, fn, *args)
        except DownloadError:
            raise
        except Exception as e:  # yt_dlp.utils.DownloadError va boshqalar
            msg = str(e).replace("ERROR: ", "")
            raise DownloadError(msg[:300]) from e


async def download_video(url: str, outdir: Path):
    return await _run(_video_sync, url, outdir)


async def download_audio(target: str, outdir: Path):
    return await _run(_audio_sync, target, outdir)


async def search_music(query: str, n: int = 8) -> list[dict]:
    return await _run(_search_sync, query, n)


async def extract_audio(video: Path, outdir: Path) -> Path | None:
    """Videodagi audio trekni MP3 qilib ajratadi (ffmpeg kerak)."""
    if not shutil.which("ffmpeg"):
        return None
    out = outdir / f"{video.stem}.mp3"
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(video), "-vn", "-acodec", "libmp3lame", "-q:a", "2", str(out),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await proc.wait()
    return out if proc.returncode == 0 and out.exists() and out.stat().st_size > 0 else None
