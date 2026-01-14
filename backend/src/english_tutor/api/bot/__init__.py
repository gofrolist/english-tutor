"""Bot package - re-exports from parent bot.py module."""

import importlib.util
from pathlib import Path

# Import bot.py from parent directory to avoid naming conflict
_bot_py_path = Path(__file__).parent.parent / "bot.py"
spec = importlib.util.spec_from_file_location("bot_module", _bot_py_path)
bot_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot_module)

# Re-export public functions
start_bot = bot_module.start_bot
stop_bot = bot_module.stop_bot
get_bot_application = bot_module.get_bot_application
