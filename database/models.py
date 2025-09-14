"""Модели базы данных."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config.settings import DATABASE_URL

Base = declarative_base()

class Receipt(Base):
    """Модель чека."""
    __tablename__ = 'receipts'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    chat_id = Column(Integer, nullable=False)
    message_id = Column(Integer, nullable=False)

    # Данные чека
    amount = Column(Float, nullable=True)
    recipient_account = Column(String(255), nullable=True)
    date = Column(DateTime, nullable=True)
    raw_text = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)

    # Статус обработки
    is_valid = Column(Boolean, default=False)
    validation_message = Column(Text, nullable=True)

    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Receipt(id={self.id}, user_id={self.user_id}, amount={self.amount})>"

class ValidationRule(Base):
    """Модель правила валидации."""
    __tablename__ = 'validation_rules'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    expected_amount = Column(Float, nullable=True)
    expected_recipient = Column(String(255), nullable=True)
    tolerance = Column(Float, default=0.01)
    file_to_send = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ValidationRule(id={self.id}, name={self.name})>"

class UserSession(Base):
    """Модель сессии пользователя."""
    __tablename__ = 'user_sessions'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, unique=True)
    chat_id = Column(Integer, nullable=False)
    current_state = Column(String(100), default='idle')
    expected_amount = Column(Float, nullable=True)
    expected_recipient = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<UserSession(user_id={self.user_id}, state={self.current_state})>"

# Создаем движок базы данных
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """Создает все таблицы в базе данных."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Получает сессию базы данных."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
