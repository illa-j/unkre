# UNKRE — Landing & Studio

Студія підключена до FastAPI backend: Google / Telegram login, профіль і баланс, створення та перегляд генерацій, каталог workflow / LoRA, криптооплата, Telegram Stars, реферальні запрошення й промокоди. Відкрити `/studio` або натиснути Start creating. Запуск і контракт інтеграції: [docs/BACKEND.md](docs/BACKEND.md).

Темний адаптивний лендинг на Next.js App Router, TypeScript і Tailwind. Секції мають темний фон без фонових зображень; під час скролу він плавно змінює графітовий, холодний, винний та бронзовий відтінки. Крилата статуя супроводжує сторінку й реагує на курсор. Hero, огляд моделей та social preview представляють Krea 2 Turbo / Raw і Qwen Image 2.1; інші секції пояснюють сумісні LoRA та reference images із позиціонуванням uncensored / NSFW для дорослих.

Different LoRAs згруповано за моделями: Krea 2 (Realistic Snapshot, [KREA 2] Mystic XXX, Lenovo UltraReal, NiceGirls UltraReal) та Qwen Image 2.1 (Lenovo UltraReal, NiceGirls UltraReal, FemaledVaginus-NSFW). SFW / NSFW приклади згруповані окремо; NSFW-галереї розкриваються через доступні native details без додаткового JavaScript. Дані та вихідні пропорції: `src/lib/lora-collections.ts`.

Основний контент — серверний HTML. Інтерактивні приклади, сцена, авторизація, мобільний CTA та збір Web Vitals — окремі клієнтські компоненти.

Telegram MiniApp (автоматичний вхід за `initData`, back-кнопка, safe-area,
оплата через `openInvoice`): [docs/MINIAPP.md](docs/MINIAPP.md).

## Локальний запуск

Потрібні Node.js 26+ та npm.

```sh
npm ci
npm run dev
```

Відкрити http://localhost:3000.

Запуск усього стека разом із backend, PostgreSQL, Redis і nginx у Docker —
[DOCKER.md](../DOCKER.md).
```sh
npm run lint
npm run typecheck
npm run build
npm start
```

`npm test` перевіряє API-клієнт (cookies, CSRF, refresh, seed, ціни та шляхи backend), лендинг, індексацію, сторінки студії й відновлення локальних даних. HTTP-перевірки потребують запущеного сервера. Для іншого порту: `TEST_BASE_URL=http://localhost:3001 npm test`. Для preview-збірки з `SITE_INDEXABLE=false` також передати `TEST_EXPECT_NOINDEX=true`.

## Авторизація та запуск у production

Скопіювати `.env.example` у `.env.local` та вказати реальні значення:

- `NEXT_PUBLIC_SITE_URL` — повний URL головної сторінки production-сайту.
- `BACKEND_URL` — серверна адреса FastAPI, типово `http://127.0.0.1:8000`.
- `NEXT_PUBLIC_API_URL` — адреса API для браузера, типово `/api`.
- `NEXT_PUBLIC_CSRF_HEADER_NAME` — заголовок CSRF, типово `X-CSRF-Token`.
- `SITE_INDEXABLE` — індексація увімкнена за замовчуванням; `false` явно вимикає її для приватного preview.

Після зміни змінних потрібна нова збірка. Кнопки входу та реєстрації відкривають Google / Telegram login. API використовує HttpOnly cookies, CSRF та ротацію refresh cookies. Ціни, баланс, генерації й платежі беруться з backend; обране для прикладів і налаштування відображення залишаються локальними. Налаштування backend та провайдерів: [docs/BACKEND.md](docs/BACKEND.md).

За замовчуванням сторінка містить `index, follow`, а `robots.txt` дозволяє сканування. Індексація не залежить від URL авторизації чи наявності домену в конфігурації. `SITE_INDEXABLE=false` повертає `noindex, nofollow`, забороняє сканування та очищує sitemap. Canonical, структуровані дані, URL у sitemap і посилання на нього в robots.txt з’являються після визначення `NEXT_PUBLIC_SITE_URL`; localhost не підставляється як публічний домен. Зміни конфігурації індексації потребують нової збірки або перезапуску dev-сервера. Open Graph, Twitter preview та favicon вже реалізовані.

Юридичні посилання слід додати після появи реальних Terms / Privacy. NSFW LoRAs мають позначку 18+; глобальної позначки 18+ для всього продукту немає. Вона інформаційна, не механізм перевірки віку.

## Рух і доступність

