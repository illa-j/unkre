# Візуальні асети

Растрові ілюстрації, окрім наданих користувачем прикладів Krea 2, Qwen Image 2.1 та LoRA, створені 26 жовтня 2026 року вбудованим imagegen. Після генерації виконано лише зменшення розміру та WebP-стиснення через Sharp. Alpha статуї збережена. Згенеровані для оформлення ілюстрації не заявляються як результати Krea 2.

## Приклади Krea 2 від користувача

Додані в секцію моделей та мініатюри hero у порядку Turbo / Raw зі збереженням відповідності, вказаної користувачем:

- `public/images/krea-2-raw.png` — перше прикріплене фото, 450 × 600, 696 467 байтів. Джерело: `codex-clipboard-37c7e3d7-0e94-4699-ae95-1af498199818.png`.
- `public/images/krea-2-turbo.png` — друге прикріплене фото, 832 × 1248, 1 468 846 байтів. Джерело: `codex-clipboard-4638c3be-fad8-4f67-b9d9-03da90decbf3.png`.

Оригінальні PNG збережено без редагування. Next Image доставляє оптимізовані адаптивні версії; картки мають вихідні пропорції 3:4 для Raw та 2:3 для Turbo.

## Сталість персонажа Krea 2: приклади від користувача

Три PNG, надані 27 жовтня 2026 року, скопійовано без редагування в `public/images/krea-2-character/` та додано до секції CHARACTER CONSISTENCY перед прикладами Qwen Image 2.1.

| Прикріплене фото | Категорія | Файл | Розміри |
| --- | --- | --- | --- |
| 1 (`codex-clipboard-2994afba-a4c6-45b5-b728-4b186ad03962.png`) | SFW | `sfw-1.png` | 1024 × 1536 |
| 2 (`codex-clipboard-4b59e035-48bf-430c-bd85-f3c9219eb8e9.png`) | SFW | `sfw-2.png` | 1024 × 1536 |
| 3 (`codex-clipboard-fe63ef9f-0f36-487e-99b7-47af320748f3.png`) | NSFW | `nsfw-1.png` | 1024 × 1536 |

Перші два фото показані поруч; останнє, позначене користувачем як NSFW, відкривається через native details з позначкою 18+. Вихідні пропорції 2:3 збережено без обрізання, Next Image доставляє адаптивні оптимізовані версії. Промпти, seed та конкретний варіант моделі Krea 2 не надані й не вигадуються. Компонент: `src/components/krea-character-examples.tsx`.

## Приклади LoRA від користувача

Усі дев’ять прикріплених PNG скопійовано без редагування в `public/images/loras/`. Відповідність і класифікація — за списком користувача; користувач уточнив, що в промптах зазначено 20+ років.

| № | LoRA | Категорія | Файл |
| --- | --- | --- | --- |
| 1 | Realistic Snapshot | SFW | realistic-snapshot-sfw-1.png |
| 2 | Realistic Snapshot | SFW | realistic-snapshot-sfw-2.png |
| 3 | Realistic Snapshot | NSFW | realistic-snapshot-nsfw-1.png |
| 4, біля ялинки | Realistic Snapshot | NSFW | realistic-snapshot-nsfw-2.png |
| 5, пляж | [KREA 2] Mystic XXX | NSFW | mystic-xxx-nsfw-1.png |
| 6 | [KREA 2] Mystic XXX | NSFW | mystic-xxx-nsfw-2.png |
| 7 | Lenovo UltraReal | SFW | lenovo-ultrareal-1.png |
| 8 | NiceGirls UltraReal | SFW | nicegirls-ultrareal-1.png |
| 9 | NiceGirls UltraReal | SFW | nicegirls-ultrareal-2.png |

Вихідні пропорції збережено; Next Image доставляє адаптивні оптимізовані версії. NSFW-приклади містяться в закритих за замовчуванням native details. Реальні промпти та параметри генерації не надані й не вигадуються. Назва Realistic Snapshot посилається на сторінку Civitai, надану користувачем; автоматичне читання цієї сторінки було недоступне.

## Приклади LoRA для Qwen Image 2.1 від користувача

Шість PNG, надані 27 жовтня 2026 року, скопійовано без редагування в `public/images/loras/`. Класифікація та відповідність — за списком користувача:

