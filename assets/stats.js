/* Counts page views, button clicks, downloads and checkout openings on zemaris.com for the owner's private page
   (admin.html). No cookies and no personal data: only the page, the button, the site you came from and a random tab
   id that lives in this tab only (sessionStorage) and is gone when the tab closes. The country, city, phone or
   computer and browser are worked out by the server from the request; no IP address is kept.
   On the owner's own devices ("This device is mine" on admin.html) every hit carries o:1 so it is counted apart.
   Nothing is sent when the browser asks sites not to track it. */
(function () {
  var END = "https://velocity-activate.velocity-licence-server.workers.dev/hit";
  var ADMIN = /^\/admin(\.html)?$/;
  var on = navigator.doNotTrack !== "1" && !!navigator.sendBeacon && location.hostname.replace(/^www\./, "") === "zemaris.com";
  function tab() {
    try {
      var t = sessionStorage.getItem("zt");
      if (!t || !/^[a-z0-9]{10}$/.test(t)) {
        var abc = "abcdefghijklmnopqrstuvwxyz0123456789", a = new Uint8Array(10);
        (window.crypto || window.msCrypto).getRandomValues(a);
        t = ""; for (var i = 0; i < 10; i++) t += abc[a[i] % 36];
        sessionStorage.setItem("zt", t);
      }
      return t;
    } catch (e) { return ""; }
  }
  function mine() { try { return localStorage.getItem("zemaris_owner") === "1"; } catch (e) { return false; } }
  function clean(s) { return String(s || "").replace(/\s+/g, " ").trim().slice(0, 60); }
  // k = view | click | download | checkout_open
  function send(k, n) {
    if (!on || ADMIN.test(location.pathname)) return;
    var b = { k: k, n: clean(n), p: location.pathname, r: document.referrer, t: tab() };
    if (mine()) b.o = 1;
    try { navigator.sendBeacon(END, JSON.stringify(b)); } catch (e) {}
  }
  window.ZemarisStats = { send: send };
  send("view");
  document.addEventListener("click", function (e) {
    var a = e.target.closest ? e.target.closest("a,button") : null;
    if (!a || a.hasAttribute("data-checkout")) return; // checkout.js sends checkout_open for Buy buttons
    // downloads: links marked data-track-download, or links straight to an installer / package file
    var d = a.getAttribute("data-track-download"), href = a.getAttribute("href") || "";
    if (d === null && /\.(exe|msi|msix|msixbundle|zip|dmg|pkg|deb|rpm|appimage)([?#]|$)/i.test(href)) d = href.split(/[?#]/)[0].split("/").pop();
    if (d !== null) { send("download", d || a.getAttribute("data-track") || a.textContent); return; }
    var t = a.getAttribute("data-track");
    if (!t && (a.classList.contains("btn") || /^mailto:/i.test(a.getAttribute("href") || ""))) t = a.textContent || a.getAttribute("title");
    if (t) send("click", t);
  }, true);
})();
