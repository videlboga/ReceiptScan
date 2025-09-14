"""Управление файлами для отправки пользователям."""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger
from config.settings import FILES_PATH

class FileManager:
    """Менеджер файлов для отправки пользователям."""

    def __init__(self):
        self.files_path = Path(FILES_PATH)
        self.templates_path = self.files_path / "templates"
        self.certificates_path = self.files_path / "certificates"

        # Создаем необходимые директории
        self.templates_path.mkdir(parents=True, exist_ok=True)
        self.certificates_path.mkdir(parents=True, exist_ok=True)

    def get_file_path(self, filename: str) -> Optional[Path]:
        """
        Получает путь к файлу для отправки.

        Args:
            filename: Имя файла

        Returns:
            Path: Путь к файлу или None если файл не найден
        """
        # Проверяем в шаблонах
        template_path = self.templates_path / filename
        if template_path.exists():
            return template_path

        # Проверяем в сертификатах
        cert_path = self.certificates_path / filename
        if cert_path.exists():
            return cert_path

        # Проверяем в корневой директории файлов
        root_path = self.files_path / filename
        if root_path.exists():
            return root_path

        logger.warning(f"Файл не найден: {filename}")
        return None

    def generate_certificate(self, receipt_data: Dict[str, Any],
                           template_name: str = "default_certificate.txt") -> Optional[Path]:
        """
        Генерирует сертификат на основе данных чека.

        Args:
            receipt_data: Данные чека
            template_name: Имя шаблона

        Returns:
            Path: Путь к сгенерированному сертификату
        """
        try:
            # Загружаем шаблон
            template_path = self.templates_path / template_name
            if not template_path.exists():
                logger.error(f"Шаблон не найден: {template_name}")
                return None

            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()

            # Заполняем шаблон данными
            certificate_content = self._fill_template(template_content, receipt_data)

            # Генерируем имя файла сертификата
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            cert_filename = f"certificate_{timestamp}.txt"
            cert_path = self.certificates_path / cert_filename

            # Сохраняем сертификат
            with open(cert_path, 'w', encoding='utf-8') as f:
                f.write(certificate_content)

            logger.info(f"Сертификат создан: {cert_path}")
            return cert_path

        except Exception as e:
            logger.error(f"Ошибка при создании сертификата: {e}")
            return None

    def _fill_template(self, template: str, data: Dict[str, Any]) -> str:
        """Заполняет шаблон данными."""
        # Заменяем плейсхолдеры в шаблоне
        filled_template = template

        # Стандартные поля
        replacements = {
            '{date}': datetime.now().strftime("%d.%m.%Y"),
            '{time}': datetime.now().strftime("%H:%M:%S"),
            '{amount}': str(data.get('amount', 'N/A')),
            '{recipient}': data.get('recipient_account', 'N/A'),
            '{confidence}': f"{data.get('confidence', 0):.1f}%",
            '{items_count}': str(len(data.get('items', []))),
        }

        for placeholder, value in replacements.items():
            filled_template = filled_template.replace(placeholder, value)

        return filled_template

    def create_default_template(self) -> bool:
        """Создает шаблон по умолчанию."""
        template_content = """СЕРТИФИКАТ ПРОВЕРКИ ЧЕКА
================================

Дата проверки: {date}
Время проверки: {time}

ДАННЫЕ ЧЕКА:
- Сумма: {amount} руб.
- Получатель: {recipient}
- Уверенность распознавания: {confidence}
- Количество позиций: {items_count}

СТАТУС: Чек успешно проверен и соответствует требованиям.

Сертификат сгенерирован автоматически системой проверки чеков.
"""

        try:
            template_path = self.templates_path / "default_certificate.txt"
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(template_content)

            logger.info("Шаблон по умолчанию создан")
            return True

        except Exception as e:
            logger.error(f"Ошибка при создании шаблона: {e}")
            return False

    def list_available_files(self) -> Dict[str, list]:
        """Возвращает список доступных файлов."""
        return {
            'templates': [f.name for f in self.templates_path.iterdir() if f.is_file()],
            'certificates': [f.name for f in self.certificates_path.iterdir() if f.is_file()],
            'root': [f.name for f in self.files_path.iterdir() if f.is_file()]
        }

    def cleanup_old_certificates(self, days: int = 7) -> int:
        """
        Удаляет старые сертификаты.

        Args:
            days: Количество дней для хранения

        Returns:
            int: Количество удаленных файлов
        """
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0

        for cert_file in self.certificates_path.iterdir():
            if cert_file.is_file():
                file_time = datetime.fromtimestamp(cert_file.stat().st_mtime)
                if file_time < cutoff_date:
                    try:
                        cert_file.unlink()
                        deleted_count += 1
                        logger.info(f"Удален старый сертификат: {cert_file.name}")
                    except Exception as e:
                        logger.error(f"Ошибка при удалении файла {cert_file.name}: {e}")

        return deleted_count

    def get_file_info(self, filepath: Path) -> Dict[str, Any]:
        """Получает информацию о файле."""
        try:
            stat = filepath.stat()
            return {
                'name': filepath.name,
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime),
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'extension': filepath.suffix,
                'exists': True
            }
        except Exception as e:
            logger.error(f"Ошибка при получении информации о файле {filepath}: {e}")
            return {'exists': False, 'error': str(e)}
