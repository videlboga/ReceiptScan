"""Основной файл Telegram бота для проверки чеков."""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

from telegram.ext import Application, CommandHandler, MessageHandler, filters
from loguru import logger
from config.settings import BOT_TOKEN, ENABLE_DEBUG
from database.models import create_tables
from bot.handlers import BotHandlers

# Настройка логирования
logger.remove()
logger.add(
    sys.stdout,
    level="DEBUG" if ENABLE_DEBUG else "INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)
logger.add(
    "logs/bot.log",
    rotation="1 day",
    retention="30 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
)

async def main():
    """Основная функция запуска бота."""
    logger.info("Запуск бота проверки чеков...")

    # Создаем таблицы в базе данных
    try:
        create_tables()
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        return

    # Создаем приложение бота
    application = Application.builder().token(BOT_TOKEN).build()

    # Создаем обработчики
    handlers = BotHandlers()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", handlers.start_command))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("status", handlers.status_command))

    # Регистрируем обработчик фотографий
    application.add_handler(MessageHandler(filters.PHOTO, handlers.handle_photo))

    # Регистрируем обработчик ошибок
    application.add_error_handler(handlers.error_handler)

    logger.info("Бот запущен и готов к работе")

    # Запускаем бота
    try:
        await application.run_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True
        )
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        logger.info("Бот остановлен")

if __name__ == "__main__":
    # Создаем директорию для логов
    Path("logs").mkdir(exist_ok=True)

    # Запускаем бота
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Программа завершена пользователем")
    except Exception as e:
        logger.error(f"Ошибка запуска: {e}")
        sys.exit(1)
