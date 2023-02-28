# Проводим викторину
Данный проект предствляет собой `викторину`, которая реализована посредством ботов на 2-х платформах: `VK` и `Telegram`.

## Что необходимо для запуска
Для данного проекта необходим `Python3.6` (или выше).
Создадим виртуальное окружение в корневой директории проекта:
```
python3 -m venv env
```
После активации виртуального окружения установим необходимые зависимости:
```
pip install -r requirements.txt
```
Также заранее создадим файл `.env` в директории проекта.

## Создаём ботов
Напишите [отцу ботов](https://telegram.me/BotFather) для создания телеграм бота.

Запишите его токен в `.env`:
```
QUIZ_BOT_TG_TOKEN=
```
Для создания VK-бота для начала создадим группу, в которой уже потом запустим самого бота. В `управлении` созданной группы во вкладке `сообщения` убедимся, что сами сообщения включены, добавим их в левое меню и запишем преветствие.

Для получения `API токена` необходимо создать ключ во вкладке настроек `Работа с API`. Разрешим приложению `доступ к сообщениям сообщества`. Запишем токен в файл `.env`:
```
QUIZ_BOT_VK_TOKEN=
```
## Подключаем Redis
Регистрируемся на [Redis](https://redis.com/) и заводим себе удаленную `базу данных`. Для подключения к ней вам понадобятся `host`, `port` и `password`. Запишите их в файле `.env`:
```
REDIS_HOST=
REDIS_PORT=
REDIS_PASSWORD=
```
## Запуск ботов
Боты запускаются командами
```
python tg_bot.py
python vk_bot.py 
```