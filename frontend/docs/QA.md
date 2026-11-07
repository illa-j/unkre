# Перевірка UNKRE — очищена геометрія літер і mobile

Дата: 26 жовтня 2026 року.

## Реферали та промокоди — 30 жовтня 2026 року

- Додано `/studio/referrals` з кодом, посиланням `/?ref=...`, кількістю запрошених і заробленими кредитами. Посилання та код копіюються кнопками; для клієнта без Clipboard API показано текстову підказку.
- `?ref=` зберігається в sessionStorage і передається лише під час першого входу. Після успішного входу код очищується; повторний вхід не нараховує бонус.
- На `/studio/credits` додано форму промокоду. У браузері перевірено `POST /promos/redeem`, повідомлення про нараховані кредити та очищення поля; баланс перечитується з `/users/me`.
- Backend: додано `referrals`, `promo_codes`, `promo_redemptions`, нарахування через `adjustment`-транзакції з idempotency key, маршрути `/referrals`, `/promos/redeem` і адмінські `/admins/promo-codes`.
- `pytest` проходить повністю, ruff без зауважень; `npm run lint`, `npm run typecheck`, production build і 25 frontend-тестів проходять. HTTP-тести виконувались на production-збірці.
- Обмеження: справжній Google / Telegram callback і нарахування в PostgreSQL не перевірялися цим прогоном; перевірено контракт, SQLite-транзакції та UI на локальному backend stub.

## Робочий простір студії — 28 жовтня 2026 року

- Реалізовано генератор, галерею, каталог LoRA, детальний перегляд фото, кредити/концепти тарифів та профіль/налаштування. Спільна адаптивна навігація, сторінки loading/error, noindex для робочого інтерфейсу, перехід із CTA лендингу.
- Пройшли lint без попереджень, `tsc --noEmit`, production build через Webpack та всі 8 тестів на оновленому localhost:3000. Turbopack у середовищі перевірки блокувався обмеженням створення службового TCP-порту, тому production-збірку перевірено через `npm run build -- --webpack`.
- У браузері перевірено вибір моделі, редагування промпта й формату, збереження preview, обране, відновлення локального профілю після reload, збережений промпт у деталях фото, перехід із Qwen LoRA в генератор із правильним вибором та локальне завантаження референсу.
- На мобільному перевірено нижню панель налаштувань, збереження введеного промпта без закриття панелі, закриття після preview, навігацію та вибір концепту тарифу. Усі шість екранів перевірено при 320 × 740: горизонтального overflow немає. Візуально перевірено також 390 × 844 та desktop 1440 × 900.
- Preview використовує наявні зображення. Оригінальні промпти, seed, справжні генерації, баланс, платежі й акаунти не імітуються. Реальні API відсутні в репозиторії.
- Знімки: `screenshots/studio-generator-desktop.png`, `studio-gallery-desktop.png`, `studio-loras-desktop.png`, `studio-image-detail-desktop.png`, `studio-credits-desktop.png`, `studio-settings-desktop.png`, `studio-generator-mobile.png`, `studio-settings-sheet-mobile.png`.

## SEO та індексація — 28 жовтня 2026 року

- Прибрано вимогу домену й обох URL авторизації для індексації. За замовчуванням сторінка повертає `index, follow`, robots.txt — `Allow: /`; для приватного preview збережено явний `SITE_INDEXABLE=false`.
- Після production build та перезапуску localhost:3000 перевірено HTTP 200, відсутність X-Robots-Tag, метатег robots і дозвіл сканування. Canonical та sitemap URL залишаються залежними від реального NEXT_PUBLIC_SITE_URL.
- Lighthouse 13.4.1, SEO-only, mobile preset: **100/100**, is-crawlable і robots-txt пройшли, runWarnings відсутні. Звіт: `reports/lighthouse-seo-2026-10-28.html`.
- Пройшли lint, TypeScript, production build та всі 5 тестів, включно з перевірками порожньої конфігурації, домену без авторизації й явного preview opt-out.

## Фон при мобільному скролі — 27 жовтня 2026 року

- Фоновий шар переведено з absolute/sticky на fixed/absolute. Висоту 100svh замінено на повну висоту контейнера з мінімумом 100lvh, щоб фон покривав екран після приховування панелей мобільного браузера.
- У браузері перевірено scrollY 3150 при 390 × 844, збільшення viewport до 390 × 932 і наступний скрол до scrollY 4082: верх фону лишається 0, низ дорівнює висоті viewport. На desktop 1440 × 900 покриття також повне. Перевірка емулює зміну висоти; реальний Android із рухом панелей браузера окремо не перевірявся.
- Lint, TypeScript та production build пройшли. Знімок мобільної секції LoRA без нижньої смуги: `screenshots/mobile-fixed-background.png`.

