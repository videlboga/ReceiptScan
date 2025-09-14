#!/usr/bin/env python3
"""Простая версия бота для поиска конкретных значений: сумма 1500 и номер 7 987 933 55 15."""
import os
import asyncio
import tempfile
import subprocess
import re
from datetime import datetime
from typing import Optional
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pdf2image import convert_from_path
import PyPDF2

# Получаем токен из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN', '7922755841:AAG12lYZ2B8X5-ByauPXwppqCwZfnU-FjJo')

# Конкретные значения для поиска
TARGET_AMOUNT = 1500
TARGET_PHONE = '79879335515'
TARGET_PHONE_FORMATTED = '7 987 933 55 15'

class ReceiptChecker:
    """Класс для проверки чеков с поиском конкретных значений."""

    def __init__(self):
        self.target_amount = TARGET_AMOUNT
        self.target_phone = TARGET_PHONE
        self.target_phone_formatted = TARGET_PHONE_FORMATTED

    async def process_receipt(self, file_path: str) -> dict:
        """Обрабатывает чек и возвращает результат."""
        try:
            # Определяем тип файла
            file_ext = os.path.splitext(file_path)[1].lower()
            print(f"📁 Обрабатываю файл: {file_path} (тип: {file_ext})")

            if file_ext == '.pdf':
                # Обрабатываем PDF
                text = await self.extract_text_from_pdf(file_path)
            else:
                # Обрабатываем изображение
                text = await self.extract_text(file_path)

            # Парсим данные чека
            receipt_data = self.parse_receipt(text)

            # Валидируем чек
            validation_result = self.validate_receipt(receipt_data)

            return {
                'success': True,
                'text': text,
                'data': receipt_data,
                'validation': validation_result
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    async def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Извлекает текст из PDF файла."""
        try:
            print(f"📄 Обрабатываю PDF: {pdf_path}")

            # Сначала пробуем извлечь текст напрямую из PDF
            try:
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"

                    if text.strip():
                        print(f"✅ Текст извлечен из PDF напрямую: {text[:200]}...")
                        return text.strip()
            except Exception as e:
                print(f"⚠️ Не удалось извлечь текст напрямую: {e}")

            # Если не получилось, конвертируем в изображения и используем OCR
            print("🖼️ Конвертирую PDF в изображения...")
            images = convert_from_path(pdf_path, dpi=300)

            all_text = ""
            for i, image in enumerate(images):
                print(f"🔍 Обрабатываю страницу {i+1}/{len(images)}")

                # Сохраняем изображение во временный файл
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_img:
                    image.save(temp_img.name, 'PNG')

                    # Извлекаем текст с помощью OCR
                    page_text = await self.extract_text(temp_img.name)
                    all_text += page_text + "\n"

                    # Удаляем временный файл
                    os.unlink(temp_img.name)

            print(f"📝 Текст извлечен из PDF через OCR: {all_text[:200]}...")
            return all_text.strip()

        except Exception as e:
            raise Exception(f"PDF processing error: {str(e)}")

    async def extract_text(self, image_path: str) -> str:
        """Извлекает текст из изображения с помощью Tesseract."""
        try:
            print(f"🔍 Запускаю Tesseract для файла: {image_path}")

            # Пробуем разные режимы распознавания
            psm_modes = ['6', '3', '4', '8']
            best_text = ""
            all_results = {}

            for psm in psm_modes:
                print(f"🔍 Пробую режим PSM {psm}")
                result = subprocess.run([
                    'tesseract', image_path, 'stdout',
                    '-l', 'rus+eng', '--psm', psm,
                    '--oem', '3'
                ], capture_output=True, text=True, timeout=30)

                if result.returncode == 0:
                    text = result.stdout.strip()
                    all_results[psm] = text
                    print(f"✅ PSM {psm} успешно:")
                    print(f"📄 Полный текст PSM {psm}:")
                    print("=" * 50)
                    print(text)
                    print("=" * 50)

                    if len(text) > len(best_text):
                        best_text = text
                else:
                    print(f"❌ PSM {psm} failed: {result.stderr}")
                    all_results[psm] = f"ERROR: {result.stderr}"

            if not best_text:
                print("❌ Все режимы PSM не сработали!")
                print("📊 Все результаты:")
                for psm, text in all_results.items():
                    print(f"PSM {psm}: {text}")
                raise Exception("Не удалось извлечь текст ни одним режимом")

            print(f"📝 Лучший результат (длина: {len(best_text)}):")
            print("=" * 50)
            print(best_text)
            print("=" * 50)
            return best_text

        except subprocess.TimeoutExpired:
            raise Exception("Tesseract timeout")
        except Exception as e:
            raise Exception(f"OCR error: {str(e)}")

    def parse_receipt(self, text: str) -> dict:
        """Парсит данные чека из текста с поиском конкретных значений."""
        print(f"🔍 Парсинг текста для поиска конкретных значений...")
        print(f"🎯 Ищем сумму: {self.target_amount}")
        print(f"🎯 Ищем номер: {self.target_phone_formatted}")

        data = {
            'amount': None,
            'account': None,
            'date': None,
            'raw_text': text,
            'target_amount_found': False,
            'target_phone_found': False
        }

        # Поиск конкретной суммы 1500
        data['amount'] = self._find_target_amount(text)
        if data['amount'] == self.target_amount:
            data['target_amount_found'] = True
            print(f"✅ Найдена целевая сумма: {self.target_amount}")

        # Поиск конкретного номера телефона
        data['account'] = self._find_target_phone(text)
        if data['account']:
            data['target_phone_found'] = True
            print(f"✅ Найден целевой номер телефона: {data['account']}")

        # Поиск даты
        data['date'] = self._find_date(text)

        print(f"📊 Результат парсинга: {data}")
        return data

    def _find_target_amount(self, text: str) -> Optional[float]:
        """Ищет конкретную сумму 1500 в тексте."""
        print(f"🔍 Поиск суммы {self.target_amount}...")

        # Различные варианты написания суммы 1500
        amount_variants = [
            str(self.target_amount),           # 1500
            f"{self.target_amount} руб",       # 1500 руб
            f"{self.target_amount} ₽",         # 1500 ₽
            f"{self.target_amount} р.",        # 1500 р.
            f"{self.target_amount},00",        # 1500,00
            f"{self.target_amount}.00",        # 1500.00
            f"{self.target_amount}Р",          # 1500Р
        ]

        for variant in amount_variants:
            if variant in text:
                print(f"💰 Найдена сумма {variant}")
                return float(self.target_amount)

        # Поиск с пробелами
        spaced_amount = f"{self.target_amount//1000} {self.target_amount%1000:03d}"
        if spaced_amount in text:
            print(f"💰 Найдена сумма с пробелом: {spaced_amount}")
            return float(self.target_amount)

        print(f"❌ Сумма {self.target_amount} не найдена")
        return None

    def _find_target_phone(self, text: str) -> Optional[str]:
        """Ищет конкретный номер телефона в тексте."""
        print(f"🔍 Поиск номера телефона {self.target_phone_formatted}...")

        # Различные варианты написания номера
        phone_variants = [
            self.target_phone,                    # 79879335515
            self.target_phone_formatted,          # 7 987 933 55 15
            f"+{self.target_phone}",              # +79879335515
            f"+{self.target_phone[:1]} {self.target_phone[1:4]} {self.target_phone[4:7]} {self.target_phone[7:9]} {self.target_phone[9:11]}",  # +7 987 933 55 15
            f"8{self.target_phone[1:]}",          # 89879335515
            f"8 {self.target_phone[1:4]} {self.target_phone[4:7]} {self.target_phone[7:9]} {self.target_phone[9:11]}",  # 8 987 933 55 15
        ]

        for variant in phone_variants:
            if variant in text:
                print(f"📱 Найден номер телефона: {variant}")
                return variant

        # Поиск с помощью регулярного выражения
        phone_patterns = [
            r'\+?7\s*9\s*8\s*7\s*9\s*3\s*3\s*5\s*5\s*1\s*5',
            r'\+?7\s*987\s*933\s*55\s*15',
            r'\+?7\s*987\s*933\s*5515',
            r'\+?79879335515',
        ]

        for pattern in phone_patterns:
            match = re.search(pattern, text)
            if match:
                found_phone = match.group(0).strip()
                print(f"📱 Найден номер телефона по паттерну: {found_phone}")
                return found_phone

        print(f"❌ Номер телефона {self.target_phone_formatted} не найден")
        return None

    def _find_date(self, text: str) -> Optional[str]:
        """Ищет дату в тексте."""
        date_patterns = [
            r'(\d{1,2}[./]\d{1,2}[./]\d{2,4})',
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{1,2}\s+\d{1,2}\s+\d{2,4})',
        ]

        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                date = matches[0]
                print(f"📅 Найдена дата: {date}")
                return date

        return None

    def validate_receipt(self, data: dict) -> dict:
        """Валидирует данные чека по конкретным значениям."""
        result = {
            'valid': False,
            'errors': [],
            'warnings': []
        }

        # Проверяем, найдены ли оба целевых значения
        if data['target_amount_found'] and data['target_phone_found']:
            result['valid'] = True
            result['warnings'].append("Найдены все целевые значения!")
        else:
            if not data['target_amount_found']:
                result['errors'].append(f"Не найдена целевая сумма {self.target_amount}")
            if not data['target_phone_found']:
                result['errors'].append(f"Не найден целевой номер телефона {self.target_phone_formatted}")

        # Дополнительная информация
        if data['amount']:
            result['warnings'].append(f"Найдена сумма: {data['amount']}")
        if data['account']:
            result['warnings'].append(f"Найден номер: {data['account']}")
        if data['date']:
            result['warnings'].append(f"Найдена дата: {data['date']}")

        return result

# Создаем экземпляр проверяльщика
checker = ReceiptChecker()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    await update.message.reply_text(
        "🤖 **Бот проверки чеков v4 - поиск конкретных значений**\n\n"
        "🎯 **Ищем в чеке:**\n"
        f"• Сумму: **{checker.target_amount} руб**\n"
        f"• Номер телефона: **{checker.target_phone_formatted}**\n\n"
        "✅ **Если найдены оба значения - чек валиден!**\n\n"
        "📸 **Отправьте фотографию чека или PDF файл для проверки**"
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографий."""
    print("=" * 60)
    print("📸 ПОЛУЧЕНО ФОТО ОТ ПОЛЬЗОВАТЕЛЯ")
    print("=" * 60)
    await update.message.reply_text("📸 Фото получено! Ищу конкретные значения...")

    try:
        # Получаем файл
        file = await context.bot.get_file(update.message.photo[-1].file_id)
        print(f"📁 Файл получен: {file.file_id}")
        print(f"📁 Размер файла: {file.file_size} байт")

        # Создаем временный файл
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
            await file.download_to_drive(temp_file.name)
            print(f"💾 Файл сохранен: {temp_file.name}")

            # Проверяем размер файла
            file_size = os.path.getsize(temp_file.name)
            print(f"💾 Размер сохраненного файла: {file_size} байт")

            # Обрабатываем чек
            print("🔍 НАЧИНАЮ ПОИСК КОНКРЕТНЫХ ЗНАЧЕНИЙ...")
            result = await checker.process_receipt(temp_file.name)
            print("=" * 60)
            print("✅ ОБРАБОТКА ЗАВЕРШЕНА")
            print("=" * 60)
            print(f"📊 Результат: {result}")
            print("=" * 60)

            # Удаляем временный файл
            os.unlink(temp_file.name)
            print(f"🗑️ Временный файл удален: {temp_file.name}")

        if result['success']:
            # Отправляем результат
            await send_result(update, result)
        else:
            await update.message.reply_text(f"❌ Ошибка обработки: {result['error']}")

    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
        import traceback
        print(f"📋 Traceback: {traceback.format_exc()}")
        await update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик документов (PDF)."""
    document = update.message.document

    # Проверяем, что это PDF
    if not document.file_name.lower().endswith('.pdf'):
        await update.message.reply_text("❌ Поддерживаются только PDF файлы. Отправьте PDF документ.")
        return

    print("=" * 60)
    print("📄 ПОЛУЧЕН PDF ДОКУМЕНТ")
    print("=" * 60)
    await update.message.reply_text("📄 PDF получен! Ищу конкретные значения...")

    try:
        # Получаем файл
        file = await context.bot.get_file(document.file_id)
        print(f"📁 Файл получен: {file.file_id}")
        print(f"📁 Имя файла: {document.file_name}")
        print(f"📁 Размер файла: {document.file_size} байт")

        # Создаем временный файл
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            await file.download_to_drive(temp_file.name)
            print(f"💾 Файл сохранен: {temp_file.name}")

            # Проверяем размер файла
            file_size = os.path.getsize(temp_file.name)
            print(f"💾 Размер сохраненного файла: {file_size} байт")

            # Обрабатываем чек
            print("🔍 НАЧИНАЮ ПОИСК КОНКРЕТНЫХ ЗНАЧЕНИЙ...")
            result = await checker.process_receipt(temp_file.name)
            print("=" * 60)
            print("✅ ОБРАБОТКА ЗАВЕРШЕНА")
            print("=" * 60)
            print(f"📊 Результат: {result}")
            print("=" * 60)

            # Удаляем временный файл
            os.unlink(temp_file.name)
            print(f"🗑️ Временный файл удален: {temp_file.name}")

        if result['success']:
            # Отправляем результат
            await send_result(update, result)
        else:
            await update.message.reply_text(f"❌ Ошибка обработки: {result['error']}")

    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
        import traceback
        print(f"📋 Traceback: {traceback.format_exc()}")
        await update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")

async def send_result(update: Update, result: dict):
    """Отправляет результат проверки."""
    data = result['data']
    validation = result['validation']

    # Формируем сообщение
    message = "📊 **Результат поиска конкретных значений (v4):**\n\n"

    # Показываем найденные значения
    if data['target_amount_found']:
        message += f"✅ **Сумма {checker.target_amount}:** найдена!\n"
    else:
        message += f"❌ **Сумма {checker.target_amount}:** не найдена\n"

    if data['target_phone_found']:
        message += f"✅ **Номер {checker.target_phone_formatted}:** найден!\n"
    else:
        message += f"❌ **Номер {checker.target_phone_formatted}:** не найден\n"

    message += "\n"

    if validation['valid']:
        message += "🎉 **СТАТУС: ЧЕК ВАЛИДЕН!**\n"
        message += "✅ Найдены все целевые значения!\n"
    else:
        message += "❌ **СТАТУС: ЧЕК НЕ ВАЛИДЕН**\n"
        message += "🚫 Не найдены все целевые значения\n"

    if validation['warnings']:
        message += "\n📋 **Найденная информация:**\n"
        for warning in validation['warnings']:
            message += f"• {warning}\n"

    if validation['errors']:
        message += "\n🚫 **Ошибки:**\n"
        for error in validation['errors']:
            message += f"• {error}\n"

    await update.message.reply_text(message)

def main():
    """Основная функция."""
    print("Запуск бота проверки чеков v4 (поиск конкретных значений)...")
    print(f"Токен бота: {BOT_TOKEN[:20]}...")
    print(f"🎯 Ищем сумму: {checker.target_amount}")
    print(f"🎯 Ищем номер: {checker.target_phone_formatted}")

    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("Бот v4 запущен и готов к работе!")
    print("Ожидаю сообщения...")

    # Запускаем бота
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Бот остановлен пользователем")
    except Exception as e:
        print(f"Ошибка: {e}")
