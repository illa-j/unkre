import assert from "node:assert/strict";
import { test } from "node:test";
import { defaultDraft, galleryItems, readWorkspace, studioImages } from "../src/lib/studio.ts";
import { loraTitle, workflowTitle } from "../src/lib/catalog.ts";
import { clampLoraStrength, isValidLoraStrength } from "../src/lib/lora-strength.ts";
import { loraCollections } from "../src/lib/lora-collections.ts";

const base = process.env.TEST_BASE_URL || "http://localhost:3000";

test("all studio screens are age-gated and remain outside search indexing", async () => {
  for (const path of ["/studio", "/studio/gallery", "/studio/presets", "/studio/loras", "/studio/credits", "/studio/referrals", "/studio/settings", "/studio/images/mint-portrait"]) {
    const response = await fetch(new URL(path, base));
    assert.equal(response.status, 200, path);
    const html = await response.text();
    assert.match(html, /Your studio is for adults/, path);
    assert.match(html, /name="robots" content="noindex, nofollow"/, path);
    assert.match(html, /I confirm that I am/, path);
    assert.doesNotMatch(html, /id="studio-main"/, path);
    assert.doesNotMatch(html, /rel="canonical"/, path);
  }
});

test("studio can recover from missing, corrupt and unexpected local data", () => {
  assert.equal(readWorkspace(null).saved.length, 0);
  assert.equal(readWorkspace("not json").draft.model, "qwen");
  assert.equal(defaultDraft.prompt, "");
  const legacyPrompts = [
    studioImages[0].promptIdea,
    "A natural portrait of the adult person in my reference photo, soft daylight, realistic skin texture and a photographic feel.",
  ];
  for (const prompt of legacyPrompts) {
    assert.equal(readWorkspace(JSON.stringify({ draft: { ...defaultDraft, prompt } })).draft.prompt, "");
  }
  const savedDefault = readWorkspace(JSON.stringify({ saved: [{ id: "default-prompt", sourceId: "mint-portrait", createdAt: "2026-11-03T12:00:00.000Z", draft: { ...defaultDraft, prompt: legacyPrompts[1] } }] }));
  assert.equal(savedDefault.saved[0].draft.prompt, legacyPrompts[1]);
  const value = readWorkspace(JSON.stringify({ saved: [{ id: "bad", sourceId: "missing", draft: defaultDraft }], settings: { name: "a".repeat(120), defaultModel: "unknown", showAdult: "true" }, draft: { model: "qwen", prompt: "x".repeat(4500), negativePrompt: "y".repeat(9000), ratio: "bad", loras: [{ id: "a", strength: 50 }, { id: "a", strength: 0.2 }, { id: "b", strength: "broken" }], batch: -1 } }));
  assert.equal(value.saved.length, 0);
  assert.equal(value.settings.name.length, 60);
  assert.equal(value.settings.defaultModel, "qwen");
  assert.equal(value.settings.showAdult, false);
  assert.equal(value.draft.prompt.length, 4000);
  assert.equal(value.draft.negativePrompt.length, 8192);
  assert.equal(value.draft.ratio, "2:3");
  assert.deepEqual(value.draft.loras, [{ id: "a", strength: 2 }, { id: "b", strength: 0.7 }]);
  assert.equal(value.draft.batch, 1);
  assert.equal(clampLoraStrength(1.5), 1.5);
  assert.equal(clampLoraStrength(2), 2);
  assert.equal(clampLoraStrength(3), 2);
  assert.equal(clampLoraStrength(-1), 0);
  assert.equal(isValidLoraStrength(1.5), true);
  assert.equal(isValidLoraStrength(2), true);
  assert.equal(isValidLoraStrength(2.5), false);
  assert.equal(isValidLoraStrength(-0.1), false);
  const saved = readWorkspace(JSON.stringify({ saved: [{ id: "saved-test", sourceId: "mint-portrait", createdAt: "2026-10-28T12:00:00.000Z", draft: { model: "qwen", prompt: "An idea", lora: "legacy-id", strength: "broken" } }] }));
  assert.deepEqual(saved.saved[0].draft.loras, [{ id: "legacy-id", strength: 0.7 }]);
  assert.equal(saved.saved[0].draft.ratio, "2:3");
});

test("saved previews retain the original image and editable preview settings", () => {
  const workspace = readWorkspace(JSON.stringify({ saved: [{ id: "saved-test", sourceId: "mint-portrait", createdAt: "2026-10-28T12:00:00.000Z", draft: { ...defaultDraft, prompt: "My own idea" } }] }));
  const [image] = galleryItems(workspace);
  assert.equal(image.id, "saved-test");
  assert.equal(image.src, studioImages[0].src);
  assert.equal(image.draft.prompt, "My own idea");
  assert.equal(image.category, "SFW");
  assert.ok(loraCollections.some(lora => lora.model === "Qwen Image 2.1"));
  assert.ok(loraCollections.some(lora => lora.model === "Krea 2"));
});

test("catalog labels never show technical workflow names or LoRA file names", () => {
  assert.equal(workflowTitle({ name: "krea2_turbo_all_api" }), "Krea 2 Turbo");
  assert.equal(workflowTitle({ name: "krea2_raw_t2image_api" }), "Krea 2 Raw");
  assert.equal(workflowTitle({ name: "Qwen Image 2.1" }), "Qwen Image 2.1");
  assert.equal(loraTitle({ id: "a", name: "lenovo-ultrareal.safetensors", description: "Lenovo UltraReal", preview_urls: [] }), "Lenovo UltraReal");
  assert.equal(loraTitle({ id: "b", name: "portrait-master.safetensors", description: null, preview_urls: [] }), "Portrait Master");
  assert.ok(!loraTitle({ id: "c", name: "nicegirls-ultrareal.safetensors", description: null, preview_urls: [] }).includes(".safetensors"));
});
