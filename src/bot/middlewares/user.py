from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.users import get_or_create_user


class UserMiddleware(BaseMiddleware):
    """Registers the user and refreshes `last_active_at`. Needs DbSessionMiddleware before it."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)

        session: AsyncSession = data["session"]
        user, created = await get_or_create_user(session, tg_user)
        data["user"] = user
        data["is_new_user"] = created
        return await handler(event, data)
