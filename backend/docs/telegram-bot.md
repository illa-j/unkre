# Telegram-бот

Окремий процес `adapters.bot.main` на aiogram 3: довге опитування (long
polling), жодного вебхука й жодного впливу на API. Команда `/start` відповідає
англійською назвою бренду, коротким описом продукту та кнопкою, що відкриває
Telegram MiniApp.

## Налаштування

| Змінна | Призначення |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Токен від @BotFather (той самий, що для Stars-платежів) |
| `TELEGRAM_MINIAPP_URL` | URL, який відкриває кнопка, наприклад `https://unkre.com/studio` |
| `TELEGRAM_BOT_POLLING_TIMEOUT` | Таймаут getUpdates, типово 10 секунд |
| `USER_INITIAL_CREDITS` | Скільки безкоштовних кредитів згадувати в описі |

Telegram приймає для `web_app`-кнопок лише `https://`. Виняток —
`http://localhost` і `http://127.0.0.1` для локальних експериментів; інші
`http://`-адреси відхиляються на старті з помилкою конфігурації.

У BotFather увімкніть MiniApp (Menu Button → Configure Mini App) на той самий
URL. Кнопка в повідомленні працює і без Menu Button, але меню дає швидший
доступ.

MiniApp відкривається у WebView/iframe Telegram, тому для збереження сесії
потрібні `COOKIE_SAMESITE=none` і `COOKIE_SECURE=true` на HTTPS-домені.
Інакше `initData`-логін повертає `200`, але наступний `/users/me` уже не бачить
session-cookie.

## Запуск

```sh
# у складі стека
docker compose up -d bot

# локально
cd backend
PYTHONPATH=src .venv/bin/python -m adapters.bot.main
```

Без `TELEGRAM_BOT_TOKEN` процес завершується з попередженням у лог; без
`TELEGRAM_MINIAPP_URL` — з помилкою. Обидва випадки — код виходу 0, а сервіс у
Compose має `restart: on-failure`, тому вимкнений бот не крутиться в циклі
перезапусків.

Перед стартом polling бот знімає вебхук (`delete_webhook`), тому один і той
самий токен не може одночасно обслуговуватися вебхуком і цим процесом.

## Що надсилає /start

- `UNKRE — uncensored AI image studio.`
- опис: Krea 2, Qwen Image 2.1, референс-фото, персонажі, LoRA;
- переваги: безкоштовні кредити для нових акаунтів, вхід через Google або
  Telegram;
- inline-кнопка `Open UNKRE Studio` з `WebAppInfo`.

Текст і кнопки зібрані в `src/adapters/bot/texts.py`, обробник — у
`src/adapters/bot/handlers.py` (`send_start`, `start_keyboard`), тому їх можна
оновлювати без зміни запуску.

## Telegram Stars

The bot runs in long-polling mode and therefore handles Stars payment updates
itself: `pre_checkout_query` is validated and answered, and a successful
`invoice_payment` credits the wallet. The API webhook
`/payments/webhooks/telegram` remains available for a webhook-based deployment,
but it must not be registered while this bot uses `getUpdates` — Telegram allows
only one delivery mode per bot.

`allowed_updates` must include both `message` and `pre_checkout_query`. The worker
also reconciles the last seven days of `getStarTransactions` every five minutes,
so a missed bot update can still be recovered. Set `TELEGRAM_WEBHOOK_SECRET` only
for the webhook deployment; the polling bot does not need it.