| Фото / джерело | LoRA | Категорія | Файл | Розміри |
| --- | --- | --- | --- | --- |
| 1 (`codex-clipboard-0c13f2c7-8cb6-4eac-be89-b2242c0cc2b8.png`) | Lenovo UltraReal | SFW | `qwen-lenovo-ultrareal-sfw-1.png` | 1088 × 1440 |
| 2 (`codex-clipboard-6057fe31-0d05-438d-bff6-6d9b0859b207.png`) | Lenovo UltraReal | SFW | `qwen-lenovo-ultrareal-sfw-2.png` | 2048 × 3072 |
| 3 (`codex-clipboard-9c097965-4637-4222-8f50-013d65c8c0cb.png`) | NiceGirls UltraReal | SFW | `qwen-nicegirls-ultrareal-sfw-1.png` | 1776 × 1184 |
| 4 (`codex-clipboard-44d00a00-da5e-43ac-89b3-1de4a16721ec.png`) | NiceGirls UltraReal | SFW | `qwen-nicegirls-ultrareal-sfw-2.png` | 896 × 1184 |
| 5 (`codex-clipboard-a61d770e-bf65-48e8-92dc-852fbb5086fe.png`) | FemaledVaginus-NSFW | NSFW | `qwen-femaledvaginus-nsfw-1.png` | 1536 × 2048 |
| 6 (`codex-clipboard-3a21c865-0249-4226-8524-b2284963aa58.png`) | FemaledVaginus-NSFW | NSFW | `qwen-femaledvaginus-nsfw-2.png` | 450 × 681 |

У секції LoRA створено окремі групи Krea 2 та Qwen Image 2.1; назви моделей також включено до alt-текстів. Нові NSFW-приклади закриті за замовчуванням у native details 18+. Вихідні пропорції всіх фото збережено без обрізання. Промпти та параметри генерації не надані й не вигадуються.

## Приклади Qwen Image 2.1 від користувача

Додатковий приклад для огляду моделей: `public/images/qwen-image-2-1/example.png`, 2048 × 3072. Джерело: наданий користувачем `codex-clipboard-4115cce9-eef1-4ea5-b24c-c287b7ed742c.png`, скопійований без редагування. Використано як третій приклад у hero, окрему картку Qwen Image 2.1 у секції моделей та мініатюру у фінальному CTA. У мобільних мініатюрах збережено повне фото у вихідних пропорціях. Цей приклад не замінює набір референс → результат нижче.

Три PNG, надані 27 жовтня 2026 року, скопійовано без редагування в `public/images/qwen-image-2-1/`. Відповідність задано користувачем:

| Прикріплене фото | Призначення | Файл | Розміри |
| --- | --- | --- | --- |
| 1 (`codex-clipboard-81715839-dfb2-4007-bcdf-0c47121141bf.png`) | SFW генерація | `sfw.png` | 896 × 1184 |
| 2 (`codex-clipboard-caadbdfe-15a0-4851-a82a-d68deb450ce9.png`) | NSFW генерація | `nsfw.png` | 896 × 1184 |
| 3 (`codex-clipboard-78c380db-e170-4d3c-9bb4-4abeb231f249.png`) | Вхідний референс | `reference.png` | 450 × 600 |

Набір замінює ілюстративну пару пейзажів у секції reference images. Референс і SFW результат показані поруч; NSFW відкривається через native details з позначкою 18+, аналогічно прикладам LoRA. Вихідні пропорції збережено без обрізання, Next Image доставляє адаптивні оптимізовані версії. Промпти та параметри генерації не надані.

## Темний редизайн

За останнім запитом фонові зображення секцій прибрано з лендингу. Наведені нижче фонові файли збережені як архів асетів і не завантажуються сторінкою.

П’ять нових фонових сцен створено вбудованим imagegen. Для кожної підготовлено desktop-версію 1672 × 941 і mobile-crop 900 × 1200. Фінальні промпти, вхідні референси та шляхи оригінальних результатів: [dark-assets.json](dark-assets.json).

| Секція | Файл у public/images/backgrounds/ | Концепція | Desktop / mobile |
| --- | --- | --- | --- |
| Hero | hero.webp / hero-mobile.webp | Кам’яна галерея з верхнім світлом | 110 / 80 KiB |
| Models | models.webp / models-mobile.webp | Туманна гірська долина, два світлові акценти | 94 / 87 KiB |
| LoRAs | loras.webp / loras-mobile.webp | Темна галерея з винними рефлексами | 64 / 46 KiB |
| Reference images | reference.webp / reference-mobile.webp | Нічний інтер’єр із вікном на місто | 145 / 93 KiB |
| Final CTA | final.webp / final-mobile.webp | Дверний отвір на морський горизонт | 104 / 69 KiB |

Додаткові змістові приклади:

- `public/images/portrait-painterly.webp` — 1000 × 1250, приблизно 234 KiB; живописна варіація на основі `portrait.webp`.
- `public/images/reference-result.webp` — 1000 × 1250, приблизно 152 KiB; нова нічна сцена, створена з `landscape.webp` як вхідного референсу.

