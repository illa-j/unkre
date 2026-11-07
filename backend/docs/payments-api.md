# Payments API

Маршрути підключені в `main.py`. Користувацькі запити використовують access JWT
у cookie `cl_access_token`, як інші маршрути користувача. Ідентифікатор користувача
береться з авторизованої сесії.

| Метод | Шлях | Призначення |
| --- | --- | --- |
| GET | `/payments/prices` | Поточна ціна одного кредиту для crypto та Stars |
| POST | `/payments/crypto` | Створити рахунок ATLOS |
| POST | `/payments/stars` | Створити рахунок Telegram Stars |
| GET | `/payments?provider=atlos` | Власні криптооплати |
| GET | `/payments?provider=telegram_stars` | Власні оплати Stars |
| GET | `/payments/{id}?provider=atlos` | Одна власна оплата вибраного провайдера |
| POST | `/payments/webhooks/atlos` | Підтвердження ATLOS із заголовком `Signature` |
| POST | `/payments/webhooks/telegram` | Telegram Update із секретом вебхука |

Для списку доступні `limit` від 1 до 100 та `offset` від 0. Чужий платіж або
платіж іншого провайдера повертає 404. Створення та перегляд вимагають cookie;
вебхуки перевіряють автентичність провайдера.

## Налаштування

`PaymentSettings` читає `.env`. Вкажіть узгоджені ціни:

- `CRYPTO_PRICE_PER_CREDIT`: точна десяткова ціна кредиту;
- `CRYPTO_CURRENCY`: валюта рахунка, за замовчуванням `USD`;
- `STARS_PRICE_PER_CREDIT`: додатна ціла кількість Stars за кредит.

Сума рахунка дорівнює ціні з налаштувань, помноженій на кількість кредитів.
Порожня ціна вимикає створення рахунків відповідного провайдера (503),
збережена історія та підтвердження попередніх оплат залишаються доступними.

Для ATLOS задайте `ATLOS_MERCHANT_ID` і `ATLOS_API_SECRET` та налаштуйте
postback URL `https://YOUR_API/payments/webhooks/atlos` у Merchant Panel.
Сервіс перевіряє HMAC-SHA256 сирого тіла запиту за заголовком `Signature`.
[Підпис ATLOS](https://atlos.io/docs/postback/signature).

Для Stars задайте `TELEGRAM_BOT_TOKEN`. За замовчуванням бот обробляє платежі
через polling; одночасно реєструвати Telegram webhook не потрібно.
Якщо замість polling використовується webhook, задайте `TELEGRAM_WEBHOOK_SECRET`
і зареєструйте `https://YOUR_API/payments/webhooks/telegram` через `setWebhook`
з тим самим `secret_token` та `allowed_updates=["message", "pre_checkout_query"]`.
API перевіряє заголовок `X-Telegram-Bot-Api-Secret-Token`.
[Telegram setWebhook](https://core.telegram.org/bots/api#setwebhook).

Додаткові параметри: `PAYMENT_INVOICE_TTL_SECONDS` (3600) та
`PAYMENT_PROVIDER_TIMEOUT_SECONDS` (10). Клієнти HTTP і Bot створюються
залежностями запиту та закриваються після його обробки.

## Створення рахунка

Для обох провайдерів тіло однакове:

```json
{
  "credits": 100,
  "idempotency_key": "unique-order-key"
}
```

Клієнт передає додатну цілу кількість кредитів. Суму, валюту й платника
визначає сервер. Додаткові поля, зокрема `amount`, `stars` та `user_id`,
відхиляються. Stars-рахунок може створити будь-який акаунт: якщо Telegram
не прив'язаний, посилання оплачується з будь-якого Telegram-акаунта, а
кредити зараховуються власнику рахунку UNKRE.
Під час підтвердження зберігається Telegram ID фактичного платника, потрібний
для подальшої перевірки подій та повернення Stars.

Відповідь 201 містить `id`, провайдера, статус, кількість кредитів, суму,
валюту, `checkout_url` та часові поля. Відкривайте отриманий `checkout_url`.
Повтор того самого замовлення з тим самим ключем повертає наявний рахунок.
Для нового замовлення використовуйте новий ключ; зміна параметрів із наявним
ключем повертає 409.

Браузерні запити на створення перевіряють `Origin`; окремий origin фронтенду
має бути в `CORS_ALLOWED_ORIGINS`. Відповіді оплат мають `Cache-Control: no-store`.
Для створення рахунків також потрібен `X-CSRF-Token`, отриманий через
попередній GET з cookies. [CSRF і API guard](api-guard.md).

## Підтвердження

Створення рахунка і Stars pre-checkout не зараховують кредити. Telegram
pre-checkout резервує рахунок та повертає `answerPreCheckoutQuery` у відповіді
вебхука. Commit завершується перед відправленням схвалення.
[Відповідь Telegram через вебхук](https://core.telegram.org/bots/api#making-requests-when-getting-updates).

Підтверджений ATLOS postback або Telegram `successful_payment` проводить
зарахування один раз. Статус оплати, баланс і запис покупки зберігаються
атомарно в поточному `session_scope()`. Підтвердження після локального
прострочення також обробляється. У користувацькому API немає маршруту
самостійного позначення платежу оплаченим.

Відсутня авторизація або неправильний підпис ATLOS дає 401, неправильний
секрет Telegram чи заборонений Origin — 403, конфлікт замовлення — 409,
неправильні дані — 422, недоступний або неналаштований провайдер — 503.

## Postback URL

`PAYMENT_POSTBACK_URL` is sent as `PostbackUrl` in every ATLOS
`Invoice/Create` request, so the merchant panel setting is not required. Set it
to the public endpoint:

```text
https://unkre.cc/api/payments/webhooks/atlos
```

Telegram Stars uses the bot's polling handlers for `pre_checkout_query` and
`successful_payment`; do not register the API webhook while the bot is polling.
If a provider callback is missed, the worker attempts recovery every five minutes
(ATLOS `Transaction/List`, Telegram `getStarTransactions`). Invalid records are
logged and isolated so they do not prevent other valid payments from settling.
