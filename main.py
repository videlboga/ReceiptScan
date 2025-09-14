"""Точка входа в приложение."""
import sys
from pathlib import Path

# Добавляем текущую директорию в путь
sys.path.append(str(Path(__file__).parent))

from bot.main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
