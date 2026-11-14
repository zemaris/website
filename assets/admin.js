/* The owner's private analytics page (admin.html). Asks the licence server for the numbers with the admin key
   (POST /stats, /stats-live every 20 s, /sale-flag), see ANALYTICS-API.md. Every value from the server is put on the
   page as text (textContent / attributes), never as HTML. Open admin.html?demo to preview with the sample file in
   _tests (only on a local copy of the site: the live site does not publish _tests). */
(function () {
  "use strict";
  var BASE = "https://velocity-activate.velocity-licence-server.workers.dev";
  var DEMO = /(^|[?&])demo\b/.test(location.search);
  var TZ = "Asia/Muscat";
  var $ = function (id) { return document.getElementById(id); };
  // ?still (for screenshots) or the system's reduce-motion setting: no count-up or moving bars
  var REDUCED = /(^|[?&])still\b/.test(location.search) || !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
  if (REDUCED) document.documentElement.classList.add("za-still");
  var state = { key: "", days: 30, data: null, metric: "sessions", maxTs: 0, timer: 0, seen: {}, product: "" };

  // ---------- small helpers ----------
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = String(text);
    return e;
  }
  function clear(e) { while (e.firstChild) e.removeChild(e.firstChild); return e; }
  function num(n) { return (+n || 0).toLocaleString("en-US"); }
  function short(n) {
    n = +n || 0;
    if (n >= 1e6) return (n / 1e6).toFixed(n >= 1e7 ? 0 : 1) + "M";
    if (n >= 1e4) return Math.round(n / 1e3) + "k";
    if (n >= 1e3) return (n / 1e3).toFixed(1) + "k";
    return String(n);
  }
  function money(minor, cur, compact) {
    cur = /^[A-Z]{3}$/.test(cur || "") ? cur : "USD";
    try {
      return new Intl.NumberFormat("en-US", { style: "currency", currency: cur, maximumFractionDigits: compact ? 0 : 2,
        minimumFractionDigits: compact ? 0 : 2 }).format((+minor || 0) / 100);
    } catch (e) { return cur + " " + ((+minor || 0) / 100).toFixed(2); }
  }
  var regionNames = null;
  try { regionNames = new Intl.DisplayNames(["en"], { type: "region" }); } catch (e) {}
  function country(cc) {
    if (!cc || cc === "??" || !/^[A-Z]{2}$/.test(cc)) return "Unknown";
    try { return regionNames ? regionNames.of(cc) : cc; } catch (e) { return cc; }
  }
  function flag(cc) {
    if (!/^[A-Z]{2}$/.test(cc || "")) return "\u{1F310}";
    return String.fromCodePoint(0x1F1E6 + cc.charCodeAt(0) - 65, 0x1F1E6 + cc.charCodeAt(1) - 65);
  }
  var NICE = { phone: "Phone", tablet: "Tablet", computer: "Computer", direct: "Typed in or a bookmark", "zemaris.com": "Inside the site",
    paddle: "Paddle", app: "The app", "??": "Unknown" };
  function nice(n) { return NICE[n] || n || "Unknown"; }
  var fmtTime = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit" });
  var fmtDayTime = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  var fmtDay = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" });
  function omanDay(ts) { var p = fmtDay.formatToParts(new Date(ts)), o = {}; p.forEach(function (x) { o[x.type] = x.value; }); return o.year + "-" + o.month + "-" + o.day; }
  function dayLabel(day) {
    var d = new Date(day + "T00:00:00Z");
    return isNaN(d) ? day : d.getUTCDate() + " " + ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][d.getUTCMonth()];
  }
  function when(ts) { return omanDay(ts) === omanDay(Date.now()) ? fmtTime.format(new Date(ts)) : fmtDayTime.format(new Date(ts)); }
  function say(t, demo) { var m = $("admMsg"); m.textContent = t || ""; m.className = "za-msg" + (demo ? " demo" : ""); }
  function tip(node, text) { node.setAttribute("data-tip", text); return node; }

  function post(path, body) {
    return fetch(BASE + path, { method: "POST", headers: { "content-type": "text/plain" }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().then(function (j) { return { status: r.status, j: j }; }, function () { return { status: r.status, j: {} }; }); });
  }

  // ---------- count-up numbers ----------
  function countUp(node, to, fmt) {
    fmt = fmt || num;
    if (REDUCED || !(to > 0)) { node.textContent = fmt(to); return; }
    var t0 = performance.now(), dur = 900;
    (function step(t) {
      var k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      node.textContent = fmt(k < 1 ? Math.round(to * e) : to);
      if (k < 1) requestAnimationFrame(step);
    })(t0);
    setTimeout(function () { node.textContent = fmt(to); }, dur + 150); // always end on the exact number
  }
  function delta(cur, prev) {
    var d = el("span", "za-d");
    if (prev === undefined || prev === null) { d.textContent = " "; return d; }
    if (!prev) { d.textContent = cur ? "new" : "same"; d.append(el("span", "za-dv", " vs prev. period")); if (cur) d.className += " up"; return d; }
    var p = Math.round((cur - prev) / prev * 100);
    d.textContent = (p > 0 ? "▲ " : p < 0 ? "▼ " : "") + Math.abs(p) + "%";
    d.append(el("span", "za-dv", " vs prev. " + state.days + " days"));
    d.className += p > 0 ? " up" : p < 0 ? " down" : "";
    return d;
  }

  // ---------- KPIs ----------
  function mainRevenue(t) {
    var r = (t && t.revenue) || [];
    return r[0] || null;
  }
  // every currency after the first one, as text such as "€25.00 + £10.00" (empty when there is only one)
  function otherRevenue(t) {
    var r = (t && t.revenue) || [];
    return r.slice(1).filter(function (x) { return +x.net; }).map(function (x) { return money(+x.net, x.currency); }).join(" + ");
  }
  function kpis(s) {
    var box = clear($("zKpis")), t = s.totals || {}, p = s.previous || null, rev = mainRevenue(t), prevRev = p ? mainRevenue(p) : null;
    var cur = rev ? rev.currency : (prevRev ? prevRev.currency : "USD");
    var list = [
      ["Visitors", t.sessions !== undefined ? t.sessions : t.visits, p && (p.sessions !== undefined ? p.sessions : p.visits), "hero", "Different browser tabs that opened the site"],
      ["Page views", t.views, p && p.views, "", "Pages opened by visitors (not you)"],
      ["Arrived from outside", t.visits, p && p.visits, "", "Visits that came from another site or were typed in"],
      ["Downloads", t.downloads, p && p.downloads, "", "Download button clicks"],
      ["Checkouts opened", t.checkouts, p && p.checkouts, "", "Paddle checkout windows opened"],
      ["Purchases", t.purchases, p && p.purchases, "", "Paid orders, test purchases left out"],
      ["Revenue (net)", rev ? rev.net : (s.analytics ? 0 : undefined), prevRev ? prevRev.net : (p ? 0 : null), "hero money", "Paid minus refunds, test purchases left out"],
      ["Activations", t.activations, p && p.activations, "", "Licences activated in the app"]
    ];
    list.forEach(function (k) {
      if (k[1] === undefined) return;
      var c = tip(el("div", "za-kpi " + k[3]), k[4]);
      var b = el("b");
      c.append(el("small", null, k[0]), b);
      var more = k[3].indexOf("money") >= 0 ? otherRevenue(t) : "";
      if (more) {
        c.append(el("span", "za-more", "+ " + more));
        tip(c, k[4] + ". The big number is " + cur + " only; other currencies are shown below it, not converted.");
      }
      c.append(delta(+k[1] || 0, p ? (+k[2] || 0) : null));
      box.append(c);
      countUp(b, +k[1] || 0, k[3].indexOf("money") >= 0 ? function (v) { return money(v, cur); } : num);
    });
  }

  // ---------- bar lists ----------
  function rows(id, list, label, value) {
    var ol = clear($(id)); list = list || [];
    if (!list.length) { ol.append(el("li", "za-empty", "Nothing yet")); return; }
    var total = 0, max = 0;
    list.forEach(function (r) { var v = value ? value(r) : r.n; total += +v || 0; if (v > max) max = v; });
    list.forEach(function (r) {
      var v = +(value ? value(r) : r.n) || 0, li = el("li"), bar = el("i");
      bar.style.width = (max ? Math.max(2, v / max * 100) : 0) + "%";
      var b = el("b", null, num(v)); b.append(el("small", null, (total ? Math.round(v / total * 100) : 0) + "%"));
      li.append(bar, el("span", null, label ? label(r) : r.name), b);
      tip(li, (label ? label(r) : r.name) + ": " + num(v));
      ol.append(li);
    });
  }

  // ---------- daily bars ----------
  function dayKeys(since, days) {
    var out = [], t0 = Date.parse(since + "T00:00:00Z");
    if (isNaN(t0)) return out;
    for (var i = 0; i < days; i++) out.push(new Date(t0 + i * 86400000).toISOString().slice(0, 10));
    return out;
  }
  // The server counts new numbers by Oman day, so for 4 hours after Oman midnight its newest day can be one past
  // since + days - 1 (since was a UTC date on older servers). End the range on the newest day the server sent.
  function rangeKeys(s) {
    var keys = dayKeys(s.since, s.days), last = keys[keys.length - 1] || "";
    (s.daily || []).forEach(function (d) { if (d.day > last) last = d.day; });
    if (!keys.length || last === keys[keys.length - 1]) return keys;
    var t1 = Date.parse(last + "T00:00:00Z");
    return dayKeys(new Date(t1 - (s.days - 1) * 86400000).toISOString().slice(0, 10), s.days);
  }
  function bars(box, daily, keys, metric, fmt, label) {
    clear(box);
    var by = {}; (daily || []).forEach(function (d) { by[d.day] = d; });
    if (!keys.length) keys = (daily || []).map(function (d) { return d.day; });
    var vals = keys.map(function (k) { var d = by[k] || {}; var v = d[metric]; if (v === undefined && metric === "sessions") v = d.visits; return +v || 0; });
    var max = Math.max.apply(null, vals.concat([1]));
    var inner = el("div", "za-bars-in"), axis = el("div", "za-bars-x"), mini = box.classList.contains("za-mini"),
      every = keys.length > 31 || (mini && keys.length > 10) ? 7 : 1;
    keys.forEach(function (k, i) {
      var v = vals[i], col = el("div", "za-bar1" + (v ? "" : " zero")), bar = el("i");
      bar.style.height = Math.max(1, v / max * 100) + "%";
      bar.style.animationDelay = (REDUCED ? 0 : Math.min(i * 18, 600)) + "ms";
      col.append(el("em", null, fmt(v, true)), bar);
      tip(col, dayLabel(k) + "\n" + fmt(v) + " " + label);
      inner.append(col);
      axis.append(el("span", null, (i % every === 0 && !(mini && i > keys.length - 5)) || (!mini && i === keys.length - 1) ? dayLabel(k) : ""));
    });
    box.append(inner, axis);
  }
  function drawDaily() {
    var s = state.data; if (!s) return;
    var m = state.metric, rev = mainRevenue(s.totals), cur = rev ? rev.currency : "USD";
    var labels = { sessions: "visitors", views: "page views", downloads: "downloads",
      revenue: "net revenue in " + cur + (otherRevenue(s.totals) ? " (other currencies not in this chart)" : "") };
    var fmt = m === "revenue" ? function (v, c) { return money(v, cur, c); } : function (v, c) { return c ? short(v) : num(v); };
    bars($("zBars"), s.daily, rangeKeys(s), m, fmt, labels[m]);
  }

  // ---------- funnel + heat ----------
  function funnel(list) {
    var box = clear($("zFunnel")); list = list || [];
    var names = { visits: "Visits", downloads: "Downloads", checkout_open: "Checkout opened", purchase: "Purchases", activate: "Activations" };
    if (!list.length) { box.append(el("p", "za-empty", "Starts after the D1 update.")); return; }
    var top = Math.max(+list[0].n || 0, 1);
    list.forEach(function (st, i) {
      var row = el("div", "za-fstep"), bar = el("div", "bar"), fill = el("i", null, num(st.n));
      fill.style.width = Math.max(4, Math.min(100, (+st.n || 0) / top * 100)) + "%";
      fill.style.animationDelay = (REDUCED ? 0 : i * 120) + "ms";
      bar.append(fill);
      var prev = i ? +list[i - 1].n || 0 : 0;
      row.append(el("span", null, names[st.step] || st.step), bar, el("small", null, i ? (prev ? Math.round(st.n / prev * 100) + "%" : "-") : "100%"));
      tip(row, (names[st.step] || st.step) + ": " + num(st.n) + (i && prev ? " (" + Math.round(st.n / prev * 100) + "% of the step before)" : ""));
      box.append(row);
    });
  }
  function heat(h) {
    var box = clear($("zHeat")), dows = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    if (!h || h.length !== 7) { box.style.display = "block"; box.append(el("p", "za-empty", "Starts after the D1 update.")); return; }
    box.style.display = "";
    var max = 1; h.forEach(function (r) { r.forEach(function (v) { if (v > max) max = v; }); });
    box.append(el("span"));
    for (var x = 0; x < 24; x++) box.append(el("span", null, x % 3 === 0 ? String(x) : ""));
    h.forEach(function (r, d) {
      box.append(el("span", "d", dows[d]));
      for (var hr = 0; hr < 24; hr++) {
        var v = +r[hr] || 0, c = el("div");
        if (v) c.style.background = "rgba(" + (v / max > .6 ? "6,182,212" : "99,82,240") + "," + (0.15 + 0.85 * v / max).toFixed(2) + ")";
        tip(c, dows[d] + " " + (hr < 10 ? "0" : "") + hr + ":00–" + (hr < 9 ? "0" : "") + (hr + 1) + ":00\n" + num(v) + " page views");
        box.append(c);
      }
    });
  }

  // ---------- world map (TopoJSON decoded here, no library) ----------
  var ISO = "AF004AL008DZ012AO024AR032AM051AU036AT040AZ031BS044BH048BD050BY112BE056BZ084BJ204BT064BO068BA070BW072BR076BN096" +
    "BG100BF854BI108KH116CM120CA124CF140TD148CL152CN156CO170CG178CD180CR188CI384HR191CU192CY196CZ203DK208DJ262DO214EC218EG818" +
    "SV222GQ226ER232EE233SZ748ET231FK238FJ242FI246FR250GA266GM270GE268DE276GH288GR300GL304GT320GN324GW624GY328HT332HN340HU348" +
    "IS352IN356ID360IR364IQ368IE372IL376IT380JM388JP392JO400KZ398KE404KP408KR410KW414KG417LA418LV428LB422LS426LR430LY434LT440" +
    "LU442MG450MW454MY458ML466MR478MX484MD498MN496ME499MA504MZ508MM104NA516NP524NL528NC540NZ554NI558NE562NG566MK807NO578OM512" +
    "PK586PS275PA591PG598PY600PE604PH608PL616PT620PR630QA634RO642RU643RW646SA682SN686RS688SL694SK703SI705SB090SO706ZA710SS728" +
    "ES724LK144SD729SR740SE752CH756SY760TW158TJ762TZ834TH764TL626TG768TT780TN788TR792TM795UG800UA804AE784GB826US840UY858UZ860" +
    "VU548VE862VN704EH732YE887ZM894ZW716TF260SG702HK344MT470MU480MV462";
  var toNum = {}, toCC = {};
  for (var i = 0; i < ISO.length; i += 5) { toNum[ISO.substr(i, 2)] = ISO.substr(i + 2, 3); toCC[ISO.substr(i + 2, 3)] = ISO.substr(i, 2); }
  var W = 960, LAT_TOP = 84, LAT_BOT = -58, K = W / 360, H = Math.round((LAT_TOP - LAT_BOT) * K);
  var mapPromise = null, mapShapes = null;
  function loadMap() {
    if (!mapPromise) mapPromise = fetch("/assets/countries-110m.json").then(function (r) { return r.json(); }).then(decodeTopo);
    return mapPromise;
  }
  function decodeTopo(topo) {
    var sc = topo.transform.scale, tr = topo.transform.translate;
    var arcs = topo.arcs.map(function (arc) {
      var x = 0, y = 0;
      return arc.map(function (p) { x += p[0]; y += p[1]; return [(x * sc[0] + tr[0] + 180) * K, (LAT_TOP - (y * sc[1] + tr[1])) * K]; });
    });
    function ring(ids) {
      var pts = [];
      ids.forEach(function (a, j) {
        var seq = a < 0 ? arcs[~a].slice().reverse() : arcs[a];
        for (var k = j ? 1 : 0; k < seq.length; k++) pts.push(seq[k]);
      });
      return pts;
    }
    var shapes = [];
    topo.objects.countries.geometries.forEach(function (g) {
      if (g.id === "010" || !g.arcs) return; // Antarctica left out
      var polys = g.type === "Polygon" ? [g.arcs] : g.arcs, d = "", best = 0, centre = null;
      polys.forEach(function (poly) {
        poly.forEach(function (r, ri) {
          var pts = ring(r);
          if (!pts.length) return;
          d += "M" + pts.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join("L") + "Z";
          if (ri === 0) {
            var x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
            pts.forEach(function (p) { x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); y0 = Math.min(y0, p[1]); y1 = Math.max(y1, p[1]); });
            var area = (x1 - x0) * (y1 - y0);
            if (area > best) { best = area; centre = [(x0 + x1) / 2, (y0 + y1) / 2]; }
          }
        });
      });
      var id = String(g.id || "").padStart(3, "0");
      shapes.push({ id: id, cc: toCC[id] || "", name: (g.properties && g.properties.name) || "", d: d, centre: centre });
    });
    mapShapes = shapes;
    return shapes;
  }
  var STOPS = [[196, 181, 253], [124, 58, 237], [79, 70, 229], [6, 182, 212]];
  function ramp(t) {
    t = Math.max(0, Math.min(1, t)) * (STOPS.length - 1);
    var i = Math.min(STOPS.length - 2, Math.floor(t)), f = t - i, a = STOPS[i], b = STOPS[i + 1];
    return "rgb(" + [0, 1, 2].map(function (k) { return Math.round(a[k] + (b[k] - a[k]) * f); }).join(",") + ")";
  }
  var SVGNS = "http://www.w3.org/2000/svg";
  function drawMap(s) {
    var box = $("zMap");
    loadMap().then(function (shapes) {
      clear(box);
      var by = {}, max = 0;
      (s.countries || []).forEach(function (c) { var v = +(c.visitors || c.n) || 0; by[c.name] = v; if (v > max) max = v; });
      var svg = document.createElementNS(SVGNS, "svg");
      svg.setAttribute("viewBox", "0 0 " + W + " " + H); svg.setAttribute("role", "img"); svg.setAttribute("aria-label", "World map of visitors");
      shapes.forEach(function (sh) {
        var p = document.createElementNS(SVGNS, "path"), v = by[sh.cc] || 0;
        p.setAttribute("d", sh.d); p.setAttribute("fill-rule", "evenodd");
        if (v) { p.setAttribute("class", "has"); p.style.fill = ramp(Math.sqrt(v / max)); }
        p.setAttribute("data-tip", (sh.cc ? country(sh.cc) : sh.name) + "\n" + (v ? num(v) + " visitors" : "no visitors yet"));
        svg.append(p);
      });
      // pulsing dots where the newest visitor events came from
      var done = {}, n = 0;
      (s.live || []).some(function (e) {
        if (e.owner || done[e.country] || !toNum[e.country]) return false;
        done[e.country] = 1;
        var sh = shapes.filter(function (x) { return x.cc === e.country; })[0];
        if (sh && sh.centre) {
          var ping = document.createElementNS(SVGNS, "circle"), dot = document.createElementNS(SVGNS, "circle");
          [ping, dot].forEach(function (c, j) { c.setAttribute("cx", sh.centre[0].toFixed(1)); c.setAttribute("cy", sh.centre[1].toFixed(1)); c.setAttribute("r", j ? "3.5" : "7"); c.setAttribute("class", j ? "dot" : "ping"); });
          ping.style.animationDelay = (n * 0.4) + "s";
          svg.append(ping, dot); n++;
        }
        return n >= 6;
      });
      box.append(svg);
      var lg = el("div", "za-legend"); lg.append(el("span", null, "fewer"), el("i"), el("span", null, "more visitors"), el("span", null, " · green dot = latest activity"));
      box.append(lg);
    }).catch(function () { clear(box).append(el("p", "za-empty", "The map file could not be loaded.")); });
  }

  // ---------- live feed ----------
  var KIND = { view: ["V", "Viewed "], click: ["C", "Clicked "], download: ["D", "Downloaded "], checkout_open: ["$", "Opened checkout: "],
    purchase: ["✓", "Bought "], refund: ["R", "Refund: "], chargeback: ["!", "Chargeback: "], activate: ["A", "Activated "], release: ["↩", "Released a licence: "] };
  function feedItem(e, fresh) {
    var k = KIND[e.kind] || ["•", e.kind + " "], li = el("li", (fresh ? "new" : "") + (e.owner ? " mine" : ""));
    var body = el("div"), txt = k[1] + (e.kind === "click" ? "“" + e.name + "”" : e.name || "");
    if (e.amount) txt += " · " + money(e.amount, e.currency);
    var place = [e.city, country(e.country)].filter(Boolean).join(", ");
    var meta = [e.owner ? "You" : place, nice(e.device), e.browser && e.browser !== "Other" ? e.browser : "", e.source && e.source !== "direct" ? "from " + nice(e.source) : ""]
      .filter(Boolean).join(" · ");
    body.append(el("div", "t", (e.owner ? "" : flag(e.country) + " ") + txt), el("div", "m", meta));
    li.append(el("span", "za-ic k-" + String(e.kind).replace(/[^a-z_]/g, ""), k[0]), body, el("time", null, when(e.ts)));
    return li;
  }
  function feed(list, fresh) {
    var ol = $("zFeed");
    if (!fresh) clear(ol);
    var items = (list || []).filter(function (e) { var id = e.ts + ":" + e.kind + ":" + e.tab + ":" + e.name; if (state.seen[id]) return false; state.seen[id] = 1; return true; });
    items.forEach(function (e) { if (e.ts > state.maxTs) state.maxTs = e.ts; });
    if (fresh) items.slice().reverse().forEach(function (e) { ol.insertBefore(feedItem(e, true), ol.firstChild); });
    else items.forEach(function (e) { ol.append(feedItem(e, false)); });
    while (ol.children.length > 100) ol.removeChild(ol.lastChild);
    if (!ol.children.length) ol.append(el("li", "za-empty", "No events yet. New ones slide in here."));
    else { var e0 = ol.querySelector(".za-empty"); if (e0) e0.remove(); }
  }
  function today(t) {
    var box = clear($("zToday"));
    [["Visitors today", t.sessions], ["Views today", t.views], ["Clicks today", t.clicks]].forEach(function (x) {
      var d = el("div"), b = el("b"); d.append(b, el("small", null, x[0])); box.append(d); countUp(b, +x[1] || 0);
    });
  }
  function poll() {
    clearTimeout(state.timer);
    if (DEMO || !state.key || !state.data || !state.data.analytics) return;
    state.timer = setTimeout(function () {
      if (document.hidden) { poll(); return; }
      post("/stats-live", { token: state.key, since_ts: state.maxTs }).then(function (x) {
        if (x.j && x.j.ok) {
          live(true);
          if (x.j.events && x.j.events.length) feed(x.j.events, true);
          if (x.j.today) today(x.j.today);
        } else live(false);
      }).catch(function () { live(false); }).then(poll);
    }, 20000);
  }
  function live(on, text) {
    $("zLiveDot").className = "za-pulse" + (on ? " on" : "");
    $("zLiveText").textContent = text || (on ? "Live" : "Not connected");
  }

  // ---------- purchases ----------
  // Both apps use the same plan names (Yearly, Lifetime...), so every sale shows which app it was for. The server sends
  // product "pdf" for Velocity PDF; old rows and Download Manager rows say "dm" or nothing.
  var PRODUCTS = { dm: "Download Manager", pdf: "Velocity PDF" };
  function productOf(s) { return s && String(s.product || "").toLowerCase() === "pdf" ? "pdf" : "dm"; }
  function saleLabel(s) { return PRODUCTS[productOf(s)] + " · " + (s.plan || "?") + (s.pcs > 1 ? " ×" + s.pcs : ""); }
  function salesFor(list, product) { return (list || []).filter(function (s) { return !product || productOf(s) === product; }); }
  var SALES_CSV_HEAD = ["time_utc", "txn", "serial", "product", "plan", "pcs", "amount_minor", "currency", "country", "email", "name", "status", "refunded_minor", "test"];
  function csvSaleRow(x) {
    return [new Date(x.ts).toISOString(), x.txn, x.serial, productOf(x), x.plan, x.pcs, x.amount, x.currency, x.country, x.email, x.name, x.status, x.refunded, x.test ? 1 : 0];
  }
  function sales(all) {
    var tb = clear($("tSales").tBodies[0]), list = salesFor(all, state.product);
    if (!list.length) {
      var r = tb.insertRow(), c = r.insertCell(); c.colSpan = 7; c.className = "za-empty";
      c.textContent = state.product ? "No " + PRODUCTS[state.product] + " purchases in this period." : "No purchases in this period."; return;
    }
    list.forEach(function (s) {
      var tr = tb.insertRow(); if (s.test) tr.className = "test";
      tr.insertCell().textContent = when(s.ts);
      var b = tr.insertCell(); b.append(document.createTextNode(s.name || "(no name)"), el("small", null, s.email || "(no email)"));
      var p = tr.insertCell(); p.append(document.createTextNode(saleLabel(s)), el("small", null, "Key " + s.serial));
      var a = tr.insertCell(); a.className = "num"; a.append(document.createTextNode(money(s.amount, s.currency)));
      if (s.refunded) a.append(el("small", null, "refunded " + money(s.refunded, s.currency)));
      tr.insertCell().textContent = flag(s.country) + " " + country(s.country);
      var st = tr.insertCell(), labels = { paid: "Paid", partly_refunded: "Part refunded", refunded: "Refunded", chargeback: "Chargeback" };
      st.append(el("span", "za-chip " + (labels[s.status] ? s.status : "paid"), labels[s.status] || s.status));
      if (s.test) st.append(el("span", "za-chip test", "Test"));
      var tc = tr.insertCell(), lab = el("label", "za-switch"), box = el("input");
      box.type = "checkbox"; box.checked = !!s.test; lab.title = "Mark as a test purchase (never counted as revenue)";
      lab.append(box, el("span", "za-knob"));
      box.addEventListener("change", function () { flagSale(s, box.checked, box); });
      tc.append(lab);
    });
  }
  function recountDemo(s) {
    var by = {}, count = 0;
    (s.sales || []).forEach(function (x) {
      if (x.test) return;
      count++;
      var r = by[x.currency] || (by[x.currency] = { currency: x.currency, gross: 0, refunded: 0, net: 0, count: 0 });
      r.gross += x.amount; r.refunded += x.refunded || 0; r.net = r.gross - r.refunded; r.count++;
    });
    s.totals.revenue = Object.keys(by).map(function (k) { return by[k]; });
    s.totals.purchases = count;
  }
  function flagSale(s, test, box) {
    if (DEMO) { s.test = test ? 1 : 0; recountDemo(state.data); render(state.data, true); return; }
    box.disabled = true;
    post("/sale-flag", { token: state.key, txn: s.txn, test: test }).then(function (x) {
      if (x.j && x.j.ok) { say(test ? "Marked as a test purchase." : "Marked as a real sale."); load(); }
      else { box.checked = !test; box.disabled = false; say((x.j && x.j.reason) || "The server did not change it."); }
    }).catch(function () { box.checked = !test; box.disabled = false; say("Could not reach the server."); });
  }

  // ---------- owner ----------
  function owner(o) {
    o = o || {};
    countUp($("oViews"), +o.views || 0); countUp($("oClicks"), +o.clicks || 0);
    var s = state.data;
    bars($("oDaily"), (o.daily || []), rangeKeys(s), "views", function (v, c) { return c ? short(v) : num(v); }, "of your page views");
    rows("oPages", o.pages);
  }

  // ---------- CSV ----------
  function csvCell(v) {
    v = v === undefined || v === null ? "" : String(v);
    if (/^[=+\-@\t\r]/.test(v)) v = "'" + v;
    return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
  }
  function exportCsv() {
    var s = state.data; if (!s) { say("Load the numbers first."); return; }
    var out = [["day", "visitors", "visits", "views", "clicks", "downloads", "checkouts", "purchases", "revenue_net_minor", "own_views"]];
    var by = {}; (s.daily || []).forEach(function (d) { by[d.day] = d; });
    rangeKeys(s).forEach(function (k) {
      var d = by[k] || {};
      out.push([k, d.sessions, d.visits, d.views, d.clicks, d.downloads, d.checkouts, d.purchases, d.revenue, d.owner_views]);
    });
    out.push([]);
    out.push(SALES_CSV_HEAD);
    (s.sales || []).forEach(function (x) { out.push(csvSaleRow(x)); });
    var text = out.map(function (r) { return r.map(csvCell).join(","); }).join("\r\n");
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + text], { type: "text/csv" }));
    a.download = "zemaris-analytics-" + omanDay(Date.now()) + (DEMO ? "-demo" : "") + ".csv";
    document.body.append(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }

  // ---------- reviews (unchanged behaviour) ----------
  function reviews(key, action, id) {
    var box = $("admReviews"), names = { velocity: "Velocity Download Manager", "velocity-pdf": "Velocity PDF" };
    if (DEMO) { box.textContent = "Reviews load from the server (not shown in the demo)."; return; }
    post("/reviews-admin", { token: key, action: action || "list", id: id }).then(function (x) {
      var d = x.j || {};
      clear(box);
      if (!d.ok) { box.textContent = d.reason || "Reviews could not be loaded."; return; }
      if (!d.reviews.length) { box.textContent = "No reviews yet."; return; }
      d.reviews.forEach(function (r) {
        var c = el("div", "adm-rv " + r.status);
        var h = el("b", null, (r.status === "pending" ? "Waiting · " : r.status === "approved" ? "Shown · " : "Hidden · ") +
          (names[r.product] || r.product) + " · " + "★★★★★".slice(0, r.stars) + " · " + r.name + (r.country ? " (" + r.country + ")" : "") +
          (r.verified ? " · Verified buyer" : "") + " · " + String(r.created).slice(0, 10));
        var act = el("div", "adm-rv-act");
        [["approve", "Approve", "Show this review on the product page"], ["hide", "Hide", "Keep it but do not show it"], ["delete", "Delete", "Delete this review for good"]]
          .forEach(function (a) {
            if ((a[0] === "approve" && r.status === "approved") || (a[0] === "hide" && r.status === "hidden")) return;
            var b = el("button", "btn small" + (a[0] === "approve" ? " primary" : ""), a[1]); b.type = "button"; b.title = a[2];
            b.addEventListener("click", function () { if (a[0] !== "delete" || confirm("Delete this review for good?")) reviews(key, a[0], r.id); });
            act.append(b);
          });
        c.append(h, el("p", null, r.text), act); box.append(c);
      });
    }).catch(function () { box.textContent = "Could not reach the server."; });
  }

  // ---------- render everything ----------
  function render(s, keepFeed) {
    state.data = s;
    $("zPre").hidden = s.analytics !== false;
    $("zSince").textContent = "From " + dayLabel(rangeKeys(s)[0] || s.since) + " · last " + s.days + " day" + (s.days === 1 ? "" : "s") + " · days and hours in Oman time" +
      (DEMO ? " · DEMO: sample numbers from _tests/analytics-sample.json, not real visitors" : "");
    kpis(s);
    drawMap(s);
    rows("tCountries", s.countries, function (r) { return flag(r.name) + " " + country(r.name); }, function (r) { return r.visitors || r.n; });
    rows("tCities", s.cities, function (r) { return r.name + ", " + country(r.country); });
    drawDaily();
    funnel(s.funnel);
    heat(s.hourly);
    rows("tPages", s.pages); rows("tClicks", s.clicks); rows("tSources", s.sources, function (r) { return nice(r.name); });
    rows("tDevices", s.devices, function (r) { return nice(r.name); }); rows("tBrowsers", s.browsers); rows("tOs", s.os);
    sales(s.sales);
    owner(s.owner);
    if (!keepFeed) {
      state.seen = {}; state.maxTs = 0; feed(s.live, false);
      var last = (s.daily || [])[(s.daily || []).length - 1] || {};
      today(last.day === omanDay(Date.now()) ? { sessions: last.sessions !== undefined ? last.sessions : last.visits, views: last.views, clicks: last.clicks } : {});
    }
    $("admOut").hidden = false;
  }
  function load() {
    var days = state.days;
    if (DEMO) {
      say("Loading the demo…", true);
      fetch("/_tests/analytics-sample.json").then(function (r) { if (!r.ok) throw 0; return r.json(); }).then(function (s) {
        s.days = s.days || days;
        render(s);
        live(true, "Demo (sample data)");
        say("Demo mode: these are sample numbers to preview the page, not real visitors.", true);
      }).catch(function () { say("The demo file (_tests/analytics-sample.json) is only on a local copy of the site."); });
      return;
    }
    if (!state.key) { say("Enter your admin key."); return; }
    say("Loading…");
    post("/stats", { token: state.key, days: days }).then(function (x) {
      if (x.status === 403) { say("That key is not right."); $("admOut").hidden = true; live(false); return; }
      if (!x.j || !x.j.ok) { say((x.j && x.j.reason) || "The server could not give the numbers."); return; }
      try { sessionStorage.setItem("admKey", state.key); } catch (e) {}
      render(x.j);
      say("Updated " + fmtTime.format(new Date()) + " Oman time.");
      live(!!x.j.analytics, x.j.analytics ? "Live" : "Basic counts only");
      reviews(state.key);
      poll();
    }).catch(function () { say("Could not reach the server. Check the internet connection."); live(false); });
  }

  // the pure purchase helpers, for _tests/admin.test.mjs (no DOM, no network)
  window.ZemarisAdmin = { productOf: productOf, saleLabel: saleLabel, salesFor: salesFor, SALES_CSV_HEAD: SALES_CSV_HEAD, csvSaleRow: csvSaleRow };

  // ---------- wiring ----------
  function clock() { $("zClock").textContent = fmtTime.format(new Date()) + " Oman time"; }
  document.addEventListener("DOMContentLoaded", function () {
    clock(); setInterval(clock, 15000);
    var mine = $("zMine");
    try { mine.checked = localStorage.getItem("zemaris_owner") === "1"; } catch (e) {}
    mine.addEventListener("change", function () {
      try { if (mine.checked) localStorage.setItem("zemaris_owner", "1"); else localStorage.removeItem("zemaris_owner"); } catch (e) {}
      say(mine.checked ? "This device is marked as yours: its visits are counted apart as your own visits." : "This device now counts as a normal visitor.");
    });
    document.querySelectorAll(".za-bar [data-days]").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll(".za-bar [data-days]").forEach(function (x) { x.classList.toggle("on", x === b); });
        state.days = +b.getAttribute("data-days");
        if (DEMO || state.key) load();
      });
    });
    document.querySelectorAll("#zMetric [data-m]").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll("#zMetric [data-m]").forEach(function (x) { x.classList.toggle("on", x === b); });
        state.metric = b.getAttribute("data-m"); drawDaily();
      });
    });
    document.querySelectorAll("#zProduct [data-p]").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll("#zProduct [data-p]").forEach(function (x) { x.classList.toggle("on", x === b); });
        state.product = b.getAttribute("data-p"); if (state.data) sales(state.data.sales);
      });
    });
    $("adm").addEventListener("submit", function (e) { e.preventDefault(); state.key = $("admKey").value.trim(); load(); });
    $("zCsv").addEventListener("click", exportCsv);
    $("admForget").addEventListener("click", function () {
      try { sessionStorage.removeItem("admKey"); } catch (e) {}
      state.key = ""; state.data = null; clearTimeout(state.timer);
      $("admKey").value = ""; $("admOut").hidden = true; live(false); say("Key forgotten.");
    });
    // one tooltip for every [data-tip]
    var tipBox = $("zTip");
    document.addEventListener("mousemove", function (e) {
      var t = e.target.closest ? e.target.closest(".za [data-tip]") : null;
      if (!t) { tipBox.hidden = true; return; }
      tipBox.textContent = t.getAttribute("data-tip"); tipBox.hidden = false;
      tipBox.style.left = Math.min(window.innerWidth - 90, Math.max(90, e.clientX)) + "px"; tipBox.style.top = e.clientY + "px";
    });
    if (DEMO) { load(); return; }
    try { state.key = sessionStorage.getItem("admKey") || ""; } catch (e) {}
    if (state.key) { $("admKey").value = state.key; load(); } else say("Enter your admin key to see the numbers.");
  });
})();
