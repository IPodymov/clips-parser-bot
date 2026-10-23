from aiogram import Router

from src.bot.handlers import links, start


def build_router() -> Router:
    router = Router(name="root")
    # Order matters: commands first, catch-all link handler last
    router.include_routers(start.router, links.router)
    return router


__all__ = ["build_router"]
