# Запуск у Docker

Проєкти мають імена `unkre` (production) і `unkre-dev` (розробка), тому обидва
стеки можна тримати запущеними одночасно: контейнери, мережі та томи не
перетинаються. Без `name:` обидва файли належали б до одного Compose-проєкту і
`up` для dev витісняв би production-контейнери.

Стек: PostgreSQL, Redis, MinIO, FastAPI (`web`), ARQ worker, Next.js і nginx як
єдина точка входу. nginx віддає `/api/*` у FastAPI (знімаючи префікс `/api`), а все
інше — у Next.js. Міграції Alembic застосовуються окремим контейнером
`migrator` до старту API.

Образ nginx збирається з `nginx/Dockerfile`, конфігурація входить в образ.
Після змін `nginx/nginx.conf` у production виконайте:

```sh
docker compose up -d --build --no-deps nginx
```

У dev конфігурація додатково змонтована з хоста; після її зміни достатньо
`docker compose -f docker-compose-dev.yml exec nginx nginx -s reload`.
`/healthz` перевіряє сам nginx; healthcheck входить у його Dockerfile.

## Підготовка

```sh
cp backend/.env.example backend/.env
```

Файл має бути непорожнім: без `POSTGRES_PASSWORD` контейнер `db` не
ініціалізується, а без JWT-секретів не стартує API. Заповніть у `backend/.env`
щонайменше:

- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` — з них створюється база;
- `SECRET_KEY_ACCESS`, `SECRET_KEY_REFRESH` — два різні випадкові секрети;
- `GOOGLE_CLIENT_ID`, `TELEGRAM_CLIENT_ID` — для входу (можна лишити порожніми,
  тоді відповідний провайдер недоступний);
- `RUNPOD_API_KEY`, `RUNPOD_ENDPOINT_ID` — для генерацій (без ключа worker
  запускається, але polling вимкнений);
- `CRYPTO_PRICE_PER_CREDIT`, `STARS_PRICE_PER_CREDIT` та ключі провайдерів —
  лише якщо потрібні оплати.

`POSTGRES_HOST` і `REDIS_URL` у compose перевизначаються на `db` і
`redis://redis:6379/0`, тому локальні значення (`localhost`) можна не змінювати.
Файл `frontend/.env` не потрібен: `BACKEND_URL` задає compose, а
`NEXT_PUBLIC_API_URL` за замовчуванням `/api`.

## Production

```sh
docker compose up -d --build
```

Сайт: <http://localhost> (або `${HTTP_PORT}`). Назовні відкритий лише nginx;
PostgreSQL, Redis, FastAPI і Next.js доступні тільки всередині мережі `unkre`.

`NEXT_PUBLIC_SITE_URL`, `SITE_INDEXABLE` та `NEXT_PUBLIC_API_URL` вшиваються у
frontend під час збірки. Для публічного домену задайте їх у кореневому `.env` і
перезберіть frontend:

```sh
NEXT_PUBLIC_SITE_URL=https://your-domain.com docker compose build frontend
docker compose up -d frontend
```

Корисні команди:

```sh
docker compose ps
docker compose logs -f web worker frontend nginx
docker compose run --rm migrator          # застосувати міграції вручну
docker compose down                       # зупинити, дані лишаються
docker compose down -v                    # ТАКОЖ ВИДАЛИТЬ базу
```

Після зміни залежностей перезберіть образи:

```sh
docker compose build --no-cache
docker compose up -d
```

## Розробка

```sh
docker compose -f docker-compose-dev.yml up --build
```

- UI через nginx: <http://localhost:8080>
- Next.js напряму (HMR): <http://localhost:3000>
- FastAPI: <http://localhost:8000>, OpenAPI: <http://localhost:8000/docs>
- PostgreSQL: `127.0.0.1:5432`, Redis: `127.0.0.1:6379`
- MinIO: `127.0.0.1:9000` (S3 API), `127.0.0.1:9001` (консоль, `unkre` /
  `unkre-minio-dev-secret`) — тимчасовий 24-годинний кеш зображень

Код `backend/` і `frontend/` змонтований у контейнери: FastAPI перезапускається
`uvicorn --reload`, Next.js працює в dev-режимі. Міграції виконуються під час
`up`; після нової міграції достатньо перезапустити стек або виконати
`docker compose -f docker-compose-dev.yml run --rm migrator`.

## Порты

