"""Парсер для извлечения данных из чеков."""
import re
from datetime import datetime
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from loguru import logger

@dataclass
class ReceiptData:
    """Структура данных чека."""
    amount: Optional[float] = None
    recipient_account: Optional[str] = None
    date: Optional[datetime] = None
    time: Optional[datetime] = None
    raw_text: str = ""
    confidence: float = 0.0
    items: list = None

    def __post_init__(self):
        if self.items is None:
            self.items = []

class ReceiptParser:
    """Парсер для извлечения структурированных данных из текста чеков."""

    def __init__(self):
        # Паттерны для поиска сумм
        self.amount_patterns = [
            r'(?:сумма|итого|к оплате|total|amount)[\s:]*(\d+(?:[.,]\d{2})?)',
            r'(\d+(?:[.,]\d{2})?)\s*(?:руб|₽|rub|р\.)',
            r'(\d+(?:[.,]\d{2})?)\s*(?:€|eur|euro)',
            r'(\d+(?:[.,]\d{2})?)\s*(?:\$|usd|dollar)',
        ]

        # Паттерны для поиска счетов
        self.account_patterns = [
            r'(?:счет|account|номер счета)[\s:]*(\d{20})',
            r'(?:получатель|recipient)[\s:]*([А-Яа-я\s]+)',
            r'(\d{20})',  # Просто 20-значный номер
        ]

        # Паттерны для даты
        self.date_patterns = [
            r'(\d{1,2})[./](\d{1,2})[./](\d{4})',
            r'(\d{4})[./](\d{1,2})[./](\d{1,2})',
            r'(\d{1,2})\s+(?:янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек)\w*\s+(\d{4})',
        ]

        # Паттерны для времени
        self.time_patterns = [
            r'(\d{1,2}):(\d{2})(?::(\d{2}))?',
        ]

        # Словарь месяцев
        self.months = {
            'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'июн': 6,
            'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
        }

    def parse_receipt(self, text: str, confidence: float = 0.0) -> ReceiptData:
        """
        Парсит текст чека и извлекает структурированные данные.

        Args:
            text: Текст чека
            confidence: Уверенность распознавания

        Returns:
            ReceiptData: Структурированные данные чека
        """
        receipt_data = ReceiptData(
            raw_text=text,
            confidence=confidence
        )

        # Извлекаем сумму
        receipt_data.amount = self._extract_amount(text)

        # Извлекаем счет получателя
        receipt_data.recipient_account = self._extract_account(text)

        # Извлекаем дату и время
        receipt_data.date, receipt_data.time = self._extract_datetime(text)

        # Извлекаем товары/услуги
        receipt_data.items = self._extract_items(text)

        if logger.level("DEBUG").no <= logger._core.min_level:
            logger.debug(f"Распарсенные данные: {receipt_data}")

        return receipt_data

    def _extract_amount(self, text: str) -> Optional[float]:
        """Извлекает сумму из текста."""
        text_lower = text.lower()

        for pattern in self.amount_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            if matches:
                try:
                    # Берем последнее найденное значение (обычно итоговая сумма)
                    amount_str = matches[-1].replace(',', '.')
                    amount = float(amount_str)
                    logger.info(f"Найдена сумма: {amount}")
                    return amount
                except ValueError:
                    continue

        logger.warning("Сумма не найдена в тексте чека")
        return None

    def _extract_account(self, text: str) -> Optional[str]:
        """Извлекает счет получателя из текста."""
        text_lower = text.lower()

        for pattern in self.account_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            if matches:
                account = matches[0].strip()
                logger.info(f"Найден счет: {account}")
                return account

        logger.warning("Счет получателя не найден в тексте чека")
        return None

    def _extract_datetime(self, text: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Извлекает дату и время из текста."""
        date = None
        time = None

        # Ищем дату
        for pattern in self.date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    match = matches[0]
                    if len(match) == 3:  # ДД.ММ.ГГГГ или ГГГГ.ММ.ДД
                        if len(match[0]) == 4:  # ГГГГ.ММ.ДД
                            year, month, day = match
                        else:  # ДД.ММ.ГГГГ
                            day, month, year = match
                        date = datetime(int(year), int(month), int(day))
                        logger.info(f"Найдена дата: {date.date()}")
                        break
                    elif len(match) == 2:  # ДД МММ ГГГГ
                        day, month_name, year = match
                        month = self.months.get(month_name.lower()[:3])
                        if month:
                            date = datetime(int(year), month, int(day))
                            logger.info(f"Найдена дата: {date.date()}")
                            break
                except (ValueError, TypeError):
                    continue

        # Ищем время
        for pattern in self.time_patterns:
            matches = re.findall(pattern, text)
            if matches:
                try:
                    match = matches[0]
                    hour, minute = int(match[0]), int(match[1])
                    second = int(match[2]) if len(match) > 2 and match[2] else 0
                    time = datetime(1900, 1, 1, hour, minute, second)
                    logger.info(f"Найдено время: {time.time()}")
                    break
                except (ValueError, TypeError):
                    continue

        return date, time

    def _extract_items(self, text: str) -> list:
        """Извлекает список товаров/услуг из чека."""
        items = []
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Ищем строки с товарами (содержат цену)
            if re.search(r'\d+(?:[.,]\d{2})?', line):
                # Пытаемся разделить название и цену
                parts = re.split(r'\s+(\d+(?:[.,]\d{2})?)\s*', line)
                if len(parts) >= 2:
                    name = parts[0].strip()
                    price_str = parts[1].replace(',', '.')
                    try:
                        price = float(price_str)
                        items.append({
                            'name': name,
                            'price': price
                        })
                    except ValueError:
                        continue

        logger.info(f"Найдено товаров: {len(items)}")
        return items

    def validate_receipt_data(self, receipt_data: ReceiptData) -> Dict[str, bool]:
        """
        Проверяет корректность извлеченных данных.

        Args:
            receipt_data: Данные чека

        Returns:
            Dict[str, bool]: Результаты валидации
        """
        validation_results = {
            'has_amount': receipt_data.amount is not None and receipt_data.amount > 0,
            'has_account': receipt_data.recipient_account is not None and len(receipt_data.recipient_account) > 0,
            'has_date': receipt_data.date is not None,
            'has_items': len(receipt_data.items) > 0,
            'confidence_ok': receipt_data.confidence > 50.0,  # Минимальная уверенность 50%
        }

        validation_results['is_valid'] = all([
            validation_results['has_amount'],
            validation_results['has_account'],
            validation_results['confidence_ok']
        ])

        return validation_results
