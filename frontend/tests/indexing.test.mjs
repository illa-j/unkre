import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { test } from "node:test";

test("indexing works without domain or auth configuration and supports preview opt-out", () => {
  const baseEnv = { ...process.env };
  for (const key of ["SITE_INDEXABLE", "NEXT_PUBLIC_SITE_URL"]) {
    delete baseEnv[key];
  }
  const siteModule = new URL("../src/lib/site.ts", import.meta.url).href;
  const script = `const { isIndexable } = await import(${JSON.stringify(siteModule)}); process.stdout.write(JSON.stringify(isIndexable));`;
  for (const { name, env, expected } of [
    { name: "default configuration", env: {}, expected: true },
    { name: "public domain without authentication", env: { NEXT_PUBLIC_SITE_URL: "https://unkre.example" }, expected: true },
    { name: "explicit indexing", env: { SITE_INDEXABLE: "true" }, expected: true },
    { name: "private preview", env: { SITE_INDEXABLE: "false" }, expected: false },
  ]) {
    const output = execFileSync(process.execPath, ["--input-type=module", "-e", script], {
      env: { ...baseEnv, ...env },
      encoding: "utf8",
    });
    assert.equal(JSON.parse(output), expected, name);
  }
});
