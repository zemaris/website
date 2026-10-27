/* Reviews on a product page: <div class="reviews" data-product="velocity"></div>. Shows approved reviews and a form.
   New reviews wait until the owner checks them (admin.html). A Velocity licence key is optional and only checked, never kept. */
(function () {
  var API = "https://velocity-activate.velocity-licence-server.workers.dev";
  function post(path, body) {
    return fetch(API + path, { method: "POST", headers: { "content-type": "text/plain" }, body: JSON.stringify(body) }).then(function (r) { return r.json(); });
  }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function stars(n) { return "★★★★★".slice(0, n) + "☆☆☆☆☆".slice(0, 5 - n); }
  function render(box, product) {
    var list = el("div", "rv-list"), head = el("p", "rv-head", "Loading reviews…");
    box.textContent = ""; box.append(head, list, form(box, product));
    post("/reviews", { product: product }).then(function (d) {
      if (!d.ok || !d.count) { head.textContent = "No reviews yet. Used it? Be the first to write one."; return; }
      head.textContent = stars(Math.round(d.average)) + "  " + d.average + " out of 5 · " + d.count + " review" + (d.count > 1 ? "s" : "");
      d.reviews.forEach(function (r) {
        var c = el("div", "rv-card");
        c.append(el("div", "rv-stars", stars(r.stars)), el("p", "rv-text", r.text));
        var who = el("div", "rv-who", r.name + (r.country ? " · " + r.country : "") + " · " + r.created);
        if (r.verified) who.append(el("span", "rv-badge", "Verified buyer"));
        c.append(who); list.append(c);
      });
    }).catch(function () { head.textContent = "Reviews could not be loaded right now."; });
  }
  function form(box, product) {
    var f = el("form", "rv-form"), chosen = 0;
    f.append(el("h3", "", "Write a review"));
    var row = el("div", "rv-pick");
    for (var i = 1; i <= 5; i++) (function (n) {
      var b = el("button", "rv-star", "☆"); b.type = "button"; b.title = n + " star" + (n > 1 ? "s" : ""); b.setAttribute("aria-label", b.title);
      b.addEventListener("click", function () { chosen = n; row.querySelectorAll("button").forEach(function (x, k) { x.textContent = k < n ? "★" : "☆"; }); });
      row.append(b);
    })(i);
    var name = el("input"); name.placeholder = "Your name (optional)"; name.maxLength = 40; name.title = "Shown with your review";
    var text = el("textarea"); text.placeholder = "What did you like, and what could be better? (at least 20 characters)"; text.maxLength = 1000; text.rows = 4; text.title = "Your review";
    var key = el("input"); key.placeholder = "Licence key (optional, for the Verified buyer badge; it is checked, not kept)"; key.title = "Optional: your Velocity licence key";
    var hp = el("input"); hp.name = "website"; hp.tabIndex = -1; hp.autocomplete = "off"; hp.className = "rv-hp"; hp.setAttribute("aria-hidden", "true");
    var used = el("label", "rv-used"), cb = el("input"); cb.type = "checkbox"; cb.title = "Only people who used it can review"; used.append(cb, document.createTextNode(" I have used this product"));
    var send = el("button", "btn primary", "Send review"); send.type = "submit"; send.title = "Send your review; it appears after we check it";
    var msg = el("p", "rv-msg"); msg.setAttribute("role", "status");
    f.append(row, name, text);
    if (product === "velocity") f.append(key);
    f.append(hp, used, send, msg);
    f.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!chosen) { msg.textContent = "Choose 1 to 5 stars."; return; }
      send.disabled = true; msg.textContent = "Sending…";
      post("/review", { product: product, stars: chosen, name: name.value, text: text.value, used: cb.checked, key: key.value.trim() || undefined, hp: hp.value })
        .then(function (d) {
          msg.textContent = d.ok ? (d.message || "Thank you!") : d.reason;
          if (d.ok) { f.reset(); chosen = 0; row.querySelectorAll("button").forEach(function (x) { x.textContent = "☆"; }); }
        })
        .catch(function () { msg.textContent = "Could not send. Check the internet connection and try again."; })
        .then(function () { send.disabled = false; });
    });
    return f;
  }
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".reviews[data-product]").forEach(function (b) { render(b, b.getAttribute("data-product")); });
  });
})();
