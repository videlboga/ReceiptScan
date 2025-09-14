"""Обработка изображений с помощью Tesseract OCR."""
import pytesseract
from PIL import Image
import io
from typing import Tuple, Optional
from config.settings import TESSERACT_LANG, ENABLE_DEBUG
from loguru import logger

class TesseractProcessor:
    """Процессор для работы с Tesseract OCR."""

    def __init__(self):
        self.language = TESSERACT_LANG
        self.config = '--oem 3 --psm 6'  # Оптимальные настройки для чеков

    def extract_text(self, image_data: bytes) -> Tuple[str, float]:
        """
        Извлекает текст из изображения.

        Args:
            image_data: Байты изображения

        Returns:
            Tuple[str, float]: Текст и уверенность распознавания
        """
        try:
            # Открываем изображение
            image = Image.open(io.BytesIO(image_data))

            # Конвертируем в RGB если необходимо
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Извлекаем текст с уверенностью
            data = pytesseract.image_to_data(
                image,
                lang=self.language,
                config=self.config,
                output_type=pytesseract.Output.DICT
            )

            # Собираем текст
            text_parts = []
            confidences = []

            for i in range(len(data['text'])):
                if int(data['conf'][i]) > 0:  # Игнорируем пустые блоки
                    text_parts.append(data['text'][i])
                    confidences.append(int(data['conf'][i]))

            full_text = ' '.join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            if ENABLE_DEBUG:
                logger.info(f"Извлечен текст: {full_text[:100]}...")
                logger.info(f"Уверенность: {avg_confidence:.2f}%")

            return full_text, avg_confidence

        except Exception as e:
            logger.error(f"Ошибка при извлечении текста: {e}")
            return "", 0.0

    def extract_text_simple(self, image_data: bytes) -> str:
        """
        Простое извлечение текста без детальной информации.

        Args:
            image_data: Байты изображения

        Returns:
            str: Извлеченный текст
        """
        try:
            image = Image.open(io.BytesIO(image_data))

            if image.mode != 'RGB':
                image = image.convert('RGB')

            text = pytesseract.image_to_string(
                image,
                lang=self.language,
                config=self.config
            )

            return text.strip()

        except Exception as e:
            logger.error(f"Ошибка при простом извлечении текста: {e}")
            return ""

    def preprocess_image(self, image_data: bytes) -> bytes:
        """
        Предобработка изображения для улучшения распознавания.

        Args:
            image_data: Исходные байты изображения

        Returns:
            bytes: Обработанные байты изображения
        """
        try:
            image = Image.open(io.BytesIO(image_data))

            # Конвертируем в RGB
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Увеличиваем контрастность
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.5)

            # Увеличиваем резкость
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(2.0)

            # Сохраняем обработанное изображение
            output = io.BytesIO()
            image.save(output, format='PNG')
            return output.getvalue()

        except Exception as e:
            logger.error(f"Ошибка при предобработке изображения: {e}")
            return image_data
