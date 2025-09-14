"""Гибкий парсер для извлечения данных из чеков с поддержкой различных форматов номеров."""
import re
import yaml
from datetime import datetime
from typing import Dict, Optional, Tuple, List, Any
from dataclasses import dataclass
from loguru import logger
from pathlib import Path

@dataclass
class ParsedData:
    """Структура распарсенных данных чека."""
    amount: Optional[float] = None
    recipient_phone: Optional[str] = None
    recipient_account: Optional[str] = None
    date: Optional[datetime] = None
    time: Optional[datetime] = None
    raw_text: str = ""
    confidence: float = 0.0
    items: List[Dict] = None
    validation_matches: Dict[str, bool] = None

    def __post_init__(self):
        if self.items is None:
            self.items = []
        if self.validation_matches is None:
            self.validation_matches = {}

class FlexibleReceiptParser:
    """Гибкий парсер чеков с настраиваемыми правилами."""

    def __init__(self, config_path: str = None):
        """
        Инициализация парсера.

        Args:
            config_path: Путь к YAML конфигурации
        """
        self.config = self._load_config(config_path)
        self._compile_patterns()

    def _load_config(self, config_path: str = None) -> Dict:
        """Загружает конфигурацию из YAML файла."""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "validation_config_v1.yaml"

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"Конфигурация загружена из {config_path}")
            return config
        except FileNotFoundError:
            logger.warning(f"Файл конфигурации {config_path} не найден, используем значения по умолчанию")
            return self._get_default_config()
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """Возвращает конфигурацию по умолчанию."""
        return {
            'phone_validation': {
                'patterns': [
                    {'pattern': '(\+?7|8)[\s\-\(\)]?(\d{3})[\s\-\(\)]?(\d{3})[\s\-\(\)]?(\d{2})[\s\-\(\)]?(\d{2})', 'description': 'Российский номер'},
                    {'pattern': '(\+?7|8)[\s\-\(\)]?(\d{3})[\s\-\(\)]?(\d{3})[\s\-\(\)]?(\d{4})', 'description': 'Российский номер 3-3-4'},
                    {'pattern': '(\+?7|8)(\d{10})', 'description': 'Российский номер без разделителей'}
                ],
                'valid_phones': ['79879335515', '+79879335515', '89879335515'],
                'keywords': ['телефон', 'номер телефона', 'мобильный', 'на телефон']
            },
            'amount_validation': {
                'patterns': [
                    {'pattern': '(\d+(?:[.,]\d{2})?)\s*(?:руб|₽|rub|р\.)', 'description': 'Сумма в рублях'},
                    {'pattern': '(?:сумма|итого|к оплате)[\s:]*(\d+(?:[.,]\d{2})?)', 'description': 'Сумма с ключевым словом'}
                ],
                'valid_amounts': [1500.00, 1500, 1500.0],
                'keywords': ['сумма', 'итого', 'к оплате', 'перевод']
            },
            'account_validation': {
                'patterns': [
                    {'pattern': '(\d{20})', 'description': '20-значный счет'},
                    {'pattern': '(\d{16})', 'description': '16-значная карта'}
                ],
                'valid_accounts': ['40817810099910004312'],
                'valid_cards': ['2200590431900533'],
                'keywords': ['счет', 'карта', 'получатель']
            }
        }

    def _compile_patterns(self):
        """Компилирует регулярные выражения для ускорения работы."""
        self.compiled_patterns = {}

        # Компилируем паттерны для телефонов
        self.compiled_patterns['phone'] = []
        for pattern_info in self.config['phone_validation']['patterns']:
            try:
                compiled = re.compile(pattern_info['pattern'], re.IGNORECASE)
                self.compiled_patterns['phone'].append({
                    'pattern': compiled,
                    'description': pattern_info['description'],
                    'country_code': pattern_info.get('country_code', '+7')
                })
            except re.error as e:
                logger.warning(f"Ошибка компиляции паттерна телефона: {e}")

        # Компилируем паттерны для сумм
        self.compiled_patterns['amount'] = []
        for pattern_info in self.config['amount_validation']['patterns']:
            try:
                compiled = re.compile(pattern_info['pattern'], re.IGNORECASE)
                self.compiled_patterns['amount'].append({
                    'pattern': compiled,
                    'description': pattern_info['description'],
                    'currency': pattern_info.get('currency', 'RUB')
                })
            except re.error as e:
                logger.warning(f"Ошибка компиляции паттерна суммы: {e}")

        # Компилируем паттерны для счетов
        self.compiled_patterns['account'] = []
        for pattern_info in self.config['account_validation']['patterns']:
            try:
                compiled = re.compile(pattern_info['pattern'], re.IGNORECASE)
                self.compiled_patterns['account'].append({
                    'pattern': compiled,
                    'description': pattern_info['description'],
                    'type': pattern_info.get('type', 'unknown')
                })
            except re.error as e:
                logger.warning(f"Ошибка компиляции паттерна счета: {e}")

    def parse_receipt(self, text: str, confidence: float = 0.0) -> ParsedData:
        """
        Парсит текст чека и извлекает структурированные данные.

        Args:
            text: Текст чека
            confidence: Уверенность распознавания

        Returns:
            ParsedData: Структурированные данные чека
        """
        logger.info("Начинаем парсинг чека с гибкими правилами")

        parsed_data = ParsedData(
            raw_text=text,
            confidence=confidence
        )

        # Извлекаем сумму
        parsed_data.amount = self._extract_amount(text)

        # Извлекаем номер телефона
        parsed_data.recipient_phone = self._extract_phone(text)

        # Извлекаем банковский счет/карту
        parsed_data.recipient_account = self._extract_account(text)

        # Извлекаем дату и время
        parsed_data.date, parsed_data.time = self._extract_datetime(text)

        # Извлекаем товары/услуги
        parsed_data.items = self._extract_items(text)

        # Проверяем соответствие валидным значениям
        parsed_data.validation_matches = self._validate_against_config(parsed_data)

        logger.info(f"Парсинг завершен. Найдено: сумма={parsed_data.amount}, "
                   f"телефон={parsed_data.recipient_phone}, "
                   f"счет={parsed_data.recipient_account}")

        return parsed_data

    def _extract_phone(self, text: str) -> Optional[str]:
        """Извлекает номер телефона из текста с поддержкой различных форматов."""
        logger.debug("Поиск номера телефона...")

        # Сначала ищем по ключевым словам
        phone_keywords = self.config['phone_validation']['keywords']
        for keyword in phone_keywords:
            keyword_pattern = f"{keyword}[\\s:]*([\\d\\s\\-\\(\\)\\+]+)"
            matches = re.findall(keyword_pattern, text, re.IGNORECASE)
            if matches:
                potential_phone = matches[0].strip()
                normalized = self._normalize_phone(potential_phone)
                if normalized:
                    logger.info(f"Найден номер телефона по ключевому слову '{keyword}': {normalized}")
                    return normalized

        # Затем ищем по паттернам
        for pattern_info in self.compiled_patterns['phone']:
            matches = pattern_info['pattern'].findall(text)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        # Объединяем группы
                        phone_parts = [part for part in match if part]
                        potential_phone = ''.join(phone_parts)
                    else:
                        potential_phone = match

                    normalized = self._normalize_phone(potential_phone)
                    if normalized:
                        logger.info(f"Найден номер телефона по паттерну '{pattern_info['description']}': {normalized}")
                        return normalized

        logger.warning("Номер телефона не найден")
        return None

    def _normalize_phone(self, phone: str) -> Optional[str]:
        """Нормализует номер телефона к стандартному формату."""
        if not phone:
            return None

        # Убираем все символы кроме цифр и плюса
        cleaned = re.sub(r'[^\d\+]', '', phone)

        # Проверяем длину и формат
        if len(cleaned) == 11 and cleaned.startswith('7'):
            return cleaned
        elif len(cleaned) == 11 and cleaned.startswith('8'):
            return '7' + cleaned[1:]
        elif len(cleaned) == 12 and cleaned.startswith('+7'):
            return cleaned[1:]
        elif len(cleaned) == 10 and not cleaned.startswith('7'):
            return '7' + cleaned

        return None

    def _extract_amount(self, text: str) -> Optional[float]:
        """Извлекает сумму из текста."""
        logger.debug("Поиск суммы...")

        # Сначала ищем по ключевым словам
        amount_keywords = self.config['amount_validation']['keywords']
        for keyword in amount_keywords:
            keyword_pattern = f"{keyword}[\\s:]*([\\d\\s\\.,]+)"
            matches = re.findall(keyword_pattern, text, re.IGNORECASE)
            if matches:
                potential_amount = matches[0].strip()
                amount = self._parse_amount_value(potential_amount)
                if amount:
                    logger.info(f"Найдена сумма по ключевому слову '{keyword}': {amount}")
                    return amount

        # Затем ищем по паттернам
        for pattern_info in self.compiled_patterns['amount']:
            matches = pattern_info['pattern'].findall(text)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        amount_str = match[0]
                    else:
                        amount_str = match

                    amount = self._parse_amount_value(amount_str)
                    if amount:
                        logger.info(f"Найдена сумма по паттерну '{pattern_info['description']}': {amount}")
                        return amount

        logger.warning("Сумма не найдена")
        return None

    def _parse_amount_value(self, amount_str: str) -> Optional[float]:
        """Парсит строку суммы в число."""
        try:
            # Заменяем запятую на точку и убираем пробелы
            cleaned = amount_str.replace(',', '.').replace(' ', '')
            amount = float(cleaned)

            # Проверяем разумность суммы
            if 0 < amount < 10000000:  # От 0 до 10 миллионов
                return amount
        except (ValueError, TypeError):
            pass

        return None

    def _extract_account(self, text: str) -> Optional[str]:
        """Извлекает банковский счет или номер карты из текста."""
        logger.debug("Поиск банковского счета/карты...")

        # Сначала ищем по ключевым словам
        account_keywords = self.config['account_validation']['keywords']
        for keyword in account_keywords:
            keyword_pattern = f"{keyword}[\\s:]*([\\d\\s]+)"
            matches = re.findall(keyword_pattern, text, re.IGNORECASE)
            if matches:
                potential_account = matches[0].strip()
                normalized = self._normalize_account(potential_account)
                if normalized:
                    logger.info(f"Найден счет по ключевому слову '{keyword}': {normalized}")
                    return normalized

        # Затем ищем по паттернам
        for pattern_info in self.compiled_patterns['account']:
            matches = pattern_info['pattern'].findall(text)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        account_str = match[0]
                    else:
                        account_str = match

                    normalized = self._normalize_account(account_str)
                    if normalized:
                        logger.info(f"Найден счет по паттерну '{pattern_info['description']}': {normalized}")
                        return normalized

        logger.warning("Банковский счет/карта не найдены")
        return None

    def _normalize_account(self, account: str) -> Optional[str]:
        """Нормализует номер счета/карты."""
        if not account:
            return None

        # Убираем все символы кроме цифр
        cleaned = re.sub(r'[^\d]', '', account)

        # Проверяем длину
        if len(cleaned) == 20:  # Банковский счет
            return cleaned
        elif len(cleaned) == 16:  # Номер карты
            return cleaned

        return None

    def _extract_datetime(self, text: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Извлекает дату и время из текста."""
        date = None
        time = None

        # Паттерны для даты
        date_patterns = [
            r'(\d{1,2})[./](\d{1,2})[./](\d{2,4})',
            r'(\d{4})[./](\d{1,2})[./](\d{1,2})',
            r'(\d{1,2})\s+(?:янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек)\w*\s+(\d{4})',
        ]

        # Словарь месяцев
        months = {
            'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'июн': 6,
            'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
        }

        # Ищем дату
        for pattern in date_patterns:
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
                        month = months.get(month_name.lower()[:3])
                        if month:
                            date = datetime(int(year), month, int(day))
                            logger.info(f"Найдена дата: {date.date()}")
                            break
                except (ValueError, TypeError):
                    continue

        # Паттерны для времени
        time_patterns = [
            r'(\d{1,2}):(\d{2})(?::(\d{2}))?',
        ]

        # Ищем время
        for pattern in time_patterns:
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

    def _extract_items(self, text: str) -> List[Dict]:
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

    def _validate_against_config(self, parsed_data: ParsedData) -> Dict[str, bool]:
        """Проверяет соответствие найденных данных валидным значениям из конфигурации."""
        matches = {}

        # Проверяем телефон
        if parsed_data.recipient_phone:
            valid_phones = self.config['phone_validation']['valid_phones']
            matches['phone_valid'] = parsed_data.recipient_phone in valid_phones
        else:
            matches['phone_valid'] = False

        # Проверяем сумму
        if parsed_data.amount:
            valid_amounts = self.config['amount_validation']['valid_amounts']
            matches['amount_valid'] = any(
                abs(parsed_data.amount - valid_amount) < 0.01
                for valid_amount in valid_amounts
            )
        else:
            matches['amount_valid'] = False

        # Проверяем счет
        if parsed_data.recipient_account:
            valid_accounts = self.config['account_validation']['valid_accounts']
            valid_cards = self.config['account_validation']['valid_cards']
            matches['account_valid'] = (
                parsed_data.recipient_account in valid_accounts or
                parsed_data.recipient_account in valid_cards
            )
        else:
            matches['account_valid'] = False

        # Общая валидность
        matches['overall_valid'] = matches.get('phone_valid', False) and matches.get('amount_valid', False)

        return matches

    def get_validation_summary(self, parsed_data: ParsedData) -> Dict[str, Any]:
        """Возвращает сводку по данным чека для отладки."""
        return {
            'amount': parsed_data.amount,
            'recipient_phone': parsed_data.recipient_phone,
            'recipient_account': parsed_data.recipient_account,
            'date': parsed_data.date.isoformat() if parsed_data.date else None,
            'time': parsed_data.time.isoformat() if parsed_data.time else None,
            'confidence': parsed_data.confidence,
            'items_count': len(parsed_data.items),
            'text_length': len(parsed_data.raw_text),
            'validation_matches': parsed_data.validation_matches,
            'has_required_data': all([
                parsed_data.amount is not None,
                parsed_data.recipient_phone is not None or parsed_data.recipient_account is not None,
                parsed_data.confidence > 50.0
            ])
        }