| Змінна | Production | Dev | Призначення |
| --- | --- | --- | --- |
| `HTTP_PORT` | `80` | `8080` | nginx, єдина публічна точка |
| `BACKEND_PORT` | — | `8000` | FastAPI напряму (dev) |
| `FRONTEND_PORT` | — | `3000` | Next.js напряму (dev) |
| `POSTGRES_PORT` | — | `5432` | PostgreSQL (dev) |
| `REDIS_PORT` | — | `6379` | Redis (dev) |
| `MINIO_IMAGE` | `cgr.dev/chainguard/minio:latest` | те саме | образ MinIO |
| `MINIO_PORT` | — | `9000` | MinIO S3 API (dev) |
| `MINIO_CONSOLE_PORT` | — | `9001` | MinIO console (dev) |
| `API_WORKERS` | `2` | 1 (`--reload`) | кількість процесів uvicorn |

Порти можна перевизначити у кореневому `.env` (див. `.env.example`) або змінними
середовища, наприклад `HTTP_PORT=18080 docker compose up -d`.

## Образ MinIO

MinIO видалив `minio/minio` з Docker Hub у вересні 2026 (і закрив анонімний
доступ на quay.io), тому стек використовує відкритий образ Chainguard:

```yaml
image: ${MINIO_IMAGE:-cgr.dev/chainguard/minio:latest}
```

Образ містить той самий бінарник MinIO і той самий CLI, тому `command`, змінні
`MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` і порти не змінилися. Оскільки він
працює від uid 65532, сервіс запускається з `user: "0:0"`, щоб свіжий named
volume був доступний на запис.

Замінити образ можна через `MINIO_IMAGE` у кореневому `.env`:

- `MINIO_IMAGE=cgr.dev/chainguard/minio@sha256:0a01100085e30fb08d2f39e39c9f5c9d83a95707f220b007d813b690cd41622d`
  — пін на конкретну збірку;
- `MINIO_IMAGE=pgsty/silo:RELEASE.2026-09-16T00-00-00Z` — community-форк MinIO;
- власний образ, зібраний з вихідників (MinIO community edition архівовано у
  квітні 2026, але код лишається доступним).

Якщо образ запускається не від root, том треба попередньо віддати uid 65532:

```sh
docker compose down
docker run --rm -v "unkre_minio-data:/data" busybox:1.37 chown -R 65532:65532 /data
```

## OAuth, cookies і TLS

Додайте origin у Google Cloud Console і BotFather:

- production: `http://localhost` (або ваша публічна схема/домен);
- dev: `http://localhost:8080` і, за потреби, `http://localhost:3000`.

Локальний стек працює по HTTP, тому в `backend/.env` має бути
`COOKIE_SECURE=false`, `COOKIE_SAMESITE=lax`. Для публічного домену термінуйте
TLS перед nginx (Cloudflare, Caddy, traefik або інший проксі) і встановіть
`COOKIE_SECURE=true`, `COOKIE_SAMESITE=lax` (для того самого сайту) чи `none`
(для різних сайтів). Платіжні webhook-и провайдерів мають бачити публічний
HTTPS-origin, а не локальний HTTP.

## Що змінено порівняно з імпортованим стеком

Принесені файли були від іншого проєкту (Persk) і посилалися на неіснуючі
`adapters/web/Dockerfile`, `adapters/bot/Dockerfile`, `adapters.web.main`,
MinIO, окремий admin-порт 8010 і Cloudflare-специфічні real-IP правила.
Адаптована версія:

- збирає backend з `backend/pyproject.toml` + `uv.lock` (Python 3.14, venv у
  `/opt/venv`, щоб dev-том не перекривав залежності);
- запускає `adapters.api.main:app`, `arq adapters.task_queue.worker.WorkerSettings`
  і Alembic з `src/adapters/database/alembic.ini`;
- MinIO додано пізніше як тимчасовий 24-годинний кеш зображень (див.
  `backend/docs/image-cache.md`), а не як постійне сховище; bot та додаткового
  admin-порту немає, наявний admin API доступний через `/api/admins/` зі
  стандартною перевіркою авторизації;
- nginx має один публічний server на :80 з `/api/` → FastAPI, `/_next/` і
  HMR → Next.js, без Cloudflare- і brotli-модулів;
- frontend отримав власний multi-stage Dockerfile із target `builder` для dev.
- nginx збирається окремим Dockerfile на офіційному `nginx:1.30-alpine`.
