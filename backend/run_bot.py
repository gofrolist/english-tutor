"""Run the Telegram bot locally."""

import asyncio

from src.english_tutor.api.bot import start_bot


async def main() -> None:
    """Start the bot and keep the event loop alive."""
    await start_bot()
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
