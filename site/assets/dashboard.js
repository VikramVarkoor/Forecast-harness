/* Dashboard. Data: data/dashboard.json plus one data/zones/<id>.json per zone, loaded on demand. */
(function () {
  "use strict";
  var H = window.H, el = H.el, rich = H.rich;
  var D = null, zoneCache = {}, ui = { tab: "Forecast", zone: null, day: null, band: true, zc1: null, zc2: null, dayb: null, storm: 0, play: null };
  var BASE_TABS = ["Forecast", "Compare zones", "Scoreboard", "Where it fails", "Storm days", "Method", "About"], TABS = BASE_TABS;
  var geoCache = null, nudged = false;
  var HINTS = {
    "Forecast": "Pick a zone, then click any tick in the strip to open that day. Replay steps through the held-out weeks.",
    "Compare zones": "Pick two or three zones to see the same day side by side.",
    "Scoreboard": "Scroll for the daily results, the hour-by-weekday heatmap and the zone table. Every column header in the table sorts.",
    "Where it fails": "The days and hours where the forecast missed by the most.",
    "Storm days": "Pick a day from the list to see how the forecast coped with it.",
    "Map": "Scroll to zoom, drag to pan, click a zone to open its forecast."
  };
  var f0 = function (v) { return Math.round(v).toLocaleString("en-US"); };
  var MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  function dparts(iso) { var p = iso.slice(0, 10).split("-"); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function dshort(iso) { var d = dparts(iso); return DOW[d.getDay()] + " " + String(d.getDate()).padStart(2, "0") + " " + MON[d.getMonth()]; }

  /* A readable failure with a way out, instead of an empty chart. */
  function fail(what, retry, where) {
    var host = where || panel || document.getElementById("main"), b = el("div", "errbox"); b.setAttribute("role", "alert");
    b.appendChild(el("p", null, "Could not load " + what + ". Check your connection, then try again."));
    var r = el("button", "btn small", "Try again"); r.type = "button"; r.addEventListener("click", retry); b.appendChild(r);
    host.replaceChildren(b);
  }
  function loadZone(id) {
    if (!zoneCache[id]) zoneCache[id] = fetch("data/zones/" + id + ".json").then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .catch(function () { delete zoneCache[id]; fail("the data for zone " + id, function () { renderTab(); }); return new Promise(function () {}); });
    return zoneCache[id];
  }
  /* rows of one zone on one forecast day */
  function dayRows(z, iso) {
    var out = [];
    for (var i = 0; i < z.origin.length; i++) if (z.origin[i] === iso) out.push({ ts: z.ts[i], y: z.y[i], lgbm: z.lgbm[i], base: z.base[i], q10: z.q10[i], q90: z.q90[i], held: z.held[i] });
    return out;
  }
  function mae(rows, k) { var s = 0; rows.forEach(function (r) { s += Math.abs(r[k] - r.y); }); return rows.length ? s / rows.length : null; }
  function dayMae(z, iso) { var m = z.mae && z.mae[iso]; return m ? { m: m[0], b: m[1] } : null; }
  function tsOf(z, iso) { return dayRows(z, iso).map(function (x) { return +new Date(x.ts); }); }
  function zoneName(id) { var z = D.zones.filter(function (x) { return x.id === id; })[0]; return z ? z.name : "Zone " + id; }
  function zoneDays(z) { var s = {}; z.origin.forEach(function (o) { s[o] = 1; }); return Object.keys(s).sort(); }

  /* ---- small UI parts ---- */
  function select(label, opts, value, onChange) {
    var w = el("label", "field"); w.appendChild(el("span", null, label));
    var s = el("select"); opts.forEach(function (o) { var x = el("option", null, o.label); x.value = o.value; if (String(o.value) === String(value)) x.selected = true; s.appendChild(x); });
    s.addEventListener("change", function () { onChange(s.value); }); w.appendChild(s); return w;
  }
  function slider(days, value, onInput) {
    var w = el("div", "scrub"), r = el("input"); r.type = "range"; r.min = 0; r.max = days.length - 1; r.value = Math.max(0, days.indexOf(value));
    r.setAttribute("aria-label", "Day"); var out = el("output", null, dshort(days[+r.value]));
    r.addEventListener("input", function () { out.textContent = dshort(days[+r.value]); H.setProgress(+r.value / Math.max(1, days.length - 1)); onInput(days[+r.value]); });
    w.appendChild(r); w.appendChild(out); w.input = r; w.out = out; return w;
  }
  function metric(big, lab, sub) { var c = H.card(big, lab, sub || ""); c.classList.add("mini"); if (!sub) c.querySelector(".sub").remove(); return c; }
  function download(name, mime, text) {
    var a = el("a", "btn small ghost", name.label); a.href = "data/" + name.file; a.download = name.file; return a;
  }
  /* One toolbar row above a chart: the hover hint on the left, that chart's actions on the right. */
  function chartbar(tip, actions) {
    var b = el("div", "chartbar"); b.appendChild(tip); if (actions) b.appendChild(actions); return b;
  }
  function note(t) { return el("p", "caption", t); }
  function sec(parent, t) { parent.appendChild(el("h2", null, t)); }
  function kids(node) { return Array.prototype.slice.call(node.children); }

  function heldDayCount() { return D.days.filter(function (d) { return D.held_start && d >= D.held_start; }).length; }

  /* ---- forecast chart with band, optional synced hover ---- */
  function forecastSpec(rows, opts) {
    var t = H.theme(), N = { a: "What happened", m: "Model forecast", r: "Simple rule" };
    var wide = rows.map(function (r) {
      return { ts: r.ts, a: r.y, m: r.lgbm, r: r.base, lo: r.q10, hi: r.q90,
        t_a: f0(r.y) + " ride requests", t_m: f0(r.lgbm) + ", off by " + f0(Math.abs(r.lgbm - r.y)), t_r: f0(r.base) + ", off by " + f0(Math.abs(r.base - r.y)),
        t_range: r.q10 == null ? "" : f0(r.q10) + " to " + f0(r.q90) };
    });
    var long = []; wide.forEach(function (w) { long.push({ ts: w.ts, s: N.a, v: w.a }, { ts: w.ts, s: N.m, v: w.m }, { ts: w.ts, s: N.r, v: w.r }); });
    var tip = [{ field: "ts", type: "temporal", title: "Hour", format: "%H:%M" }, { field: "t_a", title: N.a }, { field: "t_m", title: N.m }, { field: "t_r", title: N.r }];
    if (opts.band) tip.push({ field: "t_range", title: "Model expected" });
    var X = { field: "ts", type: "temporal", title: "hour of the day", axis: { format: "%H:%M", tickCount: 8, grid: false } };
    var layers = [];
    if (rows.length > 1 && rows.length <= 26) {
      var P2 = function (n) { return String(n).padStart(2, "0"); };
      var shade = rows.map(function (r) {
        var d0 = new Date(r.ts), h = d0.getHours(), d1 = new Date(d0.getTime() + 3600000), day = Math.max(0, Math.sin(Math.PI * (h + 0.5 - 6) / 12));
        return { a: r.ts, b: d1.getFullYear() + "-" + P2(d1.getMonth() + 1) + "-" + P2(d1.getDate()) + "T" + P2(d1.getHours()) + ":00:00",
          c: day > 0.02 ? "#FFC72C" : "#3B4CC0", o: day > 0.02 ? 0.08 * day : (H.state.dark ? 0.2 : 0.09) };
      });
      layers.push({ data: { values: shade }, mark: { type: "rect", tooltip: false, interactive: false }, encoding: { x: { field: "a", type: "temporal" }, x2: { field: "b" },
        fill: { field: "c", type: "nominal", scale: null }, fillOpacity: { field: "o", type: "quantitative", scale: null } } });
    }
    if (opts.band) layers.push({ data: { values: wide }, mark: { type: "area", opacity: t.band, color: "#FFC72C" },
      encoding: { x: { field: "ts", type: "temporal" }, y: { field: "lo", type: "quantitative" }, y2: { field: "hi" } } });
    layers.push({ data: { values: long }, mark: { type: "line", strokeWidth: 2.2 }, encoding: { x: X,
      y: { field: "v", type: "quantitative", title: "ride requests per hour" },
      color: { field: "s", type: "nominal", scale: { domain: [N.a, N.m, N.r], range: [t.actual, t.model, t.base] }, legend: { orient: "bottom", title: null } },
      strokeDash: { field: "s", type: "nominal", legend: null, scale: { domain: [N.a, N.m, N.r], range: [[1, 0], [1, 0], [5, 4]] } } } });
    layers.push({ data: { values: wide }, params: [{ name: "pick", select: { type: "point", nearest: true, on: "pointerover", fields: ["ts"], clear: "pointerout" } }],
      mark: { type: "rule", color: t.text }, encoding: { x: { field: "ts", type: "temporal" },
        opacity: { condition: { param: "pick", empty: false, value: 0.9 }, value: 0 }, tooltip: tip } });
    if (opts.ghosts && opts.ghosts.length) {
      var at = {}; wide.forEach(function (w) { at[new Date(w.ts).getHours()] = w.ts; });
      var gh = []; opts.ghosts.forEach(function (rs, k) { var o = [0.1, 0.2, 0.34][Math.max(0, 2 - k)];
        rs.forEach(function (r) { var tsn = at[new Date(r.ts).getHours()]; if (tsn && r.lgbm != null) gh.push({ ts: tsn, v: r.lgbm, g: k, o: o }); }); });
      layers.splice(layers.length - 1, 0, { data: { values: gh }, mark: { type: "line", strokeWidth: 1.6, interactive: false, color: t.model },
        encoding: { x: { field: "ts", type: "temporal", title: "hour of the day" }, y: { field: "v", type: "quantitative", title: "ride requests per hour" }, detail: { field: "g", type: "nominal" }, opacity: { field: "o", type: "quantitative", scale: null } } });
    }
    if (opts.sync) layers.push({ data: { values: wide, format: { parse: { ts: "date" } } }, transform: [{ filter: "sync != null && time(datum.ts) === sync" }],
      mark: { type: "rule", color: t.text, opacity: 0.55, strokeDash: [4, 3] }, encoding: { x: { field: "ts", type: "temporal" } } });
    var spec = { height: opts.height || 320, layer: layers };
    if (opts.sync) spec.params = [{ name: "sync", value: null }];
    return spec;
  }
  /* Two charts that follow each other's hover: send the hovered time to the other chart's `sync` signal. */
  function linkCharts(a, b, ta, tb) {
    function wire(from, to, ts) {
      var v = from.view;
      v.addEventListener("pointermove", function (e) {
        var r = v.container().getBoundingClientRect(), o = v.origin(), x = e.clientX - r.left - o[0], t;
        try { t = +v.scale("x").invert(x); } catch (err) { return; }
        var best = null; ts.forEach(function (m) { if (best == null || Math.abs(m - t) < Math.abs(best - t)) best = m; });
        to.view.signal("sync", best).run();
      });
      v.addEventListener("pointerout", function () { to.view.signal("sync", null).run(); });
    }
    wire(a, b, ta); wire(b, a, tb);
  }
  /* A small cab rides the model line: it drives across when the day changes, then follows the mouse. Decoration only, no numbers. */
  function rideCab(host, view, rows, ms) {
    var old = host.querySelector(".rider"); if (old) old.remove();
    var svgEl = host.querySelector("svg"); if (!svgEl) return;
    var cab = el("div", "rider"); cab.innerHTML = H.taxi(); host.appendChild(cab);
    var pts = rows.filter(function (r) { return r.lgbm != null; }).map(function (r) { return { t: +new Date(r.ts), v: r.lgbm }; });
    if (pts.length < 2) { cab.remove(); return; }
    var sx = view.scale("x"), sy = view.scale("y");
    function valueAt(t) { for (var i = 1; i < pts.length; i++) if (t <= pts[i].t) { var a = pts[i - 1], b = pts[i], f = (t - a.t) / (b.t - a.t || 1); return a.v + (b.v - a.v) * f; } return pts[pts.length - 1].v; }
    function place(t) {
      t = Math.max(pts[0].t, Math.min(pts[pts.length - 1].t, t));
      var o = view.origin(), s = svgEl.getBoundingClientRect(), h = host.getBoundingClientRect(), dt = 3600000 / 2;
      var x = sx(t), y = sy(valueAt(t)), x2 = sx(t + dt), y2 = sy(valueAt(t + dt)), ang = Math.atan2(y2 - y, x2 - x) * 180 / Math.PI;
      cab.style.transform = "translate(" + (s.left - h.left + o[0] + x - 23) + "px," + (s.top - h.top + o[1] + y - 17) + "px) rotate(" + Math.max(-35, Math.min(35, ang)) + "deg)";
      cab.style.opacity = 1;
    }
    var raf = null, still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    function drive() {
      if (still) return; var t0 = performance.now(), D = ms || 3200;
      (function step(now) { var k = Math.min(1, (now - t0) / D); place(pts[0].t + (pts[pts.length - 1].t - pts[0].t) * k); if (k < 1) raf = requestAnimationFrame(step); })(t0);
    }
    host.addEventListener("pointermove", function (e) {
      if (raf) { cancelAnimationFrame(raf); raf = null; }
      var s = svgEl.getBoundingClientRect(), o = view.origin(); place(+sx.invert(e.clientX - s.left - o[0]));
    });
    cab.style.opacity = 0; drive();
  }
  /* Title of the nearest heading above a chart, so a saved picture says what it shows. */
  function chartTitle(host) {
    var n = host;
    while (n && n !== panel) { var p = n.previousElementSibling; while (p) { if (/^H[1-4]$/.test(p.tagName)) return p.textContent; p = p.previousElementSibling; } n = n.parentElement; }
    return ui.tab;
  }
  /* A chart picture with a title and a footer on the page background, not a bare plot. */
  function savePng(host, filename) {
    var r = host._r; if (!r) return;
    var t = H.theme(), title = chartTitle(host);
    return Promise.all([r.view.toImageURL("png", 2), document.fonts.load("700 30px Figtree").catch(function () {})]).then(function (x) {
      return new Promise(function (res) {
        var img = new Image(); img.onload = function () {
          var k = 2, pad = 28 * k, head = 64 * k, foot = 44 * k, cv = el("canvas"); cv.width = img.width + pad * 2; cv.height = img.height + head + foot; var g = cv.getContext("2d");
          g.fillStyle = t.bg; g.fillRect(0, 0, cv.width, cv.height);
          g.fillStyle = t.text; g.font = "800 " + 26 * k + "px Figtree"; g.textBaseline = "alphabetic"; g.fillText(title, pad, pad + 20 * k, cv.width - pad * 2);
          g.drawImage(img, pad, head);
          g.fillStyle = t.muted; g.font = "600 " + 15 * k + "px Figtree";
          g.fillText("NYC ride-hail day-ahead forecast. Made by Vikram" + (/^(localhost|127\.|\[::1\])/.test(location.hostname) ? "" : "  |  " + location.host), pad, cv.height - 16 * k);
          cv.toBlob(function (b) { var a = el("a"); a.href = URL.createObjectURL(b); a.download = filename + ".png"; a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000); res(); }, "image/png");
        }; img.src = x[0];
      });
    });
  }
  function shareButtons(host, getView, filename) {
    var w = el("div", "actions"); host.dataset.hasSave = "1";
    var png = el("button", "btn small", "Save chart as image"); png.type = "button";
    png.addEventListener("click", function () { getView().then(function (r) { host._r = host._r || r; return savePng(host, filename); }); });
    w.appendChild(png); w.appendChild(copyLinkBtn()); return w;
  }
  /* Every other chart gets a save button under it too. */
  var embed0 = H.embed;
  H.embed = function (host, spec) {
    return embed0(host, spec).then(function (r) {
      if (!host._r) host._r = r;
      if (!host.dataset.hasSave && host.parentNode) {
        host.dataset.hasSave = "1";
        var b = el("button", "btn small ghost", "Save chart as image"); b.type = "button";
        b.addEventListener("click", function () { savePng(host, "chart-" + ui.tab.toLowerCase().replace(/\W+/g, "-")); });
        var row = el("div", "actions chartsave"); row.appendChild(b); host.parentNode.insertBefore(row, host.nextSibling);
      }
      return r;
    });
  };
  /* The shared link opens just this chart (focus=1) with a button to the full dashboard. */
  function chartLink() { var p = new URLSearchParams(location.search); p.set("view", "Dashboard"); p.set("focus", "1"); return location.origin + location.pathname + "?" + p.toString(); }
  function copyLinkBtn() {
    var cp = el("button", "btn small ghost", "Copy link to this chart"); cp.type = "button";
    cp.addEventListener("click", function () {
      var done = function () { cp.textContent = "Link copied"; setTimeout(function () { cp.textContent = "Copy link to this chart"; }, 1600); };
      try { navigator.clipboard.writeText(chartLink()).then(done, done); } catch (e) { done(); }
    });
    return cp;
  }
  function copyLink() { var w = el("div", "actions"); w.appendChild(copyLinkBtn()); return w; }
  function syncUrl() {
    var p = new URLSearchParams(location.search); p.set("view", "Dashboard"); p.set("tab", ui.tab);
    if (ui.tab === "Forecast" && ui.zone) { p.set("zone", ui.zone); if (ui.day) p.set("day", ui.day); }
    history.replaceState(null, "", "?" + p.toString());
  }

  /* ---- Forecast tab: the time machine ---- */
  function tabForecast(box) {
    var zid = ui.zone, ftitle = el("h2", "focus-title"), host = el("div", "chart"), take = el("p", "takeaway center"), tbl = el("div"), metrics = el("div", "cards minis"), strip = el("div", "daystrip"), tools = el("div", "tools"), pending = null;
    host.appendChild(el("div", "skel"));
    loadZone(zid).then(function (z) {
      var days = zoneDays(z);
      if (days.indexOf(ui.day) < 0) ui.day = days[days.length - 1];
      var heldFrom = D.held_start;
      var sl = slider(days, ui.day, function (d) { ui.day = d; draw(); });
      H.setProgress(Math.max(0, days.indexOf(ui.day)) / Math.max(1, days.length - 1));
      var play = el("button", "btn small", "Play"); play.type = "button"; play.setAttribute("aria-pressed", "false");
      var speed = el("label", "field inline"); speed.appendChild(el("span", null, "Speed")); var ss = el("select"); [["Slow", 2000], ["Normal", 1000], ["Fast", 500]].forEach(function (o) { var x = el("option", null, o[0]); x.value = o[1]; if (+o[1] === (ui.speed || 1000)) x.selected = true; ss.appendChild(x); }); ss.addEventListener("change", function () { ui.speed = +ss.value; if (ui.play && ui.tickFn) { clearInterval(ui.play); ui.play = setInterval(ui.tickFn, period()); } }); speed.appendChild(ss);
      function period() { return ui.speed || 1000; }
      var trail = [], trailNote = el("span", "trail-note", "Faint lines: the model on earlier days"); trailNote.hidden = true;
      function stop() { if (ui.play) { clearInterval(ui.play); ui.play = null; } play.textContent = "Play"; play.setAttribute("aria-pressed", "false"); if (trail.length) { trail = []; trailNote.hidden = true; draw(); } }
      function step(n) { if (n > 0) { trail.push(dayRows(z, ui.day)); if (trail.length > 3) trail.shift(); trailNote.hidden = false; } var i = Math.min(days.length - 1, Math.max(0, days.indexOf(ui.day) + n)); ui.day = days[i]; H.setProgress(i / Math.max(1, days.length - 1)); sl.input.value = i; sl.out.textContent = dshort(ui.day); draw(); return i; }
      play.addEventListener("click", function () {
        if (ui.play) return stop();
        if (days.indexOf(ui.day) === days.length - 1) { ui.day = days[0]; sl.input.value = 0; }
        play.textContent = "Pause"; play.setAttribute("aria-pressed", "true");
        ui.tickFn = function () { if (step(1) >= days.length - 1) stop(); }; ui.play = setInterval(ui.tickFn, period());
      });
      sl.input.addEventListener("keydown", function (e) { if (e.key === "ArrowLeft" || e.key === "ArrowRight") stop(); });
      var band = el("label", "check"), cb = el("input"); cb.type = "checkbox"; cb.checked = ui.band;
      cb.addEventListener("change", function () { ui.band = cb.checked; draw(); }); band.appendChild(cb); band.appendChild(document.createTextNode(" Show 10-90% interval"));
      var rep = el("button", "btn small ghost", "Replay the held-out weeks"); rep.type = "button";
      var tally = el("p", "tally"); tally.hidden = true;
      rep.addEventListener("click", function () {
        stop(); var hd = days.filter(function (d) { return heldFrom && d >= heldFrom; }); if (hd.length < 2) return;
        var k = 0, w = 0, sm = 0, sb = 0, i0 = days.indexOf(hd[0]);
        ui.day = hd[0]; sl.input.value = i0; sl.out.textContent = dshort(ui.day); H.setProgress(i0 / Math.max(1, days.length - 1)); draw();
        function tick() { var a = dayMae(z, ui.day); if (!a || a.m == null) return; k++; if (a.m < a.b) w++; sm += a.m; sb += a.b;
          tally.textContent = "Held-out day " + k + " of " + hd.length + " in this zone: the model won " + w + ", average miss " + (sm / k).toFixed(1) + " against the simple rule's " + (sb / k).toFixed(1) + "."; }
        tally.hidden = false; tick(); play.textContent = "Pause"; play.setAttribute("aria-pressed", "true");
        ui.tickFn = function () { if (k >= hd.length) { stop(); return; } step(1); tick(); }; ui.play = setInterval(ui.tickFn, period());
      });
      tools.replaceChildren(sl, play, rep, speed, band, trailNote, tally);
      /* one tick per day, colored by who won that day in this zone; click to jump */
      strip.replaceChildren();
      days.forEach(function (d, i) {
        var a = dayMae(z, d), m = a.m, b = a.b;
        var t = el("button", "tick " + (m < b ? "win" : "loss") + (heldFrom && d >= heldFrom ? " held" : "")); t.type = "button"; t.dataset.day = d; t.style.setProperty("--i", String(Math.round(i * 40 / days.length)));
        t.title = dshort(d) + ": " + (m < b ? "model won" : "simple rule won"); t.setAttribute("aria-label", t.title);
        t.addEventListener("click", function () { stop(); ui.day = d; H.setProgress(i / Math.max(1, days.length - 1)); sl.input.value = i; sl.out.textContent = dshort(d); draw(); });
        strip.appendChild(t);
      });
      draw();
      function draw() {
        syncUrl();
        var rows = dayRows(z, ui.day);
        strip.querySelectorAll(".tick").forEach(function (t) { t.classList.toggle("on", t.dataset.day === ui.day); });
        var token = pending = {}; H.embed(host, forecastSpec(rows, { band: ui.band, height: 320, ghosts: ui.play ? trail : null })).then(function (r) { if (token === pending) { host._r = r; rideCab(host, r.view, rows, ui.play ? Math.round(period() * 0.85) : 0); } });
        take.textContent = z.takeaway[ui.day] || ""; ftitle.textContent = zoneName(zid) + ", " + dshort(ui.day);
        tbl.replaceChildren(H.rowsTable(rows)); host.setAttribute("role", "img"); host.setAttribute("aria-label", "Line chart of ride requests by hour for " + zoneName(zid) + ". " + (z.takeaway[ui.day] || ""));
        var a = dayMae(z, ui.day), m = a && a.m, b = a && a.b;
        metrics.replaceChildren(metric(m == null ? "n/a" : m.toFixed(2), "Model: average miss, this day"), metric(b == null ? "n/a" : b.toFixed(2), "Simple rule: average miss, this day"),
          metric(rows.length && rows[0].held ? "Held-out" : "Development", "Data"));
      }
    });
    var head = el("div", "controls");
    head.appendChild(select("Taxi zone", D.zones.map(function (z) { return { value: z.id, label: z.id + ": " + z.name }; }), zid, function (v) { ui.zone = +v; ui.day = null; if (H.motion) H.motion.ping(); renderTab(); }));
    box.appendChild(head); box.appendChild(ftitle);
    if (zid === 265) box.appendChild(note("Zone 265 is the city's catch-all for trips outside New York City, not a neighbourhood."));
    box.appendChild(note("How to read this: black is what actually happened. Blue is the model's forecast, made the night before. The gray dashed line is the simple rule of thumb. The yellow band is the range the model expected most hours to land in. The faint shading behind it is a rough guide to night and day, not real sunrise times."));
    box.appendChild(tools);
    box.appendChild(el("p", "strip-key", "Every day in this zone. Blue ticks: the model won. Orange: the simple rule won. Yellow underline: held-out days. Click one, or use the arrow keys on the slider."));
    box.appendChild(strip);
    if (!nudged) { nudged = true; setTimeout(function () { strip.classList.add("nudge"); }, 900); }
    box.appendChild(chartbar(H.tipPill("Hover over the chart to read the numbers."), shareButtons(host, function () { return Promise.resolve(host._r); }, "forecast-zone-" + zid)));
    take.setAttribute("aria-live", "polite"); box.appendChild(host); box.appendChild(tbl); box.appendChild(take); box.appendChild(metrics);
    box.appendChild(note("One zone on one day proves nothing. The overall result is at the top of the page. The address bar link keeps your zone and day, so you can share this exact view."));
  }

  /* ---- Compare zones ---- */
  function compareTakeaway(items, iso) {
    var rows = [];
    for (var i = 0; i < items.length; i++) {
      var it = items[i]; if (it.m == null) return "";
      var m = it.m, b = it.b;
      rows.push({ n: it.name, m: m, b: b, p: b > 0 ? 100 * (b - m) / b : null });
    }
    var a = rows[0], c = rows[1];
    if (a.n === c.n || a.p == null || c.p == null) return "";
    var lead = dshort(iso) + ": ";
    if (a.p > 0 && c.p > 0) { var hi = a.p >= c.p ? [a, c] : [c, a];
      return lead + "the model beat the simple rule in both zones, and helped more in " + hi[0].n + " (" + hi[0].p.toFixed(0) + "% fewer misses) than in " + hi[1].n + " (" + hi[1].p.toFixed(0) + "%)."; }
    if (a.p <= 0 && c.p <= 0) return lead + "the simple rule beat the model in both zones.";
    var w = a.p > 0 ? a : c, l = a.p > 0 ? c : a;
    return lead + "the model beat the simple rule in " + w.n + " (" + w.p.toFixed(0) + "% fewer misses) but lost in " + l.n + ", where the rule missed by " + l.b.toFixed(1) + " rides an hour and the model by " + l.m.toFixed(1) + ".";
  }
  function tabCompare(box) {
    var ids = [ui.zc1 || D.zones[0].id, ui.zc2 || (D.zones[1] || D.zones[0]).id]; ui.zc1 = ids[0]; ui.zc2 = ids[1];
    var days = D.days; if (!ui.dayb || days.indexOf(ui.dayb) < 0) ui.dayb = days[days.length - 1];
    var take = el("p", "takeaway center"), cols = el("div", "twin"), views = [];
    var sl = slider(days, ui.dayb, function (d) { ui.dayb = d; draw(); });
    var tools = el("div", "tools"); tools.appendChild(sl);
    box.appendChild(tools); box.appendChild(chartbar(H.tipPill("Hover one chart and the other follows."), copyLink())); box.appendChild(cols); box.appendChild(take);
    var panels = ids.map(function (id, k) {
      var p = el("div", "panel"), host = el("div", "chart"), m = el("div", "cards minis");
      p.appendChild(select("Taxi zone " + (k + 1), D.zones.map(function (z) { return { value: z.id, label: z.id + ": " + z.name }; }), id, function (v) { (k ? (ui.zc2 = +v) : (ui.zc1 = +v)); if (H.motion) H.motion.ping(); renderTab(); }));
      p.appendChild(host); p.appendChild(m); cols.appendChild(p); return { host: host, m: m, id: id };
    });
    Promise.all(ids.map(loadZone)).then(function (zs) { draw(); function draw() {
      var items = [];
      var done = panels.map(function (p, k) {
        var rows = dayRows(zs[k], ui.dayb), am = dayMae(zs[k], ui.dayb); items.push({ name: zoneName(p.id), m: am && am.m, b: am && am.b });
        if (!rows.length) { p.host.replaceChildren(el("p", "panel-note", "No forecast for this zone on this day.")); p.m.replaceChildren(); return Promise.resolve(null); }
        var mm = am.m, bb = am.b;
        p.m.replaceChildren(metric(mm.toFixed(2), "Model miss", "Simple rule: " + bb.toFixed(2)));
        return H.embed(p.host, forecastSpec(rows, { band: true, height: 260, sync: true }));
      });
      Promise.all(done).then(function (r) { if (r[0] && r[1]) linkCharts(r[0], r[1], tsOf(zs[0], ui.dayb), tsOf(zs[1], ui.dayb)); });
      take.textContent = compareTakeaway(items, ui.dayb);
    } });
  }

  /* ---- Scoreboard: the fare receipt, the bars, and the zone table ---- */
  function tabScore(box) {
    var sb = D.scoreboard;
    if (!sb.length) { box.appendChild(el("p", "panel-note", "heldout.csv is not in the results folder yet.")); return; }
    var sorted = sb.slice().sort(function (a, b) { return a.MAE - b.MAE; });
    var days = heldDayCount();
    var rc = el("div", "receipt");
    rc.appendChild(el("p", "rc-title", "Held-out scoreboard"));
    rc.appendChild(el("p", "rc-sub", "Metered over " + days + " days the models never saw. Scored once."));
    var list = el("div", "rc-rows");
    sorted.forEach(function (r) {
      var row = el("div", "rc-row" + (r.key === "lgbm" ? " best" : "")); row.appendChild(el("span", "rc-name", r.model)); row.appendChild(el("i", "rc-dots")); row.appendChild(el("b", null, r.MAE.toFixed(2)));
      list.appendChild(row);
    });
    rc.appendChild(list);
    rc.appendChild(el("p", "rc-foot", "Average miss, in rides per zone per hour. Lower is better."));
    rc.appendChild(el("i", "rc-tear"));
    box.appendChild(el("h2", null, "Every model on the held-out weeks"));
    box.appendChild(note("Same harness, same days, same zones. LightGBM (blue) is lowest. Exponential smoothing lost to the simple 4-week mean, and blending LightGBM back toward it made LightGBM worse."));
    var top = el("div", "score-top"); top.appendChild(rc); if (H.motion) H.motion.print(rc);
    var right = el("div"), dl = el("div", "actions"); dl.appendChild(download({ label: "Download scoreboard CSV", file: "heldout_scoreboard.csv" }));
    right.appendChild(chartbar(H.tipPill("Hover a bar to see what each method is and why it is here."), dl));
    var host = el("div", "chart"); right.appendChild(host); top.appendChild(right); box.appendChild(top);
    var t = H.theme();
    H.embed(host, { height: 34 * sorted.length + 40, data: { values: sorted }, mark: { type: "bar", cornerRadiusEnd: 3, height: 22 },
      encoding: { y: { field: "model", type: "nominal", sort: sorted.map(function (r) { return r.model; }), title: null, axis: { labelLimit: 260 } },
        x: { field: "MAE", type: "quantitative", title: "held-out MAE, rides per zone-hour" },
        color: { condition: { test: "datum.key === 'lgbm'", value: t.model }, value: t.base },
        tooltip: [{ field: "model", title: "Method" }, { field: "what", title: "What it is" }, { field: "why", title: "Why it is here" },
          { field: "MAE", type: "quantitative", title: "Average miss (MAE)", format: ".2f" }, { field: "MASE", type: "quantitative", format: ".3f" }] } }).then(function (r) { if (H.motion) H.motion.bars(host, r.view); });
    var sp = D.spread, zt = D.zone_table;
    if (sp) {
      box.appendChild(el("h2", null, "Is the gain spread across zones, or carried by a few?"));
      var s = "The model beat the simple rule in " + sp.beaten + " of " + sp.zones + " zones." + (sp.top_saving != null ? " The 5 busiest zones carry " + Math.round(sp.top_rides * 100) + "% of the rides and supplied " + Math.round(sp.top_saving * 100) + "% of the total saving." : "");
      box.appendChild(el("p", "takeaway center", s));
      var zh = el("div", "chart"); box.appendChild(zh);
      var d = zt.filter(function (r) { return r.gain_pct != null; }).sort(function (a, b) { return b.gain_pct - a.gain_pct; });
      H.embed(zh, { height: 18 * d.length + 40, data: { values: d }, mark: { type: "bar", cornerRadiusEnd: 2 },
        encoding: { y: { field: "name", type: "nominal", sort: d.map(function (r) { return r.name; }), title: null, axis: { labelLimit: 220 } },
          x: { field: "gain_pct", type: "quantitative", title: "percent fewer misses than the simple rule (left of zero: the rule won)" },
          color: { condition: { test: "datum.gain_pct >= 0", value: t.model }, value: t.warn },
          tooltip: [{ field: "name", title: "Zone" }, { field: "gain_pct", type: "quantitative", title: "Fewer misses, %", format: ".1f" }, { field: "rides", type: "quantitative", title: "Rides per hour", format: ".1f" }] } }).then(function (r) { if (H.motion) H.motion.bars(zh, r.view, 0); });
      box.appendChild(el("p", "zone-note", "Busiest zone first; click a column header to sort. Miss means the average number of rides per hour the forecast was off by, on held-out days."));
      box.appendChild(sortTable(zt.map(function (r) { return [r.name, r.rides, r.model_miss, r.rule_miss, r.gain_pct]; }),
        ["Zone", "Rides per hour", "Model miss", "Rule miss", "Fewer misses, %"], [null, 1, 2, 2, 1]));
    }
  }
  function sortTable(rows, heads, dec) {
    var wrap = el("div", "tablewrap"), tb = el("table", "dt"), thead = el("thead"), tr = el("tr"), body = el("tbody"), st = { c: -1, asc: false };
    function fill() {
      var before = {}; Array.prototype.forEach.call(body.children, function (tr) { before[tr.firstChild.textContent] = tr.getBoundingClientRect().top; });
      var r = rows.slice(); if (st.c >= 0) r.sort(function (a, b) { var x = a[st.c], y = b[st.c]; if (x == null) return 1; if (y == null) return -1; return (typeof x === "string" ? x.localeCompare(y) : x - y) * (st.asc ? 1 : -1); });
      body.replaceChildren(); r.forEach(function (row) { var t = el("tr"); row.forEach(function (v, i) { t.appendChild(el("td", i ? "num" : null, v == null ? "" : dec[i] == null ? v : v.toFixed(dec[i]))); }); body.appendChild(t); });
      if (H.motion && st.c >= 0) H.motion.flip(before, Array.prototype.slice.call(body.children), function (tr) { return tr.firstChild.textContent; });
    }
    heads.forEach(function (h, i) {
      var th = el("th", rows.some(function (r) { return typeof r[i] === "number"; }) ? "num" : null), b = el("button", null, h); b.type = "button";
      b.addEventListener("click", function () { st.asc = st.c === i ? !st.asc : i === 0; st.c = i; th.parentNode.querySelectorAll("th").forEach(function (x) { x.removeAttribute("aria-sort"); }); th.setAttribute("aria-sort", st.asc ? "ascending" : "descending"); fill(); });
      th.appendChild(b); tr.appendChild(th);
    });
    thead.appendChild(tr); tb.appendChild(thead); tb.appendChild(body); wrap.appendChild(tb); fill(); return wrap;
  }

  /* ---- Where it fails ---- */
  function dispatchLog() {
    var why = {}; (D.reasons || []).forEach(function (r) { why[r.date] = r.reason; });
    var days = D.daily.slice().sort(function (a, b) { return b.model - a.model; }).slice(0, 6); if (!days.length) return null;
    var p = el("div", "dispatch"); p.setAttribute("role", "list");
    days.forEach(function (d) {
      var l = el("p", "dl-line"); l.setAttribute("role", "listitem");
      var go = el("button", "dl-go", "See this day"); go.type = "button"; go.setAttribute("aria-label", "See " + dshort(d.date) + " in the forecast chart");
      go.addEventListener("click", function () { ui.tab = "Forecast"; ui.day = d.date; renderTab(); window.scrollTo(0, 0); });
      l.appendChild(el("b", null, dshort(d.date) + "  "));
      l.appendChild(document.createTextNode("model missed by " + d.model.toFixed(1) + ", simple rule by " + d.base.toFixed(1) + ". " + (why[d.date] ? "Cause: " + String(why[d.date]).split(";")[0] + "." : "No verified cause."))); l.appendChild(go);
      p.appendChild(l);
    });
    return p;
  }
  function tabFails(box) {
    var t = H.theme(), g = D.daily, held = g.filter(function (x) { return x.split === "held-out"; });
    box.appendChild(el("h2", null, "Daily error, all zones"));
    box.appendChild(note("Each line is how far off the forecasts were on average each day. Lower is better. Rings mark days with a verified cause; hover them. Yellow marks the held-out weeks."));
    box.appendChild(H.tipPill("Hover over the chart to read the numbers."));
    var h1 = el("div", "chart"); box.appendChild(h1);
    var lines = []; g.forEach(function (x) { lines.push({ date: x.date, s: "LightGBM", v: x.model }, { date: x.date, s: "4-week same-hour mean", v: x.base }); });
    var wide = g.map(function (x) { return { date: x.date, model: x.model, base: x.base, split: x.split }; });
    var rings = D.reasons.map(function (r) { var x = g.filter(function (q) { return q.date === r.date; })[0]; return x ? { date: r.date, model: x.model, reason: r.reason } : null; }).filter(Boolean);
    var layers = [];
    if (held.length) layers.push({ data: { values: [{ a: held[0].date, b: held[held.length - 1].date }] }, mark: { type: "rect", color: "#FFC72C", opacity: t.held }, encoding: { x: { field: "a", type: "temporal" }, x2: { field: "b" } } });
    layers.push({ data: { values: lines }, mark: { type: "line", strokeWidth: 1.8 }, encoding: { x: { field: "date", type: "temporal", title: null, axis: { format: "%b", tickCount: "month", grid: false } },
      y: { field: "v", type: "quantitative", title: "MAE, rides per zone-hour" }, color: { field: "s", type: "nominal", scale: { domain: ["LightGBM", "4-week same-hour mean"], range: [t.model, t.base] }, legend: { orient: "bottom", title: null } } } });
    layers.push({ data: { values: wide }, params: [{ name: "pk", select: { type: "point", nearest: true, on: "pointerover", fields: ["date"], clear: "pointerout" } }], mark: { type: "rule", color: t.text },
      encoding: { x: { field: "date", type: "temporal" }, opacity: { condition: { param: "pk", empty: false, value: 0.9 }, value: 0 },
        tooltip: [{ field: "date", type: "temporal", title: "Day" }, { field: "model", type: "quantitative", title: "LightGBM", format: ".1f" }, { field: "base", type: "quantitative", title: "4-week mean", format: ".1f" }, { field: "split", title: "Data" }] } });
    if (rings.length) layers.push({ data: { values: rings }, mark: { type: "point", size: 130, filled: false, color: t.warn, strokeWidth: 2.5 },
      encoding: { x: { field: "date", type: "temporal" }, y: { field: "model", type: "quantitative" }, tooltip: [{ field: "date", type: "temporal", title: "Day" }, { field: "reason", title: "cause" }] } });
    H.embed(h1, { height: 300, layer: layers });
    box.appendChild(el("h2", null, "Where LightGBM beats the baseline"));
    box.appendChild(note("Blue: LightGBM has the lower error. Orange: the baseline does. Averaged over every day in the data."));
    var h2 = el("div", "chart"); box.appendChild(h2);
    var lim = Math.max.apply(null, D.heat.map(function (x) { return Math.abs(x.gain); }));
    H.embed(h2, { height: 300, data: { values: D.heat }, mark: { type: "rect", stroke: t.bg, strokeWidth: 1.5 },
      encoding: { x: { field: "hour", type: "ordinal", title: "hour of day", axis: { labelAngle: 0, labelOverlap: true } },
        y: { field: "weekday", type: "nominal", sort: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], title: null },
        color: { field: "gain", type: "quantitative", title: "rides per zone-hour", scale: { domain: [-lim, 0, lim], range: [t.warn, t.mid, t.model], interpolate: "lab" }, legend: { orient: "bottom" } },
        tooltip: [{ field: "weekday" }, { field: "hour", type: "ordinal" }, { field: "gain", type: "quantitative", title: "LightGBM better by", format: ".2f" }] } }).then(function () { if (H.motion) H.motion.sweep(h2); });
    var dl = dispatchLog(); if (dl) { box.appendChild(el("h2", null, "Dispatch log")); box.appendChild(note("The days the model missed by the most, across all zones, with the cause where one was verified. Press \"See this day\" to open that day in the Forecast tab for the zone you last picked.")); box.appendChild(dl); if (H.motion) H.motion.dispatch(dl); }
    box.appendChild(el("h2", null, "Best and worst days"));
    box.appendChild(note("Daily average miss across all zones. A positive last column means the model beat the simple rule that day, negative means the rule won."));
    var two = el("div", "twin");
    [["Days the model beat the rule by the most", D.best], ["Days that went worst for the model", D.worst]].forEach(function (x) {
      var p = el("div"); p.appendChild(el("p", "lead-b", x[0]));
      var heads = ["Day", "Data", "Model miss", "Rule miss", "Rule minus model"];
      p.appendChild(sortTable(x[1].map(function (r) { return [r.Day, r.Data, r["Model miss"], r["Rule miss"], r["Rule minus model"]]; }), heads, [null, null, 2, 2, 2])); two.appendChild(p);
    });
    box.appendChild(two);
  }

  /* Traffic eases down on a storm day and back up after, without a jump. */
  function setRoadSpeed(r) { if (H.motion) H.motion.setStorm(r); }

  /* ---- Storm days, with a light weather replay ---- */
  function weatherKind(reason) { var s = reason.toLowerCase(); return /snow|blizzard|winter|ice/.test(s) ? "snow" : /rain|flood|storm|hurricane|tropical/.test(s) ? "rain" : null; }
  function weather(host, kind) {
    if (!kind || matchMedia("(prefers-reduced-motion: reduce)").matches) return function () {};
    var c = el("canvas", "wx"); c.setAttribute("aria-hidden", "true"); host.appendChild(c);
    var ctx = c.getContext("2d"), w, h, ps = [], raf, alive = true, t0 = performance.now(), RUN = 8000, FADE = 1500;
    function size() { w = c.width = host.clientWidth; h = c.height = host.clientHeight; }
    size(); for (var i = 0; i < (kind === "snow" ? 70 : 110); i++) ps.push({ x: Math.random() * w, y: Math.random() * h, s: 0.6 + Math.random() * 1.4, r: 1.4 + Math.random() * 2.2 });
    (function tick() {
      if (!alive) return; var age = performance.now() - t0; if (age > RUN + FADE) { alive = false; return; } c.style.opacity = age > RUN ? String(1 - (age - RUN) / FADE) : "1"; if (c.width !== host.clientWidth || c.height !== host.clientHeight) size(); ctx.clearRect(0, 0, w, h); ctx.fillStyle = ctx.strokeStyle = H.state.dark ? "rgba(236,238,242,.7)" : "rgba(40,60,110,.75)";
      ps.forEach(function (p) {
        if (kind === "snow") { p.y += p.s; p.x += Math.sin(p.y / 30 + p.r) * 0.5; ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 6.3); ctx.fill(); }
        else { p.y += p.s * 6; p.x -= 1.2; ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x + 2, p.y - 9); ctx.stroke(); }
        if (p.y > h) { p.y = -10; p.x = Math.random() * w; }
      });
      raf = requestAnimationFrame(tick);
    })();
    return function () { alive = false; cancelAnimationFrame(raf); c.remove(); };
  }
  var stopWx = function () {};
  function tabStorm(box) {
    var S = D.storm; if (!S.length) { box.appendChild(el("p", "panel-note", "No verified storm days in the data.")); return; }
    ui.storm = Math.min(ui.storm, S.length - 1); var s = S[ui.storm];
    box.appendChild(el("h2", null, "Days the weather broke the forecast"));
    box.appendChild(note("City-wide pickups across all 30 zones. Each cause below was checked against a news source."));
    var un = D.unexplained;
    box.appendChild(note("Only days where I read a source for the cause are listed. " + (un.length ? un.length + " other day" + (un.length !== 1 ? "s" : "") + " had a miss at least 1.5 times the typical day (" + un.slice(0, 8).join(", ") + (un.length > 8 ? ", and more" : "") + "). I did not look up their causes, so none are guessed." : "No other day had a miss that large.")));
    box.appendChild(select("Day", S.map(function (x, i) { return { value: i, label: x.label + " (" + (x.split === "held-out" ? "held-out" : "development") + "): " + x.cause }; }), ui.storm, function (v) { ui.storm = +v; renderTab(); }));
    var wrapHost = el("div", "wxhost"), host = el("div", "chart"); wrapHost.appendChild(host);
    var acts = shareButtons(host, function () { return Promise.resolve(host._r); }, "storm-" + s.date);
    box.appendChild(chartbar(H.tipPill("Hover over the chart to read the numbers."), acts)); box.appendChild(wrapHost);
    var rows = s.rows.map(function (r) { return r; });
    H.embed(host, forecastSpec(rows.map(function (r) { return { ts: r.ts, y: r.y, lgbm: r.lgbm, base: r.base, q10: null, q90: null }; }), { band: false, height: 320 })).then(function (r) { host._r = r; });
    var kind = weatherKind(s.reason), stop = null;
    if (kind) {
      var btn = el("button", "btn small ghost", "Replay the weather"); btn.type = "button";
      function play() { if (stop) stop(); var a = weather(wrapHost, kind), b = weather(document.getElementById("hero"), kind); stop = function () { a(); b(); }; setRoadSpeed(0.35); }
      stopWx(); play(); stopWx = function () { if (stop) stop(); stop = null; };
      btn.addEventListener("click", function () { play(); stopWx = function () { if (stop) stop(); stop = null; }; });
      acts.insertBefore(btn, acts.firstChild);
    }
    var cards = el("div", "cards minis"); cards.appendChild(metric(s.model.toFixed(1), "LightGBM MAE that day", "median day " + D.median_daily_miss.toFixed(1))); cards.appendChild(metric(s.base.toFixed(1), "Baseline MAE that day"));
    box.appendChild(cards);
    var cause = el("p", "intro"); cause.appendChild(el("b", null, "Cause: ")); cause.appendChild(document.createTextNode(s.reason + ". ")); var u = H.safeUrl(s.source);
    if (u) { var a = el("a", null, "Source"); a.href = u; a.target = "_blank"; a.rel = "noopener noreferrer"; cause.appendChild(a); } box.appendChild(cause);
    document.documentElement.classList.toggle("storm-on", !!kind);
  }


  /* d3 fills the outside of a polygon whose outer ring runs the wrong way, so force outer rings clockwise and holes counter-clockwise */
  function rewind(geo) {
    function area(r) { var a = 0; for (var i = 0, n = r.length; i < n - 1; i++) a += r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1]; return a; }
    function fix(poly) { return poly.map(function (r, i) { var cw = area(r) < 0; return (i === 0) === cw ? r : r.slice().reverse(); }); }
    geo.features.forEach(function (f) { var g = f.geometry; if (!g) return; if (g.type === "Polygon") g.coordinates = fix(g.coordinates); else if (g.type === "MultiPolygon") g.coordinates = g.coordinates.map(fix); });
    return geo;
  }
  function geoBounds(geo) {
    var x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9, R = Math.PI / 180;
    (function walk(c) { if (typeof c[0] === "number") { var x = c[0] * R, y = Math.log(Math.tan(Math.PI / 4 + c[1] * R / 2)); x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); } else c.forEach(walk); })(geo.features.map(function (f) { return f.geometry.coordinates; }));
    return { dx: x1 - x0, dy: y1 - y0, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2 };
  }

  /* ---- Map: where the model helps, and demand through the day ---- */
  function tabMap(box) {
    var t = H.theme(), mode = ui.mapMode || "help", hour = ui.mapHour == null ? 8 : ui.mapHour;
    var modes = el("div", "seg"); modes.setAttribute("role", "group"); modes.setAttribute("aria-label", "Map view");
    [["help", "Where it helps"], ["demand", "Demand by hour"]].forEach(function (m) {
      var b = el("button", null, m[1]); b.type = "button"; b.setAttribute("aria-pressed", String(mode === m[0])); b.addEventListener("click", function () { ui.mapMode = m[0]; renderTab(); }); modes.appendChild(b);
    });
    box.appendChild(el("h2", null, mode === "help" ? "Where the model helps most" : "How demand moves through the day"));
    box.appendChild(modes);
    box.appendChild(note(mode === "help" ? "Percent fewer misses than the simple rule, by zone, on held-out days. Orange means the rule won." : "Average rides per hour in each zone at the chosen hour of the day, on held-out days. One shared scale, so busy hours look busy."));
    var out = el("div", "chart"), cap = el("span", null, ""), clock = el("div", "mapclock"); clock.setAttribute("aria-hidden", "true");
    if (mode === "demand") {
      var sl = el("div", "scrub"), r = el("input"); r.type = "range"; r.min = 0; r.max = 23; r.value = hour; r.setAttribute("aria-label", "Hour of the day"); var o = el("output", null, String(hour).padStart(2, "0") + ":00");
      var play = el("button", "btn small", "Play the day"); play.type = "button";
      r.addEventListener("input", function () { H.setProgress(+r.value / 23); hour = +r.value; busy(hour); ui.mapHour = hour; o.textContent = String(hour).padStart(2, "0") + ":00"; draw(); });
      /* Play the day: the hour glides between whole hours instead of jumping, and the clock and tint follow it. */
      var reduceM = matchMedia("(prefers-reduced-motion: reduce)").matches;
      function clockText(x) { var h = Math.floor(x) % 24, m = Math.floor((x - Math.floor(x)) * 60); return String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0"); }
      function shadeMap(x) { var day = Math.max(0, Math.sin(Math.PI * (x - 6) / 12)); out.style.setProperty("--night", (1 - day).toFixed(2)); out.dataset.part = day > 0.7 ? "day" : day > 0.05 ? (x < 12 ? "morning" : "evening") : "night"; }
      function setHour(x) {
        var h0 = Math.floor(x) % 24, h1 = (h0 + 1) % 24, f = x - Math.floor(x);
        clock.textContent = clockText(x); shadeMap(x);
        var v = ui.mapView; if (!v || !draw.geo) return;
        var feats2 = draw.geo.features.map(function (g) { var id = g.properties.zone, a = D.hourly[id] ? D.hourly[id][h0] : null, b = D.hourly[id] ? D.hourly[id][h1] : null;
          return { type: "Feature", geometry: g.geometry, properties: { zone: id, name: zoneName(id), rides: a == null ? null : a + (b - a) * f, clock: clockText(x) } }; });
        try { v.change("source_0", vega.changeset().remove(function () { return true; }).insert(feats2)).run(); } catch (e) {}
      }
      play.addEventListener("click", function () {
        if (ui.play) { clearInterval(ui.play); ui.play = null; play.textContent = "Play the day"; return; }
        play.textContent = "Pause"; var x = hour, last = performance.now();
        ui.play = setInterval(function () {
          var now = performance.now(), dt = now - last; last = now;
          x = (x + dt / (reduceM ? 700 : 900)) % 24; if (reduceM) x = Math.floor(x);
          hour = Math.floor(x); ui.mapHour = hour; busy(hour); r.value = hour; o.textContent = String(hour).padStart(2, "0") + ":00"; setHour(x);
        }, reduceM ? 700 : 40);
      });
      sl.appendChild(r); sl.appendChild(o); var tools = el("div", "tools"); tools.appendChild(sl); tools.appendChild(play); box.appendChild(tools);
    }
    /* traffic on the banner follows the share of the day's rides in this hour */
    function busy(h) { if (!H.motion) return; var tot = [], mx = 0; for (var q = 0; q < 24; q++) { var sum = 0; Object.keys(D.hourly).forEach(function (z) { sum += D.hourly[z][q] || 0; }); tot.push(sum); mx = Math.max(mx, sum); } var lv = mx ? tot[h] / mx : null; H.motion.traffic(lv); out.classList.toggle("peak", lv != null && lv >= 0.92); }
    if (mode === "demand") { busy(hour); out.classList.add("daymap"); clock.textContent = String(hour).padStart(2, "0") + ":00"; var dd = Math.max(0, Math.sin(Math.PI * (hour - 6) / 12)); out.style.setProperty("--night", (1 - dd).toFixed(2)); out.dataset.part = dd > 0.7 ? "day" : dd > 0.05 ? (hour < 12 ? "morning" : "evening") : "night"; }
    var zb = el("div", "actions");
    [["Zoom in", 1.5], ["Zoom out", 1 / 1.5], ["Reset", 0]].forEach(function (z) {
      var b = el("button", "btn small ghost", z[0]); b.type = "button";
      b.addEventListener("click", function () {
        var v = ui.mapView; if (!v) return; var k = z[1] === 0 ? 1 : Math.max(1, Math.min(14, v.signal("zoom") * z[1]));
        v.signal("zoom", k); if (k === 1) { v.signal("panx", 0); v.signal("pany", 0); } v.run(); ui.mapZ = { zoom: k, panx: v.signal("panx"), pany: v.signal("pany") };
      }); zb.appendChild(b); });
    function openZone(id) { if (!D.zones.some(function (z) { return z.id === id; })) return; ui.zone = id; ui.day = null; ui.tab = "Forecast"; if (H.motion) H.motion.ping(); renderTab(); window.scrollTo(0, 0); }
    var pd = [0, 0]; out.addEventListener("pointerdown", function (e) { pd = [e.clientX, e.clientY]; });
    var jump = select("Open a zone's forecast", [{ value: "", label: "Choose a zone" }].concat(D.zones.map(function (z) { return { value: z.id, label: z.id + ": " + z.name }; })), "", function (v) { if (v) openZone(+v); });
    box.appendChild(chartbar(H.tipPill("Hover a zone to read its numbers, click it to open its forecast. Drag to move when zoomed, or ctrl/cmd + scroll."), zb)); box.appendChild(out);
    box.appendChild(jump);
    var gm = el("details", "gloss"); gm.appendChild(el("summary", null, "Read this map as a table")); box.appendChild(gm);
    (geoCache || (geoCache = fetch("data/zones.geojson").then(function (r) { return r.json(); }))).then(function (geo) { draw.geo = rewind(geo); draw(); });
    function draw() {
      var geo = draw.geo; if (!geo) return; var byZone = {}; D.zone_table.forEach(function (z) { byZone[z.zone] = z; });
      var all = []; Object.keys(D.hourly).forEach(function (z) { all = all.concat(D.hourly[z]); }); var top = Math.max.apply(null, all.concat([1]));
      var feats = geo.features.map(function (f) { var z = byZone[f.properties.zone] || {}, id = f.properties.zone;
        return { type: "Feature", geometry: f.geometry, properties: { zone: id, name: zoneName(id), gain: z.gain_pct == null ? null : z.gain_pct, model: z.model_miss, rule: z.rule_miss, rides: D.hourly[id] ? D.hourly[id][hour] : null, clock: String(hour).padStart(2, "0") + ":00" } }; });
      var lim = Math.max.apply(null, [1].concat(feats.map(function (f) { return Math.abs(f.properties.gain || 0); })));
      var enc = mode === "help" ? { color: { field: "properties.gain", type: "quantitative", title: "fewer misses than the simple rule, %", scale: { domain: [-lim, 0, lim], range: [t.warn, t.mid, t.model], interpolate: "lab" }, legend: { orient: "bottom" } },
        tooltip: [{ field: "properties.name", title: "Zone" }, { field: "properties.gain", type: "quantitative", title: "Fewer misses, %", format: ".1f" }, { field: "properties.model", type: "quantitative", title: "Model miss", format: ".2f" }, { field: "properties.rule", type: "quantitative", title: "Rule miss", format: ".2f" }] }
        : { color: { field: "properties.rides", type: "quantitative", title: "average rides per hour", scale: { domain: [0, top], range: [t.mid, "#FFC72C", "#8A5A00"], interpolate: "lab" }, legend: { orient: "bottom" } },
        tooltip: [{ field: "properties.name", title: "Zone" }, { field: "properties.rides", type: "quantitative", title: "Rides per hour", format: ".1f" }, { field: "properties.clock", title: "Time" }] };
      if (ui.mapView) { try { ui.mapZ = { zoom: ui.mapView.signal("zoom"), panx: ui.mapView.signal("panx"), pany: ui.mapView.signal("pany") }; } catch (e) {} }
      var Z = ui.mapZ || { zoom: 1, panx: 0, pany: 0 }, bd = geoBounds(geo), ns = "min(width / " + bd.dx + ", height / " + bd.dy + ") * 0.92 * zoom";
      var drag = { source: "window", type: "pointermove", between: [{ type: "pointerdown" }, { source: "window", type: "pointerup" }] };
      H.embed(out, { height: 460, data: { values: feats }, usermeta: {},
        params: [{ name: "zoom", value: Z.zoom, on: [{ events: { type: "wheel", filter: "event.ctrlKey || event.metaKey", consume: true }, update: "clamp(zoom * pow(1.002, -event.deltaY), 1, 14)" }] },
          { name: "panx", value: Z.panx, on: [{ events: drag, update: "zoom > 1 ? panx + event.movementX : 0" }] },
          { name: "pany", value: Z.pany, on: [{ events: drag, update: "zoom > 1 ? pany + event.movementY : 0" }] },
          { name: "S", expr: ns }],
        projection: { type: "mercator", scale: { expr: "S" }, translate: { expr: "[width / 2 - S * " + bd.cx + " + panx, height / 2 + S * " + bd.cy + " + pany]" } },
        mark: { type: "geoshape", stroke: t.bg, strokeWidth: 1, clip: true, cursor: "pointer" }, encoding: enc, description: "Map of the taxi zones." }).then(function (r) { if (mode === "demand" && !clock.isConnected) out.appendChild(clock); ui.mapView = r.view; r.view.addEventListener("click", function (ev, item) { var pr = item && item.datum && item.datum.properties; if (pr && Math.hypot(ev.clientX - pd[0], ev.clientY - pd[1]) < 6) openZone(pr.zone); }); if (H.motion && mode === "demand") H.motion.pulse(out, feats.map(function (f) { return f.properties.rides; }), top); });
      var tb = [["Zone", mode === "help" ? "Fewer misses, %" : "Rides at " + String(hour).padStart(2, "0") + ":00"]].concat(feats.map(function (f) { return [f.properties.name, mode === "help" ? (f.properties.gain == null ? "" : f.properties.gain.toFixed(1)) : (f.properties.rides == null ? "" : f.properties.rides.toFixed(1))]; }));
      var old = gm.querySelector(".tablewrap"); if (old) old.remove(); gm.appendChild(sortTable(tb.slice(1), tb[0], [null, null]));
    }
  }

  function tabMethod(box) {
    var cov = D.coverage, tl = (H.data() || {}).timeline || {};
    box.appendChild(el("h2", null, "The test in 60 seconds"));
    var ol = el("ol", "list steps60");
    ["Pick a day. At midnight the model may only look at what happened before that moment.",
     "It forecasts every hour of that day, in every zone.",
     "The real numbers are revealed and the miss is scored. Then the clock moves forward one day and it repeats.",
     "The simple guess plays by the same rules, so the comparison is fair.",
     "Choices were made on the earlier days" + (tl.dev ? " (" + tl.dev + " forecast days)" : "") + ". The last " + (tl.held ? tl.held + " days" : "days") + " were kept locked and scored once, at the end.",
     "A forecast that quietly sees tomorrow looks brilliant and is useless. The leak test below is there to catch exactly that."]
      .forEach(function (x) { ol.appendChild(el("li", null, x)); });
    box.appendChild(ol);
    var secs = [["Setup", ["Every day at midnight, forecast the next 24 hours for each zone, using only data from before that moment.", "Rolling-origin backtest with an expanding window. The last 4 weeks were held out and scored once.", "Error is MAE, RMSE, bias and MASE (scaled by a one-week seasonal naive). No MAPE, because quiet zone-hours are near zero."]],
      ["Model", ["One global LightGBM across all zones, Poisson objective, refit every 7 days.", "Features: demand 24 and 168 hours ago, the mean of the previous 24 hours, the mean of the same hour over the past 4 weeks, hour, weekday, holiday flag and zone.", "Settings fixed in advance, not tuned on the backtest: 300 rounds, learning rate 0.05, 63 leaves.", "The yellow band comes from two more LightGBM models fitted for the 10% and 90% quantiles."]],
      ["Checks", ["A leak test recomputes every feature from raw history and is shown to fail on three deliberately planted leaks.", "Four simple baselines and exponential smoothing were scored by the same code first, so the model had to beat them."].concat(cov != null ? ["The 10 to 90% band contained " + Math.round(cov * 100) + "% of held-out hours (an ideal band would be 80%)."] : []).concat(["Decisions were written down before the code, in the repository."])]];
    secs.forEach(function (s) { box.appendChild(el("h2", null, s[0])); var ul = el("ul", "list"); s[1].forEach(function (x) { ul.appendChild(el("li", null, x)); }); box.appendChild(ul); });
  }
  function tabAbout(box) {
    var a = el("div", "actions"); a.appendChild(download({ label: "Download held-out forecasts (CSV)", file: "heldout_forecasts.csv" }));
    var row = el("div", "chartbar"); row.appendChild(el("p", "caption", "Every forecast made for the 4 held-out weeks, next to what actually happened.")); row.appendChild(a); box.appendChild(row);
    var ul = el("ul", "list");
    [["Task", "at midnight, forecast hourly pickups for each zone for the next 24 hours."], ["Data", "NYC TLC High Volume For-Hire Vehicle trips, 30 zones (busiest, mid, quiet)."],
      ["Evaluation", "rolling-origin backtest with a daily origin; the last 4 weeks were held out and scored once."],
      ["Models", "four baselines, exponential smoothing, and one global LightGBM. LightGBM was best; exponential smoothing lost to the simple baseline."],
      ["Limits", "28 held-out days in one month, one year of history, no weather input. Storm days are the largest errors."], ["Credit", "NYC Taxi and Limousine Commission trip records and zone lookup."]]
      .forEach(function (x) { var li = el("li"); li.appendChild(el("b", null, x[0] + ": ")); li.appendChild(document.createTextNode(x[1])); ul.appendChild(li); });
    box.appendChild(ul);
  }

  /* ---- shell ---- */
  var panel;
  function renderTab() {
    ui.mapView = null;
    setRoadSpeed(1); if (H.motion) { H.motion.reset(); H.motion.traffic(null); }
    if (ui.play) { clearInterval(ui.play); ui.play = null; }
    stopWx(); document.documentElement.classList.remove("storm-on");
    panel.replaceChildren(); var box = panel;
    if (HINTS[ui.tab]) panel.appendChild(el("p", "tabhint", HINTS[ui.tab]));
    ({ "Forecast": tabForecast, "Compare zones": tabCompare, "Scoreboard": tabScore, "Where it fails": tabFails, "Storm days": tabStorm, "Map": tabMap, "Method": tabMethod, "About": tabAbout })[ui.tab](box);
    panel.setAttribute("aria-labelledby", "tab-" + ui.tab.replace(/\W/g, ""));
    document.querySelectorAll(".tabs button").forEach(function (b) { b.setAttribute("aria-selected", String(b.dataset.tab === ui.tab)); b.tabIndex = b.dataset.tab === ui.tab ? 0 : -1; });
    var seltab = document.querySelector('.tabs button[aria-selected="true"]'); if (seltab && seltab.scrollIntoView) try { seltab.scrollIntoView({ inline: "center", block: "nearest" }); } catch (e) {}
    if (ui.tab !== "Forecast") { var p = new URLSearchParams(location.search); p.set("view", "Dashboard"); p.set("tab", ui.tab); p.delete("zone"); p.delete("day"); history.replaceState(null, "", "?" + p.toString()); }
  }
  H.compareTakeaway = compareTakeaway; H.dayRows = dayRows;
  window.renderDashboard = function (main) {
    function go() {
      var qp = new URLSearchParams(location.search);
      TABS = D.map ? BASE_TABS.slice(0, 5).concat(["Map"], BASE_TABS.slice(5)) : BASE_TABS;
      if (TABS.indexOf(qp.get("tab")) >= 0 && !ui._seeded) ui.tab = qp.get("tab");
      if (!ui._seeded) { var z = +qp.get("zone"); if (D.zones.some(function (x) { return x.id === z; })) ui.zone = z; if (qp.get("day")) ui.day = qp.get("day"); ui._seeded = true; }
      if (!ui.zone) ui.zone = D.zones[0].id;
      var bar = el("div", "tabs"); bar.setAttribute("role", "tablist");
      TABS.forEach(function (t) { var b = el("button", null, t); b.type = "button"; b.dataset.tab = t; b.id = "tab-" + t.replace(/\W/g, ""); b.setAttribute("role", "tab"); b.setAttribute("aria-controls", "tabpanel");
        b.addEventListener("click", function () { ui.tab = t; renderTab(); });
        b.addEventListener("keydown", function (e) { var i = TABS.indexOf(ui.tab); if (e.key === "ArrowRight") i = (i + 1) % TABS.length; else if (e.key === "ArrowLeft") i = (i + TABS.length - 1) % TABS.length; else return; ui.tab = TABS[i]; renderTab(); bar.querySelector('[data-tab="' + ui.tab + '"]').focus(); });
        bar.appendChild(b); });
      panel = el("section", "tabpanel"); panel.id = "tabpanel"; panel.setAttribute("role", "tabpanel");
      main.appendChild(bar); main.appendChild(panel); renderTab();
    }
    var sk = el("div", "skel tall"); if (!D) main.appendChild(sk);
    if (D) go(); else fetch("data/dashboard.json").then(function (r) { return r.json(); }).then(function (d) { D = d; sk.remove(); go(); }).catch(function () { sk.remove(); fail("the dashboard data", function () { main.replaceChildren(); window.renderDashboard(main); }, main); });
  };
})();
