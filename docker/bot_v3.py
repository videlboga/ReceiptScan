#!/usr/bin/env python3
"""Улучшенная версия бота для проверки чеков с исправленным парсингом."""
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
from bot_config import VALIDATION_CONFIG, PARSING_CONFIG, OCR_CONFIG, BOT_CONFIG

# Получаем токен из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN', '7922755841:AAG12lYZ2B8X5-ByauPXwppqCwZfnU-FjJo')

class ReceiptChecker:
    """Улучшенный класс для проверки чеков с исправленным парсингом."""

    def __init__(self):
        self.validation_rules = VALIDATION_CONFIG
        self.parsing_rules = PARSING_CONFIG
        self.ocr_config = OCR_CONFIG

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
            psm_modes = self.ocr_config['psm_modes']
            best_text = ""
            all_results = {}

            for psm in psm_modes:
                print(f"🔍 Пробую режим PSM {psm}")
                result = subprocess.run([
                    'tesseract', image_path, 'stdout',
                    '-l', self.ocr_config['languages'], '--psm', psm,
                    '--oem', self.ocr_config['oem_mode']
                ], capture_output=True, text=True, timeout=self.ocr_config['timeout'])

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
        """Улучшенный парсер данных чека из текста."""
        print(f"🔍 Парсинг текста: {text[:200]}...")

        data = {
            'amount': None,
            'account': None,
            'date': None,
            'raw_text': text
        }

        # Сначала ищем даты, чтобы исключить их из поиска сумм
        date_patterns = [
            r'(\d{1,2}[./]\d{1,2}[./]\d{2,4})',
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{1,2}\s+\d{1,2}\s+\d{2,4})',
            r'дата[:\s]*(\d{1,2}[./]\d{1,2}[./]\d{2,4})',
        ]

        dates_found = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            dates_found.extend(matches)

        print(f"📅 Найденные даты: {dates_found}")

        # Ищем сумму с улучшенной логикой
        data['amount'] = self._find_amount(text, dates_found)

        # Ищем номер счета, телефона или карты
        account_patterns = [
            # Названия карт с номерами (приоритет)
            r'счёт[:\s]*списания[:\s]*([^•]+?)\s*•+\s*(\d+)',
            r'счет[:\s]*списания[:\s]*([^•]+?)\s*•+\s*(\d+)',
            r'карта[:\s]*([^•]+?)\s*•+\s*(\d+)',
            r'МИР[:\s]*([^•]+?)\s*•+\s*(\d+)',
            r'VISA[:\s]*([^•]+?)\s*•+\s*(\d+)',
            r'MASTERCARD[:\s]*([^•]+?)\s*•+\s*(\d+)',
            
            # Номера карт (16 цифр)
            r'(\d{16})',  # 16 цифр подряд
            r'(\d{4}\s*\d{4}\s*\d{4}\s*\d{4})',  # С пробелами
            r'номер[:\s]*карты[:\s]*(\d{16})',
            r'номер[:\s]*карты[:\s]*(\d{4}\s*\d{4}\s*\d{4}\s*\d{4})',
            r'карта[:\s]*(\d{16})',
            r'карта[:\s]*(\d{4}\s*\d{4}\s*\d{4}\s*\d{4})',
            r'по\s*номеру\s*карты[:\s]*(\d{16})',
            r'по\s*номеру\s*карты[:\s]*(\d{4}\s*\d{4}\s*\d{4}\s*\d{4})',

            # Банковские счета (20 цифр)
            r'(\d{20})',
            r'(\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4})',
            r'счет[:\s]*(\d{16,20})',
            r'получатель[:\s]*(\d{16,20})',
            r'р/с[:\s]*(\d{16,20})',
            r'расчетный[:\s]*счет[:\s]*(\d{16,20})',

            # Номера телефонов
            r'(\+7\s*\d{3}\s*\d{3}\s*\d{2}\s*\d{2})',
            r'(8\s*\d{3}\s*\d{3}\s*\d{2}\s*\d{2})',
            r'(\d{3}\s*\d{3}\s*\d{2}\s*\d{2})',
            r'телефон[:\s]*(\+?[78]\s*\d{3}\s*\d{3}\s*\d{2}\s*\d{2})',
        ]

        for pattern in account_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Обрабатываем разные типы совпадений
                if len(match.groups()) >= 2:
                    # Паттерн с названием карты и номером
                    card_name = match.group(1).strip()
                    card_number = match.group(2).strip()
                    data['account'] = f"{card_name} •• {card_number}"
                    print(f"💳 Найден счет карты: {card_name} •• {card_number}")
                    break
                else:
                    # Обычный паттерн с номером
                    account = re.sub(r'\s+', '', match.group(1))  # Убираем пробелы

                    # Проверяем тип найденного номера
                    if len(account) == 20 and account.isdigit():
                        data['account'] = account
                        print(f"🏦 Найден банковский счет: {account}")
                        break
                    elif len(account) == 16 and account.isdigit():
                        data['account'] = account
                        print(f"💳 Найден номер карты: {account}")
                        break
                    elif len(account) >= 10 and (account.startswith('7') or account.startswith('8')):
                        data['account'] = account
                        print(f"📱 Найден номер телефона: {account}")
                        break

        # Сохраняем первую найденную дату
        if dates_found:
            data['date'] = dates_found[0]
            print(f"📅 Найдена дата: {dates_found[0]}")

        print(f"📊 Результат парсинга: {data}")
        return data

    def _find_amount(self, text: str, dates_found: list) -> Optional[float]:
        """Находит сумму с улучшенной логикой, исключая курсы валют."""
        print("🔍 Поиск суммы с улучшенной логикой...")

        # Сначала ищем суммы с ключевыми словами (приоритет)
        for keyword in self.parsing_rules['amount_keywords']:
            patterns = [
                rf'{keyword}[:\s]*(\d+)\s*руб',
                rf'{keyword}[:\s]*(\d+[.,]\d{{2}})\s*руб',
                rf'{keyword}[:\s]*(\d+)\s*₽',
                rf'{keyword}[:\s]*(\d+[.,]\d{{2}})\s*₽',
                rf'{keyword}[:\s]*(\d+)\s*р\.',
                rf'{keyword}[:\s]*(\d+[.,]\d{{2}})\s*р\.',
            ]

            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    amount_str = match.group(1).replace(',', '.')
                    try:
                        amount = float(amount_str)
                        if self.validation_rules['min_amount'] <= amount <= self.validation_rules['max_amount']:
                            print(f"💰 Найдена сумма по ключевому слову '{keyword}': {amount}")
                            return amount
                    except ValueError:
                        continue

        # Затем ищем суммы с валютными обозначениями, но проверяем контекст
        amount_patterns = [
            r'(\d+)\s*руб',
            r'(\d+[.,]\d{2})\s*руб',
            r'(\d+)\s*₽',
            r'(\d+[.,]\d{2})\s*₽',
            r'(\d+)\s*р\.',
            r'(\d+[.,]\d{2})\s*р\.',
        ]

        for pattern in amount_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                amount_str = match.group(1).replace(',', '.')
                try:
                    amount = float(amount_str)
                    if self.validation_rules['min_amount'] <= amount <= self.validation_rules['max_amount']:
                        # Проверяем контекст - не является ли это курсом валют
                        start_pos = max(0, match.start() - 50)
                        end_pos = min(len(text), match.end() + 50)
                        context = text[start_pos:end_pos].lower()

                        # Проверяем, есть ли слова-исключения в контексте
                        # Исключаем только если это явно курс валют, а не просто сумма с упоминанием валюты
                        has_exclusion = False
                        for exclusion in self.parsing_rules['amount_exclusions']:
                            if exclusion in context:
                                # Дополнительная проверка - исключаем только если это действительно курс
                                if 'курс' in exclusion or 'обмен' in exclusion or 'exchange' in exclusion:
                                    has_exclusion = True
                                    break

                        if not has_exclusion:
                            print(f"💰 Найдена сумма: {amount} (контекст: {context})")
                            return amount
                        else:
                            print(f"⚠️ Пропущена сумма {amount} - найдены слова-исключения в контексте: {context}")
                except ValueError:
                    continue

        # Если не нашли сумму с валютой, ищем числа с копейками, исключая даты и курсы
        all_numbers = re.findall(r'(\d+[.,]\d{2})', text)
        print(f"🔢 Все числа с копейками: {all_numbers}")

        for number_str in all_numbers:
            # Проверяем, не является ли это датой
            is_date = any(number_str in date or date in number_str for date in dates_found)

            if not is_date:
                try:
                    amount = float(number_str.replace(',', '.'))
                    if self.validation_rules['min_amount'] <= amount <= self.validation_rules['max_amount']:
                        # Находим позицию числа в тексте для проверки контекста
                        pos = text.find(number_str)
                        if pos != -1:
                            start_pos = max(0, pos - 50)
                            end_pos = min(len(text), pos + len(number_str) + 50)
                            context = text[start_pos:end_pos].lower()

                            # Проверяем контекст на исключения
                            has_exclusion = False
                            for exclusion in self.parsing_rules['amount_exclusions']:
                                if exclusion in context:
                                    # Дополнительная проверка - исключаем только если это действительно курс
                                    if 'курс' in exclusion or 'обмен' in exclusion or 'exchange' in exclusion:
                                        has_exclusion = True
                                        break

                            if not has_exclusion:
                                print(f"💰 Найдена сумма (без валюты): {amount}")
                                return amount
                            else:
                                print(f"⚠️ Пропущена сумма {amount} - найдены слова-исключения: {context}")
                except ValueError:
                    continue

        print("❌ Сумма не найдена")
        return None

    def validate_receipt(self, data: dict) -> dict:
        """Валидирует данные чека."""
        result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }

        # Проверяем сумму
        if data['amount'] is None:
            result['valid'] = False
            result['errors'].append("Не удалось определить сумму")
        elif data['amount'] < self.validation_rules['min_amount']:
            result['valid'] = False
            result['errors'].append(f"Сумма слишком мала (минимум {self.validation_rules['min_amount']} руб)")
        elif data['amount'] > self.validation_rules['max_amount']:
            result['valid'] = False
            result['errors'].append(f"Сумма слишком велика (максимум {self.validation_rules['max_amount']} руб)")

        # Проверяем счет/карту/телефон
        if data['account'] is None:
            result['warnings'].append("Не удалось определить номер счета/карты/телефона")
        else:
            account = data['account']
            is_valid = False

            # Проверяем по типу номера
            if len(account) == 20 and account.isdigit():
                # Банковский счет
                if account in self.validation_rules['valid_accounts']:
                    is_valid = True
            elif len(account) == 16 and account.isdigit():
                # Номер карты
                if account in self.validation_rules['valid_cards']:
                    is_valid = True
            elif len(account) >= 10 and (account.startswith('7') or account.startswith('8')):
                # Номер телефона
                if account in self.validation_rules['valid_phones']:
                    is_valid = True
            else:
                # Проверяем названия карт
                for valid_card in self.validation_rules['valid_cards']:
                    if valid_card in account:
                        is_valid = True
                        break

            if not is_valid:
                result['warnings'].append("Номер счета/карты/телефона не найден в списке валидных")

        # Проверяем дату
        if data['date'] is None:
            result['warnings'].append("Не удалось определить дату")

        return result

