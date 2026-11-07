import assert from "node:assert/strict";
import { test } from "node:test";
import { createApiClient, ApiError, generationBody, parseApiJson } from "../src/lib/api.ts";
import { creditsForPrice, multiplyPrice, safeCheckoutUrl } from "../src/lib/payments.ts";
import { inviteUrl, normalizeReferralCode } from "../src/lib/referral.ts";

function json(body, status = 200, csrf = "csrf-test") {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf } });
}

test("writes bootstrap CSRF and use cookie credentials without bearer tokens", async () => {
  const calls = [];
  const client = createApiClient("https://api.example", async (url, options) => {
    calls.push({ url, options });
    return url.endsWith("/users/me") ? json({ detail: "Unauthorized" }, 401) : json({ nonce: "nonce", client_id: "client", expires_in: 300 });
  });
  await client.challenge("google");
  assert.equal(calls.length, 2);
  assert.equal(calls[0].url, "https://api.example/users/me");
  assert.equal(calls[1].options.headers.get("X-CSRF-Token"), "csrf-test");
  assert.deepEqual(JSON.parse(calls[1].options.body), { provider: "google" });
  for (const { options } of calls) { assert.equal(options.credentials, "include"); assert.equal(options.cache, "no-store"); assert.equal(options.headers.has("Authorization"), false); }
});

test("Telegram MiniApp login skips the CSRF bootstrap and posts initData", async () => {
  const calls = [];
  const client = createApiClient("/api", async (url, options) => {
    calls.push({ url, csrf: options.headers.get("X-CSRF-Token") });
    return json({ user: { id: "u" } }, 200);
  });
  const session = await client.miniappLogin("signed-init-data");
  assert.equal(session.user.id, "u");
  assert.deepEqual(calls, [{ url: "/api/users/auth/telegram-webapp", csrf: null }]);
});

test("concurrent unauthorized requests refresh the cookie session once", async () => {
  let expired = true;
  let refreshes = 0;
  const client = createApiClient("/api", async (url, options) => {
    if (url.endsWith("/users/auth/refresh")) {
      refreshes += 1;
      assert.equal(options.headers.get("X-CSRF-Token"), "csrf-test");
      await new Promise(resolve => setTimeout(resolve, 5));
      expired = false;
      return json({ user: { id: "u" }, expires_in: 900 });
    }
    return expired ? json({ detail: "Expired" }, 401) : json({ ok: true });
  });
  const results = await Promise.all([client.request("/one"), client.request("/two"), client.request("/three")]);
  assert.equal(refreshes, 1);
  assert.deepEqual(results, [{ ok: true }, { ok: true }, { ok: true }]);
});

test("an expired refresh cookie stops without a retry loop", async () => {
  const paths = [];
  const client = createApiClient("/api", async url => { paths.push(url); return json({ detail: "Invalid or expired credentials" }, 401); });
  await assert.rejects(client.me(), error => error instanceof ApiError && error.status === 401);
  assert.equal(paths.filter(path => path.endsWith("/users/auth/refresh")).length, 1);
  assert.equal(paths.length, 2);
});

test("a stale CSRF token is refreshed before retrying a rejected write", async () => {
  let bootstrap = 0;
  let writes = 0;
  const client = createApiClient("/api", async (url, options) => {
    if (url.endsWith("/users/me")) { bootstrap += 1; return json({ detail: "Unauthorized" }, 401, bootstrap === 1 ? "old" : "new"); }
    writes += 1;
    if (writes === 1) return json({ detail: "CSRF validation failed" }, 403, "old");
    assert.equal(options.headers.get("X-CSRF-Token"), "new");
    return json({ ok: true });
  });
  assert.deepEqual(await client.request("/write", { method: "POST", json: {} }), { ok: true });
  assert.equal(writes, 2);
  assert.equal(bootstrap, 2);
});

test("generation failures are not automatically resubmitted", async () => {
  let submitted = 0;
  const client = createApiClient("/api", async url => {
    if (url.endsWith("/users/me")) return json({}, 200);
    submitted += 1;
    return json({ detail: "Generation provider is unavailable" }, 503);
  });
  await assert.rejects(client.createGeneration({ workflow_id: "workflow", prompt: "An idea" }), error => error.status === 503);
  assert.equal(submitted, 1);
});