## Character consistency — 27 жовтня 2026 року

- У секції референсів додано два семантичні article з окремими H3: Krea 2 та Qwen Image 2.1. Krea пояснює повторне використання seed і незмінного опису персонажа на початку промпта; Qwen — фото людини як референс і сумісну LoRA для покращення NSFW-результатів. Повну ідентичність результатів не обіцяємо.
- Qwen додано в опис hero, фінальний CTA-опис, SEO та social preview. Застарілий загальний підпис про дві моделі прибрано; дві конкретні моделі Krea лишаються у своїй секції.
- Production build із перевіркою TypeScript і всі 4 HTTP smoke-тести проходять. Додатково перевірено, що новий текст та Qwen у description присутні в server-rendered HTML.
- У браузері на доступному viewport 479 × 1260 перевірено читабельність і вертикальне розміщення обох пояснень; горизонтального переповнення немає. Окремий desktop-прогін цього оновлення не виконувався.
- Знімок: `screenshots/character-consistency.png`. Ця зміна додає контент лендингу, а не інтеграцію моделей у Studio.

## Колекції LoRA

- Different LoRAs тепер містить чотири article-підсекції: Realistic Snapshot, [KREA 2] Mystic XXX, Lenovo UltraReal та NiceGirls UltraReal. Всі назви й приклади доступні в server-rendered HTML.
- Додано всі 9 наданих PNG: 2 SFW + 2 NSFW для Realistic Snapshot, 2 NSFW для Mystic XXX, 1 портрет Lenovo та 2 портрети NiceGirls. Оригінальні пропорції збережено.
- Realistic Snapshot посилається на точний URL Civitai від користувача. Автоматичне читання сторінки було недоступне; описів можливостей чи параметрів із неї не вигадано.
- NSFW-приклади приховані у закритих native details. У браузері перевірено відкриття та закриття обох груп; 4 NSFW-прев’ю завантажуються, зокрема кадри біля ялинки та на пляжі. Розкриття клавішею Enter працює.
- Перевірено desktop 1440 × 1000 та mobile 390 × 844 і 320 × 740. Переповнення по горизонталі немає. Нові фото використовують адаптивний Next Image та lazy loading.
- Проходять lint, TypeScript, production build і 4 HTTP smoke-тести. Тести перевіряють усі чотири назви та доступність усіх 9 оригінальних файлів через HEAD-запити.
- Знімки: `screenshots/lora-collections-desktop.jpg`, `screenshots/lora-collections-mobile.jpg`.

## Оновлення прикладів моделей

- Ті самі фото Turbo / Raw додано також у мініатюри hero. Кадрування налаштовано на обличчя; підпис змінено на Krea 2 examples. Перевірено desktop 1440 × 900 та mobile 390 × 844: обидва фото завантажені, overflow немає. Збірка та 4 тести проходять. Знімки: `screenshots/hero-krea-examples-desktop.jpg`, `screenshots/hero-krea-examples-mobile.jpg`.

- Перше надане користувачем фото додано як Krea 2 Raw, друге — як Krea 2 Turbo. Оригінальні PNG збережені без редагування.
- Картки повторюють пропорції вихідних фото: Turbo 2:3, Raw 3:4; повний кадр збережено на desktop та mobile.
- У браузері на 1440 × 1000 та 390 × 844 перевірено відповідність підписів, завантаження обох фото й відсутність горизонтального overflow. На mobile Next Image вибирає оптимізовані версії шириною 384 px.
- TypeScript, production build та 4 HTTP smoke-тести проходять; перевірка асетів охоплює обидва нові PNG.
- Знімки: `screenshots/krea-model-examples-desktop.jpg` та `screenshots/krea-model-examples-mobile.jpg`.

## Виправлено

