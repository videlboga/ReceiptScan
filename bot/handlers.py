"""Обработчики команд и сообщений Telegram бота."""
import asyncio
from typing import Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger

from database.database import DatabaseManager
from database.models import ValidationRule
from ocr.tesseract_processor import TesseractProcessor
from ocr.receipt_parser import ReceiptParser
from validation.validator import ReceiptValidator
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from files.file_manager import FileManager

class BotHandlers:
    """Обработчики команд и сообщений бота."""

    def __init__(self):
        self.ocr_processor = TesseractProcessor()
        self.receipt_parser = ReceiptParser()
        self.validator = ReceiptValidator()
        self.file_manager = FileManager()

        # Создаем шаблон по умолчанию если его нет
        self.file_manager.create_default_template()

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start."""
        user = update.effective_user
        chat_id = update.effective_chat.id

        logger.info(f"Пользователь {user.id} ({user.username}) запустил бота")

        # Создаем или обновляем сессию пользователя
        with DatabaseManager() as db:
            db.create_or_update_user_session(
                user_id=user.id,
                chat_id=chat_id,
                current_state='idle'
            )

        welcome_message = """
🤖 **Добро пожаловать в бот проверки чеков!**

Этот бот поможет вам проверить чеки на соответствие указанным требованиям.

**Как пользоваться:**
1. Отправьте фотографию чека
2. Бот распознает текст с помощью OCR
3. Проверит сумму и счет получателя
4. При успешной проверке выдаст сертификат

**Поддерживаемые форматы:**
• JPG, PNG, JPEG
• Максимальный размер: 10MB

**Команды:**
/help - Справка
/status - Статус последней проверки
/settings - Настройки (для администратора)

