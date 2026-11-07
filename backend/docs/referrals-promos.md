# Referrals and promo codes

Both features use the existing wallet and transaction ledger. Credits are posted
as `adjustment` transactions with deterministic idempotency keys, so a repeated
request cannot credit the same referral or promo redemption twice.

## Referral attribution

Every user already has a 24-character hexadecimal `referral_code` in `/users/me`.
When a **new** account signs in, the browser may include that code in the login
body:

```json
{
  "id_token": "provider-token",
  "nonce": "challenge-nonce",
  "referral_code": "0123456789abcdef01234567"
}
```

The field is optional and ignored for returning accounts. An unknown, malformed
or blocked referrer is ignored and the normal signup proceeds. When attribution
succeeds, both accounts receive the configured credits exactly once:

- `REFERRAL_INVITER_CREDITS` (default `5`);
- `REFERRAL_INVITEE_CREDITS` (default `5`).

A new account can be referred only once. The referral record and both ledger
entries are written in the same request transaction.

## Referral statistics

`GET /referrals` requires the user access cookie and returns:

```json
{
  "referral_code": "0123456789abcdef01234567",
  "invited_count": 2,
  "credits_earned": 10,
  "referrer_credits": 5,
  "invitee_credits": 5
}
```

`credits_earned` is the sum of inviter credits recorded for that account.

## Promo codes

`POST /promos/redeem` requires the user access cookie and CSRF token:

```json
{ "code": "WELCOME7" }
```

Codes are trimmed and uppercased. A successful response is:

```json
{ "code": "WELCOME7", "credits": 7, "balance": 42 }
```

A code can be redeemed once per account. Inactive, expired, exhausted, unknown
and already-used codes are rejected without changing the balance:

- 404 — unknown code;
- 409 — inactive, expired, exhausted or already used;
- 422 — malformed code.

Creating and managing codes is an admin operation. These routes use the admin
access cookie and CSRF rules:

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/admins/promo-codes` | Create a code |
| GET | `/admins/promo-codes?limit=100&offset=0` | List codes |
| PATCH | `/admins/promo-codes/{id}` | Enable or disable a code |

Create body:

```json
{
  "code": "WELCOME7",
  "credits": 7,
  "max_redemptions": 100,
  "expires_at": "2026-12-31T23:59:59Z",
  "is_active": true
}
```

`max_redemptions` and `expires_at` are optional. The code name must contain
3–64 letters, numbers, dashes or underscores. Duplicate names return 409.

## Storage

Migration `0003_referrals_promo_codes` adds `referrals`, `promo_codes` and
`promo_redemptions`. Promo and referral credits are visible in the wallet and in
`transactions`; no seeded codes are inserted by the migration.
