import assert from "node:assert/strict";
import { test } from "node:test";

const base = process.env.TEST_BASE_URL || "http://localhost:3000";

const pages = [
  ["/trust", "Trust center"],
  ["/about", "About UNKRE"],
  ["/contact", "Contact UNKRE"],
  ["/privacy", "Privacy Policy"],
  ["/terms", "Terms of Service"],
  ["/refunds", "Refunds & cancellations"],
  ["/acceptable-use", "Acceptable use & content policy"],
  ["/copyright", "Copyright & likeness"],
  ["/security", "Security at UNKRE"],
  ["/transparency", "Transparency & moderation"],
  ["/status", "Service status"],
];

test("legal and trust pages are public, indexable and canonical", async () => {
  for (const [path, heading] of pages) {
    const response = await fetch(new URL(path, base));
    assert.equal(response.status, 200, path);
    const html = await response.text();
    assert.match(html, /name="robots" content="index, follow[^"]*"/, path);
    assert.ok(html.includes(`<link rel="canonical" href="https://unkre.cc${path}"/>`), `${path} canonical`);
    assert.ok(html.includes(heading), `${path} heading`);
    assert.match(html, /property="og:image" content="https:\/\/unkre.cc\/og\/home.jpg"/, `${path} open graph image`);
    assert.match(html, /name="twitter:image"/, `${path} twitter image`);
  }
});

test("the trust center links every policy and the sitemap includes them", async () => {
  const trust = await (await fetch(new URL("/trust", base))).text();
  for (const [path] of pages) {
    if (path === "/trust") continue;
    assert.ok(trust.includes(`href="${path}"`), `${path} linked from trust center`);
  }
  const sitemap = await (await fetch(new URL("/sitemap.xml", base))).text();
  for (const [path] of pages) {
    assert.ok(sitemap.includes(`<loc>https://unkre.cc${path}</loc>`), `${path} in sitemap`);
  }
  assert.match(sitemap, /<lastmod>2026-11-03T00:00:00.000Z<\/lastmod>/);
});

test("the public footer exposes the legal pages", async () => {
  const html = await (await fetch(base)).text();
  for (const path of ["/about", "/trust", "/contact", "/privacy", "/terms", "/refunds", "/acceptable-use", "/copyright", "/security", "/transparency", "/status"]) {
    assert.ok(html.includes(`href="${path}"`), `${path} footer link`);
  }
});