Отправьте фотографию чека для начала проверки! 📸
        """

        await update.message.reply_text(welcome_message, parse_mode='Markdown')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help."""
        help_message = """
📖 **Справка по использованию бота**

**Основные функции:**
• Распознавание текста с чеков
• Проверка суммы и счета получателя
• Выдача сертификатов при успешной проверке

**Пошаговая инструкция:**
1. Сделайте четкую фотографию чека
2. Отправьте фото боту
3. Дождитесь обработки (обычно 10-30 секунд)
4. Получите результат проверки

**Требования к фото:**
• Хорошее освещение
• Четкий текст
• Весь чек в кадре
• Форматы: JPG, PNG, JPEG

**Возможные проблемы:**
• Низкое качество фото → сделайте новое фото
• Нечеткий текст → улучшите освещение
• Неправильное распознавание → попробуйте другой угол

**Поддержка:**
Если у вас возникли проблемы, обратитесь к администратору.
        """

        await update.message.reply_text(help_message, parse_mode='Markdown')

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status."""
        user = update.effective_user

        with DatabaseManager() as db:
            receipts = db.get_user_receipts(user.id, limit=5)

        if not receipts:
            await update.message.reply_text("У вас пока нет обработанных чеков.")
            return

        status_message = "📊 **Статус ваших последних чеков:**\n\n"

        for receipt in receipts:
            status_emoji = "✅" if receipt.is_valid else "❌"
            amount = f"{receipt.amount:.2f} руб." if receipt.amount else "N/A"
            date = receipt.created_at.strftime("%d.%m.%Y %H:%M")

            status_message += f"{status_emoji} {date}\n"
            status_message += f"   Сумма: {amount}\n"
            status_message += f"   Статус: {'Проверен' if receipt.is_valid else 'Ошибка'}\n\n"

        await update.message.reply_text(status_message, parse_mode='Markdown')

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик фотографий."""
        user = update.effective_user
        chat_id = update.effective_chat.id
        message = update.message

        logger.info(f"Пользователь {user.id} отправил фото")

        # Отправляем сообщение о начале обработки
        processing_msg = await message.reply_text("🔄 Обрабатываю чек... Пожалуйста, подождите.")

        try:
            # Получаем файл фотографии
            photo = message.photo[-1]  # Берем фото наивысшего качества
            file = await context.bot.get_file(photo.file_id)

            # Скачиваем изображение
            image_data = await file.download_as_bytearray()

            # Создаем запись в базе данных
            with DatabaseManager() as db:
                receipt = db.create_receipt(
                    user_id=user.id,
                    chat_id=chat_id,
                    message_id=message.message_id
                )

            # Обрабатываем изображение
            await self._process_receipt_image(
                context, processing_msg, receipt.id, image_data, user.id
            )

        except Exception as e:
            logger.error(f"Ошибка при обработке фото: {e}")
            await processing_msg.edit_text(
                "❌ Произошла ошибка при обработке изображения. "
                "Попробуйте отправить фото еще раз."
            )

    async def _process_receipt_image(self, context: ContextTypes.DEFAULT_TYPE,
                                   processing_msg, receipt_id: int,
                                   image_data: bytes, user_id: int):
        """Обрабатывает изображение чека."""
        try:
            # Извлекаем текст с помощью OCR
            text, confidence = self.ocr_processor.extract_text(image_data)

            if not text or confidence < 30:
                await processing_msg.edit_text(
                    "❌ Не удалось распознать текст на чеке. "
                    "Попробуйте сделать более четкое фото."
                )
                return

            # Парсим данные чека
            receipt_data = self.receipt_parser.parse_receipt(text, confidence)

            # Получаем правила валидации
            with DatabaseManager() as db:
                validation_rules = db.get_active_validation_rules()

            # Валидируем чек
            validation_result = self.validator.validate_receipt(receipt_data, validation_rules)

            # Обновляем запись в базе данных
            with DatabaseManager() as db:
                db.update_receipt(
                    receipt_id,
                    amount=receipt_data.amount,
                    recipient_account=receipt_data.recipient_account,
                    date=receipt_data.date,
                    raw_text=text,
                    confidence=confidence,
                    is_valid=validation_result.is_valid,
                    validation_message=validation_result.message
                )

            # Отправляем результат
            await self._send_validation_result(
                context, processing_msg, receipt_data, validation_result
            )

        except Exception as e:
            logger.error(f"Ошибка при обработке чека: {e}")
            await processing_msg.edit_text(
                "❌ Произошла ошибка при обработке чека. "
                "Попробуйте еще раз."
            )

    async def _send_validation_result(self, context: ContextTypes.DEFAULT_TYPE,
                                    processing_msg, receipt_data, validation_result):
        """Отправляет результат валидации пользователю."""
        if validation_result.is_valid:
            # Успешная валидация
            success_message = f"""
✅ **Чек успешно проверен!**

📊 **Данные чека:**
• Сумма: {receipt_data.amount:.2f} руб.
• Получатель: {receipt_data.recipient_account}
• Уверенность: {receipt_data.confidence:.1f}%
• Дата: {receipt_data.date.strftime('%d.%m.%Y') if receipt_data.date else 'N/A'}

{validation_result.message}
            """

            await processing_msg.edit_text(success_message, parse_mode='Markdown')

            # Отправляем файл если указан
            if validation_result.file_to_send:
                file_path = self.file_manager.get_file_path(validation_result.file_to_send)
                if file_path:
                    await context.bot.send_document(
                        chat_id=processing_msg.chat_id,
                        document=open(file_path, 'rb'),
                        caption="📄 Сертификат проверки чека"
                    )
                else:
                    # Генерируем сертификат
                    cert_data = {
                        'amount': receipt_data.amount,
                        'recipient_account': receipt_data.recipient_account,
                        'confidence': receipt_data.confidence,
                        'items': receipt_data.items
                    }
                    cert_path = self.file_manager.generate_certificate(cert_data)
                    if cert_path:
                        await context.bot.send_document(
                            chat_id=processing_msg.chat_id,
                            document=open(cert_path, 'rb'),
                            caption="📄 Сертификат проверки чека"
                        )
        else:
            # Ошибка валидации
            error_message = f"""
❌ **Чек не прошел проверку**

📊 **Данные чека:**
• Сумма: {receipt_data.amount:.2f} руб. if receipt_data.amount else 'N/A'
• Получатель: {receipt_data.recipient_account or 'N/A'}
• Уверенность: {receipt_data.confidence:.1f}%

**Причина:** {validation_result.message}

Проверьте правильность данных в чеке и попробуйте еще раз.
            """

            await processing_msg.edit_text(error_message, parse_mode='Markdown')

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок."""
        logger.error(f"Ошибка в боте: {context.error}")

        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла неожиданная ошибка. Попробуйте еще раз."
            )