- Статуя — прозорий WebP. Спільний fixed-шар закріплено на viewport; контент лишається у природному потоці. Фон займає всю висоту та має мінімум 100lvh, щоб приховування панелей мобільного браузера не оголювало смугу знизу.
- Фонові зображення секцій не рендеряться й не завантажуються; видалено пов’язану логіку crossfade та попереднього завантаження.
- Контурні слова KREA 2 / TURBO / RAW / LORA / REFERENCE / CREATE рендеряться як готові SVG paths з об’єднаними контурами гліфів і заокругленими стиками та плавно змінюються разом із секціями; типографіка та світлова дуга за статуєю декоративні й приховані від screen reader.
- У hero — інтерактивний приклад моделі з рекомендованим промптом і переходом у Studio. Нижче розміщені reference → result, повторюваний персонаж, три кроки створення, картки моделей, компактні LoRA, кредити, FAQ і фінальний CTA. Мобільні картки моделей прокручуються горизонтально; контекстний CTA з’являється після першого екрана.
- М’яке тепле світло біля статуї слідує за курсором з інерцією; на touch-пристроях залишається нерухомим.
- Курсор і скрол керують окремими вкладеними transform-шарами; React не перемальовується на кожен кадр.
- Animation loop працює лише при зміні положення та зупиняється у прихованій вкладці.
- На mobile статуя має власні розміри й фіксоване розташування збоку; desktop-зміщення при скролі до неї не застосовується. Контурні SVG-написи повністю вміщуються в доступну ширину.
- Touch-пристрої та viewport до 760 px не використовують pointer parallax. `prefers-reduced-motion` вимикає рух статуї, світла та зміну відтінків. Аналогічний fallback передбачений без JavaScript.
- Статуя декоративна та прихована від screen reader; змістові приклади моделей, стилів і reference/result мають alt-тексти.
- Native dialog забезпечує модальність, клавіатурний фокус і Escape; після закриття фокус повертається до CTA.

Візуальні tokens і responsive-правила: `src/app/globals.css`. Параметри інерції та амплітуди: `src/components/statue-scene.tsx`. Геометрія написів: `src/lib/outline-words.ts`; відтворювана генерація з локального DM Sans: `scripts/generate-outline-words.py` (інструменти потрібні лише для повторної генерації). Дані бренду й налаштування URL: `src/lib/site.ts`.

Походження зображень і фінальні промпти: [docs/ASSETS.md](docs/ASSETS.md). Поточна перевірка: [docs/QA.md](docs/QA.md). План: `../LANDING_PLAN.md`.

## Landing, public guides and conversion events

The landing keeps SFW and optional NSFW examples together. Its creation links carry a model, suggested prompt, LoRA name or reference intent through sign-in; Studio remains outside search indexing. Public `/learn/` guides cover Qwen, Krea, reference photos, consistent characters, LoRAs and credits, and are included in the sitemap.

Set `NEXT_PUBLIC_SITE_URL=https://unkre.com` for the approved production domain. Use `SITE_INDEXABLE=false` for private previews. `NEXT_PUBLIC_WELCOME_CREDITS` must match backend `USER_INITIAL_CREDITS` (both default to 15). Rebuild after changing public configuration. `NEXT_PUBLIC_SUPPORT_EMAIL` is the contact address shown on the public site and in the legal pages. The legal and trust pages live at `/about`, `/trust`, `/privacy`, `/terms`, `/refunds`, `/acceptable-use`, `/copyright`, `/security`, `/transparency`, `/status` and `/contact`; they are linked from the footer and included in the sitemap. Studio is age-gated in the browser, NSFW details require an 18+ confirmation, and reference uploads require the consent checkbox (`unkre.adult.v1` and `unkre.reference-consent.v1` in local storage). Registered entity details, the governing jurisdiction and the refund window should be reviewed and inserted in `src/lib/legal.ts` and the policy text before commercial launch.

First-party `/api/analytics` accepts an allowlist of aggregate funnel events: landing view, CTA click, completed sign-up/sign-in, accepted generation, successful/failed generation, and LCP/INP/CLS measurements. It emits JSON records with `type: "unkre.analytics"` to the frontend server log. Use the existing container log collector to aggregate stage counts and Web Vitals percentiles by device/path. It does not create an analytics dashboard or persist a separate event database. No prompts, photos, account IDs, metric entries, query strings or session identifiers are sent in these events. The client honours Do Not Track. Nginx routes this exact endpoint to Next.js before the general backend `/api/` proxy.

Primary conversion is a successful first generation, not merely a Studio visit. Event totals are aggregate counts, not unique-user cohorts. Live OAuth completion, real traffic conversion and field Web Vitals require the running production service and real visits; local checks do not establish rankings or field performance.
