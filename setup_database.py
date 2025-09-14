"""Скрипт для настройки базы данных и создания тестовых данных."""
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent))

from database.models import create_tables, SessionLocal, ValidationRule
from database.database import DatabaseManager
from loguru import logger

def setup_database():
    """Настраивает базу данных и создает тестовые данные."""
    logger.info("Настройка базы данных...")

    # Создаем таблицы
    create_tables()
    logger.info("Таблицы созданы")

    # Создаем тестовые правила валидации
    with DatabaseManager() as db:
        # Правило 1: Тестовый чек на 1000 рублей
        rule1 = db.create_validation_rule(
            name="Тестовый чек 1000 руб",
            expected_amount=1000.0,
            expected_recipient="12345678901234567890",
            tolerance=0.01,
            file_to_send="default_certificate.txt"
        )
        logger.info(f"Создано правило: {rule1.name}")

        # Правило 2: Тестовый чек на 500 рублей
        rule2 = db.create_validation_rule(
            name="Тестовый чек 500 руб",
            expected_amount=500.0,
            expected_recipient="98765432109876543210",
            tolerance=0.01,
            file_to_send="default_certificate.txt"
        )
        logger.info(f"Создано правило: {rule2.name}")

        # Правило 3: Гибкое правило (только счет)
        rule3 = db.create_validation_rule(
            name="Гибкое правило",
            expected_amount=None,  # Любая сумма
            expected_recipient="11111111111111111111",
            tolerance=0.01,
            file_to_send="default_certificate.txt"
        )
        logger.info(f"Создано правило: {rule3.name}")

    logger.info("База данных настроена успешно!")

def show_rules():
    """Показывает все правила валидации."""
    with DatabaseManager() as db:
        rules = db.get_active_validation_rules()

        if not rules:
            logger.info("Правила валидации не найдены")
            return

        logger.info("Активные правила валидации:")
        for rule in rules:
            logger.info(f"  - {rule.name}")
            logger.info(f"    Сумма: {rule.expected_amount}")
            logger.info(f"    Получатель: {rule.expected_recipient}")
            logger.info(f"    Допуск: {rule.tolerance}")
            logger.info(f"    Файл: {rule.file_to_send}")
            logger.info("")

if __name__ == "__main__":
    setup_database()
    show_rules()
