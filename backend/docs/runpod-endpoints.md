# RunPod endpoints: один endpoint на workflow

Проєкт підтримує два режими:

1. **Legacy — один endpoint на весь застосунок.** Задається `RUNPOD_ENDPOINT_ID`.
   Використовується лише тоді, коли `RUNPOD_ENDPOINTS` порожній.
2. **Multi-endpoint — один endpoint на кожен workflow.** Задається
   `RUNPOD_ENDPOINTS`. У цьому режимі `RUNPOD_ENDPOINT_ID` ігнорується, а кожен
   workflow **мусить** мати рівно один endpoint. Якщо запису немає, генерація
   завершується помилкою `RunPodNotConfiguredError` ще до створення job — мовчазного
   fallback на інший endpoint немає.

Ключ мапи — точна назва workflow у таблиці `workflows.name`. Вона ж використовується
як ім'я JSON-графа в `backend/src/adapters/runpod/workflows/` (з `.json` або без).

## Формат у `.env`

Компактний варіант (зручніше для довгих назв з пробілами):

```dotenv
RUNPOD_ENDPOINTS=krea2_turbo_all_api=abc123,krea2_raw_t2image_api=def456,Qwen Image 2.1=ghi789
```

JSON-варіант (еквівалентний):

```dotenv
RUNPOD_ENDPOINTS={"krea2_turbo_all_api":"abc123","krea2_raw_t2image_api":"def456","Qwen Image 2.1":"ghi789"}
```

Правила:

- назва і endpoint обрізаються від пробілів;
- порожні назви/значення заборонені;
- повторна назва workflow — помилка конфігурації;
- кілька workflow можуть вказувати на один endpoint, якщо це потрібно;
- регістр назви має значення: `Krea 2 Turbo` і `krea2_turbo_all_api` — різні ключі.

Приклад для трьох образів:

```dotenv
RUNPOD_API_KEY=...
RUNPOD_ENDPOINTS=krea2_turbo_all_api=<turbo-endpoint>,krea2_raw_t2image_api=<raw-endpoint>,Qwen Image 2.1=<qwen-endpoint>
RUNPOD_TIMEOUT_SECONDS=30
```

## Як це працює

`GenerationService.create_generation()` після завантаження workflow викликає
`RunPodClient.endpoint_for(workflow.name)`:

- `RUNPOD_ENDPOINTS` непорожній → береться endpoint цього workflow;
- інакше → `RUNPOD_ENDPOINT_ID`.

Знайдений endpoint одразу зберігається в `generations.runpod_endpoint_id`. Усі подальші
операції (status, error, cancel, отримання зображення) використовують саме це збережене
значення, тому зміна `.env` не «перекидає» вже запущені генерації на інший endpoint.

## Перевірка

```bash
cd backend
uv run python - <<'PY'
from adapters.settings import RunPodSettings
s = RunPodSettings(
    RUNPOD_ENDPOINTS="krea2_turbo_all_api=abc,krea2_raw_t2image_api=def"
)
print(s.RUNPOD_ENDPOINTS)
PY
```

Очікується `{'krea2_turbo_all_api': 'abc', 'krea2_raw_t2image_api': 'def'}`.

Юніт-тести: `uv run pytest tests/test_runpod_client.py tests/test_generation_service.py`.

## Діагностика

- `No RunPod endpoint configured for workflow '<name>'` — у `RUNPOD_ENDPOINTS` немає
  ключа з такою точною назвою. Перевірте `GET /workflows` (поле `name`).
- `RUNPOD_ENDPOINTS is configured but no workflow was given` — endpoint намагалися
  отримати без назви workflow; це внутрішня помилка виклику, не конфігурації.
- `RUNPOD_ENDPOINT_ID is not configured` — `RUNPOD_ENDPOINTS` порожній і legacy
  endpoint теж не заданий.
