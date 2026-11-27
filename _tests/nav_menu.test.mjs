// assets/site.js: the Products menu in the top bar opens with its button, closes with the button again, with a click
// anywhere else and with Escape, and keeps aria-expanded right. A tiny stand-in page in Node (no browser, no network).
// Run:  node --test _tests/nav_menu.test.mjs   (portable Node 24 in D:\Zemaris\07-Server-and-Tools\Local-Tools\node)
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const code = readFileSync(new URL("../assets/site.js", import.meta.url), "utf8");

function element(tagName, attrs = {}, parent = null) {
  const classes = new Set();
  const el = {
    tagName, attrs, id: attrs.id || "", parent, parentNode: parent, focused: false,
    getAttribute: n => (n in attrs ? attrs[n] : null),
    setAttribute: (n, v) => { attrs[n] = String(v) },
    focus() { el.focused = true },
    classList: { toggle: (c, on) => { (on ?? !classes.has(c)) ? classes.add(c) : classes.delete(c); return classes.has(c) },
                 contains: c => classes.has(c) },
  };
  el.closest = sel => {
    const id = /^#([\w-]+)$/.exec(sel), cls = /^\.([\w-]+)$/.exec(sel);
    for (let e = el; e; e = e.parent) if ((id && e.id === id[1]) || (cls && (e.attrs.class || "").split(" ").includes(cls[1]))) return e;
    return null;
  };
  el.contains = other => { for (let e = other; e; e = e.parent) if (e === el) return true; return false; };
  return el;
}

function page() {
  const handlers = {};
  const dd = element("DIV", { class: "dd" });
  const btn = element("BUTTON", { id: "prodBtn", "aria-expanded": "false" }, dd);
  const menu = element("DIV", { id: "prodMenu" }, dd);
  const item = element("A", { href: "/zemaris-scan.html" }, menu);
  const item2 = element("A", { href: "/zemaris-camera.html" }, menu);
  const outside = element("P");
  const ids = { prodBtn: btn, prodMenu: menu };
  const doc = {
    documentElement: { getAttribute: () => null, setAttribute() {} },
    addEventListener: (t, f) => { (handlers[t] ||= []).push(f) },
    getElementById: id => ids[id] || null,
    querySelector: () => null, querySelectorAll: () => [],
  };
  const ctx = { document: doc, location: { hash: "" }, localStorage: { getItem: () => null, setItem() {} },
    matchMedia: () => ({ matches: false }), navigator: {}, setTimeout, clearTimeout, addEventListener() {} };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(code, ctx);
  const fire = (type, ev) => { for (const f of handlers[type] || []) f(ev) };
  const open = () => btn.getAttribute("aria-expanded") === "true" && dd.classList.contains("open");
  return { btn, item, item2, outside, open, click: target => fire("click", { target }), key: key => fire("keydown", { key }),
    blur: (target, relatedTarget) => fire("focusout", { target, relatedTarget }) };
}

test("the button opens and closes the menu", () => {
  const p = page();
  p.click(p.btn);
  assert.equal(p.open(), true);
  p.click(p.btn);
  assert.equal(p.open(), false);
  assert.equal(p.btn.getAttribute("aria-expanded"), "false");
});

test("a click inside the menu keeps it open; a click elsewhere closes it", () => {
  const p = page();
  p.click(p.btn);
  p.click(p.item);
  assert.equal(p.open(), true);
  p.click(p.outside);
  assert.equal(p.open(), false);
});

test("Escape closes it and puts the keyboard back on the button", () => {
  const p = page();
  p.click(p.btn);
  p.key("Escape");
  assert.equal(p.open(), false);
  assert.equal(p.btn.focused, true);
  p.btn.focused = false;
  p.key("Escape");                       // already closed: nothing moves
  assert.equal(p.btn.focused, false);
});

test("Tab out of the menu closes it; moving inside it or to nowhere keeps it open", () => {
  const p = page();
  p.click(p.btn);
  p.blur(p.btn, p.item);                 // button -> first app: still inside
  p.blur(p.item, p.item2);               // app -> app: still inside
  assert.equal(p.open(), true);
  p.blur(p.item2, null);                 // a press on a blank part of the menu: focus goes nowhere
  assert.equal(p.open(), true);
  p.blur(p.item2, p.outside);            // Tab past the last item, to the next link on the page
  assert.equal(p.open(), false);
  assert.equal(p.btn.getAttribute("aria-expanded"), "false");
});