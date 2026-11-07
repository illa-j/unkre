# Підключення backend

Фронтенд використовує FastAPI з сусіднього `backend/`. Необхідні маршрути:
`/users/*`, `/generations/*`, `/workflows`, `/payments/*`.

## Локальний запуск

У `backend/` скопіюйте `.env.example` в `.env` і заповніть PostgreSQL, JWT secrets,
Google / Telegram Client ID, RunPod API key та endpoint. Запустіть Redis,
застосуйте міграції та запустіть API:

```sh
uv sync
uv run alembic -c src/adapters/database/alembic.ini upgrade head
uv run uvicorn adapters.api.main:app --app-dir src --reload
```

`CORS_ALLOWED_ORIGINS` має містити origin фронтенду, локально
`http://localhost:3000`. Для локального HTTP використовуйте
`COOKIE_SECURE=false`, `COOKIE_SAMESITE=lax`.

У `frontend/`:

```sh
cp .env.example .env.local
npm ci
npm run dev
```

Типово браузер звертається до `/api`, а Next.js передає запити на
`BACKEND_URL=http://127.0.0.1:8000`. Cookies і `Set-Cookie` проходять через
rewrite. `BACKEND_URL` залишається на сервері. Для прямого запиту до окремого
API задайте `NEXT_PUBLIC_API_URL=https://api.example.com`; у backend дозвольте
origin фронтенду в CORS. Production cookies потребують HTTPS; для різних sites —
`COOKIE_SAMESITE=none`, `COOKIE_SECURE=true`.

`NEXT_PUBLIC_CSRF_HEADER_NAME` має збігатися з backend `CSRF_HEADER_NAME`;
типово це `X-CSRF-Token`. Публічні змінні фіксуються під час `next build`.

## Авторизація

Фронтенд отримує challenge, передає nonce офіційному SDK, а ID token —
відповідному маршруту входу. Google Client ID і Telegram Client ID приходять
із backend, дублювати їх у frontend `.env` не потрібно. Зареєструйте origin
фронтенду в Google Cloud Console та BotFather.

Використовуються [Google Identity Services](https://developers.google.com/identity/gsi/web/reference/js-reference)
і [Telegram Login](https://core.telegram.org/bots/telegram-login).
Заголовок сторінки `Cross-Origin-Opener-Policy: same-origin-allow-popups`
дозволяє SDK спілкуватися з popup. Реальне підтвердження входу відбувається
через обліковий запис користувача у провайдера.

JWT залишаються в HttpOnly cookies. `api.ts` використовує
`credentials: include`, отримує CSRF через GET `/users/me`, додає токен до
POST / DELETE та виконує один спільний refresh для одночасних 401.
JWT не зберігаються у JavaScript, URL чи localStorage.

## Генерації

Моделі та сумісні LoRA приходять через GET `/workflows`. Записи workflow в БД
мають відповідати JSON-файлам у `backend/src/adapters/runpod/workflows/` за
назвою. До API надсилаються UUID із каталогу; фронтенд не вигадує їх.

POST `/generations` передає prompt, необов'язковий negative prompt, workflow,
ваги LoRA, base64 reference без data-префікса й необов'язковий seed. Seed
передається як JSON integer без втрати точності 64 біт. Negative prompt
зберігається разом із генерацією та передається в RunPod. Пропорції й batch
не показані як доступні налаштування, оскільки поточний API їх не приймає.

Для оновлення станів запустіть наявний task worker за інструкцією
`backend/docs/task_queue.md`. Recovery підхоплює запис після commit при
наступному проході, тому перед початком polling worker можлива затримка.
Фронтенд перевіряє активні генерації кожні 5 секунд і припиняє polling
після завершення. Створення автоматично не повторюється при збоях мережі.

Результат завантажується через авторизований GET `/generations/{id}/image`
і показується через тимчасовий blob URL. Backend перевіряє власника та
звертається до RunPod на збереженому endpoint. Зображення доступне, доки
RunPod зберігає output; окремого постійного сховища зображень у проєкті ще немає.
Видалення використовує DELETE; активна задача спочатку скасовується сервером.

## Пресети

`GET /presets`, `POST /presets` і `DELETE /presets/{id}` зберігають налаштування
генерації на сервері для поточного користувача: модель, prompt, negative prompt,
seed і всі вибрані LoRA з вагами. Пресети не містять reference-файлів; їх можна
застосувати в Studio й змінити перед генерацією. Детальний контракт —
`backend/docs/generations-api.md`.

## Реферали та промокоди

`GET /referrals` повертає код поточного користувача, кількість запрошених і
зароблені кредити. Посилання-запрошення має вигляд `/?ref=<24-char-code>`;
SessionProvider зберігає код до першого входу й передає його в тілі
`/users/auth/google` або `/users/auth/telegram`. Повторні входи бонус не
нараховують. Суми бонусів задають `REFERRAL_INVITER_CREDITS` і
`REFERRAL_INVITEE_CREDITS` у backend `.env`.

`POST /promos/redeem` приймає `{ "code": "..." }` і повертає нараховані
кредити та новий баланс. Промокоди створюються через адмінські маршрути
`/admins/promo-codes`; у репозиторії немає наперед створених кодів. Повний
контракт і коди помилок: `backend/docs/referrals-promos.md`.

## Оплата

Ціни приходять із GET `/payments/prices`; порожня ціна вимикає відповідний
метод. Для реальних оплат заповніть price settings та реквізити провайдерів
у backend `.env` і налаштуйте підписані webhook-и за `backend/docs/payments-api.md`.

Фронтенд надсилає тільки кількість кредитів та idempotency key. Одна спроба
зберігає ключ при повторному натисканні після помилки. Після створення рахунка
користувач сам відкриває отримане HTTPS checkout-посилання. Статус і баланс
оновлюються з backend; повернення з checkout саме по собі не зараховує кредити.
Telegram Stars доступні всім зареєстрованим акаунтам. Якщо акаунт створено
через Google, користувач відкриває Stars-посилання у своєму Telegram і платить
з будь-якого Telegram-акаунта; кредити зараховуються на акаунт UNKRE, який
створив рахунок.