- SVG text замінено на готові paths, отримані з DM Sans regular 400. Перед експортом перекриття гліфів об’єднані через fontTools / skia-pathops. Це прибирає внутрішні шви, які залишалися при звичайній обводці шрифту. Контур R очищено з трьох петель до двох; у A прибрано зайву точку контуру. Генератор перевіряє два контури в A та R. Співвідношення сторін і незмінну товщину обводки збережено.
- На mobile усі п’ять контурних написів вписані в окрему область. Контури тепер не залежать від завантаження чи способу обведення шрифту браузером; зарезервована область SVG збережена.
- Прибрано додаткове mobile-зміщення статуї, яке виводило її за екран при скролі. Фігура лишається внизу збоку; рух курсора на viewport до 760 px вимкнено.
- Мініатюри на mobile розміщено у звичайній сітці з двох колонок без обертання. Caption та Explore the studio знаходяться у природному потоці.
- Прибрано фіксовану мінімальну висоту mobile hero; висота визначається контентом. Виправлено відповідні no-JavaScript та reduced-motion стилі.
- На планшетних ширинах статуя менш контрастна, а контурні написи зміщені від основного тексту. Mobile footer має власний непрозорий фон, щоб декорації не накладалися на бренд і службовий текст.

## Перевірено

- Генератор створює 5 написів загальним розміром 8,809 байтів. У браузері кожен напис містить один готовий path і жодного SVG text. Декоративний aria-hidden збережено.

- `npm run lint`, `npm run typecheck`, `npm run build` проходять; усі 4 HTTP smoke-тести успішні. Після останньої корекції CSS production build повторно пройшов.
- У Chromium-based in-app browser оглянуто hero, моделі, LoRA, reference images і фінал на 390 × 844; додатково перевірено 320 × 740, 430 × 932, 768 × 900 та desktop 1440 × 900.
- На перевірених ширинах немає горизонтального overflow. На mobile немає текстових блоків за межами доступної ширини.
- CTA-група в hero закінчується приблизно на 573 px для 320 × 740, 603 px для 390 × 844, 574 px для 430 × 932 та 740 px для 768 × 900.
- Після прокручування mobile-статуя лишається на екрані, transform дорівнює none; написи правильно змінюються між секціями.
- Нових console errors / warnings не зафіксовано.
- Uncensored / NSFW image generator, 18+, змістові приклади, метадані та CTA збережено. Фонові фотографії не повернуто.

## Знімки

- `screenshots/fixed-mobile-hero.jpg` — поточний hero, viewport 390 × 844.
- `screenshots/fixed-mobile-models.png` — моделі після прокручування.
- `screenshots/fixed-mobile-final.jpg` — фінальний блок.
- `screenshots/merged-outline-letters.jpg` — очищені векторні літери на сторінці.
- `screenshots/fixed-outlines-desktop.png` — попередня ітерація SVG text; вона не показує останнє очищення геометрії.

## Межі перевірки

- Реальний iOS / Android, Safari / Firefox, окремий screen reader та zoom 200% не перевірено.
- Reduced motion та no-JavaScript перевірено за кодом; окремий runtime-прогін цих режимів не виконувався.
- Повний WCAG-аудит і польові LCP / INP / CLS не виконувалися. Авторизація й генерація залишаються майбутніми інтеграціями.

## Landing conversion and SEO redesign — 31 October 2026

- New hero leads with ultra-realistic, uncensored AI images, original characters and reference photos. A labelled model-example showcase offers suggested prompts without claiming recorded original settings.
- Reference results and recurring-character proof now precede the model and LoRA catalog. Existing NSFW samples remain in optional native details on the homepage, including Qwen, Krea and LoRA examples.
- Contextual creation links preserve model/prompt/LoRA/seed/reference intent through sign-in. Unknown preset models require an explicit available-model choice instead of silently selecting another workflow. Reference CTAs open the reference controls in Studio.
- New-account welcome-credit copy is shared between landing, help and sign-in. Public offer defaults to 15 and is configurable to match backend settings.
- Public static guides cover Qwen, Krea, reference images, character consistency, LoRAs and credits. Sitemap includes public guides and excludes Studio. Canonical checks normalize equivalent root URLs rather than failing on a trailing slash. Approved production domain: unkre.com.
- Native FAQ, descriptive model/use-case content, breadcrumbs, social previews and explicit-content metadata are present in server-rendered HTML.
- First-party events and Core Web Vitals are emitted to structured frontend logs with an allowlisted payload, without prompt/file/account data or analytics credentials/cookies. Do Not Track is honoured. An exact Nginx route keeps the endpoint on Next.js.
- Support and approved legal links are configurable; their content and addresses were not fabricated. They remain dependent on owner-supplied contact/policy information.
- Earlier local Lighthouse SEO-only scores do not establish live rankings or field Core Web Vitals. Real OAuth callbacks and production traffic measurements are outside a local fixture run.
