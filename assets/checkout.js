/* zemaris.com checkout: opens Paddle's secure checkout over the pricing page.
   The page only includes this file when checkout is switched on in _launch.json (see LAUNCH-PREP.md).
   Paddle's own script is fetched only when someone points at or clicks a Buy button. */
(function () {
  "use strict";
  var el = document.getElementById("checkout-config");
  if (!el) return;
  var cfg;
  try { cfg = JSON.parse(el.textContent) } catch (e) { return }
  var PRICE = /^pri_[a-z0-9]{26}$/;
  var TOKEN = cfg.environment === "sandbox" ? /^test_[A-Za-z0-9]{10,}$/ : /^live_[A-Za-z0-9]{10,}$/;
  var ok = (cfg.environment === "sandbox" || cfg.environment === "production") && TOKEN.test(cfg.token || "");
  var loading = null;

  function say(text) {
    var m = document.getElementById("checkoutMsg");
    if (m) m.textContent = text || "";
  }

  function dark() {
    var t = document.documentElement.getAttribute("data-theme");
    if (t) return t === "dark";
    return !!(window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches);
  }

  // Loads and starts Paddle.js once. Resolves with the Paddle object.
  function paddle() {
    if (loading) return loading;
    loading = new Promise(function (resolve, reject) {
      function start() {
        try {
          if (cfg.environment === "sandbox") window.Paddle.Environment.set("sandbox");
          window.Paddle.Initialize({ token: cfg.token });
          resolve(window.Paddle);
        } catch (e) { reject(e) }
      }
      if (window.Paddle && window.Paddle.Checkout) return start();
      var s = document.createElement("script");
      s.src = cfg.paddleJs;
      s.async = true;
      s.onload = function () { window.Paddle && window.Paddle.Checkout ? start() : reject(new Error("no Paddle")) };
      s.onerror = function () { reject(new Error("load failed")) };
      document.head.appendChild(s);
    });
    loading.catch(function () { loading = null });
    return loading;
  }

  function buy(btn) {
    var plan = btn.getAttribute("data-checkout"), price = (cfg.prices || {})[plan];
    if (!ok || !PRICE.test(price || "")) {
      say("Checkout isn't available right now. Please email " + cfg.support + " and we'll help you buy.");
      return;
    }
    var label = btn.textContent;
    btn.setAttribute("aria-busy", "true");
    btn.textContent = "Opening checkout…";
    say("");
    paddle().then(function (P) {
      P.Checkout.open({
        items: [{ priceId: price, quantity: 1 }],
        settings: { displayMode: "overlay", theme: dark() ? "dark" : "light", locale: "en", successUrl: cfg.successUrl }
      });
    }).catch(function () {
      say("The secure checkout could not open. Check your internet connection and try again, or email " + cfg.support + ".");
    }).then(function () {
      btn.textContent = label;
      btn.removeAttribute("aria-busy");
    });
  }

  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-checkout]");
    if (b) { e.preventDefault(); buy(b) }
  });
  // warm up: fetch Paddle.js when someone is about to click, so the window opens quickly
  ["pointerover", "focusin"].forEach(function (type) {
    document.addEventListener(type, function (e) {
      if (ok && e.target.closest && e.target.closest("[data-checkout]")) paddle().catch(function () {});
    });
  });
  window.ZemarisCheckout = { buy: buy, ready: function () { return ok } };
})();
