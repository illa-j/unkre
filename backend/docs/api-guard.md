# API guard

`src/adapters/api/guard/config.py` підключає `fastapi-guard` у `main.py`.
Налаштування читаються з `.env` через `ApiSettings`; `lifespan` залишається порожнім.

Guard обмежує кількість запитів на IP, блокує повторні підозрілі запити та
налаштовані User-Agent, перевіряє URL, query parameters і заголовки, додає
заголовки безпеки та CORS. JSON тіла перевіряють схеми API й сервіси:
regex-сканування тіл вимкнене, щоб приймати довільні prompts, credentials та
підписані вебхуки без помилкових блокувань і зміни їхніх байтів.

За замовчуванням ліміт — 1200 запитів за 60 секунд. Redis використовує той самий
`REDIS_URL`, що й черга, з окремим `SECURITY_REDIS_PREFIX`. Ліміти та блокування
спільні між API workers. Якщо Redis недоступний, guard повертає 503.
`SECURITY_REDIS_ENABLED=false` залишає ліміти в пам'яті окремого процесу.

`CORS_ALLOWED_ORIGINS` містить явні origins через кому, наприклад
`http://localhost:3000,https://app.example.com`. Wildcard заборонений, оскільки
API використовує cookies. Порожнє значення дозволяє браузеру працювати лише
з того самого origin. Дозволені сторонні origins отримують credentialed CORS
та доступ до response header `X-CSRF-Token`.

## CSRF і cookies

JWT access/refresh залишаються в HttpOnly cookies. Окремий підписаний
CSRF-токен зберігається в `csrf_token` cookie й повертається в заголовку
`X-CSRF-Token`. Підпис використовує JWT access secret з окремим префіксом `csrf:`;
токени працюють між workers без збереження в БД чи Redis.

Перед першим POST, зокрема перед входом, зробіть GET `/users/me` із
`credentials: "include"`. Навіть відповідь 401 встановлює CSRF cookie та повертає
токен. Додавайте цей токен у `X-CSRF-Token` для POST, PUT, PATCH і DELETE:

```javascript
const bootstrap = await fetch(`${api}/users/me`, { credentials: "include" });
const csrfToken = bootstrap.headers.get("X-CSRF-Token");

const response = await fetch(`${api}/users/auth/challenge`, {
  method: "POST",
  credentials: "include",
  headers: {
    "Content-Type": "application/json",
    "X-CSRF-Token": csrfToken,
  },
  body: JSON.stringify({ provider: "google" }),
});
```

Сервер перевіряє підпис cookie, збіг cookie з заголовком та Origin.
Відсутній, підмінений токен або сторонній Origin дає 403 до виконання маршруту.
Відповіді з CSRF-токеном мають `Cache-Control: no-store`.

Лише точні шляхи `/payments/webhooks/atlos` і `/payments/webhooks/telegram`
звільнені від CSRF. Вони продовжують проходити guard, ліміти та перевірки
підпису ATLOS / секрету Telegram у наявних маршрутах.
`CSRF_EXEMPT_PATHS` дозволяє явно додати інші точні шляхи через кому.

`Referer` видаляється на вході API перед guard: `guard-core` 4.4 помилково
сприймає звичайні localhost/private-network URL у цьому заголовку як SSRF.
API не використовує `Referer` і не завантажує вказані в ньому адреси.
`Origin` залишається без змін; CSRF продовжує перевіряти origin та підписаний
токен. URL, query parameters та інші заголовки проходять перевірки guard.

## HTTPS і proxy

У production установіть `COOKIE_SECURE=true`, `SECURITY_ENFORCE_HTTPS=true`.
Для frontend і API на різних sites потрібні `COOKIE_SAMESITE=none` та HTTPS.
`SECURITY_TRUSTED_PROXIES` задає IP/CIDR фактичного reverse proxy; за замовчуванням
список порожній. Guard використовує forwarded IP і protocol лише від цих
проксі. Налаштування proxy headers ASGI-сервера також мають довіряти лише
фактичному проксі. HSTS додається, коли ввімкнено HTTPS enforcement.

`SECURITY_PASSIVE_MODE=true` переводить перевірки fastapi-guard у режим
логування; CSRF-перевірка залишається активною.

API бібліотеки: [FastAPI Guard](https://github.com/guard-core/fastapi-guard/blob/master/docs/tutorial/first-steps.md).

## Ліміти на окремі маршрути

Окрім глобального ліміту fastapi-guard, `RouteRateLimitMiddleware`
(`src/adapters/api/rate_limit.py`) застосовує окремі бюджети на IP для
чутливих і дорогих маршрутів:

| Маршрут | Ліміт |
| --- | --- |
| `POST /users/auth/challenge`, `/google`, `/telegram`, `/telegram-webapp` | 10 / хв |
| `POST /users/auth/refresh` | 60 / хв |
| `POST /payments/*` | 20 / хв |
| `POST /payments/webhooks/*` | 300 / хв |
| `POST /generations` | 10 / хв |
| `POST/PATCH/DELETE /presets*` | 30 / хв |
| `POST /promos/redeem` | 15 / хв |
| `GET /admins*` та інші admin-запити | 300 / хв |
| Усі інші маршрути | 300 / хв |

Ліміти зберігаються в Redis у просторі `SECURITY_REDIS_PREFIX` + `route:`.
Якщо Redis недоступний, middleware переходить на процес-локальний лічильник,
а fastapi-guard зберігає свою fail-closed поведінку. Відповідь `429` містить
`Retry-After`, `X-RateLimit-Limit` і `X-RateLimit-Remaining`.

Вимкнути додаткові маршрутні ліміти можна через
`SECURITY_ROUTE_RATE_LIMIT_ENABLED=false`.

Nginx додатково обмежує трафік до `/api/users/auth/`, `/api/payments/`,
`/api/generations`, `/api/` та фронтенду. Для реального IP використовується
`CF-Connecting-IP` від cloudflared; локальні запити падають на `$remote_addr`.
