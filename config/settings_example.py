#!/usr/bin/env python3
"""Пример настроек приложения.
Скопируйте этот файл в settings.py и настройте под свои нужды.
"""

import os
from pathlib import Path

# Базовые пути
BASE_DIR = Path(__file__).parent.parent
FILES_DIR = BASE_DIR / 'files'
LOGS_DIR = BASE_DIR / 'logs'
TEMPLATES_DIR = FILES_DIR / 'templates'
CERTIFICATES_DIR = FILES_DIR / 'certificates'

# Создаем директории если их нет
for directory in [FILES_DIR, LOGS_DIR, TEMPLATES_DIR, CERTIFICATES_DIR]:
    directory.mkdir(exist_ok=True)

# Настройки Telegram бота
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
BOT_NAME = os.getenv('BOT_NAME', 'ReceiptCheckerBot')
BOT_USERNAME = os.getenv('BOT_USERNAME', 'receipt_checker_bot')

# Настройки базы данных
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot.db')
DATABASE_ECHO = os.getenv('DATABASE_ECHO', 'false').lower() == 'true'

# Настройки файлов
FILES_PATH = os.getenv('FILES_PATH', str(FILES_DIR))
MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', '20971520'))  # 20 MB

# Настройки OCR
TESSERACT_LANG = os.getenv('TESSERACT_LANG', 'rus+eng')
TESSERACT_TIMEOUT = int(os.getenv('TESSERACT_TIMEOUT', '30'))

# Настройки логирования
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', str(LOGS_DIR / 'bot.log'))
LOG_MAX_SIZE = os.getenv('LOG_MAX_SIZE', '10MB')
LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', '5'))

# Настройки отладки
ENABLE_DEBUG = os.getenv('ENABLE_DEBUG', 'false').lower() == 'true'
ENABLE_VERBOSE_LOGGING = os.getenv('ENABLE_VERBOSE_LOGGING', 'false').lower() == 'true'

# Настройки безопасности
ALLOWED_USERS = os.getenv('ALLOWED_USERS', '').split(',') if os.getenv('ALLOWED_USERS') else []
BLOCKED_USERS = os.getenv('BLOCKED_USERS', '').split(',') if os.getenv('BLOCKED_USERS') else []

# Настройки валидации
VALIDATION_CONFIG_PATH = os.getenv('VALIDATION_CONFIG_PATH', str(BASE_DIR / 'validation_config.yaml'))
MIN_CONFIDENCE = float(os.getenv('MIN_CONFIDENCE', '50.0'))
AMOUNT_TOLERANCE = float(os.getenv('AMOUNT_TOLERANCE', '0.01'))

# Настройки Docker
IS_DOCKER = os.getenv('IS_DOCKER', 'false').lower() == 'true'
DOCKER_WORKDIR = os.getenv('DOCKER_WORKDIR', '/app')

# Настройки веб-хуков (для продакшена)
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', '8443'))
WEBHOOK_CERT = os.getenv('WEBHOOK_CERT', '')
WEBHOOK_KEY = os.getenv('WEBHOOK_KEY', '')

# Настройки Redis (для кэширования и очередей)
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
USE_REDIS = os.getenv('USE_REDIS', 'false').lower() == 'true'

# Настройки мониторинга
ENABLE_METRICS = os.getenv('ENABLE_METRICS', 'false').lower() == 'true'
METRICS_PORT = int(os.getenv('METRICS_PORT', '9090'))

# Настройки уведомлений
NOTIFICATION_EMAIL = os.getenv('NOTIFICATION_EMAIL', '')
NOTIFICATION_SMTP_SERVER = os.getenv('NOTIFICATION_SMTP_SERVER', '')
NOTIFICATION_SMTP_PORT = int(os.getenv('NOTIFICATION_SMTP_PORT', '587'))
NOTIFICATION_SMTP_USER = os.getenv('NOTIFICATION_SMTP_USER', '')
NOTIFICATION_SMTP_PASSWORD = os.getenv('NOTIFICATION_SMTP_PASSWORD', '')

# Настройки бэкапа
BACKUP_ENABLED = os.getenv('BACKUP_ENABLED', 'false').lower() == 'true'
BACKUP_SCHEDULE = os.getenv('BACKUP_SCHEDULE', '0 2 * * *')  # Каждый день в 2:00
BACKUP_RETENTION_DAYS = int(os.getenv('BACKUP_RETENTION_DAYS', '30'))

# Настройки API
API_ENABLED = os.getenv('API_ENABLED', 'false').lower() == 'true'
API_PORT = int(os.getenv('API_PORT', '8000'))
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_SECRET_KEY = os.getenv('API_SECRET_KEY', 'your-secret-key-here')

# Настройки тестирования
TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true'
TEST_DATABASE_URL = os.getenv('TEST_DATABASE_URL', 'sqlite:///test_bot.db')
