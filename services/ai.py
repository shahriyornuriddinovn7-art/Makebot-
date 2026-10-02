"""Gemini va OpenAI (matn) klientlari — aiohttp orqali."""
from __future__ import annotations

from typing import Optional

import asyncio

import aiohttp

import config
from database import db

TIMEOUT = aiohttp.ClientTimeout(total=120)
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class AIError(Exception):
    pass


class NoKeyError(AIError):
    pass


NO_KEY_TEXT = ("⚠️ AI moduli hali faol emas.\n"
               "Bot egasi /admin → 🔑 API kalitlar bo'limidan kalit ulashi kerak.")


def _err_message(data) -> str:
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            return str(err.get("message", err))[:300]
        if err:
            return str(err)[:300]
    return "Noma'lum xato"


async def gemini_chat(api_key: str, messages: list[tuple[str, str]], system: Optional[str] = None,
                      json_mode: bool = False, model: Optional[str] = None) -> str:
    """messages: [('user'|'model', matn), ...]"""
    payload: dict = {"contents": [{"role": r, "parts": [{"text": t}]} for r, t in messages]}
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    if json_mode:
        payload["generationConfig"] = {"responseMimeType": "application/json"}
    url = GEMINI_URL.format(model=model or config.GEMINI_MODEL)
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.post(url, json=payload, headers={"x-goog-api-key": api_key}) as resp:
                data = await resp.json(content_type=None)
                if resp.status != 200:
                    raise AIError(f"Gemini [{resp.status}]: {_err_message(data)}")
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        raise AIError(f"Tarmoq xatosi: {e}") from e
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError, TypeError):
        raise AIError("Gemini bo'sh javob qaytardi (xavfsizlik filtri bo'lishi mumkin).")
    if not text:
        raise AIError("Gemini bo'sh javob qaytardi.")
    return text


async def openai_chat(api_key: str, messages: list[tuple[str, str]], system: Optional[str] = None) -> str:
    msgs = [{"role": "system", "content": system}] if system else []
    msgs += [{"role": "assistant" if r == "model" else "user", "content": t} for r, t in messages]
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.post("https://api.openai.com/v1/chat/completions",
                              json={"model": config.OPENAI_CHAT_MODEL, "messages": msgs},
                              headers={"Authorization": f"Bearer {api_key}"}) as resp:
                data = await resp.json(content_type=None)
                if resp.status != 200:
                    raise AIError(f"OpenAI [{resp.status}]: {_err_message(data)}")
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        raise AIError(f"Tarmoq xatosi: {e}") from e
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        raise AIError("OpenAI kutilmagan javob qaytardi.")


async def chat_with_keys(bot_pk: int, messages: list[tuple[str, str]], system: Optional[str] = None,
                         json_mode: bool = False) -> str:
    """Bot uchun ulangan kalitdan foydalanadi (Gemini birinchi, keyin OpenAI)."""
    g = await db.get_key(bot_pk, "gemini")
    if g:
        return await gemini_chat(g, messages, system, json_mode)
    o = await db.get_key(bot_pk, "openai")
    if o:
        return await openai_chat(o, messages, system)
    raise NoKeyError(NO_KEY_TEXT)


async def validate_gemini(key: str) -> tuple[bool, str]:
    try:
        await gemini_chat(key, [("user", "ping")])
        return True, ""
    except AIError as e:
        return False, str(e)


async def validate_openai(key: str) -> tuple[bool, str]:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
            async with s.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"}) as r:
                if r.status == 200:
                    return True, ""
                return False, f"OpenAI [{r.status}]: {_err_message(await r.json(content_type=None))}"
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        return False, f"Tarmoq xatosi: {e}"
