import html

from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from src.core.models import User
from src.services.users import apply_source

router = Router(name="start")

HELP_TEXT = (
    "Пришлите ссылку на видео — я скачаю его и отправлю сюда файлом.\n\n"
    "<b>Поддерживаются:</b> YouTube (в т.ч. Shorts), TikTok, Instagram (Reels), "
    "VK, X/Twitter и многие другие сайты.\n\n"
    "Приватные видео и видео, требующие входа в аккаунт, скачать не получится."
)


@router.message(CommandStart())
async def cmd_start(
    message: Message, command: CommandObject, user: User, is_new_user: bool
) -> None:
    apply_source(user, command.args, is_new_user=is_new_user)
    name = html.escape(user.first_name or "друг")
    await message.answer(f"Привет, {name}! 👋\n\n{HELP_TEXT}")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)
