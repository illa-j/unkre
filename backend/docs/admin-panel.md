# Адмін-панель

Веб-панель живе на `/admin` у Next.js і працює з `/admins/*` API. Це окремий
контур авторизації: admin-токени в власних cookie (`ADMIN_ACCESS_TOKEN_COOKIE`,
`ADMIN_REFRESH_TOKEN_COOKIE`), scope `admin`, ніякого зв'язку з користувацькою
сесією студії.

## Перший адміністратор

Публічної реєстрації адміністраторів немає. Основний спосіб — змінні оточення:

```env
ADMIN_NAME=owner
ADMIN_PASSWORD=replace-with-a-strong-password
```

Під час старту API (FastAPI lifespan) `ensure_bootstrap_admin()` перевіряє, чи
існує такий username, і створює **owner**-акаунт з Argon2-хешем пароля. Правила:

- потрібні обидва значення; інакше створення пропускається з попередженням;
- пароль коротший за 10 символів або ім'я коротше за 2 — помилка в лог, без
  падіння API;
- існуючий акаунт ніколи не перезаписується: зміна `ADMIN_PASSWORD` для вже
  створеного адміністратора не діє (пароль змінюється окремо);
- кілька uvicorn-воркерів безпечні: конкурентний INSERT перетворюється на no-op.

Для додаткових адміністраторів є скрипт і маршрут `POST /admins/team`:

```sh
docker compose run --rm \
  -e ADMIN_PASSWORD='another-strong-password' \
  web python scripts/create_admin.py operator
```

Скрипт ідемпотентний: якщо username вже існує, нічого не змінюється.

## Доступ

| Рівень | Що дозволено |
| --- | --- |
| Administrator | усе, крім `/admins/team` |
| Owner | усе, включно зі створенням адміністраторів |

`GET /admins/team` і `POST /admins/team` повертають 403 для не-owner акаунтів.
Усі інші `/admins/*` маршрути вимагають лише валідний admin access token.

## Маршрути панелі

| Метод | Шлях | Призначення |
| --- | --- | --- |
| GET | `/admins/overview` | Зведені метрики та 14-денний ряд |
| GET | `/admins/users` | Пошук, фільтр `state=active\|blocked`, пагінація |
| PATCH | `/admins/users/{id}` | Блокування та розблокування |
| POST | `/admins/users/{id}/credits` | Ручне коригування балансу (ledger `adjustment`) |
| GET | `/admins/generations` | Усі генерації з фільтрами `state`, `query` |
| GET | `/admins/payments` | Платежі з фільтрами `state`, `provider` |
| GET | `/admins/promo-codes` | Список промокодів |
| POST | `/admins/promo-codes` | Створення коду |
| PATCH | `/admins/promo-codes/{id}` | Увімкнення / вимкнення |
| GET | `/admins/promo-codes/{id}/redemptions` | Хто і коли активував код |
| GET | `/admins/settings` | Системні налаштування з походженням значення |
| PATCH | `/admins/settings/{key}` | Перевизначити значення |
| DELETE | `/admins/settings/{key}` | Повернути env-значення |
| GET | `/admins/workflows` | Каталог моделей для панелі |
| PATCH | `/admins/workflows/{id}/credits` | Ціна генерації в кредитах |
| GET | `/admins/team` | Список адміністраторів (owner) |
| POST | `/admins/team` | Створити адміністратора (owner) |

`POST`/`PATCH`/`DELETE` проходять ту саму CSRF-перевірку, що й решта API:
cookie `csrf_token` + заголовок `X-CSRF-Token`.

## Баланс і ledger

Ручне коригування не змінює `wallets.credits` напряму: створюється транзакція
типу `adjustment` з сумою, балансом до/після, унікальним idempotency-ключем
`admin:<uuid7>` і текстовим поясненням. Тому історія завжди відновлювана, а
від'ємний результат неможливий — сервіс повертає 422.

## Обмеження

- Пошук і фільтри працюють на стороні SQL, пагінація — 25 записів за
  замовчуванням, максимум 100.
- Метрики охоплюють останні 14 днів для графіка та 24 години / 7 / 30 днів для
  карток; «усі часи» використовуються лише там, де це позначено.
- `GET /admins/overview` сумує `transactions.amount` типу `spend`, тому сума
  ніколи не включає покупки кредитів.
