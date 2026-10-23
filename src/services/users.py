from datetime import UTC, datetime

from aiogram.types import User as TgUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import User

SOURCE_PREFIX = "src_"
SOURCE_MAX_LEN = 64


async def get_or_create_user(session: AsyncSession, tg_user: TgUser) -> tuple[User, bool]:
    """Register the user or refresh profile fields. Returns (user, created)."""
    user = await session.scalar(select(User).where(User.tg_id == tg_user.id))
    created = user is None
    if user is None:
        user = User(tg_id=tg_user.id)
        session.add(user)

    user.username = tg_user.username
    user.first_name = tg_user.first_name
    user.language_code = tg_user.language_code
    user.last_active_at = datetime.now(UTC)
    await session.flush()
    return user, created


def parse_source(start_payload: str | None) -> str | None:
    """`/start src_promo` → "promo"."""
    if not start_payload or not start_payload.startswith(SOURCE_PREFIX):
        return None
    source = start_payload[len(SOURCE_PREFIX) :].strip()
    return source[:SOURCE_MAX_LEN] or None


def apply_source(user: User, start_payload: str | None, *, is_new_user: bool) -> None:
    # Attribution belongs to the first touch only
    if not is_new_user or user.source:
        return
    user.source = parse_source(start_payload)
