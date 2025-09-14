"""Утилиты для работы с базой данных."""
from sqlalchemy.orm import Session
from database.models import Receipt, ValidationRule, UserSession, SessionLocal
from datetime import datetime
from typing import Optional, List

class DatabaseManager:
    """Менеджер базы данных."""

    def __init__(self):
        self.session = SessionLocal()

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.session.rollback()
        else:
            self.session.commit()
        self.session.close()

    def create_receipt(self, user_id: int, chat_id: int, message_id: int) -> Receipt:
        """Создает новую запись чека."""
        receipt = Receipt(
            user_id=user_id,
            chat_id=chat_id,
            message_id=message_id
        )
        self.session.add(receipt)
        self.session.commit()
        return receipt

    def update_receipt(self, receipt_id: int, **kwargs) -> Optional[Receipt]:
        """Обновляет данные чека."""
        receipt = self.session.query(Receipt).filter(Receipt.id == receipt_id).first()
        if receipt:
            for key, value in kwargs.items():
                if hasattr(receipt, key):
                    setattr(receipt, key, value)
            receipt.processed_at = datetime.utcnow()
            self.session.commit()
        return receipt

    def get_receipt(self, receipt_id: int) -> Optional[Receipt]:
        """Получает чек по ID."""
        return self.session.query(Receipt).filter(Receipt.id == receipt_id).first()

    def get_user_receipts(self, user_id: int, limit: int = 10) -> List[Receipt]:
        """Получает последние чеки пользователя."""
        return (self.session.query(Receipt)
                .filter(Receipt.user_id == user_id)
                .order_by(Receipt.created_at.desc())
                .limit(limit)
                .all())

    def create_validation_rule(self, name: str, expected_amount: float = None,
                             expected_recipient: str = None, tolerance: float = 0.01,
                             file_to_send: str = None) -> ValidationRule:
        """Создает новое правило валидации."""
        rule = ValidationRule(
            name=name,
            expected_amount=expected_amount,
            expected_recipient=expected_recipient,
            tolerance=tolerance,
            file_to_send=file_to_send
        )
        self.session.add(rule)
        self.session.commit()
        return rule

    def get_active_validation_rules(self) -> List[ValidationRule]:
        """Получает активные правила валидации."""
        return (self.session.query(ValidationRule)
                .filter(ValidationRule.is_active == True)
                .all())

    def get_user_session(self, user_id: int) -> Optional[UserSession]:
        """Получает сессию пользователя."""
        return self.session.query(UserSession).filter(UserSession.user_id == user_id).first()

    def create_or_update_user_session(self, user_id: int, chat_id: int,
                                    current_state: str = 'idle', **kwargs) -> UserSession:
        """Создает или обновляет сессию пользователя."""
        session = self.get_user_session(user_id)
        if not session:
            session = UserSession(
                user_id=user_id,
                chat_id=chat_id,
                current_state=current_state,
                **kwargs
            )
            self.session.add(session)
        else:
            session.chat_id = chat_id
            session.current_state = current_state
            session.updated_at = datetime.utcnow()
            for key, value in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, value)

        self.session.commit()
        return session
