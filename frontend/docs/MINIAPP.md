# Telegram MiniApp

Сайт працює як Telegram MiniApp без окремої збірки: той самий Next.js застосунок
відкривається у webview Telegram, підхоплює `initData` і входить у акаунт
автоматично.

## Що підключено

- `telegram.org/js/telegram-web-app.js` у кореневому layout
  (`strategy="beforeInteractive"`) — SDK доступний до гідратації.
- `TelegramMiniAppProvider` (`src/components/telegram-miniapp.tsx`):
  - `ready()`, `expand()`, `setHeaderColor("#090e12")`,
    `setBackgroundColor("#090e12")`, `disableVerticalSwipes()`;
  - висота webview у `--tg-vh`, верхній safe-area у `--tg-safe-top`;
  - `body.telegram-miniapp` вмикає CSS-адаптацію висоти для `.site-shell`,
    `.studio-app`, `.admin-app` і `.chapter`;
  - `BackButton` показується на вкладених сторінках і викликає `router.back()`,
    на `/`, `/studio` та `/admin` ховається.
- `SessionProvider` після 401 від `/users/me` робить
  `POST /users/auth/telegram-webapp` з `initData` (один раз на payload) і
  повторює запит — далі працюють звичайні cookie-сесії та refresh.
- Діалог входу всередині Telegram не показує Google/Telegram Login Widget, а
  пропонує повторити вхід через Telegram.
- Оплата: Telegram Stars відкривається через `WebApp.openInvoice()` з
  очікуванням статусу `paid` (після нього баланс і історія оновлюються), а
  крипто-чекаут — через `WebApp.openLink()`. Поза Telegram працює звичайний
  перехід на сторінку оплати.
- Реферальний код із `localStorage` передається в MiniApp-вхід.

Поза Telegram нічого не активується: провайдер перевіряє наявність
`window.Telegram.WebApp.initData`, а скрипт SDK просто завантажується.

## Налаштування

У `backend/.env`:

```env
TELEGRAM_BOT_TOKEN=...            # той самий токен, що у бота
TELEGRAM_MINIAPP_URL=https://...  # URL для кнопки /start, наприклад /studio
TELEGRAM_WEBAPP_AUTH_TTL_SECONDS=3600
```

У BotFather: Menu Button → вкажіть той самий URL. Кнопка в `/start` бота вже
відкриває MiniApp.

## Обмеження

- Telegram вимагає `https://` для `web_app`-кнопок; `http://localhost`
  дозволений лише для локальних експериментів.
- `initData` живе лише в межах запуску MiniApp. Якщо він прострочений
  (`auth_date` старіший за TTL), користувач побачить звичайний екран входу.
- Вхід через Google всередині Telegram webview не гарантований, тому основний
  шлях — `initData`.
