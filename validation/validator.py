"""Система валидации чеков."""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from loguru import logger
from config.settings import AMOUNT_TOLERANCE
from database.models import ValidationRule
from ocr.receipt_parser import ReceiptData

@dataclass
class ValidationResult:
    """Результат валидации чека."""
    is_valid: bool
    message: str
    file_to_send: Optional[str] = None
    details: Dict = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}

class ReceiptValidator:
    """Валидатор чеков."""

    def __init__(self):
        self.amount_tolerance = AMOUNT_TOLERANCE

    def validate_receipt(self, receipt_data: ReceiptData,
                        validation_rules: List[ValidationRule]) -> ValidationResult:
        """
        Валидирует чек по заданным правилам.

        Args:
            receipt_data: Данные чека
            validation_rules: Список правил валидации

        Returns:
            ValidationResult: Результат валидации
        """
        logger.info(f"Начинаем валидацию чека с суммой {receipt_data.amount}")

        # Проверяем базовую корректность данных
        basic_validation = self._validate_basic_data(receipt_data)
        if not basic_validation['is_valid']:
            return ValidationResult(
                is_valid=False,
                message=basic_validation['message'],
                details=basic_validation
            )

        # Применяем правила валидации
        for rule in validation_rules:
            rule_result = self._validate_by_rule(receipt_data, rule)
            if rule_result['is_valid']:
                logger.info(f"Чек прошел валидацию по правилу: {rule.name}")
                return ValidationResult(
                    is_valid=True,
                    message=f"Чек успешно проверен по правилу '{rule.name}'",
                    file_to_send=rule.file_to_send,
                    details=rule_result
                )

        # Если ни одно правило не подошло
        return ValidationResult(
            is_valid=False,
            message="Чек не соответствует ни одному из правил валидации",
            details={'rules_checked': len(validation_rules)}
        )

    def _validate_basic_data(self, receipt_data: ReceiptData) -> Dict:
        """Проверяет базовую корректность данных чека."""
        errors = []

        # Проверяем наличие суммы
        if receipt_data.amount is None:
            errors.append("Сумма не найдена в чеке")
        elif receipt_data.amount <= 0:
            errors.append("Сумма должна быть больше нуля")

        # Проверяем наличие счета получателя
        if not receipt_data.recipient_account:
            errors.append("Счет получателя не найден в чеке")

        # Проверяем уверенность распознавания
        if receipt_data.confidence < 50.0:
            errors.append(f"Низкая уверенность распознавания: {receipt_data.confidence:.1f}%")

        return {
            'is_valid': len(errors) == 0,
            'message': '; '.join(errors) if errors else 'Базовые данные корректны',
            'errors': errors
        }

    def _validate_by_rule(self, receipt_data: ReceiptData, rule: ValidationRule) -> Dict:
        """Валидирует чек по конкретному правилу."""
        logger.debug(f"Проверяем правило: {rule.name}")

        # Проверяем сумму
        amount_valid = True
        if rule.expected_amount is not None:
            if receipt_data.amount is None:
                amount_valid = False
            else:
                min_amount = rule.expected_amount - rule.tolerance
                max_amount = rule.expected_amount + rule.tolerance
                amount_valid = min_amount <= receipt_data.amount <= max_amount
                logger.debug(f"Сумма: {receipt_data.amount}, ожидается: {rule.expected_amount}±{rule.tolerance}")

        # Проверяем счет получателя
        account_valid = True
        if rule.expected_recipient is not None:
            if not receipt_data.recipient_account:
                account_valid = False
            else:
                # Сравниваем с учетом возможных различий в регистре и пробелах
                expected = rule.expected_recipient.lower().strip()
                actual = receipt_data.recipient_account.lower().strip()
                account_valid = expected in actual or actual in expected
                logger.debug(f"Счет: '{receipt_data.recipient_account}', ожидается: '{rule.expected_recipient}'")

        is_valid = amount_valid and account_valid

        return {
            'is_valid': is_valid,
            'rule_name': rule.name,
            'amount_valid': amount_valid,
            'account_valid': account_valid,
            'expected_amount': rule.expected_amount,
            'actual_amount': receipt_data.amount,
            'expected_recipient': rule.expected_recipient,
            'actual_recipient': receipt_data.recipient_account
        }

    def validate_amount_range(self, amount: float, expected_amount: float,
                            tolerance: float = None) -> bool:
        """Проверяет, находится ли сумма в допустимом диапазоне."""
        if tolerance is None:
            tolerance = self.amount_tolerance

        min_amount = expected_amount - tolerance
        max_amount = expected_amount + tolerance

        return min_amount <= amount <= max_amount

    def validate_account_match(self, actual_account: str, expected_account: str) -> bool:
        """Проверяет соответствие счетов."""
        if not actual_account or not expected_account:
            return False

        # Нормализуем строки для сравнения
        actual = actual_account.lower().strip()
        expected = expected_account.lower().strip()

        # Проверяем точное совпадение или вхождение
        return actual == expected or expected in actual or actual in expected

    def create_validation_rule(self, name: str, expected_amount: float = None,
                             expected_recipient: str = None, tolerance: float = None,
                             file_to_send: str = None) -> Dict:
        """Создает новое правило валидации."""
        if tolerance is None:
            tolerance = self.amount_tolerance

        return {
            'name': name,
            'expected_amount': expected_amount,
            'expected_recipient': expected_recipient,
            'tolerance': tolerance,
            'file_to_send': file_to_send,
            'is_active': True
        }

    def get_validation_summary(self, receipt_data: ReceiptData) -> Dict:
        """Возвращает сводку по данным чека для отладки."""
        return {
            'amount': receipt_data.amount,
            'recipient_account': receipt_data.recipient_account,
            'date': receipt_data.date.isoformat() if receipt_data.date else None,
            'time': receipt_data.time.isoformat() if receipt_data.time else None,
            'confidence': receipt_data.confidence,
            'items_count': len(receipt_data.items),
            'text_length': len(receipt_data.raw_text),
            'has_basic_data': all([
                receipt_data.amount is not None,
                receipt_data.recipient_account is not None,
                receipt_data.confidence > 50.0
            ])
        }
