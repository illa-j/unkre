import assert from "node:assert/strict";
import { test } from "node:test";
import { loraCollections } from "../src/lib/lora-collections.ts";

const base = process.env.TEST_BASE_URL || "http://localhost:3000";

test("the landing serves meaningful content and SEO without client JavaScript", async () => {
  const response = await fetch(base);
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /<html[^>]*lang="en"/);
  assert.equal((html.match(/<h1\b/g) || []).length, 1);
  const heroTitle = html.match(/<h1\b[^>]*>([\s\S]*?)<\/h1>/)?.[1] || "";
  assert.match(heroTitle, /Ultra-realistic/);
  assert.match(heroTitle, /Uncensored/);
  assert.match(html, /<title>UNKRE.*Uncensored &amp; NSFW AI Image Generator/);
  assert.match(html, /name="description" content="[^"]{50,}"/);
  assert.match(html, /name="robots"/);
  assert.match(html, /property="og:image" content="https:\/\/unkre.cc\/og\/home.jpg"/);
  assert.match(html, /name="twitter:card" content="summary_large_image"/);
  assert.match(html, /href="#main"/);
  for (const id of ["hero-title", "models-title", "loras-title", "references-title", "final-title"]) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.match(html, /Krea 2 Turbo/);
  assert.match(html, /SFW and NSFW images/);
  assert.doesNotMatch(html, /name="rating" content="adult"/);
  assert.doesNotMatch(html, /ADULTS 18\+/i);
  assert.match(html, /NSFW · 18\+/);
  assert.match(html, /UNCENSORED AI IMAGE GENERATOR/);
  assert.match(html, /Choose a LoRA/);
  for (const name of ["Realistic Snapshot", "Mystic XXX", "Lenovo UltraReal", "NiceGirls UltraReal"]) {
    assert.ok(html.includes(name), name);
  }
  assert.match(html, /reference photos/);
  assert.match(html, /Create my first image/);
  assert.ok(html.indexOf('id="references"') < html.indexOf('id="loras"'));
  assert.ok((html.match(/href="\/studio(?:\?|&|\")/g) || []).length >= 6);
  const referenceLink = html.match(/href="([^"]*reference=1[^"]*)"/)?.[1] ?? "";
  assert.ok(referenceLink, "reference CTA");
  assert.doesNotMatch(referenceLink, /[?&]prompt=/);
  assert.match(html, /name="theme-color" content="#090e12"/);
  assert.doesNotMatch(html, /href="#"/);
});

test("crawl controls and sitemap are valid in preview and production", async () => {
  const robots = await (await fetch(new URL("/robots.txt", base))).text();
  assert.match(robots, /User-Agent: \*/i);
  const html = await (await fetch(base)).text();
  const noindex = process.env.TEST_EXPECT_NOINDEX === "true";
  if (noindex) {
    assert.match(html, /name="robots" content="noindex, nofollow"/);
    assert.match(robots, /^Disallow: \/$/m);
  } else {
    assert.match(html, /name="robots" content="index, follow[^"]*"/);
    assert.match(robots, /Allow: \//);
    assert.doesNotMatch(robots, /^Disallow: \/$/m);
    assert.match(robots, /^Disallow: \/admin$/m);
    assert.match(robots, /^Disallow: \/studio$/m);
  }
  const sitemap = await fetch(new URL("/sitemap.xml", base));
  assert.equal(sitemap.status, 200);
  const sitemapXml = await sitemap.text();
  assert.match(sitemapXml, /<urlset/);
  const canonical = html.match(/rel="canonical" href="([^"]+)"/)?.[1];
  if (!noindex && canonical) {
    assert.match(robots, /Sitemap: https?:\/\//);
    const locations = [...sitemapXml.matchAll(/<loc>([^<]+)<\/loc>/g)].map(match => new URL(match[1].replaceAll("&amp;", "&")).href);
    assert.ok(locations.includes(new URL(canonical).href), "canonical and sitemap use the same normalized URL");
    assert.ok(locations.every(url => !new URL(url).pathname.startsWith("/studio")), "private Studio screens are excluded");
    assert.ok(locations.some(url => new URL(url).pathname === "/learn/consistent-characters"));
  } else {
    assert.doesNotMatch(sitemapXml, /<loc>/);
    assert.doesNotMatch(robots, /Sitemap:/);
  }
});

test("all artwork and share previews are available", async () => {
  for (const name of ["muse", "portrait", "still-life", "landscape", "portrait-painterly", "reference-result"]) {
    const response = await fetch(new URL(`/images/${name}.webp`, base));
    assert.equal(response.status, 200, name);
    assert.match(response.headers.get("content-type"), /image\/webp/);
    const bytes = new Uint8Array(await response.arrayBuffer());
    assert.ok(bytes.length > 1000 && bytes.length < 600_000, `${name} size budget`);
  }
  for (const path of ["/opengraph-image", "/twitter-image"]) {
    const response = await fetch(new URL(path, base));
    assert.equal(response.status, 200, path);
    assert.match(response.headers.get("content-type"), /image\/jpeg/);
  }
  for (const name of ["krea-2-turbo", "krea-2-turbo-gothic", "krea-2-raw", "qwen-image-2-1/example"]) {
    const response = await fetch(new URL(`/images/${name}.png`, base));
    assert.equal(response.status, 200, name);
    assert.match(response.headers.get("content-type"), /image\/png/);
  }
  for (const example of loraCollections.flatMap((collection) => [...collection.sfw, ...collection.nsfw])) {
    const response = await fetch(new URL(`/images/loras/${example.file}.png`, base), { method: "HEAD" });
    assert.equal(response.status, 200, example.file);
    assert.match(response.headers.get("content-type"), /image\/png/);
  }
});

test("landing retains NSFW examples on the homepage and renders content without photographic backgrounds", async () => {
  const html = await (await fetch(base)).text();
  assert.ok((html.match(/<section\b/g) || []).length >= 8);
  for (const file of ["qwen-image-2-1/nsfw.png", "krea-2-character/nsfw-1.png"]) assert.ok(html.includes(file), file);
  assert.match(html, /<details/);
  assert.match(html, /id="faq"/);
  assert.match(html, /<noscript>/);
  assert.doesNotMatch(html, /images\/backgrounds\/|--section-background|data-background=|scene-backgrounds/);
  assert.match(html, /class="statue-image"/);
});


test("public model and use-case guides have unique crawlable content and canonical URLs", async () => {
  const titles = new Set();
  for (const slug of ["qwen-image-2-1", "krea-2", "reference-images", "consistent-characters", "loras", "credits"]) {
    const response = await fetch(new URL(`/learn/${slug}`, base));
    assert.equal(response.status, 200, slug);
    const html = await response.text();
    assert.equal((html.match(/<h1\b/g) || []).length, 1, slug);
    const title = html.match(/<title>([^<]+)<\/title>/)?.[1];
    assert.ok(title && !titles.has(title), slug);
    titles.add(title);
    assert.ok((html.match(/<h2\b/g) || []).length >= 3, slug);
    assert.match(html, /BreadcrumbList/, slug);
    assert.match(html, /href="\/studio/, slug);
    assert.match(html, new RegExp(`rel="canonical" href="https?[^"\\s]+/learn/${slug}"`), slug);
  }
  assert.equal((await fetch(new URL("/learn/not-a-real-guide", base))).status, 404);
});

test("first-party analytics rejects external submissions and strips sensitive fields", async () => {
  const endpoint = new URL("/api/analytics", base);
  const accepted = await fetch(endpoint, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({event:"cta_click",placement:"hero",prompt:"not logged",user_id:"not logged"})});
  assert.equal(accepted.status, 204);
  const sameOrigin = await fetch(endpoint, {method:"POST",headers:{"Content-Type":"application/json",Origin:new URL(base).origin},body:JSON.stringify({event:"landing_view",path:"/"})});
  assert.equal(sameOrigin.status, 204, "same-origin browser requests survive a proxy's internal localhost URL");
  const rejected = await fetch(endpoint, {method:"POST",headers:{"Content-Type":"application/json",Origin:"https://untrusted.example"},body:JSON.stringify({event:"cta_click"})});
  assert.equal(rejected.status, 403);
  const invalid = await fetch(endpoint, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({event:"unknown_event"})});
  assert.equal(invalid.status, 400);
});

test("unknown pages render the branded 404", async () => {
  const response = await fetch(new URL("/definitely-not-a-page", base));
  assert.equal(response.status, 404);
  const html = await response.text();
  assert.match(html, /This page/);
  assert.match(html, /Back to UNKRE/);
});
