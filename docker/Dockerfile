# Dockerfile для бота проверки чеков
FROM python:3.11-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir pyyaml

# Копируем исходный код
COPY . .

# Создаем необходимые директории
RUN mkdir -p logs files/templates files/certificates

# Устанавливаем переменные окружения
ENV PYTHONPATH=/app:/app/bot:/app/files:/app/database:/app/ocr:/app/validation
ENV TESSERACT_LANG=rus

# Создаем пользователя для безопасности
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Команда запуска (по умолчанию запускаем гибкую версию)
CMD ["python", "docker/bot_flexible_v1.py"]
