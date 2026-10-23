import logging

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level.upper(), format=LOG_FORMAT, force=True)
    # Third-party libraries are too chatty on INFO
    for noisy in ("aiogram.event", "httpx", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
