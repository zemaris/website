// Tests for assets/checkout.js with a tiny fake page and a fake Paddle (no network, no account).
// Run:  node --test _tests/checkout.test.mjs   (portable Node 24 in D:\Zemaris\07-Server-and-Tools\Local-Tools\node)
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const code = readFileSync(new URL("../assets/checkout.js", import.meta.url), "utf8");
const GOOD = {
  environment: "sandbox", token: "test_a1b2c3d4e5f6a7b8c9d0e1f2a3b",
  prices: { monthly: "pri_" + "a".repeat(26), yearly: "pri_" + "b".repeat(26), lifetime: "pri_" + "c".repeat(26) },
  successUrl: "https://zemaris.com/thank-you.html", support: "admin@zemaris.com",
  paddleJs: "https://cdn.paddle.com/paddle/v2/paddle.js",
};

function page(cfg, { paddle = "stub", theme = null, scriptLoads = true } = {}) {
  const handlers = {}, appended = [], calls = { env: [], init: [], open: [] };
  const msg = { textContent: "" };
  const cfgEl = cfg === null ? null : { textContent: typeof cfg === "string" ? cfg : JSON.stringify(cfg) };
  const fakePaddle = {
    Environment: { set: e => calls.env.push(e) },
    Initialize: o => calls.init.push(o),
    Checkout: { open: o => calls.open.push(o) },
  };
  const win = { matchMedia: () => ({ matches: false }) };
  if (paddle === "stub") win.Paddle = fakePaddle;
  const doc = {
    documentElement: { getAttribute: () => theme },
    getElementById: id => (id === "checkout-config" ? cfgEl : id === "checkoutMsg" ? msg : null),
    addEventListener: (t, f) => { (handlers[t] ||= []).push(f) },
    createElement: () => ({}),
    head: {
      appendChild: s => {
        appended.push(s);
        setTimeout(() => {
          if (!scriptLoads) return s.onerror && s.onerror();
          win.Paddle = fakePaddle;
          s.onload && s.onload();
        }, 0);
      },
    },
  };
  const ctx = { window: win, document: doc, matchMedia: win.matchMedia, setTimeout, Promise, JSON };
  vm.runInNewContext(code, ctx);
  const button = plan => {
    const b = { textContent: "Buy " + plan, attrs: { "data-checkout": plan },
      getAttribute: k => b.attrs[k], setAttribute: (k, v) => { b.attrs[k] = v }, removeAttribute: k => { delete b.attrs[k] } };
    b.closest = sel => (sel === "[data-checkout]" ? b : null);
    return b;
  };
  const click = async b => {
    let prevented = false;
    for (const f of handlers.click || []) f({ target: b, preventDefault: () => { prevented = true } });
    await new Promise(r => setTimeout(r, 5));
    return prevented;
  };
  return { win, calls, msg, appended, button, click, handlers };
}

test("opens the overlay with the plan's price, sandbox and thank-you page", async () => {
  const p = page(GOOD);
  const b = p.button("yearly");
  assert.equal(await p.click(b), true);
  assert.deepEqual(p.calls.env, ["sandbox"]);
  assert.equal(p.calls.init.length, 1);
  assert.equal(p.calls.init[0].token, GOOD.token);
  assert.equal(p.calls.open.length, 1);
  const o = p.calls.open[0];
  assert.deepEqual(JSON.parse(JSON.stringify(o.items)), [{ priceId: GOOD.prices.yearly, quantity: 1 }]);
  assert.equal(o.settings.displayMode, "overlay");
  assert.equal(o.settings.successUrl, GOOD.successUrl);
  assert.equal(o.settings.theme, "light");
  assert.equal(b.textContent, "Buy yearly");
  assert.equal(b.attrs["aria-busy"], undefined);
  assert.equal(p.msg.textContent, "");
  // a second purchase starts Paddle only once
  await p.click(p.button("lifetime"));
  assert.equal(p.calls.init.length, 1);
  assert.equal(p.calls.open[1].items[0].priceId, GOOD.prices.lifetime);
});

test("production does not switch Paddle to sandbox; dark theme follows the page", async () => {
  const p = page({ ...GOOD, environment: "production", token: "live_a1b2c3d4e5f6a7b8c9d0e1f2a3b" }, { theme: "dark" });
  await p.click(p.button("monthly"));
  assert.deepEqual(p.calls.env, []);
  assert.equal(p.calls.open[0].settings.theme, "dark");
});

test("loads Paddle.js only when needed, from the configured address", async () => {
  const p = page(GOOD, { paddle: "none" });
  assert.equal(p.appended.length, 0, "nothing is fetched on page load");
  await p.click(p.button("monthly"));
  assert.equal(p.appended.length, 1);
  assert.equal(p.appended[0].src, GOOD.paddleJs);
  assert.equal(p.calls.open.length, 1);
});

test("hovering a Buy button warms Paddle up", async () => {
  const p = page(GOOD, { paddle: "none" });
  for (const f of p.handlers.pointerover) f({ target: p.button("yearly") });
  for (const f of p.handlers.pointerover) f({ target: p.button("yearly") });
  await new Promise(r => setTimeout(r, 5));
  assert.equal(p.appended.length, 1);
  assert.equal(p.calls.open.length, 0);
});

test("a blocked Paddle.js shows a friendly message and can be retried", async () => {
  const p = page(GOOD, { paddle: "none", scriptLoads: false });
  const b = p.button("yearly");
  await p.click(b);
  assert.match(p.msg.textContent, /could not open/);
  assert.match(p.msg.textContent, /admin@zemaris\.com/);
  assert.equal(b.textContent, "Buy yearly");
  await p.click(b);
  assert.equal(p.appended.length, 2, "tries again on the next click");
});

test("refuses bad settings without contacting Paddle", async () => {
  for (const cfg of [
    { ...GOOD, token: "" },
    { ...GOOD, token: "pdl_sdbx_apikey_01abcdefghijklmnop" },
    { ...GOOD, token: "live_a1b2c3d4e5f6a7b8c9d0e1f2a3b" },
    { ...GOOD, environment: "staging" },
    { ...GOOD, prices: { ...GOOD.prices, monthly: "pri_short" } },
  ]) {
    const p = page(cfg, { paddle: "none" });
    await p.click(p.button("monthly"));
    assert.equal(p.appended.length, 0);
    assert.equal(p.calls.open.length, 0);
    assert.match(p.msg.textContent, /isn't available/);
  }
});

test("does nothing without a config, or with broken JSON", () => {
  for (const cfg of [null, "{not json"]) {
    const p = page(cfg);
    assert.equal(p.handlers.click, undefined);
    assert.equal(p.win.ZemarisCheckout, undefined);
  }
});