test("payment creation only sends credits and the caller's idempotency key", async () => {
  const bodies = [];
  const client = createApiClient("/api", async (url, options) => {
    if (url.endsWith("/users/me")) return json({});
    bodies.push([url, JSON.parse(options.body)]);
    return json({ id: "invoice" }, 201);
  });
  await client.createPayment("telegram_stars", 100, "same-order");
  await client.createPayment("atlos", 100, "same-order");
  assert.deepEqual(bodies, [["/api/payments/stars", { credits: 100, idempotency_key: "same-order" }], ["/api/payments/crypto", { credits: 100, idempotency_key: "same-order" }]]);
});

test("logout handles the backend's empty 204 response", async () => {
  const client = createApiClient("/api", async url => url.endsWith("/users/me") ? json({}) : new Response(null, { status: 204 }));
  assert.equal(await client.logout(), undefined);
});

test("login forwards an invited referral code and omits it when absent", async () => {
  const bodies = [];
  const client = createApiClient("/api", async (url, options) => {
    if (url.endsWith("/users/me")) return json({});
    bodies.push(JSON.parse(options.body));
    return json({ user: { id: "u" }, expires_in: 900 });
  });
  await client.login("google", "token", "n".repeat(43));
  await client.login("telegram", "token", "n".repeat(43), "0123456789abcdef01234567");
  assert.deepEqual(bodies, [
    { id_token: "token", nonce: "n".repeat(43) },
    { id_token: "token", nonce: "n".repeat(43), referral_code: "0123456789abcdef01234567" },
  ]);
});

test("referral stats and promo redemption use the backend reward routes", async () => {
  const calls = [];
  const client = createApiClient("/api", async (url, options) => {
    calls.push({ url, method: options.method, body: options.body, csrf: options.headers.get("X-CSRF-Token") });
    if (url.endsWith("/users/me")) return json({});
    if (url.endsWith("/referrals")) return json({ referral_code: "code", invited_count: 1, credits_earned: 5, referrer_credits: 5, invitee_credits: 5 });
    return json({ code: "WELCOME7", credits: 7, balance: 17 });
  });
  assert.equal((await client.referral()).invited_count, 1);
  assert.deepEqual(await client.redeemPromo("WELCOME7"), { code: "WELCOME7", credits: 7, balance: 17 });
  assert.deepEqual(calls.map(call => [call.method, call.url]), [
    ["GET", "/api/referrals"],
    ["POST", "/api/promos/redeem"],
  ]);
  assert.deepEqual(JSON.parse(calls[1].body), { code: "WELCOME7" });
  assert.equal(calls[1].csrf, "csrf-test");
});

test("disabled login providers do not attempt a session refresh", async () => {
  const paths = [];
  const client = createApiClient("/api", async url => { paths.push(url); return url.endsWith("/users/me") ? json({}, 200) : json({ detail: "Provider unavailable" }, 503); });
  await assert.rejects(client.challenge("telegram"), error => error.status === 503);
  assert.equal(paths.some(path => path.endsWith("/users/auth/refresh")), false);
});

test("workflow pagination collects actual database IDs without guessing names", async () => {
  const paths = [];
  const client = createApiClient("/api", async url => { paths.push(url); return json(url.endsWith("offset=0") ? Array.from({ length: 100 }, (_, i) => ({ id: String(i) })) : [{ id: "last" }]); });
  const rows = await client.workflows();
  assert.equal(rows.length, 101);
  assert.deepEqual(paths, ["/api/workflows?limit=100&offset=0", "/api/workflows?limit=100&offset=100"]);
});

test("payment history and invoices use the provider query required by the backend", async () => {
  const paths = [];
  const client = createApiClient("/api", async url => { paths.push(url); return json(url.includes("/payments/") ? { id: "one" } : [{ id: "one" }]); });
  await client.payments("telegram_stars", 20);
  await client.payment("atlos", "payment-id");
  assert.deepEqual(paths, [
    "/api/payments?provider=telegram_stars&limit=20&offset=20",
    "/api/payments/payment-id?provider=atlos",
  ]);
});

