from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from middlewares import Ctx


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, ctx: Ctx) -> bool:
        return bool(event.from_user) and ctx.is_admin(event.from_user.id)


class NotCommand(BaseFilter):
    """Matn '/' bilan boshlanmasa (yoki matn bo'lmasa) o'tkazadi."""
    async def __call__(self, message: Message) -> bool:
        return not (message.text and message.text.startswith("/"))
