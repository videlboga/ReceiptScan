"""Гибкий валидатор чеков с настраиваемыми правилами."""
import yaml
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from loguru import logger
from pathlib import Path
from .ultra_parser_v1 import UltraReceiptParser, ParsedData

@dataclass
class ValidationResult:
    """Результат валидации чека."""
    is_valid: bool
    message: str
    confidence_score: float
    details: Dict[str, Any] = None
    recommendations: List[str] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.recommendations is None:
            self.recommendations = []

class FlexibleReceiptValidator:
    """Гибкий валидатор чеков с настраиваемыми правилами."""

    def __init__(self, config_path: str = None):
        """
        Инициализация валидатора.

        Args:
            config_path: Путь к YAML конфигурации
        """
        self.config = self._load_config(config_path)
        self.parser = UltraReceiptParser(config_path)
        self._setup_validation_rules()

    def _load_config(self, config_path: str = None) -> Dict:
        """Загружает конфигурацию из YAML файла."""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "validation_config_v1.yaml"

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"Конфигурация валидатора загружена из {config_path}")
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
            'validation': {
                'min_confidence': 50.0,
                'amount_tolerance': 0.01,
                'requirements': {
                    'required_fields': ['amount', 'recipient'],
                    'optional_fields': ['date', 'time', 'items']
                }
            },
            'phone_validation': {
                'valid_phones': ['79879335515', '+79879335515', '89879335515']
            },
            'amount_validation': {
                'valid_amounts': [1500.00, 1500, 1500.0]
            },
            'account_validation': {
                'valid_accounts': ['40817810099910004312'],
                'valid_cards': ['2200590431900533']
            }
        }

    def _setup_validation_rules(self):
        """Настраивает правила валидации."""
        self.min_confidence = self.config['validation']['min_confidence']
        self.amount_tolerance = self.config['validation']['amount_tolerance']
        self.required_fields = self.config['validation']['requirements']['required_fields']
        self.optional_fields = self.config['validation']['requirements']['optional_fields']

    def validate_receipt(self, text: str, confidence: float = 0.0) -> ValidationResult:
        """
        Валидирует чек по настраиваемым правилам.

        Args:
            text: Текст чека
            confidence: Уверенность распознавания

        Returns:
            ValidationResult: Результат валидации
        """
        logger.info("Начинаем валидацию чека с гибкими правилами")

        # Парсим данные чека
        parsed_data = self.parser.parse_receipt(text, confidence)

        # Выполняем валидацию
        validation_details = self._validate_parsed_data(parsed_data)

        # Определяем общий результат
        is_valid = self._determine_overall_validity(validation_details, parsed_data)

        # Формируем сообщение
        message = self._generate_validation_message(validation_details, parsed_data)

        # Рассчитываем оценку уверенности
        confidence_score = self._calculate_confidence_score(validation_details, parsed_data)

        # Генерируем рекомендации
        recommendations = self._generate_recommendations(validation_details, parsed_data)

        return ValidationResult(
            is_valid=is_valid,
            message=message,
            confidence_score=confidence_score,
            details=validation_details,
            recommendations=recommendations
        )

    def _validate_parsed_data(self, parsed_data: ParsedData) -> Dict[str, Any]:
        """Валидирует распарсенные данные чека."""
        validation_details = {
            'basic_validation': self._validate_basic_data(parsed_data),
            'field_validation': self._validate_required_fields(parsed_data),
            'value_validation': self._validate_values(parsed_data),
            'confidence_validation': self._validate_confidence(parsed_data)
        }

        return validation_details

    def _validate_basic_data(self, parsed_data: ParsedData) -> Dict[str, Any]:
        """Проверяет базовую корректность данных чека."""
        errors = []
        warnings = []

        # Проверяем наличие суммы
        if parsed_data.amount is None:
            errors.append("Сумма не найдена в чеке")
        elif parsed_data.amount <= 0:
            errors.append("Сумма должна быть больше нуля")
        elif parsed_data.amount > 10000000:  # 10 миллионов
            warnings.append(f"Очень большая сумма: {parsed_data.amount}")

        # Проверяем наличие получателя
        if not parsed_data.recipient_phone and not parsed_data.recipient_account:
            errors.append("Не найден получатель (телефон или счет)")

        # Проверяем уверенность распознавания
        if parsed_data.confidence < self.min_confidence:
            errors.append(f"Низкая уверенность распознавания: {parsed_data.confidence:.1f}%")

        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    def _validate_required_fields(self, parsed_data: ParsedData) -> Dict[str, Any]:
        """Проверяет наличие обязательных полей."""
        field_status = {}

        for field in self.required_fields:
            if field == 'amount':
                field_status[field] = parsed_data.amount is not None
            elif field == 'recipient':
                field_status[field] = (
                    parsed_data.recipient_phone is not None or
                    parsed_data.recipient_account is not None
                )

        # Проверяем опциональные поля
        for field in self.optional_fields:
            if field == 'date':
                field_status[field] = parsed_data.date is not None
            elif field == 'time':
                field_status[field] = parsed_data.time is not None
            elif field == 'items':
                field_status[field] = len(parsed_data.items) > 0

        return {
            'is_valid': all(field_status.get(field, False) for field in self.required_fields),
            'field_status': field_status
        }

    def _validate_values(self, parsed_data: ParsedData) -> Dict[str, Any]:
        """Проверяет соответствие найденных значений валидным."""
        value_validation = {
            'phone_valid': False,
            'amount_valid': False,
            'account_valid': False
        }

        # Проверяем телефон
        if parsed_data.recipient_phone:
            valid_phones = self.config['phone_validation']['valid_phones']
            value_validation['phone_valid'] = parsed_data.recipient_phone in valid_phones

        # Проверяем сумму
        if parsed_data.amount:
            valid_amounts = self.config['amount_validation']['valid_amounts']
            value_validation['amount_valid'] = any(
                abs(parsed_data.amount - valid_amount) <= self.amount_tolerance
                for valid_amount in valid_amounts
            )

        # Проверяем счет
        if parsed_data.recipient_account:
            valid_accounts = self.config['account_validation']['valid_accounts']
            valid_cards = self.config['account_validation']['valid_cards']
            value_validation['account_valid'] = (
                parsed_data.recipient_account in valid_accounts or
                parsed_data.recipient_account in valid_cards
            )

        return {
            'is_valid': any(value_validation.values()),
            'value_status': value_validation
        }

    def _validate_confidence(self, parsed_data: ParsedData) -> Dict[str, Any]:
        """Проверяет уверенность распознавания."""
        confidence_ok = parsed_data.confidence >= self.min_confidence

        return {
            'is_valid': confidence_ok,
            'confidence': parsed_data.confidence,
            'min_required': self.min_confidence
        }

    def _determine_overall_validity(self, validation_details: Dict, parsed_data: ParsedData) -> bool:
        """Определяет общую валидность чека."""
        # Базовые проверки должны пройти
        if not validation_details['basic_validation']['is_valid']:
            return False

        # Обязательные поля должны быть заполнены
        if not validation_details['field_validation']['is_valid']:
            return False

        # Хотя бы одно значение должно быть валидным
        if not validation_details['value_validation']['is_valid']:
            return False

        # Уверенность должна быть достаточной
        if not validation_details['confidence_validation']['is_valid']:
            return False

        return True

    def _generate_validation_message(self, validation_details: Dict, parsed_data: ParsedData) -> str:
        """Генерирует сообщение о результатах валидации."""
        messages = []

        # Базовые ошибки
        basic_errors = validation_details['basic_validation']['errors']
        if basic_errors:
            messages.extend([f"❌ {error}" for error in basic_errors])

        # Статус полей
        field_status = validation_details['field_validation']['field_status']
        for field, status in field_status.items():
            if field in self.required_fields:
                if status:
                    messages.append(f"✅ {field}: найдено")
                else:
                    messages.append(f"❌ {field}: не найдено")

        # Статус значений
        value_status = validation_details['value_validation']['value_status']
        if value_status['phone_valid']:
            messages.append(f"✅ Телефон {parsed_data.recipient_phone}: валиден")
        elif parsed_data.recipient_phone:
            messages.append(f"❌ Телефон {parsed_data.recipient_phone}: не найден в списке валидных")

        if value_status['amount_valid']:
            messages.append(f"✅ Сумма {parsed_data.amount}: валидна")
        elif parsed_data.amount:
            messages.append(f"❌ Сумма {parsed_data.amount}: не найдена в списке валидных")

        if value_status['account_valid']:
            messages.append(f"✅ Счет {parsed_data.recipient_account}: валиден")
        elif parsed_data.recipient_account:
            messages.append(f"❌ Счет {parsed_data.recipient_account}: не найден в списке валидных")

        # Уверенность
        confidence = validation_details['confidence_validation']['confidence']
        if confidence >= self.min_confidence:
            messages.append(f"✅ Уверенность распознавания: {confidence:.1f}%")
        else:
            messages.append(f"❌ Уверенность распознавания: {confidence:.1f}% (минимум {self.min_confidence}%)")

        return "\n".join(messages)

    def _calculate_confidence_score(self, validation_details: Dict, parsed_data: ParsedData) -> float:
        """Рассчитывает общую оценку уверенности."""
        score = 0.0
        max_score = 100.0

        # Базовые проверки (30%)
        if validation_details['basic_validation']['is_valid']:
            score += 30.0

        # Обязательные поля (25%)
        required_fields_found = sum(
            1 for field in self.required_fields
            if validation_details['field_validation']['field_status'].get(field, False)
        )
        score += (required_fields_found / len(self.required_fields)) * 25.0

        # Валидные значения (25%)
        value_status = validation_details['value_validation']['value_status']
        valid_values_count = sum(1 for status in value_status.values() if status)
        total_values = len(value_status)
        if total_values > 0:
            score += (valid_values_count / total_values) * 25.0

        # Уверенность OCR (20%)
        confidence_ratio = min(parsed_data.confidence / 100.0, 1.0)
        score += confidence_ratio * 20.0

        return min(score, max_score)

    def _generate_recommendations(self, validation_details: Dict, parsed_data: ParsedData) -> List[str]:
        """Генерирует рекомендации по улучшению."""
        recommendations = []

        # Рекомендации по базовым ошибкам
        basic_errors = validation_details['basic_validation']['errors']
        if "Сумма не найдена в чеке" in basic_errors:
            recommendations.append("Проверьте качество изображения чека - сумма должна быть четко видна")

        if "Не найден получатель" in basic_errors:
            recommendations.append("Убедитесь, что номер телефона или банковский счет четко видны на чеке")

        # Рекомендации по полям
        field_status = validation_details['field_validation']['field_status']
        if not field_status.get('amount', False):
            recommendations.append("Сумма не распознана - попробуйте сделать более четкое фото")

        if not field_status.get('recipient', False):
            recommendations.append("Получатель не найден - проверьте наличие номера телефона или счета")

        # Рекомендации по значениям
        value_status = validation_details['value_validation']['value_status']
        if not value_status['phone_valid'] and parsed_data.recipient_phone:
            recommendations.append(f"Номер телефона {parsed_data.recipient_phone} не найден в списке валидных")

        if not value_status['amount_valid'] and parsed_data.amount:
            recommendations.append(f"Сумма {parsed_data.amount} не найдена в списке валидных")

        # Рекомендации по уверенности
        if parsed_data.confidence < self.min_confidence:
            recommendations.append("Низкое качество распознавания - попробуйте сделать более четкое фото")

        return recommendations

    def update_config(self, new_config: Dict):
        """Обновляет конфигурацию валидатора."""
        self.config = new_config
        self._setup_validation_rules()
        self.parser.config = new_config
        self.parser._compile_patterns()
        logger.info("Конфигурация валидатора обновлена")

    def get_config(self) -> Dict:
        """Возвращает текущую конфигурацию."""
        return self.config.copy()

    def add_valid_phone(self, phone: str):
        """Добавляет валидный номер телефона."""
        if 'phone_validation' not in self.config:
            self.config['phone_validation'] = {'valid_phones': []}

        if 'valid_phones' not in self.config['phone_validation']:
            self.config['phone_validation']['valid_phones'] = []

        if phone not in self.config['phone_validation']['valid_phones']:
            self.config['phone_validation']['valid_phones'].append(phone)
            logger.info(f"Добавлен валидный номер телефона: {phone}")

    def add_valid_amount(self, amount: float):
        """Добавляет валидную сумму."""
        if 'amount_validation' not in self.config:
            self.config['amount_validation'] = {'valid_amounts': []}

        if 'valid_amounts' not in self.config['amount_validation']:
            self.config['amount_validation']['valid_amounts'] = []

        if amount not in self.config['amount_validation']['valid_amounts']:
            self.config['amount_validation']['valid_amounts'].append(amount)
            logger.info(f"Добавлена валидная сумма: {amount}")

    def add_valid_account(self, account: str):
        """Добавляет валидный счет."""
        if len(account) == 20:
            if 'account_validation' not in self.config:
                self.config['account_validation'] = {'valid_accounts': []}

            if 'valid_accounts' not in self.config['account_validation']:
                self.config['account_validation']['valid_accounts'] = []

            if account not in self.config['account_validation']['valid_accounts']:
                self.config['account_validation']['valid_accounts'].append(account)
                logger.info(f"Добавлен валидный счет: {account}")

        elif len(account) == 16:
            if 'account_validation' not in self.config:
                self.config['account_validation'] = {'valid_cards': []}

            if 'valid_cards' not in self.config['account_validation']:
                self.config['account_validation']['valid_cards'] = []

            if account not in self.config['account_validation']['valid_cards']:
                self.config['account_validation']['valid_cards'].append(account)
                logger.info(f"Добавлена валидная карта: {account}")
