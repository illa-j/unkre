# User Service

`domain.services.user.UserService` використовує порти репозиторіїв та перевірки
ідентичності. SQLAlchemy, PyJWT та HTTP розташовані в адаптерах. Для кожного
API-запиту створюється окрема сесія через `session_scope()`; commit завершується до відправлення
відповіді, помилки відкочують транзакцію. Імпорт сервісу не відкриває БД.

## Налаштування

Скопіюйте `.env.example` у `.env`, задайте PostgreSQL та два різні випадкові
JWT-секрети, згенеровані через `secrets.token_urlsafe(48)`.

Google: створіть OAuth 2.0 Client ID типу Web application у Google Cloud Console,
зареєструйте Authorized JavaScript origins фронтенду і задайте `GOOGLE_CLIENT_ID`.
Фронтенд отримує `credential` через JavaScript callback Google Identity Services.
Секрет Google OAuth для цього сценарію перевірки ID token не потрібен.
Джерело: [перевірка Google ID token](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token).

Telegram: BotFather → бот → Login Widget → Allowed URLs. Зареєструйте origin
фронтенду, скопіюйте Client ID у `TELEGRAM_CLIENT_ID`, залиште алгоритм RS256.
Для локального запуску на порту `18080` додайте `http://localhost:18080/`
до Allowed URLs. Telegram SDK передає поточні `location.origin` та
`location.pathname` як `redirect_uri`: з головної сторінки це
`http://localhost:18080/`, зі студії — `http://localhost:18080/studio`.
Для іншого порту або production-домену зареєструйте відповідні адреси.
Параметр `redirect_uri` потрібен і в popup-сценарії; офіційний SDK формує
його автоматично, але реєстрацію адрес у BotFather треба виконати окремо.
Фронтенд використовує нову бібліотеку Telegram Login з `scope: ["profile"]`.
Вона повертає підписаний `id_token`; bot token і client secret у цьому сценарії
не потрібні. Джерело: [Telegram Login](https://core.telegram.org/bots/telegram-login).

Для окремого origin фронтенду задайте `CORS_ALLOWED_ORIGINS` через кому.
На сервері використовуйте HTTPS. Порожній Client ID вимикає відповідний
провайдер: API повертає 503. Frontend UI підключається до цих маршрутів окремо.

Перед першим POST отримайте CSRF-токен через GET `/users/me` з cookies,
а для запитів, що змінюють дані, передавайте `X-CSRF-Token`.
Порядок роботи й налаштування: [API guard](api-guard.md).

## API

| Метод | Шлях | Призначення |
| --- | --- | --- |
| POST | `/users/auth/challenge` | Отримати одноразовий nonce та client ID |
| POST | `/users/auth/google` | Вхід через Google |
| POST | `/users/auth/telegram` | Вхід через Telegram Login Widget |
| POST | `/users/auth/telegram-webapp` | Вхід у Telegram MiniApp за `initData` |
| POST | `/users/auth/refresh` | Обміняти refresh на нову пару токенів |
| POST | `/users/auth/logout` | Відкликати refresh поточної сесії |
| GET | `/users/me` | Профіль за `Authorization: Bearer <access_token>` |

Спочатку виконайте:

```http
POST /users/auth/challenge
Content-Type: application/json

{"provider": "google"}
```

```json
{
  "nonce": "server-generated-random-nonce",
  "client_id": "your.apps.googleusercontent.com",
  "expires_in": 300
}
```

Передайте `nonce` у параметри SDK провайдера **до** отримання ID token.
Для Telegram використовуйте `provider: "telegram"`.

Приклад Google Identity Services після завантаження офіційного SDK:

```javascript
const challenge = await fetch(`${api}/users/auth/challenge`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ provider: "google" }),
}).then(r => r.json());

google.accounts.id.initialize({
  client_id: challenge.client_id,
  nonce: challenge.nonce,
  callback: async ({ credential }) => {
    const response = await fetch(`${api}/users/auth/google`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id_token: credential, nonce: challenge.nonce }),
    });
    if (!response.ok) throw new Error("Login failed");
    const session = await response.json();
    // Передайте session.access_token та session.refresh_token менеджеру сесії.
  },
});
google.accounts.id.renderButton(document.getElementById("google-login"), {
  type: "standard",
});
```

Telegram після отримання власного challenge та завантаження офіційного SDK:

```javascript
Telegram.Login.init({
  client_id: Number(challenge.client_id),
  scope: ["profile"],
  nonce: challenge.nonce,
}, async (result) => {
  if (!result.id_token) return;
  const response = await fetch(`${api}/users/auth/telegram`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: result.id_token, nonce: challenge.nonce }),
  });
  if (!response.ok) throw new Error("Login failed");
  const session = await response.json();
});
// Викликайте з обробника натискання кнопки, щоб браузер дозволив popup.
Telegram.Login.open();
```

Запити входу приймають JSON `{ "id_token": "...", "nonce": "..." }` і повертають:
Необов’язкове поле `referral_code` застосовується лише до першої реєстрації;
правила нарахування описані в [referrals-promos.md](referrals-promos.md).

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in": 900,
  "is_new_user": true,
  "user": {
    "id": "01900000-0000-7000-8000-000000000000",
    "first_name": "Ілля",
    "last_name": null,
    "username": null,
    "telegram_id": null,
    "google_email": "user@example.com",
    "language_code": null,
    "photo_url": null,
    "credits": 15,
    "referral_code": "0123456789abcdef01234567",
    "registered_at": "2026-10-30T12:00:00Z",
    "last_active_at": "2026-10-30T12:00:00Z"
  }
}
```

Refresh та logout приймають `{ "refresh_token": "..." }`. Refresh повертає нову
пару токенів; старий refresh одразу стає недійсним. Logout повертає 204,
повторний logout чинного JWT також повертає 204. Сесії інших пристроїв
залишаються активними. Access після logout діє до завершення його TTL
(типово 15 хвилин); клієнт видаляє обидва токени зі своєї сесії.

API використовує Bearer і не встановлює cookies. Зберігання refresh у вебклієнті
варто організувати в серверній сесії/BFF з HttpOnly cookie.
Перевірка `nonce` прив’язана до підписаного токена провайдера та одноразового
запису в БД. Для кожної нової спроби входу отримуйте новий challenge.

## Telegram MiniApp

У MiniApp браузерний Login Widget недоступний: Telegram передає підписаний
`initData`, який фронтенд надсилає без nonce.

```http
POST /users/auth/telegram-webapp
Content-Type: application/json

