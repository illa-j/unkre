# Backend

## User Service та авторизація

Реалізовано вхід через Google Identity Services та Telegram Login (OIDC),
створення користувача й гаманця з 15 кредитами при першому вході,
JWT access/refresh, ротацію refresh-токенів, вихід та поточного користувача.
Бізнес-логіка: `src/domain/services/user.py`. Контракт і приклади для фронтенду:
[docs/auth.md](docs/auth.md). Реферальні бонуси під час першої реєстрації та
промокоди на кредити: [docs/referrals-promos.md](docs/referrals-promos.md).

```sh
uv sync
cp .env.example .env
# Заповніть параметри PostgreSQL, GOOGLE_CLIENT_ID, TELEGRAM_CLIENT_ID,
# а також два незалежні випадкові JWT-секрети в .env.
uv run alembic -c src/adapters/database/alembic.ini upgrade head
uv run uvicorn adapters.api.main:app --app-dir src --reload
```

Swagger UI: `http://localhost:8000/docs`.

Запуск усього стека (PostgreSQL, Redis, API, worker, frontend, nginx) у Docker:
[DOCKER.md](../DOCKER.md).
API guard, Redis-ліміти, CORS і CSRF для cookie-авторизації:
[docs/api-guard.md](docs/api-guard.md).
Міграція `0001_initial` створює наявну схему проєкту,
`0002_user_auth_challenges` додає одноразові challenges для входу,
а `0003_referrals_promo_codes` — реферальні записи та промокоди.
Якщо схема вже створена через `Base.metadata.create_all()`, дивіться порядок
переходу в [docs/auth.md](docs/auth.md).

## Сесія БД

`DatabaseSession` створюється один раз на процес із URL асинхронного драйвера
PostgreSQL (`postgresql+asyncpg://...`). URL передається з конфігурації застосунку;
підключення не створюються під час імпорту модулів.

```python
from adapters.database import DatabaseSession

database = DatabaseSession(database_url)

async with database.session() as session:
    # Передайте session репозиторіям: усі вони працюватимуть в одній сесії.
    # session.add(entity)
    await session.flush()  # За потреби отримати ID до commit.
    await session.commit()

# Під час завершення застосунку, після завершення активних задач:
await database.dispose()
```

Зміни зберігаються лише через явний `commit()`. При виході з контексту,
зокрема через помилку, незбережені зміни відкочуються, а сесія закривається.
`rollback()` дозволяє відкотити поточну транзакцію всередині контексту.
Уже виконаний `commit()` не скасовується подальшою помилкою.
Для кожного запиту або паралельної задачі створюйте окрему сесію.

В API використовується `session_scope()`: він виконує commit після успішного
завершення та rollback при помилці. Залежність `DatabaseManagerDep` передає
цю сесію в `DatabaseManager`.

## Каталог workflow і LoRA

Початковий каталог створюється з маніфестів у `scripts/`:

- `krea2_turbo_manifest.json` → `krea2_turbo_all_api`
- `krea2_raw_manifest.json` → `krea2_raw_t2image_api`
- `qwen_image21_manifest.json` → `Qwen Image 2.1`

Скрипт ідемпотентний: UUID виводяться з назв, повторний запуск оновлює ті самі
рядки, а набір LoRA кожного workflow приводиться до маніфесту.

```sh
PYTHONPATH=src uv run python scripts/seed_catalog.py
PYTHONPATH=src uv run python scripts/seed_catalog.py --dry-run
```

У Docker-середовищі (рекомендовано; БД не публікує порт у production-стеку):

```sh
cd /home/illia/Projects/own/unkre_ai
docker compose --profile tools run --rm seed
```

Хостовий запуск працює лише тоді, коли Postgres доступний на
`POSTGRES_HOST:POSTGRES_DB_PORT` з `backend/.env` (у `docker-compose-dev.yml`
порт опубліковано на `127.0.0.1:5432`).

Ім'я workflow у БД мусить точно збігатися з ім'ям JSON-графа в
`src/adapters/runpod/workflows/` і з ключем `RUNPOD_ENDPOINTS`
(див. [docs/runpod-endpoints.md](docs/runpod-endpoints.md)).

Ціна генерації зберігається в `workflows.generation_credits` (0 — безкоштовно).
Seed задає її лише для нових workflow; наявні ціни він не перезаписує. Змінити
ціну можна через `PATCH /admins/workflows/{id}/credits`.

## Адмін-панель

Окремий контур авторизації `/admins/*`, веб-панель на `/admin`. Owner-акаунт
створюється скриптом `scripts/create_admin.py`; повний перелік маршрутів,
рівнів доступу та робота з балансом — [docs/admin-panel.md](docs/admin-panel.md).

## Telegram-бот

Окремий процес на aiogram 3: `/start` відповідає англійським описом бренду та
кнопкою запуску MiniApp. Налаштування — `TELEGRAM_BOT_TOKEN` і
`TELEGRAM_MINIAPP_URL`, запуск — `python -m adapters.bot.main` або сервіс
`bot` у Compose. Деталі: [docs/telegram-bot.md](docs/telegram-bot.md).

## Перевірка

GenerationService: CRUD, запуск RunPod і власні генерації користувача —
[docs/generation-service.md](docs/generation-service.md).
HTTP-маршрути генерацій, каталог workflow/LoRA та видача готового
зображення: [docs/generations-api.md](docs/generations-api.md).

Маршрути оплат і ціни з `.env`: [docs/payments-api.md](docs/payments-api.md).

RunPod endpoints (кілька endpoint_id, один на workflow):
[docs/runpod-endpoints.md](docs/runpod-endpoints.md).

Системні налаштування адміністратора та списання кредитів:
[docs/system-settings.md](docs/system-settings.md).

Запуск worker та доступні задачі: [docs/task_queue.md](docs/task_queue.md).
Аудит очищення генерацій, зображень і платежів:
[docs/cleanup-audit-2026-11-04.md](docs/cleanup-audit-2026-11-04.md).

```sh
uv sync
uv run pytest
uv run ruff check src tests
```

Транзакційні тести використовують тимчасову SQLite БД через `aiosqlite`.
