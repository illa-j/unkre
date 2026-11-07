# Системні налаштування та ціна генерації

Адміністратор може змінювати глобальні економічні налаштування без перезбірки
контейнера. Значення зберігаються в таблиці `system_settings`
(`key` → JSONB `value`), а `backend/.env` лишається джерелом значень за
замовчуванням. Секрети (OAuth, RunPod API key, платіжні ключі) у БД не
переносяться.

## Модель

`SystemSettingModel`:

| Поле | Призначення |
|---|---|
| `key` | унікальний ключ, наприклад `referral.inviter_credits` |
| `value` | JSON-значення (int, string, null) |
| `description` | людський опис для адмінки |
| `updated_by` | UUID адміністратора, який змінив значення |
| `created_at`, `updated_at` | часові позначки |

Якщо рядка немає, використовується значення за замовчуванням із
`backend/.env`; після першої зміни створюється override. `DELETE` повертає
значення до env-дефолту.

## Ключі

Ціна генерації належить workflow і не є системним ключем: її задає
`workflows.generation_credits` (0 — безкоштовно).

| Ключ | Тип | Дія |
|---|---|---|
| `registration.initial_credits` | int ≥ 0 | стартові кредити нового користувача |
| `referral.inviter_credits` | int ≥ 0 | бонус запрошувачу |
| `referral.invitee_credits` | int ≥ 0 | бонус запрошеному |
| `payments.crypto_price_per_credit` | decimal > 0 або null | ціна кредиту в crypto-чекауті |
| `payments.crypto_currency` | 3 літери | валюта crypto-чекауту |
| `payments.stars_price_per_credit` | int ≥ 0 або null | ціна кредиту в Telegram Stars |

`null` у ціні вимикає відповідний спосіб оплати. Ціна самої генерації
зберігається не тут, а в `workflows.generation_credits`.

## Admin API

Усі маршрути потребують admin cookie та CSRF, як інші `/admins/*`.

```http
GET /admins/settings
```

Повертає всі ключі з `value`, `default`, `source` (`default` або `database`),
`description`, `updated_at`, `updated_by`.

```http
PATCH /admins/settings/referral.inviter_credits
Content-Type: application/json

{ "value": 2 }
```

```http
DELETE /admins/settings/referral.inviter_credits
```

`PATCH` валідовує тип і діапазон; `DELETE` скидає override до env-дефолту.

Ціна генерації редагується окремо, на рівні workflow:

```http
PATCH /admins/workflows/{workflow_id}/credits
Content-Type: application/json

{ "generation_credits": 2 }
```

Це змінює `workflows.generation_credits`; нові генерації цієї моделі
списуватимуть нову ціну.

## Списання кредитів за генерацію

`GenerationService.create_generation()` тепер:

1. читає `workflows.generation_credits` вибраної моделі;
2. перевіряє баланс гаманця;
3. створює генерацію;
4. записує `SPEND`-транзакцію (`transactions.type = 'spend'`) з
   `generation_id`, `balance_before`/`balance_after`;
5. ставить `credits_spent` у генерації;
6. лише після цього відправляє job у RunPod.

Якщо RunPod відхилив запит (мережа, 401/403, невірний endpoint), вся
транзакція відкочується: генерація не створюється, кредити не списуються.
Якщо балансу недостатньо, API повертає `402 Payment Required` і текст
із потрібною/доступною кількістю кредитів.

Наразі кредити не повертаються автоматично, якщо job уже прийнятий RunPod,
але згодом завершився `FAILED`/`TIMED_OUT`/`CANCELLED`. Це окрема політика
рефандів; ledger для неї вже готовий (`transactions.type = 'reversal'`).