test("generation images use the authorized backend route and retry once after refresh", async () => {
  let expired = true;
  const calls = [];
  const client = createApiClient("/api", async (url, options) => {
    calls.push({ url, credentials: options.credentials });
    if (url.endsWith("/users/me")) return json({});
    if (url.endsWith("/users/auth/refresh")) { expired = false; return json({ user: { id: "u" }, expires_in: 900 }); }
    if (expired) return json({ detail: "Expired" }, 401);
    return new Response(new Blob(["png-bytes"], { type: "image/png" }), { status: 200, headers: { "Content-Type": "image/png" } });
  });
  const blob = await client.image("generation-id");
  assert.equal(await blob.text(), "png-bytes");
  assert.deepEqual(calls.map(call => call.url), [
    "/api/generations/generation-id/image",
    "/api/users/auth/refresh",
    "/api/generations/generation-id/image",
  ]);
  assert.ok(calls.every(call => call.credentials === "include"));
});

test("64-bit generation seeds round-trip without losing precision or editing prompts", () => {
  const prompt = 'A label reading "seed": 123 and an escaped slash \\';
  const text = `{"seed":9223372036854775807,"prompt":${JSON.stringify(prompt)},"credits_spent":3}`;
  const parsed = parseApiJson(text);
  assert.equal(parsed.seed, "9223372036854775807");
  assert.equal(parsed.prompt, prompt);
  assert.equal(parsed.credits_spent, 3);
  const body = generationBody({ workflow_id: "id", prompt, negative_prompt: "blur, extra fingers", seed: parsed.seed });
  assert.match(body, /"seed":9223372036854775807}/);
  assert.equal(parseApiJson(body).prompt, prompt);
  assert.equal(parseApiJson(body).negative_prompt, "blur, extra fingers");
  for (const seed of ["-1", "9223372036854775808", "1e3", '1,"user_id":3']) assert.throws(() => generationBody({ workflow_id: "id", prompt, seed }), ApiError);
});

test("price estimates preserve the backend's decimal precision", () => {
  assert.equal(multiplyPrice("1.25", 100), "125");
  assert.equal(multiplyPrice("0.1", 3), "0.3");
  assert.equal(multiplyPrice("1E-18", 100), "0.0000000000000001");
  assert.equal(multiplyPrice("1.2E+3", 2), "2400");
  assert.equal(multiplyPrice("100.0100", 3), "300.03");
  assert.equal(multiplyPrice("2", 100), "200");
  assert.equal(multiplyPrice("invalid", 3), null);
});

test("a typed price resolves to whole credits at the configured rate", () => {
  assert.equal(creditsForPrice("125", "1.25"), 100);
  assert.equal(creditsForPrice("0.3", "0.1"), 3);
  assert.equal(creditsForPrice("100.0100", "1"), 100);
  assert.equal(creditsForPrice("1E+3", "2"), 500);
  assert.equal(creditsForPrice("100.", "1"), 100);
  assert.equal(creditsForPrice("0.5", "1"), null);
  assert.equal(creditsForPrice("invalid", "1"), null);
  assert.equal(creditsForPrice("10", "0"), null);
});

test("referral codes and invite links stay canonical", () => {
  assert.equal(normalizeReferralCode("  0123456789ABCDEF01234567  "), "0123456789abcdef01234567");
  assert.equal(normalizeReferralCode("not-a-code"), "");
  assert.equal(normalizeReferralCode(null), "");
  assert.equal(inviteUrl("https://unkre.example", "0123456789abcdef01234567"), "https://unkre.example/?ref=0123456789abcdef01234567");
  assert.equal(inviteUrl("http://localhost:3000", "bad"), "http://localhost:3000/?ref=");
});

test("checkout links must be HTTPS URLs without credentials", () => {
  assert.equal(safeCheckoutUrl("https://t.me/$invoice"), "https://t.me/$invoice");
  for (const value of ["javascript:alert(1)", "data:text/html,test", "http://example.com", "https://user:secret@example.com", "/relative"]) assert.equal(safeCheckoutUrl(value), null);
});
