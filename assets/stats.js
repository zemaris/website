/* Counts page views and clicks on the main buttons of zemaris.com for the owner's private visitor page (admin.html).
   No cookies and no personal data: only the page, the button, and the site you came from (the country and phone or
   computer are worked out by the server). Nothing is sent when the browser asks sites not to track it. */
(function () {
  var END = "https://velocity-activate.velocity-licence-server.workers.dev/hit";
  if (navigator.doNotTrack === "1" || !navigator.sendBeacon || location.hostname.replace(/^www\./, "") !== "zemaris.com") return;
  function send(k, n) {
    try { navigator.sendBeacon(END, JSON.stringify({ k: k, n: n, p: location.pathname, r: document.referrer })); } catch (e) {}
  }
  if (!/^\/admin(\.html)?$/.test(location.pathname)) send("view");
  document.addEventListener("click", function (e) {
    var a = e.target.closest ? e.target.closest("a,button") : null;
    if (!a || /^\/admin(\.html)?$/.test(location.pathname)) return;
    var t = a.getAttribute("data-track");
    if (!t && (a.classList.contains("btn") || /^mailto:/i.test(a.getAttribute("href") || ""))) t = a.textContent || a.getAttribute("title");
    if (t) send("click", t.replace(/\s+/g, " ").trim().slice(0, 60));
  }, true);
})();
