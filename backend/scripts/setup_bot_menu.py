#!/usr/bin/env python3
"""Setup Telegram bot menu commands.

This script registers bot commands with Telegram's Bot API so they appear
in the bot's menu when users type "/". Commands are defined in Russian
since the bot is designed for Russian users.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Bot, BotCommand

from src.english_tutor.config import get_telegram_bot_token
from src.english_tutor.utils.logger import get_logger

logger = get_logger(__name__)


# Bot commands definition
BOT_COMMANDS = [
    BotCommand("start", "Начать работу с ботом и пройти оценку уровня"),
    BotCommand("assess", "Повторно пройти оценку уровня английского"),
    BotCommand("task", "Получить новое задание для практики"),
]


async def setup_bot_commands() -> None:
    """Register bot commands with Telegram.

    Sets up the bot menu commands that will appear when users type "/"
    in the Telegram chat.
    """
    token = get_telegram_bot_token()
    bot = Bot(token=token)

    try:
        # Get bot info to verify connection
        bot_info = await bot.get_me()
        logger.info(f"Connected to bot: @{bot_info.username} ({bot_info.first_name})")

        # Set commands for default scope (all users)
        await bot.set_my_commands(BOT_COMMANDS)
        logger.info(f"Successfully registered {len(BOT_COMMANDS)} bot commands:")

        for cmd in BOT_COMMANDS:
            logger.info(f"  /{cmd.command} - {cmd.description}")

        logger.info("Bot menu setup completed successfully!")

    except Exception as e:
        logger.error(f"Failed to setup bot menu: {e}")
        raise
    finally:
        await bot.close()


async def main() -> None:
    """Main entry point."""
    try:
        await setup_bot_commands()
    except Exception as e:
        logger.error(f"Error setting up bot menu: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
