# ReceiptScan - Telegram Bot для проверки чеков

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Гибкий Telegram бот для проверки чеков с использованием OCR (Tesseract) и настраиваемой валидации данных. Бот принимает фотографии чеков и PDF файлы, извлекает из них данные и проверяет их на подлинность по настраиваемым правилам.

## 🚀 Основные возможности

- 📸 **OCR обработка** - Распознавание текста с чеков с помощью Tesseract
- 🔍 **Гибкий парсинг** - Поддержка различных форматов номеров телефонов и сумм
- ✅ **Настраиваемая валидация** - Правила валидации через YAML конфигурацию
- 📄 **Поддержка PDF** - Обработка как изображений, так и PDF документов
- 🐳 **Docker готовность** - Полная контейнеризация для легкого развертывания
- 📊 **Подробная отчетность** - Детальные результаты валидации с оценкой уверенности

## 📋 Поддерживаемые форматы

### Номера телефонов
- `7 987 933 55 15` (с пробелами)
- `7-987-933-55-15` (с тире)
- `7(987)933-55-15` (со скобками и тире)
- `+7 987 933 55 15` (с плюсом)
- `8 987 933 55 15` (с кодом 8)
- `79879335515` (без разделителей)

### Суммы
- `1500Р`, `1500р`, `1500руб`
- `1500 ₽` (с символом рубля)
- `1500,00 руб`, `1500.00 руб`
- `Сумма: 1500`, `Итого: 1500`
- `К оплате: 1500`, `Перевод: 1500`

### Файлы
- **Изображения**: JPG, JPEG, PNG, BMP, TIFF
- **Документы**: PDF

## 🛠️ Установка и запуск

### Быстрый старт с Docker

1. **Клонируйте репозиторий:**
```bash
git clone https://github.com/videlboga/ReceiptScan.git
cd ReceiptScan
```

2. **Настройте переменные окружения:**
```bash
cd docker
cp env_example.txt .env
# Отредактируйте .env файл, добавив токен бота
```

3. **Настройте конфигурацию валидации:**
```bash
cd ..
cp validation_config_example.yaml validation_config.yaml
# Отредактируйте validation_config.yaml под свои нужды
```

4. **Запустите бота:**
```bash
cd docker
docker-compose -f docker-compose-flexible-v1.yml up -d
```

### Локальная установка

1. **Установите системные зависимости:**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng

# Arch Linux
sudo pacman -S tesseract tesseract-data-rus tesseract-data-eng

# macOS
brew install tesseract tesseract-lang
```

2. **Установите Python зависимости:**
```bash
pip install -r requirements.txt
```

3. **Настройте конфигурацию:**
```bash
cp validation_config_example.yaml validation_config.yaml
cp bot_config_example.py bot_config.py
cp config/settings_example.py config/settings.py
# Отредактируйте файлы конфигурации
```

4. **Запустите бота:**
```bash
python bot_flexible_v1.py
```

## ⚙️ Конфигурация

### Основные настройки

Файл `validation_config.yaml` содержит все настройки валидации:

```yaml
validation:
  min_confidence: 50.0        # Минимальная уверенность OCR
  amount_tolerance: 0.01      # Толерантность для сумм (руб)

phone_validation:
  valid_phones:               # Валидные номера телефонов
    - '79879335515'
    - '+79879335515'
    - '7 987 933 55 15'

amount_validation:
  valid_amounts:              # Валидные суммы
    - 1500.00
    - 2000.0

account_validation:
  valid_accounts:             # Валидные банковские счета
    - '40817810099910004312'
  valid_cards:               # Валидные номера карт
    - '2200590431900533'
```

### Переменные окружения

- `BOT_TOKEN` - Токен Telegram бота (обязательно)
- `DATABASE_URL` - URL базы данных (по умолчанию SQLite)
- `FILES_PATH` - Путь к папке с файлами
- `TESSERACT_LANG` - Язык для Tesseract (по умолчанию 'rus+eng')
- `ENABLE_DEBUG` - Режим отладки (true/false)

## 📱 Использование

### Команды бота

- `/start` - Начать работу с ботом
- `/config` - Показать текущую конфигурацию
- `/help` - Показать справку

### Отправка чеков

1. Отправьте фотографию чека или PDF файл боту
2. Бот автоматически проанализирует содержимое
3. Получите подробный отчет о валидации

### Пример результата

```
📊 Результат гибкой валидации чека:

