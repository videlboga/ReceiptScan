#!/usr/bin/env python3
"""Гибкий бот для проверки чеков с настраиваемыми правилами валидации."""
import os
import asyncio
import tempfile
import subprocess
from datetime import datetime
from typing import Optional
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pdf2image import convert_from_path
import PyPDF2
from loguru import logger

# Импортируем гибкие компоненты
from validation.flexible_validator_v1 import FlexibleReceiptValidator
from validation.flexible_parser_v1 import FlexibleReceiptParser

# Получаем токен из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в переменных окружения")

class FlexibleReceiptChecker:
    """Класс для проверки чеков с гибкими правилами валидации."""

    def __init__(self, config_path: str = None):
        """
        Инициализация проверяльщика.

        Args:
            config_path: Путь к конфигурационному файлу
        """
        self.validator = FlexibleReceiptValidator(config_path)
        self.parser = FlexibleReceiptParser(config_path)

        # Настройки OCR
        self.ocr_config = {
            'psm_modes': ['6', '3', '4', '8'],
            'languages': 'rus+eng',
            'oem_mode': '3',
            'timeout': 30
        }

        logger.info("Гибкий проверяльщик чеков инициализирован")

    async def process_receipt(self, file_path: str) -> dict:
        """Обрабатывает чек и возвращает результат."""
        try:
            # Определяем тип файла
            file_ext = os.path.splitext(file_path)[1].lower()
            logger.info(f"Обрабатываю файл: {file_path} (тип: {file_ext})")

            if file_ext == '.pdf':
                # Обрабатываем PDF
                text = await self.extract_text_from_pdf(file_path)
            else:
                # Обрабатываем изображение
                text = await self.extract_text(file_path)

            # Валидируем чек с помощью гибкого валидатора
            validation_result = self.validator.validate_receipt(text)

            return {
                'success': True,
                'text': text,
                'validation': validation_result,
                'parsed_data': self.parser.parse_receipt(text)
            }
        except Exception as e:
            logger.error(f"Ошибка обработки чека: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Извлекает текст из PDF файла."""
        try:
            logger.info(f"Обрабатываю PDF: {pdf_path}")

            # Сначала пробуем извлечь текст напрямую из PDF
            try:
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"

                    if text.strip():
                        logger.info(f"Текст извлечен из PDF напрямую: {text[:200]}...")
                        return text.strip()
            except Exception as e:
                logger.warning(f"Не удалось извлечь текст напрямую: {e}")

            # Если не получилось, конвертируем в изображения и используем OCR
            logger.info("Конвертирую PDF в изображения...")
            images = convert_from_path(pdf_path, dpi=300)

            all_text = ""
            for i, image in enumerate(images):
                logger.info(f"Обрабатываю страницу {i+1}/{len(images)}")

                # Сохраняем изображение во временный файл
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_img:
                    image.save(temp_img.name, 'PNG')

                    # Извлекаем текст с помощью OCR
                    page_text = await self.extract_text(temp_img.name)
                    all_text += page_text + "\n"

                    # Удаляем временный файл
                    os.unlink(temp_img.name)

            logger.info(f"Текст извлечен из PDF через OCR: {all_text[:200]}...")
            return all_text.strip()

        except Exception as e:
            raise Exception(f"PDF processing error: {str(e)}")

    async def extract_text(self, image_path: str) -> str:
        """Извлекает текст из изображения с помощью Tesseract."""
        try:
            logger.info(f"Запускаю Tesseract для файла: {image_path}")

            # Пробуем разные режимы распознавания
            psm_modes = self.ocr_config['psm_modes']
            best_text = ""
            all_results = {}

            for psm in psm_modes:
                logger.debug(f"Пробую режим PSM {psm}")
                result = subprocess.run([
                    'tesseract', image_path, 'stdout',
                    '-l', self.ocr_config['languages'], '--psm', psm,
                    '--oem', self.ocr_config['oem_mode']
                ], capture_output=True, text=True, timeout=self.ocr_config['timeout'])

                if result.returncode == 0:
                    text = result.stdout.strip()
                    all_results[psm] = text
                    logger.debug(f"PSM {psm} успешно: {text[:100]}...")

                    if len(text) > len(best_text):
                        best_text = text
                else:
                    logger.warning(f"PSM {psm} failed: {result.stderr}")
                    all_results[psm] = f"ERROR: {result.stderr}"

            if not best_text:
                logger.error("Все режимы PSM не сработали!")
                logger.debug("Все результаты:")
                for psm, text in all_results.items():
                    logger.debug(f"PSM {psm}: {text}")
                raise Exception("Не удалось извлечь текст ни одним режимом")

            logger.info(f"Лучший результат (длина: {len(best_text)}): {best_text[:200]}...")
            return best_text

        except subprocess.TimeoutExpired:
            raise Exception("Tesseract timeout")
        except Exception as e:
            raise Exception(f"OCR error: {str(e)}")

    def get_validation_summary(self) -> dict:
        """Возвращает сводку по текущим правилам валидации."""
        config = self.validator.get_config()

        return {
            'valid_phones': config.get('phone_validation', {}).get('valid_phones', []),
            'valid_amounts': config.get('amount_validation', {}).get('valid_amounts', []),
            'valid_accounts': config.get('account_validation', {}).get('valid_accounts', []),
            'valid_cards': config.get('account_validation', {}).get('valid_cards', []),
            'min_confidence': config.get('validation', {}).get('min_confidence', 50.0),
            'amount_tolerance': config.get('validation', {}).get('amount_tolerance', 0.01)
        }

# Создаем экземпляр проверяльщика
checker = FlexibleReceiptChecker()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    summary = checker.get_validation_summary()

    message = (
        "🤖 **Гибкий бот проверки чеков v1**\n\n"
        "🎯 **Текущие правила валидации:**\n"
        f"• **Валидные телефоны:** {len(summary['valid_phones'])} номеров\n"
        f"• **Валидные суммы:** {len(summary['valid_amounts'])} значений\n"
        f"• **Валидные счета:** {len(summary['valid_accounts'])} счетов\n"
        f"• **Валидные карты:** {len(summary['valid_cards'])} карт\n"
        f"• **Минимальная уверенность:** {summary['min_confidence']}%\n"
        f"• **Толерантность суммы:** ±{summary['amount_tolerance']} руб\n\n"
        "✅ **Чек считается валидным, если:**\n"
        "• Найдена сумма из списка валидных\n"
        "• Найден телефон или счет из списка валидных\n"
        "• Уверенность распознавания ≥ минимальной\n\n"
        "📸 **Отправьте фотографию чека или PDF файл для проверки**"
    )

    await update.message.reply_text(message)

async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /config - показывает текущую конфигурацию."""
    summary = checker.get_validation_summary()

    message = "⚙️ **Текущая конфигурация валидации:**\n\n"

    if summary['valid_phones']:
        message += f"📱 **Валидные телефоны:**\n"
        for phone in summary['valid_phones']:
            message += f"• {phone}\n"
        message += "\n"

    if summary['valid_amounts']:
        message += f"💰 **Валидные суммы:**\n"
        for amount in summary['valid_amounts']:
            message += f"• {amount} руб\n"
        message += "\n"

    if summary['valid_accounts']:
        message += f"🏦 **Валидные счета:**\n"
        for account in summary['valid_accounts']:
            message += f"• {account}\n"
        message += "\n"

    if summary['valid_cards']:
        message += f"💳 **Валидные карты:**\n"
        for card in summary['valid_cards']:
            message += f"• {card}\n"
        message += "\n"

    message += f"📊 **Настройки:**\n"
    message += f"• Минимальная уверенность: {summary['min_confidence']}%\n"
    message += f"• Толерантность суммы: ±{summary['amount_tolerance']} руб\n"

    await update.message.reply_text(message)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографий."""
    logger.info("Получено фото от пользователя")
    await update.message.reply_text("📸 Фото получено! Анализирую чек с гибкими правилами...")

    try:
        # Получаем файл
        file = await context.bot.get_file(update.message.photo[-1].file_id)
        logger.info(f"Файл получен: {file.file_id}, размер: {file.file_size} байт")

        # Создаем временный файл
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
            await file.download_to_drive(temp_file.name)
            logger.info(f"Файл сохранен: {temp_file.name}")

            # Обрабатываем чек
            logger.info("Начинаю обработку чека...")
            result = await checker.process_receipt(temp_file.name)
            logger.info("Обработка завершена")

            # Удаляем временный файл
            os.unlink(temp_file.name)
            logger.info(f"Временный файл удален: {temp_file.name}")

        if result['success']:
            # Отправляем результат
            await send_result(update, result)
        else:
            await update.message.reply_text(f"❌ Ошибка обработки: {result['error']}")

    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        await update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик документов (PDF)."""
    document = update.message.document

    # Проверяем, что это PDF
    if not document.file_name.lower().endswith('.pdf'):
        await update.message.reply_text("❌ Поддерживаются только PDF файлы. Отправьте PDF документ.")
        return

    logger.info("Получен PDF документ")
    await update.message.reply_text("📄 PDF получен! Анализирую чек с гибкими правилами...")

    try:
        # Получаем файл
        file = await context.bot.get_file(document.file_id)
        logger.info(f"Файл получен: {file.file_id}, имя: {document.file_name}, размер: {document.file_size} байт")

        # Создаем временный файл
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            await file.download_to_drive(temp_file.name)
            logger.info(f"Файл сохранен: {temp_file.name}")

            # Обрабатываем чек
            logger.info("Начинаю обработку чека...")
            result = await checker.process_receipt(temp_file.name)
            logger.info("Обработка завершена")

            # Удаляем временный файл
            os.unlink(temp_file.name)
            logger.info(f"Временный файл удален: {temp_file.name}")

        if result['success']:
            # Отправляем результат
            await send_result(update, result)
        else:
            await update.message.reply_text(f"❌ Ошибка обработки: {result['error']}")

    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        await update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")

async def send_result(update: Update, result: dict):
    """Отправляет результат проверки."""
    validation = result['validation']
    parsed_data = result['parsed_data']

    # Формируем сообщение
    message = "📊 **Результат гибкой валидации чека:**\n\n"

    # Общий статус
    if validation.is_valid:
        message += "🎉 **СТАТУС: ЧЕК ВАЛИДЕН!**\n"
        message += f"📈 **Оценка уверенности:** {validation.confidence_score:.1f}%\n\n"
    else:
        message += "❌ **СТАТУС: ЧЕК НЕ ВАЛИДЕН**\n"
        message += f"📉 **Оценка уверенности:** {validation.confidence_score:.1f}%\n\n"

    # Детали валидации
    message += "📋 **Детали валидации:**\n"
    message += validation.message + "\n\n"

    # Найденные данные
    message += "🔍 **Найденные данные:**\n"
    if parsed_data.amount:
        message += f"💰 Сумма: {parsed_data.amount} руб\n"
    else:
        message += "💰 Сумма: не найдена\n"

    if parsed_data.recipient_phone:
        message += f"📱 Телефон: {parsed_data.recipient_phone}\n"
    else:
        message += "📱 Телефон: не найден\n"

    if parsed_data.recipient_account:
        message += f"🏦 Счет/карта: {parsed_data.recipient_account}\n"
    else:
        message += "🏦 Счет/карта: не найдены\n"

    if parsed_data.date:
        message += f"📅 Дата: {parsed_data.date.strftime('%d.%m.%Y')}\n"

    if parsed_data.time:
        message += f"🕐 Время: {parsed_data.time.strftime('%H:%M:%S')}\n"

    message += f"📊 Уверенность OCR: {parsed_data.confidence:.1f}%\n"

    # Рекомендации
    if validation.recommendations:
        message += "\n💡 **Рекомендации:**\n"
        for recommendation in validation.recommendations:
            message += f"• {recommendation}\n"

    await update.message.reply_text(message)

def main():
    """Основная функция."""
    logger.info("Запуск гибкого бота проверки чеков v1...")
    logger.info(f"Токен бота: {BOT_TOKEN[:20]}...")

    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("config", config_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    logger.info("Гибкий бот v1 запущен и готов к работе!")
    logger.info("Ожидаю сообщения...")

    # Запускаем бота
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