{"init_data": "query_id=...&user=%7B...%7D&auth_date=...&hash=...", "referral_code": "optional"}
```

Сервер перевіряє підпис за алгоритмом Telegram:

```
secret_key = HMAC_SHA256(key="WebAppData", msg=TELEGRAM_BOT_TOKEN)
hash       = HMAC_SHA256(key=secret_key, msg=data_check_string)
```

де `data_check_string` — усі поля, крім `hash`, відсортовані за ключем і з'єднані
`\n`. Додатково перевіряється `auth_date` (типово не старіший за годину,
`TELEGRAM_WEBAPP_AUTH_TTL_SECONDS`) і коректність `user.id`.

Далі акаунт шукається або створюється за `telegram_id` — так само, як для
OAuth-входу: ті самі початкові кредити, реферальний код і блокування. Відповідь
і cookie ідентичні `/users/auth/telegram`.

Порожній `TELEGRAM_BOT_TOKEN` вимикає маршрут (401), тож без бота MiniApp
залишається доступним лише через звичайний вхід.

## Перевірки та поведінка

- ID tokens: перевірка RS256, підпису за фіксованим JWKS URL провайдера,
  issuer, audience, exp, iat, sub, nonce та azp для кількох audience.
  Публічні ключі кешуються; синхронний HTTP до JWKS працює в окремому потоці.
- Google ідентифікується за `sub`, Telegram — за підписаним `id` із scope profile.
  Telegram `sub` не підставляється в `telegram_id`.
- Google email приймається лише з `email_verified: true`.
  Автоматичного зв’язування акаунтів за email або username немає.
- Перший вхід створює користувача й гаманець; наступні оновлюють профіль та
  `last_active_at`. Кредити повторно не нараховуються. Початкову кількість
  визначає `USER_INITIAL_CREDITS` (типово 15).
- Nonce і refresh зберігаються як SHA-256 хеші. Одноразове споживання через
  `DELETE ... RETURNING` працює між процесами API; лише один паралельний запит
  може успішно обміняти конкретний nonce або refresh.
- Заблокований користувач отримує 403 при вході, refresh та `/users/me`.
- 401: недійсні, прострочені або повторно використані credentials;
  409: конфлікт паралельної реєстрації — повторіть із новим challenge;
  422: некоректний JSON; 503: провайдер не налаштований або його JWKS недоступний.
- Відповіді `/users/*` мають `Cache-Control: no-store`.

## Міграції

Для нової PostgreSQL БД:

```sh
uv run alembic -c src/adapters/database/alembic.ini upgrade head
```

У проєкті раніше не було ревізій Alembic. `0001_initial` — зафіксована початкова
схема всіх попередніх моделей; `0002_user_auth_challenges` додає таблицю nonce.
Якщо БД вже створена через `Base.metadata.create_all()`, спершу перевірте,
що її таблиці відповідають попередній схемі `0001_initial`. Після перевірки
відповідності позначте baseline та застосуйте нову міграцію:

```sh
uv run alembic -c src/adapters/database/alembic.ini stamp 0001_initial
uv run alembic -c src/adapters/database/alembic.ini upgrade head
```

`stamp` лише записує версію і не перевіряє/виправляє структуру таблиць.

## Тести

```sh
uv run pytest
uv run ruff check src tests
```

Auth-тести використовують тимчасову SQLite, локальні RSA-ключі й підмінені
JWKS-відповіді; реальні Google/Telegram акаунти та мережа не потрібні.
