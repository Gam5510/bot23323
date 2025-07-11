# Бот курса валют для Telegram

Автоматический бот для публикации курсов валют в Telegram каналах.

## Возможности

- 📊 Автоматическая публикация курсов USD, EUR, RUB
- ⏰ Настраиваемое время публикации
- 📢 Рекламные посты
- 👥 Управление несколькими администраторами
- 📋 Управление списком каналов
- 🔄 Включение/отключение рекламы

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Настройте конфигурацию в файле `config.json`:
```json
{
  "admin_ids": [5699915010, 1234567890],
  "token": "YOUR_BOT_TOKEN"
}
```

3. Запустите бота:
```bash
python bot.py
```

## Управление администраторами

### Добавление администратора
1. Откройте главное меню бота
2. Нажмите "👥 Администраторы"
3. Нажмите "➕ Добавить админа"
4. Отправьте Telegram ID нового администратора

### Удаление администратора
1. Откройте меню "👥 Администраторы"
2. Выберите администратора
3. Нажмите "❌ Удалить"

**Примечание:** Администратор не может удалить самого себя.

## Команды

- `/start` или `/menu` - Главное меню

## Структура файлов

- `bot.py` - Основной код бота
- `config.json` - Конфигурация (токен, администраторы)
- `storage.json` - Данные (каналы, реклама, настройки)
- `requirements.txt` - Зависимости Python

## Формат поста

Пост автоматически формируется в следующем формате:
```
15 - Yanvar 2024. 💵

🇺🇸 100 dollar = 12,500 sum 🇺🇿
🇪🇺 100 euro = 13,800 sum 🇺🇿
🇷🇺 1000 ruble = 135 sum 🇺🇿

@channel_username
Reklama: Ваша реклама здесь
```

## Источник данных

Курсы валют получаются с официального сайта Центрального банка Узбекистана: https://cbu.uz/uz/arkhiv-kursov-valyut/json/
