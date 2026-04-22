# Inline Yandex Link Bot

Telegram inline-бот на `aiogram`, который принимает ссылки на треки Яндекс Музыки и отправляет короткую карточку с двумя действиями:

- `ОТКРЫТЬ В ВЕБ`
- `ОТКРЫТЬ В ПРИЛОЖЕНИИ`

Метаданные трека берутся без авторизации напрямую со страницы Яндекс Музыки. Для открытия в приложении используется отдельный HTTP redirect-сервис: Telegram открывает обычный `https://` URL, а уже он пытается передать пользователя в `yandexmusic://...` и при неудаче падает обратно в веб-страницу трека.

## Что умеет

- Принимает веб-ссылки вида `https://music.yandex.ru/album/2448178/track/21404459`
- Принимает app-ссылки вида `yandexmusic://album/2448178/track/21404459`
- Канонизирует ссылку в оба формата
- Показывает название, исполнителя и длительность в inline-результате
- Умеет отдельно задавать proxy для Telegram и для запросов к Яндекс Музыке
- Поднимает отдельный `web` контейнер для app-redirect по домену

## Подготовка

1. Создай `.env` по образцу `.env.example`
2. Заполни `BOT_TOKEN`
3. Если Telegram нужен через proxy, задай `TELEGRAM_PROXY` или общий `HTTP_PROXY`
4. Если запросы к Яндексу не нужно гнать через тот же proxy, оставь `METADATA_PROXY=` пустым
5. Для кнопки открытия в приложении задай `APP_REDIRECT_BASE_URL`, например `https://music-links.example.com`
6. В `@BotFather` включи inline mode: `/setinline`

## Запуск через Docker Compose

```bash
docker compose up --build -d
```

Compose поднимает два контейнера:

- `bot` с inline-ботом
- `web` с redirect endpoint `GET /open?app=yandexmusic://album/.../track/...`

Логи:

```bash
docker compose logs -f
```

Остановка:

```bash
docker compose down
```

## Локальный запуск без Docker

Нужен `Python 3.10+`. Если системный `python3` указывает на более старую версию, укажи установленный интерпретатор явно, например `python3.12`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m bot
```

Для тестового прогона можно так же явно указать нужный бинарь, например `python3.12 -m unittest discover -s tests -v`.

## Как пользоваться

В любом чате набери:

```text
@your_bot_username https://music.yandex.ru/album/2448178/track/21404459
```

После выбора inline-результата бот отправит сообщение примерно такого вида:

```text
🎵 'Bout It
JMSN • 06:34

ОТКРЫТЬ В ВЕБ
ОТКРЫТЬ В ПРИЛОЖЕНИИ
```

## Ограничения

- Бот поддерживает ссылки на треки, в которых есть и `album_id`, и `track_id`
- Яндекс Музыка может иногда отдавать SmartCaptcha или урезанную страницу вместо нормального трека. В этом случае бот покажет код ошибки вроде `captcha_required`
- Если один proxy используется и для Telegram, и для Яндекса, вероятность капчи обычно выше. Для этого и нужен отдельный `METADATA_PROXY`
