/* The owner's private visitor page (admin.html): asks the licence server for the counts with the admin key. */
(function () {
  var END = "https://velocity-activate.velocity-licence-server.workers.dev/stats";
  var $ = function (id) { return document.getElementById(id); };
  function rows(id, list, label) {
    var t = $(id); t.textContent = "";
    if (!list.length) { t.insertRow().insertCell().textContent = "None yet"; return; }
    list.forEach(function (r) {
      var tr = t.insertRow();
      tr.insertCell().textContent = label ? label(r.name) : r.name;
      var c = tr.insertCell(); c.textContent = r.n; c.className = "num";
    });
  }
  function chart(daily, days) {
    var box = $("admChart"), byDay = {}, list = [], max = 1;
    daily.forEach(function (d) { byDay[d.day] = d.visits; });
    for (var i = days - 1; i >= 0; i--) {
      var day = new Date(Date.now() - i * 86400000).toISOString().slice(0, 10), v = byDay[day] || 0;
      list.push({ day: day, v: v }); if (v > max) max = v;
    }
    var w = 100 / list.length, svg = '<svg viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label="Visits per day">';
    list.forEach(function (d, i) {
      var h = d.v / max * 36;
      svg += '<rect x="' + (i * w + w * 0.12) + '" y="' + (38 - h) + '" width="' + (w * 0.76) + '" height="' + Math.max(h, 0.4) +
        '"><title>' + d.day + ": " + d.v + " visits</title></rect>";
    });
    box.innerHTML = svg + "</svg><div class=\"adm-axis\"><span>" + list[0].day + "</span><span>most: " + max + "</span><span>" + list[list.length - 1].day + "</span></div>";
  }
  // reviews waiting for approval first; buttons approve, hide or delete one
  function reviews(key, action, id) {
    var box = $("admReviews"), names = { velocity: "Velocity", "velocity-pdf": "Velocity PDF" };
    fetch(END.replace(/\/stats$/, "/reviews-admin"), { method: "POST", headers: { "content-type": "text/plain" },
      body: JSON.stringify({ token: key, action: action || "list", id: id }) })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        box.textContent = "";
        if (!d.ok) { box.textContent = d.reason || "Reviews could not be loaded."; return; }
        if (!d.reviews.length) { box.textContent = "No reviews yet."; return; }
        d.reviews.forEach(function (r) {
          var c = document.createElement("div"); c.className = "adm-rv " + r.status;
          var h = document.createElement("b");
          h.textContent = (r.status === "pending" ? "Waiting · " : r.status === "approved" ? "Shown · " : "Hidden · ") +
            (names[r.product] || r.product) + " · " + "★★★★★".slice(0, r.stars) + " · " + r.name + (r.country ? " (" + r.country + ")" : "") +
            (r.verified ? " · Verified buyer" : "") + " · " + String(r.created).slice(0, 10);
          var t = document.createElement("p"); t.textContent = r.text;
          var act = document.createElement("div"); act.className = "adm-rv-act";
          [["approve", "Approve", "Show this review on the product page"], ["hide", "Hide", "Keep it but do not show it"], ["delete", "Delete", "Delete this review for good"]]
            .forEach(function (a) {
              if ((a[0] === "approve" && r.status === "approved") || (a[0] === "hide" && r.status === "hidden")) return;
              var b = document.createElement("button"); b.className = "btn small" + (a[0] === "approve" ? " primary" : ""); b.type = "button";
              b.textContent = a[1]; b.title = a[2];
              b.addEventListener("click", function () { if (a[0] !== "delete" || confirm("Delete this review for good?")) reviews(key, a[0], r.id); });
              act.append(b);
            });
          c.append(h, t, act); box.append(c);
        });
      })
      .catch(function () { box.textContent = "Could not reach the server."; });
  }
  function show(key, days) {
    $("admMsg").textContent = "Loading…";
    fetch(END, { method: "POST", headers: { "content-type": "text/plain" }, body: JSON.stringify({ token: key, days: days }) })
      .then(function (r) { return r.json().then(function (j) { return { status: r.status, j: j }; }); })
      .then(function (x) {
        if (x.status === 403) { $("admMsg").textContent = "That key is not right."; $("admOut").hidden = true; return; }
        if (!x.j.ok) { $("admMsg").textContent = x.j.reason || "The server could not give the numbers."; return; }
        try { sessionStorage.setItem("admKey", key); } catch (e) {}
        var s = x.j;
        $("kVisits").textContent = s.totals.visits; $("kViews").textContent = s.totals.views; $("kClicks").textContent = s.totals.clicks;
        chart(s.daily, s.days);
        var names = { phone: "Phone", tablet: "Tablet", computer: "Computer", direct: "Typed in or a bookmark", "??": "Unknown" };
        var nice = function (n) { return names[n] || n; };
        rows("tPages", s.pages); rows("tClicks", s.clicks); rows("tCountries", s.countries, nice);
        rows("tSources", s.sources, nice); rows("tDevices", s.devices, nice);
        $("admMsg").textContent = "Since " + s.since + " (dates in UTC).";
        $("admOut").hidden = false;
        reviews(key);
      })
      .catch(function () { $("admMsg").textContent = "Could not reach the server. Check the internet connection."; });
  }
  document.addEventListener("DOMContentLoaded", function () {
    var saved = null;
    try { saved = sessionStorage.getItem("admKey"); } catch (e) {}
    $("adm").addEventListener("submit", function (e) { e.preventDefault(); show($("admKey").value.trim(), +$("admDays").value); });
    $("admForget").addEventListener("click", function () {
      try { sessionStorage.removeItem("admKey"); } catch (e) {}
      $("admKey").value = ""; $("admOut").hidden = true; $("admMsg").textContent = "Key forgotten.";
    });
    if (saved) { $("admKey").value = saved; show(saved, +$("admDays").value); }
  });
})();