Обидві варіації отримані через редагування зображень вбудованим imagegen. Пейзажі збережені в архіві асетів. У фінальному CTA показано три надані користувачем SFW-приклади: `krea-2-character/sfw-2.png`, `krea-2-turbo.png` та `qwen-image-2-1/example.png` з підписом Krea 2 & Qwen Image 2.1 examples. Композиція відповідає hero, рамки — 2 px; на mobile фото показуються повністю без обрізання.

Наведені нижче оригінальні асети перевикористано з першої версії. Освітлення статуї в темній композиції задається CSS; її вихідний асет збережений.

## Статуя

Файл: `public/images/muse.webp`, 1024 × 1536, приблизно 346 KiB. Додаткова оптимізована PNG-версія для social preview: `public/images/muse-social.png`, 500 × 750, приблизно 198 KiB.

Вхідний референс: прикріплена користувачем фотографія крилатої статуї. Використана як референс форми й настрою для створення оригінального асета; вихідне фото не публікується на лендингу.

Фінальний промпт:

> Use case: stylized-concept. Asset type: isolated website hero sculpture cutout, portrait composition, genuinely transparent alpha background. Use attached photograph only as visual reference for the feeling of a classical winged marble goddess. Create an ORIGINAL exquisite museum-quality sculpture photograph, not a reproduction of that photo. A beautiful classical female Nike/Victory marble statue, head intact with softly waved hair, graceful serene face turned toward the LEFT looking slightly upward, torso in deeply folded flowing Grecian dress, two grand feathered wings stretched upward and outward, asymmetric wings framing the figure, waist and upper thighs visible, bottom can end naturally as a sculpture fragment. Both wings fully within frame with breathing room. Cream ivory aged marble with tactile stone grain and delicate weathering, soft warm daylight from upper left, rich realistic sculptural shadows, poetic sophisticated fine-art editorial aesthetic. Three-quarter low camera angle. One continuous sculpture, realistic anatomy and elegant proportions, no modern objects, no text, no watermark, no pedestal, no border, no surrounding scenery, no floor. Marble must remain light and readable on warm cream website background. Transparent outside silhouette including gaps around feathers. Deliver high resolution approximately 1024x1536 portrait cutout.

## Портрет

Файл: `public/images/portrait.webp`, 1000 × 1250, приблизно 116 KiB.

> Original fine-art editorial photographic portrait for a premium AI image creation landing page gallery. A young adult woman in her late twenties with natural freckles, long dark wavy hair, dark brown eyes, wearing a black high-neck silk top, three-quarter portrait looking back over her shoulder toward camera, warm soft window light from left, subtle film grain, muted olive taupe background, earthy cinematic tones, beautiful realistic texture, sophisticated fashion magazine, intimate quiet mood. Vertical 4:5 framing with hair and shoulder, no nudity, no text, no watermarks, no borders. Photograph fills the entire image.

## Натюрморт

Файл: `public/images/still-life.webp`, 1000 × 1250, приблизно 175 KiB.

> Original fine-art editorial still-life photograph for a premium creative image platform gallery. Sculptural white calla lily flowers with elegantly curved long green stems in a small rustic dark ceramic vessel beside an ivory textured wall, deep soft side shadows and late afternoon warm sunlight, minimal poetic asymmetrical composition, slight vintage analog film grain, muted sage ivory and sand tones, close up texture, luxury art magazine. Portrait 4:5 framing, no text, no watermarks, no borders. Photograph fills the entire image.

## Пейзаж

Файл: `public/images/landscape.webp`, 1000 × 1250, приблизно 197 KiB.

> Original fine-art cinematic photograph for a premium creative image platform gallery. Tiny lone adult figure in a long dark coat standing on a cliff overlooking a quiet wild Atlantic sea, windswept long grasses, misty distant rugged coast and soft peach clouded sky, ethereal dawn light, earthy desaturated olive sand and grey, subtle analog film grain, wide open atmospheric poetic landscape, film still shot on 35mm, sophisticated art magazine. Portrait 4:5 framing, no text, no watermarks, no borders. Photograph fills the entire image.

## Шрифти та графіка

Контурні написи отримано з локального DM Sans regular 400, із boolean union перекриттів гліфів через fontTools 4.67.0 та skia-pathops 0.9.2. Дані: `src/lib/outline-words.ts`; відтворення: `scripts/generate-outline-words.py`. Генератор не потрібен у runtime або під час звичайної збірки.

- Instrument Serif (regular / italic) та DM Sans Variable: self-hosted із пакетів Fontsource; файли ліцензій зберігаються у відповідних npm-пакетах.
- Логотип — типографічний; іконки стрілок, зірка та favicon — локальні SVG.
- Social preview генерується локально через `next/og`; зовнішні запити для зображень або шрифтів при перегляді не потрібні.