🎉 СТАТУС: ЧЕК ВАЛИДЕН!
📈 Оценка уверенности: 85.5%

📋 Детали валидации:
✅ amount: найдено
✅ recipient: найдено
✅ Телефон 79879335515: валиден
✅ Сумма 1500.0: валидна
✅ Уверенность распознавания: 78.2%

🔍 Найденные данные:
💰 Сумма: 1500.0 руб
📱 Телефон: 79879335515
🏦 Счет/карта: не найдены
📅 Дата: 14.09.2024
🕐 Время: 16:30:45
📊 Уверенность OCR: 78.2%
```

## 🏗️ Структура проекта

```
ReceiptScan/
├── bot/                           # Telegram бот
│   ├── __init__.py
│   ├── handlers.py
│   └── main.py
├── bot_flexible_v1.py             # Основной гибкий бот
├── config/                        # Конфигурация
│   ├── __init__.py
│   ├── settings.py                # Основные настройки
│   └── settings_example.py        # Пример настроек
├── database/                      # База данных
│   ├── __init__.py
│   ├── database.py
│   └── models.py
├── docker/                        # Docker конфигурация
│   ├── Dockerfile_flexible_v1
│   ├── docker-compose-flexible-v1.yml
│   ├── env_example.txt
│   └── requirements_flexible_v1.txt
├── files/                         # Файлы и шаблоны
│   ├── file_manager.py
│   └── templates/
├── ocr/                          # OCR модуль
│   ├── __init__.py
│   ├── receipt_parser.py
│   └── tesseract_processor.py
├── validation/                   # Валидация
│   ├── __init__.py
│   ├── enhanced_parser_v1.py
│   ├── flexible_parser_v1.py
│   ├── flexible_validator_v1.py
│   ├── ultra_parser_v1.py
│   └── validator.py
├── validation_config.yaml        # Конфигурация валидации (создать из example)
├── validation_config_example.yaml # Пример конфигурации
├── bot_config_example.py         # Пример конфигурации бота
├── requirements.txt              # Python зависимости
├── setup_database.py            # Настройка базы данных
└── README.md                    # Документация
```

## 🔧 Разработка

### Добавление новых правил валидации

1. Отредактируйте `validation_config.yaml`
2. Добавьте новые валидные номера, суммы или счета
3. Перезапустите бота

### Создание собственных шаблонов сертификатов

Создайте файл в `files/templates/` с плейсхолдерами:
- `{date}` - дата проверки
- `{time}` - время проверки
- `{amount}` - сумма чека
- `{recipient}` - счет получателя
- `{confidence}` - уверенность распознавания

### Расширение функционала

1. Добавьте новые обработчики команд в `bot/handlers.py`
2. Реализуйте дополнительные проверки в `validation/`
3. Улучшите парсинг в `ocr/receipt_parser.py`

## 📊 Мониторинг и логирование

Логи сохраняются в:
- Консоль (DEBUG/INFO уровень)
- `logs/bot.log` (ротация каждый день)

Для мониторинга контейнера:
```bash
docker-compose -f docker/docker-compose-flexible-v1.yml logs -f
```

## 🔒 Безопасность

- Валидация входных данных
- Ограничение размера файлов
- Логирование всех операций
- Защита от спама
- Конфигурационные файлы с секретами в .gitignore

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## 📄 Лицензия

Этот проект распространяется под лицензией MIT. См. файл [LICENSE](LICENSE) для подробностей.

## 🆘 Поддержка

При возникновении проблем:

1. Проверьте логи в `logs/bot.log`
2. Убедитесь в правильности настроек
3. Проверьте качество фотографий чеков
4. Создайте [Issue](https://github.com/videlboga/ReceiptScan/issues) с подробным описанием проблемы

## 🙏 Благодарности

- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) - за мощный движок OCR
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - за отличную библиотеку для Telegram ботов
- [loguru](https://github.com/Delgan/loguru) - за удобное логирование

---

**Сделано с ❤️ для автоматизации проверки чеков**
