#!/bin/bash
# Скрипт для запуска гибкого бота проверки чеков v1 в Docker

echo "🚀 Запуск гибкого бота проверки чеков v1 в Docker..."

# Проверяем наличие .env файла
if [ ! -f "docker/.env" ]; then
    echo "❌ Файл docker/.env не найден!"
    echo "📝 Создайте файл docker/.env с содержимым:"
    echo "BOT_TOKEN=your_bot_token_here"
    echo "ENABLE_DEBUG=false"
    exit 1
fi

# Переходим в директорию docker
cd docker

# Останавливаем существующий контейнер если он запущен
echo "🛑 Останавливаем существующий контейнер..."
docker-compose -f docker-compose-flexible-v1.yml down

# Собираем и запускаем новый контейнер
echo "🔨 Собираем Docker образ..."
docker-compose -f docker-compose-flexible-v1.yml build

echo "🚀 Запускаем контейнер..."
docker-compose -f docker-compose-flexible-v1.yml up -d

# Показываем статус
echo "📊 Статус контейнера:"
docker-compose -f docker-compose-flexible-v1.yml ps

echo "📋 Логи контейнера:"
docker-compose -f docker-compose-flexible-v1.yml logs -f --tail=50
