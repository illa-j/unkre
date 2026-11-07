import assert from "node:assert/strict";
import { test } from "node:test";

const base = process.env.TEST_BASE_URL || "http://localhost:3000";

test("admin login is reachable and excluded from indexing", async () => {
  const response = await fetch(new URL("/admin/login", base));
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /<meta name="robots" content="noindex[^"]*"/);
  assert.match(html, /Admin access/);
});

test("the admin panel shell is not server-rendered for signed-out visitors", async () => {
  const response = await fetch(new URL("/admin", base));
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /noindex/);
  assert.doesNotMatch(html, /Accounts<\/a>/);
});

const publicBase = process.env.PUBLIC_BASE_URL;

test("the public origin never exposes the admin UI or admin API", { skip: !publicBase }, async () => {
  for (const path of ["/admin", "/admin/login", "/api/admins/me"]) {
    const response = await fetch(new URL(path, publicBase));
    assert.equal(response.status, 404, `${path} must be hidden on the public origin`);
  }
});
