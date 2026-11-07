# Credits and payments

`WalletModel` is the only stored credit balance. Each user has at most one wallet.
`UserModel.credits` reads that wallet; it is not a second database column.
Wallets and financial records use restrictive foreign keys to preserve accounting history.

`TransactionModel` records signed credit movements and their before/after balances:

| Type | Amount | Required link |
| --- | --- | --- |
| `purchase` | positive | successful `PaymentModel` |
| `spend` | negative | optional generation |
| `reversal` | positive | original spend transaction |
| `refund` | negative | active or successful `PaymentRefundModel` |
| `adjustment` | nonzero | internal administrative operation |

A payment can have one purchase transaction. A spend can have one exact reversal.
A refund can have one credit debit. Transactions cannot be edited or deleted through
ORM instance operations. SQL bulk operations intentionally bypass ORM hooks and must
not be used to rewrite accounting history.

Balance changes and transaction inserts belong in the same database transaction.
Lock the wallet with `SELECT ... FOR UPDATE`, check the available credits, update
`wallet.credits`, and insert the matching ledger row before committing. The model
also uses SQLAlchemy optimistic versioning to reject stale ORM balance updates.
Models do not perform implicit balance changes when a payment status changes.

## Payment providers

`PaymentModel` snapshots the price (`amount`, `currency`) and purchased `credits`.
`paid_amount` is the actual received total in the order currency. A successful payment
must have a provider transaction ID, `paid_at`, and sufficient `paid_amount`.
The price, purchased credits, provider, wallet and idempotency key cannot change after
creation through ORM instance updates.

- `telegram_stars`: `currency="XTR"`, a positive integer amount, the original payer's
  `telegram_user_id`, and `provider_transaction_id=telegram_payment_charge_id`.
  `paid_amount` must exactly equal `amount`.
  For accounts without a linked Telegram identity, `telegram_user_id` is initially
  null and is captured from the authenticated successful payment or reconciliation.
  Once captured, it cannot be changed or cleared.
- `atlos`: `amount`/`currency` correspond to `OrderAmount`/`OrderCurrency`.
  Store `Invoice/Create`'s `Id` in `provider_invoice_id`, `Payment/Create`'s `Id` in
  `provider_payment_id`, and postback `TransactionId` in `provider_transaction_id`.
  Preserve `PaidAmount`, `Amount`, `Fee`, `Asset`, `Blockchain`, `BlockchainHash`,
  and `UserWallet` in the corresponding payment columns. `PaymentModel.id` can be
  used as the merchant `OrderId`.

Amounts use `Decimal` and `NUMERIC(38,18)`; floats and values requiring rounding
are rejected by `PaymentAmountValidator`. Currency codes and all text columns
have explicit length limits and SQL constraints.

Provider identifiers and request idempotency keys prevent duplicate records. A
webhook handler must verify the provider signature and order details, lock the
payment and wallet, and post the purchase only once. A browser redirect or an ATLOS
payment detected only in the mempool is not confirmation. Reconciliation of ATLOS
transactions is also necessary when a webhook delivery is missed.

## Full refunds

There is one `PaymentRefundModel` per payment. Its `amount`, `credits`, and `currency`
come from the original payment; partial refunds are not represented. Failed attempts
can retry the same refund record and idempotency key. The credit debit is a separate
`refund` transaction for exactly the purchased credits.

Reserve/debit those credits atomically before sending money out. On a provider
failure, the application must release the reservation with a compensating adjustment;
do not restore credits until the outcome of an ambiguous external timeout is resolved.

For Stars, call `refundStarPayment` with the original payer and charge ID.
For ATLOS, arrange an outgoing payment and store its invoice ID, recipient address,
asset amount, fee and blockchain hash in the refund. The crypto recipient address
must be explicitly confirmed; the original sender may be an exchange or a contract.
The original asset and blockchain are retained on the linked payment.

These models provide persistence and validation. Provider adapters, webhook handlers,
locking/settlement services, and reconciliation jobs are separate application layers.

## Existing balances and migrations

Before applying this schema to an existing database, create and backfill one wallet
for each user from `users.credits`. Record nonzero opening balances as `adjustment`
transactions with stable idempotency keys. Verify totals before dropping the old
column and its constraint. Keep writers paused or synchronize the cutover so a
balance change cannot fall between the copy and the schema switch.

The Alembic baseline and subsequent migrations live in
`src/adapters/database/migrations/versions`. The payment audit changes do not
alter the database schema or apply migrations to a live database.

## References

- https://core.telegram.org/bots/payments-stars
- https://core.telegram.org/bots/api#refundstarpayment
- https://atlos.io/docs/api/invoice/create
- https://atlos.io/docs/api/payment/create
- https://atlos.io/docs/postback/fields
- https://atlos.io/docs/postback/url
- https://atlos.io/docs/api/wallet/send-token

## Confirmation and reconciliation

A browser redirect or a mempool sighting is not a confirmation. ATLOS must send a
signed postback to `https://<public-host>/api/payments/webhooks/atlos`, and the
merchant panel must have that URL configured. Telegram Stars uses the bot's
`pre_checkout_query` and `successful_payment` updates in long-polling mode.

Provider callbacks can be missed. The worker runs `reconcile_payments` every five
minutes over the last seven days:
- ATLOS `Transaction/List` with UTC `TimeStart`/`TimeFinish` as ISO-8601
  timestamps. The public documentation mentions `YYYY-MM-DD hh:mm:ss`, but the
  live API rejects that form with HTTP 400 and accepts ISO-8601;
- Telegram Stars `getStarTransactions`.

Reconciliation is idempotent and can credit a locally expired invoice when the
provider confirms payment. `cleanup_pending_payments` expires overdue `PENDING`
and `PROCESSING` invoices only when there is no evidence of funds: a linked
transaction or refund, `paid_at`, `paid_amount`, `provider_transaction_id`,
`asset_amount`, `blockchain_hash` or `sender_address` keeps the row untouched.
Expired and cancelled rows are retained for 30 days so a late callback can still
be matched, then deleted only under the same financial-evidence guard. Do not
shorten this retention without adding an equivalent durable provider-order index.

Each reconciliation record has its own savepoint covering the purchase, balance,
and referral rewards. Invalid records are rolled back and logged while the next
records are processed. Infrastructure failures still abort the outer transaction
and are retried by the next scheduled run. Telegram polling handlers catch failures
outside the transaction scope, so a failed settlement never commits partial changes
or sends a success message before commit.
