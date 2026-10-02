"""Rasm generatsiyasi: Pollinations (bepul/token) yoki OpenAI (kalit 'sk-' bilan boshlansa)."""
import asyncio
import base64
import random
from urllib.parse import quote

import aiohttp

import config
from services.ai import AIError

TIMEOUT = aiohttp.ClientTimeout(total=180)

STYLES = {
    "logo": "professional minimalist vector logo design, clean shapes, flat, white background, high quality: ",
    "avatar": "stylized high quality avatar illustration, detailed, centered portrait: ",
    "image": "highly detailed, high quality image: ",
}


async def generate_image(api_key: str, prompt: str, mode: str = "image") -> bytes:
    full = STYLES.get(mode, "") + prompt
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            if api_key.startswith("sk-"):
                async with s.post("https://api.openai.com/v1/images/generations",
                                  json={"model": config.OPENAI_IMAGE_MODEL, "prompt": full[:3900], "n": 1,
                                        "size": "1024x1024", "response_format": "b64_json"},
                                  headers={"Authorization": f"Bearer {api_key}"}) as r:
                    data = await r.json(content_type=None)
                    if r.status != 200:
                        msg = (data.get("error") or {}).get("message", "") if isinstance(data, dict) else ""
                        raise AIError(f"OpenAI [{r.status}]: {msg[:250]}")
                    return base64.b64decode(data["data"][0]["b64_json"])
            params = {"width": 1024, "height": 1024, "nologo": "true", "seed": random.randint(1, 10**6),
                      "token": api_key}
            url = config.POLLINATIONS_URL + quote(full[:1500])
            async with s.get(url, params=params, headers={"Authorization": f"Bearer {api_key}"}) as r:
                if r.status != 200:
                    raise AIError(f"Pollinations [{r.status}]")
                body = await r.read()
                if not (r.content_type or "").startswith("image/"):
                    raise AIError("Rasm qaytmadi")
                return body
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        raise AIError(f"Tarmoq xatosi: {e}") from e