# Создаем экземпляр проверяльщика
checker = ReceiptChecker()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    await update.message.reply_text(
        "🤖 **Добро пожаловать в бот проверки чеков! (v3 - улучшенная версия)**\n\n"
        "📋 **Функции бота:**\n"
        "• Проверка чеков на подлинность\n"
        "• Извлечение данных с помощью OCR\n"
        "• Валидация суммы и номера счета\n"
        "• Выдача сертификата при успешной проверке\n\n"
        "📸 **Отправьте фотографию чека или PDF файл для проверки**"
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографий."""
    print("=" * 60)
    print("📸 ПОЛУЧЕНО ФОТО ОТ ПОЛЬЗОВАТЕЛЯ")
    print("=" * 60)
    await update.message.reply_text("📸 Фото получено! Обрабатываю...")

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
            print("🔍 НАЧИНАЮ ОБРАБОТКУ ЧЕКА...")
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
    await update.message.reply_text("📄 PDF получен! Обрабатываю...")

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
            print("🔍 НАЧИНАЮ ОБРАБОТКУ PDF...")
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
    message = "📊 **Результат проверки чека (v3):**\n\n"

    if data['amount']:
        message += f"💰 **Сумма:** {data['amount']:.2f} руб\n"
    else:
        message += "💰 **Сумма:** не определена\n"

    if data['account']:
        # Определяем тип счета
        account = data['account']
        if len(account) == 20 and account.isdigit():
            account_type = "🏦 Банковский счет"
        elif len(account) == 16 and account.isdigit():
            account_type = "💳 Номер карты"
        elif len(account) >= 10 and (account.startswith('7') or account.startswith('8')):
            account_type = "📱 Номер телефона"
        else:
            account_type = "💳 Карта"

        message += f"{account_type}: {account}\n"
    else:
        message += "🔢 **Номер счета/карты/телефона:** не определен\n"

    if data['date']:
        message += f"📅 **Дата:** {data['date']}\n"
    else:
        message += "📅 **Дата:** не определена\n"

    message += "\n"

    if validation['valid']:
        message += "✅ **Статус:** Чек валиден\n"
        if validation['warnings']:
            message += "\n⚠️ **Предупреждения:**\n"
            for warning in validation['warnings']:
                message += f"• {warning}\n"

        # Отправляем сертификат
        await send_certificate(update, data)
    else:
        message += "❌ **Статус:** Чек не валиден\n"
        if validation['errors']:
            message += "\n🚫 **Ошибки:**\n"
            for error in validation['errors']:
                message += f"• {error}\n"

    await update.message.reply_text(message)

async def send_certificate(update: Update, data: dict):
    """Отправляет сертификат о проверке."""
    certificate_text = f"""
📜 **СЕРТИФИКАТ ПРОВЕРКИ ЧЕКА (v3)**

✅ Чек успешно проверен и признан валидным

📊 **Данные чека:**
• Сумма: {data['amount']:.2f} руб
• Счет: {data['account'] or 'не определен'}
• Дата: {data['date'] or 'не определена'}

🕐 Время проверки: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

🤖 Проверено улучшенным ботом проверки чеков v3
"""

    await update.message.reply_text(certificate_text)

def main():
    """Основная функция."""
    print("Запуск улучшенного бота проверки чеков v3...")
    print(f"Токен бота: {BOT_TOKEN[:20]}...")

    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("Улучшенный бот v3 запущен и готов к работе!")
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
