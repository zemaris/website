/* zemaris.com - theme, menu, reveal, live demos */
(function () {
  var root = document.documentElement;
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  // theme: saved choice wins, otherwise follow the system
  function saved() { try { return localStorage.getItem("theme") } catch (e) { return null } }
  var t = saved(); if (t) root.setAttribute("data-theme", t);
  document.addEventListener("click", function (e) {
    var b = e.target.closest("#themeBtn");
    if (b) {
      var dark = root.getAttribute("data-theme") ? root.getAttribute("data-theme") === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
      var next = dark ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next) } catch (err) {}
    }
    var m = e.target.closest("#menuBtn");
    if (m) { var n = document.querySelector("nav.links"); n.classList.toggle("open"); m.setAttribute("aria-expanded", n.classList.contains("open")) }
  });

  document.addEventListener("DOMContentLoaded", function () {
    // reveal on scroll
    var els = document.querySelectorAll(".rv");
    if ("IntersectionObserver" in window && !reduce) {
      var io = new IntersectionObserver(function (es) { es.forEach(function (x) { if (x.isIntersecting) { x.target.classList.add("in"); io.unobserve(x.target) } }) }, { threshold: .12 });
      els.forEach(function (el) { io.observe(el) });
    } else els.forEach(function (el) { el.classList.add("in") });

    // count-up stats
    document.querySelectorAll("[data-count]").forEach(function (el) {
      var end = +el.dataset.count, suf = el.dataset.suffix || "";
      if (reduce || !("IntersectionObserver" in window)) { el.textContent = end + suf; return }
      var o = new IntersectionObserver(function (es) {
        if (!es[0].isIntersecting) return; o.disconnect();
        var t0 = performance.now();
        (function step(now) { var p = Math.min(1, (now - t0) / 1200); el.textContent = Math.round(end * (1 - Math.pow(1 - p, 3))) + suf; if (p < 1) requestAnimationFrame(step) })(t0);
      }); o.observe(el);
    });

    appDemo(); raceDemo(); netBg();
  });

  // live app window in the hero
  function appDemo() {
    var rows = document.querySelectorAll(".app .r[data-size]");
    if (!rows.length) return;
    var total = document.getElementById("demoTotal"), cv = document.getElementById("demoGraph");
    var hist = [], ctx = cv && cv.getContext("2d");
    var state = Array.prototype.map.call(rows, function (r) { return { el: r, size: +r.dataset.size, done: +r.dataset.done, rate: +r.dataset.rate } });
    function fmt(b) { return b >= 1024 ? (b / 1024).toFixed(2) + " GB" : Math.round(b) + " MB" }
    function tick() {
      var sum = 0;
      state.forEach(function (s) {
        var bar = s.el.querySelector(".bar i"), sp = s.el.querySelector(".sp"), mt = s.el.querySelector(".mt b");
        if (s.done >= s.size) { s.el.classList.add("done"); bar.style.width = "100%"; sp.textContent = "Done"; if (mt) mt.textContent = "Completed"; return }
        var r = s.rate * (0.82 + Math.random() * 0.36);
        s.done = Math.min(s.size, s.done + r); sum += r;
        bar.style.width = (100 * s.done / s.size).toFixed(1) + "%";
        sp.textContent = r.toFixed(1) + " MB/s";
        if (mt) mt.textContent = fmt(s.done) + " of " + fmt(s.size);
      });
      if (state.every(function (s) { return s.done >= s.size })) state.forEach(function (s) { s.done = s.size * 0.08; s.el.classList.remove("done") });
      if (total) total.textContent = sum.toFixed(1) + " MB/s";
      if (ctx) {
        hist.push(sum); if (hist.length > 40) hist.shift();
        var w = cv.width = cv.clientWidth * 2, h = cv.height = cv.clientHeight * 2, mx = Math.max.apply(null, hist) * 1.15 || 1;
        ctx.clearRect(0, 0, w, h); ctx.beginPath();
        hist.forEach(function (v, i) { var x = i * w / 39, y = h - v / mx * h; i ? ctx.lineTo(x, y) : ctx.moveTo(x, y) });
        ctx.lineWidth = 3; ctx.strokeStyle = "#5b8cff"; ctx.stroke();
        ctx.lineTo((hist.length - 1) * w / 39, h); ctx.lineTo(0, h); ctx.fillStyle = "rgba(91,140,255,.18)"; ctx.fill();
      }
    }
    tick(); if (!reduce) setInterval(tick, 1000);
  }

  // one connection vs many, on a server that caps each connection
  function raceDemo() {
    var box = document.getElementById("race");
    if (!box) return;
    var lanes = [{ el: box.querySelector(".track.one"), n: 1, label: box.querySelector("#t1") },
                 { el: box.querySelector(".track.many"), n: 16, label: box.querySelector("#t16") }];
    lanes.forEach(function (l) { l.el.innerHTML = ""; for (var i = 0; i < l.n; i++) l.el.insertAdjacentHTML("beforeend", '<div class="seg"><i></i></div>') });
    var started = false;
    function run() {
      if (started) return; started = true;
      var t0 = performance.now(), D1 = 16000, D16 = 1300;
      (function step(now) {
        var e = now - t0;
        lanes.forEach(function (l) {
          var D = l.n === 1 ? D1 : D16, segs = l.el.querySelectorAll(".seg i");
          segs.forEach(function (s, i) { var jitter = l.n === 1 ? 1 : (0.85 + ((i * 37) % 10) / 33); s.style.width = Math.min(100, 100 * e / (D * jitter)) + "%" });
          var p = Math.min(1, e / (l.n === 1 ? D1 : D16 * 1.3));
          l.label.textContent = p >= 1 ? "Done" : Math.round(p * 100) + "%";
        });
        if (e < D1) requestAnimationFrame(step); else setTimeout(function () { started = false; run() }, 2500);
      })(t0);
    }
    if (reduce) { box.querySelectorAll(".seg i").forEach(function (s) { s.style.width = "100%" }); return }
    new IntersectionObserver(function (es) { if (es[0].isIntersecting) run() }, { threshold: .4 }).observe(box);
  }

  // drifting network lines behind the hero
  function netBg() {
    var cv = document.querySelector(".hero canvas.net");
    if (!cv || reduce) return;
    var ctx = cv.getContext("2d"), pts = [], W, H;
    function size() { W = cv.width = cv.clientWidth; H = cv.height = cv.clientHeight }
    size(); addEventListener("resize", size);
    for (var i = 0; i < 70; i++) pts.push({ x: Math.random() * W, y: Math.random() * H, vx: (Math.random() - .5) * .3, vy: (Math.random() - .5) * .3 });
    (function frame() {
      ctx.clearRect(0, 0, W, H);
      pts.forEach(function (p) { p.x += p.vx; p.y += p.vy; if (p.x < 0 || p.x > W) p.vx *= -1; if (p.y < 0 || p.y > H) p.vy *= -1 });
      for (var a = 0; a < pts.length; a++) {
        ctx.fillStyle = "rgba(150,175,255,.7)"; ctx.fillRect(pts[a].x - 1, pts[a].y - 1, 2, 2);
        for (var b = a + 1; b < pts.length; b++) {
          var dx = pts[a].x - pts[b].x, dy = pts[a].y - pts[b].y, d = dx * dx + dy * dy;
          if (d < 14000) { ctx.strokeStyle = "rgba(120,150,255," + (0.22 * (1 - d / 14000)) + ")"; ctx.beginPath(); ctx.moveTo(pts[a].x, pts[a].y); ctx.lineTo(pts[b].x, pts[b].y); ctx.stroke() }
        }
      }
      requestAnimationFrame(frame);
    })();
  }
})();
