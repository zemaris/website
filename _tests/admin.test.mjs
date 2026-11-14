// assets/admin.js: every purchase shows which app it was for (both apps use the same plan names), the
// All / Download Manager / Velocity PDF filter, and the product column of the CSV export.
// A tiny stand-in page in Node (no browser, no network).
// Run:  node --test _tests/admin.test.mjs   (portable Node 24 in D:\Zemaris\07-Server-and-Tools\Local-Tools\node)
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const code = readFileSync(new URL("../assets/admin.js", import.meta.url), "utf8");

function load() {
  const window = {};
  const ctx = {
    window, location: { search: "" },
    document: { documentElement: { classList: { add() {} } }, addEventListener() {}, getElementById: () => null },
  };
  vm.createContext(ctx);
  vm.runInContext(code, ctx);
  return window.ZemarisAdmin;
}

const pdf = { ts: Date.UTC(2026, 10, 15, 8), txn: "txn_t_pdf", serial: "PDF00001", product: "pdf", plan: "Lifetime", pcs: 1,
  amount: 4900, currency: "USD", country: "OM", email: "a@example.com", name: "A", status: "paid", refunded: 0, test: 0 };
const dm = { ts: Date.UTC(2026, 10, 14, 8), txn: "txn_t_dm", serial: "DM000001", product: "dm", plan: "Lifetime", pcs: 3,
  amount: 1999, currency: "USD", country: "AE", email: "b@example.com", name: "B", status: "paid", refunded: 0, test: 0 };
const old = { ...dm, txn: "txn_t_old", serial: "OLD00001", product: undefined, plan: "Pro", pcs: 1 };

test("a Velocity PDF sale shows its product next to the plan", () => {
  const a = load();
  assert.equal(a.saleLabel(pdf), "Velocity PDF · Lifetime");
  assert.equal(a.saleLabel(dm), "Download Manager · Lifetime ×3");
  assert.equal(a.saleLabel(old), "Download Manager · Pro");          // rows from before the product column
  assert.equal(a.saleLabel({ ...pdf, product: "PDF" }), "Velocity PDF · Lifetime");
});

test("the filter keeps only the chosen app", () => {
  const a = load(), all = [pdf, dm, old];
  assert.deepEqual(a.salesFor(all, "").map(s => s.txn), ["txn_t_pdf", "txn_t_dm", "txn_t_old"]);
  assert.deepEqual(a.salesFor(all, "pdf").map(s => s.txn), ["txn_t_pdf"]);
  assert.deepEqual(a.salesFor(all, "dm").map(s => s.txn), ["txn_t_dm", "txn_t_old"]);
  assert.equal(a.salesFor(undefined, "pdf").length, 0);
});

test("the CSV export has a product column", () => {
  const a = load(), head = [...a.SALES_CSV_HEAD], i = head.indexOf("product");
  assert.ok(i > 0, head.join(","));
  assert.equal(a.csvSaleRow(pdf)[i], "pdf");
  assert.equal(a.csvSaleRow(dm)[i], "dm");
  assert.equal(a.csvSaleRow(old)[i], "dm");
  assert.equal(a.csvSaleRow(pdf).length, head.length);
  assert.equal(a.csvSaleRow(pdf)[head.indexOf("plan")], "Lifetime");
  assert.equal(a.csvSaleRow(pdf)[head.indexOf("amount_minor")], 4900);
});

test("the admin page has the All / Download Manager / Velocity PDF filter above the purchases", () => {
  const page = readFileSync(new URL("../admin.html", import.meta.url), "utf8");
  const m = /<div class="za-seg small" role="group" aria-label="Which app" id="zProduct">(.*?)<\/div>/s.exec(page);
  assert.ok(m, "no product filter on admin.html");
  assert.deepEqual([...m[1].matchAll(/data-p="(\w*)"/g)].map(x => x[1]), ["", "dm", "pdf"]);
  assert.ok(page.indexOf('id="zProduct"') < page.indexOf('id="tSales"'));
});
