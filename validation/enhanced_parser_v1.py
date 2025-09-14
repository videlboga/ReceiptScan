"""Улучшенный парсер с более агрессивным поиском номеров телефонов."""
import re
import yaml
from datetime import datetime
from typing import Dict, Optional, Tuple, List, Any
from dataclasses import dataclass
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
    debug_info: Dict[str, Any] = None

    def __post_init__(self):
        if self.items is None:
            self.items = []
        if self.validation_matches is None:
            self.validation_matches = {}
        if self.debug_info is None:
            self.debug_info = {}

class EnhancedReceiptParser:
    """Улучшенный парсер чеков с агрессивным поиском номеров."""

    def __init__(self, config_path: str = None):
        """Инициализация парсера."""
        self.config = self._load_config(config_path)
        self._compile_patterns()

    def _load_config(self, config_path: str = None) -> Dict:
        """Загружает конфигурацию из YAML файла."""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "validation_config_v1.yaml"

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config
        except FileNotFoundError:
            return self._get_default_config()
        except Exception as e:
            print(f"Ошибка загрузки конфигурации: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """Возвращает конфигурацию по умолчанию."""
        return {
            'phone_validation': {
                'valid_phones': ['79879335515', '+79879335515', '89879335515'],
                'keywords': ['телефон', 'номер телефона', 'мобильный', 'на телефон', 'получатель', 'контакт']
            },
            'amount_validation': {
                'valid_amounts': [1500.00, 1500, 1500.0],
                'keywords': ['сумма', 'итого', 'к оплате', 'перевод']
            },
            'account_validation': {
                'valid_accounts': ['40817810099910004312'],
                'valid_cards': ['2200590431900533'],
                'keywords': ['счет', 'карта', 'получатель']
            }
        }

    def _compile_patterns(self):
        """Компилирует регулярные выражения для ускорения работы."""
        self.compiled_patterns = {}

        # Более агрессивные паттерны для телефонов
        phone_patterns = [
            # Основные паттерны
            r'(\+?7|8)[\s\-\(\)]?(\d{3})[\s\-\(\)]?(\d{3})[\s\-\(\)]?(\d{2})[\s\-\(\)]?(\d{2})',
            r'(\+?7|8)[\s\-\(\)]?(\d{3})[\s\-\(\)]?(\d{3})[\s\-\(\)]?(\d{4})',
            r'(\+?7|8)[\s\-\(\)]?(\d{4})[\s\-\(\)]?(\d{3})[\s\-\(\)]?(\d{3})',
            r'(\+?7|8)(\d{10})',

            # Дополнительные паттерны для плохого OCR
            r'(\+?7|8)[\s\-\(\)]?(\d{1,3})[\s\-\(\)]?(\d{1,3})[\s\-\(\)]?(\d{1,3})[\s\-\(\)]?(\d{1,3})',
            r'(\+?7|8)[\s\-\(\)]?(\d{2,4})[\s\-\(\)]?(\d{2,4})[\s\-\(\)]?(\d{2,4})',
            r'(\+?7|8)[\s\-\(\)]?(\d{3,4})[\s\-\(\)]?(\d{3,4})[\s\-\(\)]?(\d{2,4})',

            # Паттерны для номеров с ошибками OCR
            r'(\+?7|8)[\s\-\(\)]?(\d{2,3})[\s\-\(\)]?(\d{2,3})[\s\-\(\)]?(\d{2,3})[\s\-\(\)]?(\d{2,3})',
            r'(\+?7|8)[\s\-\(\)]?(\d{1,4})[\s\-\(\)]?(\d{1,4})[\s\-\(\)]?(\d{1,4})[\s\-\(\)]?(\d{1,4})',

            # Простой поиск 11 цифр подряд
            r'(\+?7|8)(\d{10})',
            r'(\+?7|8)(\d{9,11})',
        ]

        self.compiled_patterns['phone'] = []
        for pattern in phone_patterns:
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
                self.compiled_patterns['phone'].append(compiled)
            except re.error as e:
                print(f"Ошибка компиляции паттерна телефона: {e}")

        # Паттерны для сумм
        amount_patterns = [
            r'(\d+(?:[.,]\d{2})?)\s*(?:руб|₽|rub|р\.)',
            r'(?:сумма|итого|к оплате)[\s:]*(\d+(?:[.,]\d{2})?)',
            r'(\d+(?:[.,]\d{2})?)\s*(?:€|eur|euro)',
            r'(\d+(?:[.,]\d{2})?)\s*(?:\$|usd|dollar)',
        ]

        self.compiled_patterns['amount'] = []
        for pattern in amount_patterns:
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
                self.compiled_patterns['amount'].append(compiled)
            except re.error as e:
                print(f"Ошибка компиляции паттерна суммы: {e}")

    def parse_receipt(self, text: str, confidence: float = 0.0) -> ParsedData:
        """Парсит текст чека и извлекает структурированные данные."""
        print(f"🔍 Начинаем парсинг чека (уверенность OCR: {confidence:.1f}%)")
        print(f"📄 Длина текста: {len(text)} символов")

        parsed_data = ParsedData(
            raw_text=text,
            confidence=confidence
        )

        # Извлекаем номер телефона (приоритет)
        parsed_data.recipient_phone = self._extract_phone_aggressive(text)

        # Извлекаем сумму
        parsed_data.amount = self._extract_amount(text)

        # Извлекаем банковский счет/карту
        parsed_data.recipient_account = self._extract_account(text)

        # Извлекаем дату и время
        parsed_data.date, parsed_data.time = self._extract_datetime(text)

        # Извлекаем товары/услуги
        parsed_data.items = self._extract_items(text)

        # Проверяем соответствие валидным значениям
        parsed_data.validation_matches = self._validate_against_config(parsed_data)

        # Добавляем отладочную информацию
        parsed_data.debug_info = {
            'text_preview': text[:200] + '...' if len(text) > 200 else text,
            'phone_search_attempts': len(self.compiled_patterns['phone']),
            'amount_search_attempts': len(self.compiled_patterns['amount'])
        }

        print(f"📊 Результат парсинга:")
        print(f"  📱 Телефон: {parsed_data.recipient_phone}")
        print(f"  💰 Сумма: {parsed_data.amount}")
        print(f"  🏦 Счет: {parsed_data.recipient_account}")

        return parsed_data

    def _extract_phone_aggressive(self, text: str) -> Optional[str]:
        """Агрессивно извлекает номер телефона из текста."""
        print("🔍 Агрессивный поиск номера телефона...")

        # Сначала ищем по ключевым словам
        phone_keywords = self.config['phone_validation']['keywords']
        for keyword in phone_keywords:
            keyword_pattern = f"{keyword}[\\s:]*([\\d\\s\\-\\(\\)\\+]+)"
            matches = re.findall(keyword_pattern, text, re.IGNORECASE)
            if matches:
                potential_phone = matches[0].strip()
                normalized = self._normalize_phone(potential_phone)
                if normalized:
                    print(f"✅ Найден номер по ключевому слову '{keyword}': {normalized}")
                    return normalized

        # Затем ищем по всем паттернам
        for i, pattern in enumerate(self.compiled_patterns['phone']):
            matches = pattern.findall(text)
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
                        print(f"✅ Найден номер по паттерну {i+1}: {normalized}")
                        return normalized

        # Дополнительный поиск - ищем любые 11 цифр
        print("🔍 Дополнительный поиск - любые 11 цифр...")
        digit_sequences = re.findall(r'\d{10,12}', text)
        for sequence in digit_sequences:
            if len(sequence) == 11 and (sequence.startswith('7') or sequence.startswith('8')):
                normalized = self._normalize_phone(sequence)
                if normalized:
                    print(f"✅ Найден номер в последовательности цифр: {normalized}")
                    return normalized
            elif len(sequence) == 12 and sequence.startswith('+7'):
                normalized = self._normalize_phone(sequence)
                if normalized:
                    print(f"✅ Найден номер в последовательности цифр: {normalized}")
                    return normalized

        # Поиск по частям - ищем группы цифр, которые могут быть номером
        print("🔍 Поиск по частям...")
        digit_groups = re.findall(r'\d{2,4}', text)
        if len(digit_groups) >= 3:
            # Пытаемся собрать номер из групп
            for i in range(len(digit_groups) - 2):
                potential_parts = digit_groups[i:i+3]
                if all(len(part) >= 2 for part in potential_parts):
                    # Проверяем, может ли это быть номером
                    combined = ''.join(potential_parts)
                    if len(combined) >= 10:
                        # Добавляем код страны
                        if not combined.startswith('7') and not combined.startswith('8'):
                            combined = '7' + combined
                        elif combined.startswith('8'):
                            combined = '7' + combined[1:]

                        if len(combined) == 11:
                            normalized = self._normalize_phone(combined)
                            if normalized:
                                print(f"✅ Найден номер по частям: {normalized}")
                                return normalized

        print("❌ Номер телефона не найден")
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
        print("🔍 Поиск суммы...")

        # Сначала ищем по ключевым словам
        amount_keywords = self.config['amount_validation']['keywords']
        for keyword in amount_keywords:
            keyword_pattern = f"{keyword}[\\s:]*([\\d\\s\\.,]+)"
            matches = re.findall(keyword_pattern, text, re.IGNORECASE)
            if matches:
                potential_amount = matches[0].strip()
                amount = self._parse_amount_value(potential_amount)
                if amount:
                    print(f"✅ Найдена сумма по ключевому слову '{keyword}': {amount}")
                    return amount

        # Затем ищем по паттернам
        for pattern in self.compiled_patterns['amount']:
            matches = pattern.findall(text)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        amount_str = match[0]
                    else:
                        amount_str = match

                    amount = self._parse_amount_value(amount_str)
                    if amount:
                        print(f"✅ Найдена сумма по паттерну: {amount}")
                        return amount

        print("❌ Сумма не найдена")
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
        print("🔍 Поиск банковского счета/карты...")

        # Ищем 20-значные счета
        account_20 = re.search(r'\d{20}', text)
        if account_20:
            account = account_20.group(0)
            print(f"✅ Найден 20-значный счет: {account}")
            return account

        # Ищем 16-значные карты
        card_16 = re.search(r'\d{16}', text)
        if card_16:
            card = card_16.group(0)
            print(f"✅ Найдена 16-значная карта: {card}")
            return card

        print("❌ Банковский счет/карта не найдены")
        return None

    def _extract_datetime(self, text: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Извлекает дату и время из текста."""
        date = None
        time = None

        # Паттерны для даты
        date_patterns = [
            r'(\d{1,2})[./](\d{1,2})[./](\d{2,4})',
            r'(\d{4})[./](\d{1,2})[./](\d{1,2})',
        ]

        # Ищем дату
        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    match = matches[0]
                    if len(match) == 3:
                        if len(match[0]) == 4:  # ГГГГ.ММ.ДД
                            year, month, day = match
                        else:  # ДД.ММ.ГГГГ
                            day, month, year = match
                        date = datetime(int(year), int(month), int(day))
                        print(f"✅ Найдена дата: {date.date()}")
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
                    print(f"✅ Найдено время: {time.time()}")
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

        print(f"✅ Найдено товаров: {len(items)}")
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
