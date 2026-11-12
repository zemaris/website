// assets/site.js: a link to a collapsed answer (<details>) on the same page opens it, every time it is clicked.
// A tiny stand-in page in Node (no browser, no network).
// Run:  node --test _tests/site_links.test.mjs   (portable Node 24 in D:\Zemaris\07-Server-and-Tools\Local-Tools\node)
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const code = readFileSync(new URL("../assets/site.js", import.meta.url), "utf8");

function matches(el, sel) {
  if (!el) return false;
  let m;
  if ((m = /^#([\w-]+)$/.exec(sel))) return el.id === m[1];
  if ((m = /^\[([\w-]+)\]$/.exec(sel))) return el.attrs && m[1] in el.attrs;
  if ((m = /^a\[href\^="(.*)"\]$/.exec(sel))) return el.tagName === "A" && (el.attrs.href || "").startsWith(m[1]);
  if (sel === "a[href]") return el.tagName === "A" && "href" in el.attrs;
  return false;
}

function element(tagName, attrs = {}, parent = null) {
  const el = { tagName, attrs, id: attrs.id || "", parent, open: false,
    getAttribute: n => (n in attrs ? attrs[n] : null) };
  el.closest = sel => { for (let e = el; e; e = e.parent) if (matches(e, sel)) return e; return null; };
  return el;
}

function page(hash = "") {
  const handlers = {}, winHandlers = {};
  const details = element("DETAILS", { id: "warning-help" });
  const link = element("A", { href: "#warning-help" });
  const inLink = element("B", {}, link);                 // a click on text inside the link
  const other = element("A", { href: "/support.html#verify" });
  const ids = { "warning-help": details };
  const location = { hash };
  const doc = {
    documentElement: { getAttribute: () => null, setAttribute() {} },
    addEventListener: (t, f) => { (handlers[t] ||= []).push(f) },
    getElementById: id => ids[id] || null,
    querySelector: () => null, querySelectorAll: () => [],
  };
  const ctx = {
    document: doc, location, localStorage: { getItem: () => null, setItem() {} },
    matchMedia: () => ({ matches: false }), navigator: {}, setTimeout, clearTimeout,
    addEventListener: (t, f) => { (winHandlers[t] ||= []).push(f) },
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(code, ctx);
  // what a browser does: the click handlers run, then the link changes the address; a hashchange only comes when the
  // # is a different one
  const click = target => {
    for (const f of handlers.click || []) f({ target });
    const a = target.closest("a[href]");
    const href = a && a.getAttribute("href");
    if (href && href.startsWith("#") && href !== location.hash) {
      location.hash = href;
      for (const f of winHandlers.hashchange || []) f({});
    }
  };
  return { details, link, inLink, other, click };
}

test("the link opens the collapsed help", () => {
  const p = page();
  p.click(p.link);
  assert.equal(p.details.open, true);
});

test("closed again, the same link opens it again (the address already ends in that #: no hashchange)", () => {
  const p = page();
  p.click(p.link);
  p.details.open = false;
  p.click(p.link);
  assert.equal(p.details.open, true);
  p.details.open = false;
  p.click(p.inLink);
  assert.equal(p.details.open, true, "a click on text inside the link");
});

test("a link to another page does not open anything here", () => {
  const p = page();
  p.click(p.other);
  assert.equal(p.details.open, false);
});
