/* Electricity page. Every number and sentence comes from data/elec/elec.json, written by src/make_site_elec.py. */
(function () {
  "use strict";
  var $ = function (s) { return document.querySelector(s); };
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function rich(parent, html) {
    var doc = new DOMParser().parseFromString("<body>" + html + "</body>", "text/html");
    (function walk(src, dst) { src.childNodes.forEach(function (n) {
      if (n.nodeType === 3) dst.appendChild(document.createTextNode(n.nodeValue));
      else if (n.nodeName === "B") { var b = el("b"); dst.appendChild(b); walk(n, b); } else walk(n, dst); }); })(doc.body, parent);
    return parent;
  }
  function safeUrl(u) { try { var x = new URL(u); return x.protocol === "https:" ? x.href : null; } catch (e) { return null; } }
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) {} return null; }

  var qp = new URLSearchParams(location.search), dark = qp.has("dark") ? qp.get("dark") === "1" : (store("dark") === null ? true : store("dark") === "1"), D, ui = { c: null, d: 0, view: qp.get("view") === "Dashboard" ? "Dashboard" : "Story", tab: qp.get("tab") || "Forecast" };
  var TABS_ALL = ["Forecast", "Countries", "Worst days", "Weather", "Your turn", "Method and limits"], TABS = TABS_ALL;
  var T = { light: { bg: "#FBF8EF", text: "#111111", muted: "#5E6370", grid: "#E4DFCF", actual: "#111111", model: "#2447D6", base: "#80858F", op: "#0B7F63", band: 0.5 },
            dark: { bg: "#12151C", text: "#ECEEF2", muted: "#9AA2B1", grid: "#2A303C", actual: "#ECEEF2", model: "#5C8DF5", base: "#8A93A3", op: "#3DDBB0", band: 0.28 } };
  function t() { return T[dark ? "dark" : "light"]; }
  function applyTheme() {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    $("#dark").setAttribute("aria-checked", String(dark));
    var r = document.documentElement.style, c = t(); ["actual", "model", "base", "op"].forEach(function (k) { r.setProperty("--t-" + k, c[k]); });
    var a = $("[data-domain-link]"); if (a) a.href = "index.html" + (dark ? "?dark=1" : "");
  }
  function fmt(n) { return Math.round(n).toLocaleString("en-US"); }

  function card(big, lab, sub) { var c = el("div", "card"); c.appendChild(el("p", "big", big)); c.appendChild(el("i", "tear")); c.appendChild(el("p", "lab", lab)); c.appendChild(rich(el("p", "sub"), sub)); return c; }
  function grid(items) { var g = el("div", "cards"); items.forEach(function (i) { g.appendChild(i); }); return g; }
  function plain(paras) { var d = el("div", "plain"); paras.forEach(function (p) { d.appendChild(rich(el("p"), p)); }); return d; }
  function section(main, title) { main.appendChild(el("h2", null, title)); }
  function safeImg(u) { var x = safeUrl(u); return x && !/["'()<>\\ ;{}]/.test(x) ? x : null; }
  function news(e) {
    var url = safeUrl(e.url), a = el(url ? "a" : "div", "news");
    if (url) { a.href = url; a.target = "_blank"; a.rel = "noopener noreferrer"; }
    var img = safeImg(e.image), top = el("span", "news-img" + (img ? "" : " none") + (img && e.fit === "contain" ? " contain" : ""));
    if (img) top.style.backgroundImage = 'url("' + img + '")';
    top.appendChild(el("span", "news-date", e.date));
    if (img && e.credit) top.appendChild(el("span", "news-credit", e.credit));
    a.appendChild(top); a.appendChild(el("i", "tear"));
    var body = el("span", "news-body");
    body.appendChild(el("span", "news-src", e.outlet + (e.host ? " (" + e.host + ")" : "")));
    body.appendChild(el("span", "news-title", e.title)); body.appendChild(el("span", "news-why", e.why));
    if (url) body.appendChild(el("span", "news-go", "Read it"));
    a.appendChild(body); return a;
  }
  function tipPill(text) { var p = el("span", "tip"); p.innerHTML = '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M2 1 L2 11 L4.8 8.6 L6.6 12.6 L8.4 11.8 L6.6 7.9 L10.2 7.9 Z" fill="currentColor"/></svg>'; p.appendChild(document.createTextNode(text)); return p; }
  function select(label, opts, val, on) {
    var f = el("label", "field"); f.appendChild(el("span", null, label)); var s = el("select");
    opts.forEach(function (o) { var op = el("option", null, o.label); op.value = o.value; if (String(o.value) === String(val)) op.selected = true; s.appendChild(op); });
    s.addEventListener("change", function () { on(s.value); }); f.appendChild(s); return f;
  }

  var reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var NS = "http://www.w3.org/2000/svg";
  function sv(tag, attrs, parent) { var n = document.createElementNS(NS, tag); Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); }); if (parent) parent.appendChild(n); return n; }
  /* A real held-out day drawn across the banner: what happened, then the model's forecast of it. */
  function loadCurve(h) {
    var s = D.series[D.countries[0].code], d = D.days.length - 1, W = 1200, Hh = 300, svg = sv("svg", { "class": "curve", viewBox: "0 0 " + W + " " + Hh, preserveAspectRatio: "none", "aria-hidden": "true" });
    var all = s.y[d].concat(s.model[d]), lo = Math.min.apply(null, all), hi = Math.max.apply(null, all), pad = (hi - lo) * 0.15 || 1;
    var X = function (i) { return 40 + i * (W - 80) / 23; }, Y = function (v) { return Hh - 30 - (v - (lo - pad)) / (hi - lo + 2 * pad) * (Hh - 60); };
    [["model", s.model[d], "var(--taxi)", "10 8"], ["actual", s.y[d], "#E8F3FF", null]].forEach(function (l, k) {
      var pl = sv("polyline", { points: l[1].map(function (v, i) { return X(i) + "," + Y(v); }).join(" "), fill: "none", stroke: l[2], "stroke-width": k ? 4 : 3, "stroke-linejoin": "round", "stroke-dasharray": l[3] || "none", "stroke-linecap": "round" }, svg);
      if (!reduced && !l[3]) { var len = pl.getTotalLength ? 4000 : 0; pl.style.strokeDasharray = len; pl.style.strokeDashoffset = len; pl.getBoundingClientRect(); pl.style.transition = "stroke-dashoffset 2.2s ease .3s"; requestAnimationFrame(function () { pl.style.strokeDashoffset = 0; }); }
      else if (!reduced) { pl.style.opacity = 0; pl.style.transition = "opacity 1s ease 1.6s"; requestAnimationFrame(function () { pl.style.opacity = 1; }); }
    });
    h.appendChild(svg);
  }
  /* wipe a chart in from the left once it scrolls into view */
  function reveal(node) {
    if (reduced || !node) return;
    var top = node.getBoundingClientRect().top;
    if (top < innerHeight * 1.3) { node.classList.remove("go"); node.classList.add("rv"); void node.offsetWidth; requestAnimationFrame(function () { node.classList.add("go"); }); setTimeout(function () { node.classList.remove("rv", "go"); }, 1000); return; }   /* already on screen (a tab click): wipe starts at once, no waiting for a scroll watcher */
    node.classList.remove("go"); node.classList.add("rv"); var done = false;
    function go() { if (done) return; done = true; node.classList.add("go"); setTimeout(function () { node.classList.remove("rv", "go"); }, 1200); }
    if ("IntersectionObserver" in window) { var io = new IntersectionObserver(function (e) { if (e[0].isIntersecting) { io.disconnect(); go(); } }, { threshold: 0, rootMargin: "0px 0px -6% 0px" }); io.observe(node); setTimeout(go, 6000); } else go();
  }
  /* draw a line on, left to right */
  function drawOn(pl, delay) {
    if (reduced || !pl.getTotalLength) return; var len = Math.ceil(pl.getTotalLength()); pl.style.strokeDasharray = len; pl.style.strokeDashoffset = len; pl.getBoundingClientRect();
    pl.style.transition = "stroke-dashoffset 1s ease " + (delay || 0) + "s"; requestAnimationFrame(function () { pl.style.strokeDashoffset = 0; setTimeout(function () { pl.style.strokeDasharray = ""; pl.style.transition = ""; }, 1200 + (delay || 0) * 1000); });
  }
  function bigNumber(text) {
    var n = el("div", "bignum"); n.setAttribute("role", "img"); n.setAttribute("aria-label", text); var v = parseFloat(text), suffix = text.replace(/[0-9.]/g, "");
    n.textContent = text;
    if (!reduced && isFinite(v)) { var t0 = performance.now(), dur = 1400; (function tick(now) { var k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3); n.textContent = (v * e).toFixed(1) + suffix; if (k < 1) requestAnimationFrame(tick); else n.textContent = text; })(t0); }
    return n;
  }
  /* A transmission line across the top of the banner: pylons, two wires, and pulses of load that run along them for as long as the page is open. */
  function gridLine(h) {
    var g = el("div", "grid"); g.setAttribute("aria-hidden", "true");
    [["east", 9, .1, 1], ["east", 9, .6, 1], ["west", 12, .3, 2], ["west", 12, .85, 2], ["east", 15, .45, 2], ["east", 5.5, .7, 1, "surge"]].forEach(function (p) {
      var d = el("span", "pls l" + p[3] + (p[4] ? " " + p[4] : "")); d.style.setProperty("--dir", p[0]); d.style.setProperty("--dur", p[1] + "s"); d.style.setProperty("--delay", (-p[1] * p[2]).toFixed(2) + "s"); d.style.setProperty("--off", (p[2] * 90).toFixed(0) + "vw"); g.appendChild(d);
    });
    h.appendChild(g);
  }
  function hero(compact) {
    var c = D.hero, h = $("#hero"); h.className = "hero" + (compact ? " compact" : ""); h.replaceChildren();
    gridLine(h);
    if (!compact) loadCurve(h);
    var wrap = el("div", "wrap"), inn = el("div", "hero-in"), left = el("div");
    left.appendChild(el("p", "hero-kicker" + (compact ? "" : " lead"), c.kicker)); left.appendChild(bigNumber(c.pct)); left.appendChild(el("p", "hero-cap", c.cap)); if (!compact) left.appendChild(el("p", "hero-fine", c.fine)); inn.appendChild(left);
    var side = el("div", "hero-side"); c.side.forEach(function (x) { var d = el("div", null, x[0]); d.appendChild(el("b", null, x[1])); d.appendChild(el("span", null, x[2])); side.appendChild(d); });
    inn.appendChild(side); wrap.appendChild(inn); h.appendChild(wrap);
  }

  /* ---- ten countries, one day: the thing the ride-hail page does not have ---- */
  function europeDay(main) {
    section(main, "Ten countries, one day");
    main.appendChild(plain(["Drag the slider or press play to move through the " + D.days.length + " held-out days. In each row, <b>white is what happened</b>, blue is the model, and the shaded gap is the miss. The numbers on the right are that day's average miss as a share of demand. Every country's demand has its own shape, and the operators' forecast is shown as a number only."]));
    var tools = el("div", "scrub"), r = el("input"), o = el("output"), play = el("button", "btn small", "Play"), rows = el("div", "eurows"), idx = D.days.length - 1, timer = null;
    r.type = "range"; r.min = 0; r.max = D.days.length - 1; r.value = idx; r.setAttribute("aria-label", "Held-out day");
    var W = 400, Hh = 54, ranges = {};
    D.countries.forEach(function (c) { var s = D.series[c.code], all = [].concat.apply([], s.y).concat([].concat.apply([], s.model)); ranges[c.code] = [Math.min.apply(null, all), Math.max.apply(null, all)]; });
    var refs = {}, tm = el("div", "tilemap"), POS = { FI: [4, 0], NL: [1, 1], DE: [2, 1], PL: [3, 1], FR: [0, 2], BE: [1, 2], CH: [2, 2], AT: [3, 2], ES: [0, 3], IT: [2, 3] }, tiles = {}, extra = 0;
    D.countries.forEach(function (c) {
      var q = POS[c.code] || [extra++, 4], t1 = el("div", "tile"); t1.style.gridColumn = String(q[0] + 1); t1.style.gridRow = String(q[1] + 1);
      t1.appendChild(el("b", null, c.code)); t1.appendChild(el("span", "tv", "")); tm.appendChild(t1); tiles[c.code] = t1;
    });
    tm.setAttribute("role", "group"); tm.setAttribute("aria-label", "Rough map of the ten countries. Each tile says whether the model or the operators were closer on the chosen day.");
    main.appendChild(tm); main.appendChild(el("p", "caption", "Cyan tile: the model was closer that day. Amber tile: the operators were. Dashed tile: the operator forecast is not like for like, so no winner is called."));
    D.countries.forEach(function (c) {
      var row = el("div", "eurow"), nm = el("div", "eu-name", c.name), svg = sv("svg", { viewBox: "0 0 " + W + " " + Hh, preserveAspectRatio: "none", "aria-hidden": "true" }), fig = el("div", "eu-fig");
      var area = sv("polygon", { fill: "var(--t-model)", opacity: 0.28 }, svg), mp = sv("polyline", { fill: "none", stroke: "var(--t-model)", "stroke-width": 2.2, "vector-effect": "non-scaling-stroke" }, svg), ap = sv("polyline", { fill: "none", stroke: "var(--t-actual)", "stroke-width": 2.4, "vector-effect": "non-scaling-stroke" }, svg);
      row.appendChild(nm); row.appendChild(svg); row.appendChild(fig); rows.appendChild(row); refs[c.code] = { area: area, mp: mp, ap: ap, fig: fig, flag: c.flagged };
    });
    function draw() {
      o.textContent = D.days[idx].label; r.value = idx;
      D.countries.forEach(function (c) {
        var s = D.series[c.code], lo = ranges[c.code][0], hi = ranges[c.code][1], span = (hi - lo) || 1, X = function (i) { return i * W / 23; }, Y = function (v) { return Hh - 4 - (v - lo) / span * (Hh - 8); };
        var y = s.y[idx], m = s.model[idx], op = s.op[idx], pts = function (a) { return a.map(function (v, i) { return X(i) + "," + Y(v); }).join(" "); };
        var R = refs[c.code]; R.ap.setAttribute("points", pts(y)); R.mp.setAttribute("points", pts(m));
        R.area.setAttribute("points", pts(m) + " " + y.map(function (v, i) { return X(23 - i) + "," + Y(y[23 - i]); }).join(" "));
        var pct = function (a) { var sum = 0, tot = 0; for (var h = 0; h < 24; h++) { sum += Math.abs(a[h] - y[h]); tot += y[h]; } return 100 * sum / tot; };
        var pm = pct(m), po = pct(op), T1 = tiles[c.code]; T1.className = "tile " + (R.flag ? "flag" : (pm < po ? "win" : "lose")); T1.querySelector(".tv").textContent = (R.flag ? "not like for like" : (pm < po ? "model by " : "operators by ") + Math.abs(pm - po).toFixed(1) + " pts");
        R.fig.textContent = "Model " + pct(m).toFixed(1) + "%   Operators " + pct(op).toFixed(1) + "%" + (R.flag ? " (not like for like)" : "");
      });
    }
    r.addEventListener("input", function () { idx = +r.value; draw(); });
    play.addEventListener("click", function () {
      if (timer) { clearInterval(timer); timer = null; play.textContent = "Play"; return; }
      play.textContent = "Pause"; if (idx >= D.days.length - 1) idx = -1;
      timer = setInterval(function () { idx++; if (idx >= D.days.length) { clearInterval(timer); timer = null; play.textContent = "Play"; idx = D.days.length - 1; } draw(); if (!document.body.contains(rows)) { clearInterval(timer); timer = null; } }, 700);
    });
    tools.appendChild(r); tools.appendChild(o); tools.appendChild(play); main.appendChild(tools); main.appendChild(rows); draw();
  }

  /* ---- one country, one day ---- */
  /* Every chart gets a "Save chart as image" button: the picture comes with a title and footer on the page background. */
  function savePng(host, view, filename) {
    var c = t(), title = (function () { var n = host; while (n && n.id !== "main") { var p = n.previousElementSibling; while (p) { if (/^H[1-4]$/.test(p.tagName)) return p.textContent; p = p.previousElementSibling; } n = n.parentElement; } return "Chart"; })();
    return Promise.all([view.toImageURL("png", 2), document.fonts.load("700 30px Figtree").catch(function () {})]).then(function (x) {
      return new Promise(function (res) {
        var img = new Image(); img.onload = function () {
          var k = 2, pad = 28 * k, head = 64 * k, foot = 44 * k, cv = el("canvas"); cv.width = img.width + pad * 2; cv.height = img.height + head + foot; var g = cv.getContext("2d");
          g.fillStyle = c.bg; g.fillRect(0, 0, cv.width, cv.height);
          g.fillStyle = c.text; g.font = "800 " + 26 * k + "px Figtree"; g.fillText(title, pad, pad + 20 * k, cv.width - pad * 2);
          g.drawImage(img, pad, head);
          g.fillStyle = c.muted; g.font = "600 " + 15 * k + "px Figtree";
          g.fillText("European electricity day-ahead forecast. Made by Vikram" + (/^(localhost|127\.|\[::1\])/.test(location.hostname) ? "" : "  |  " + location.host), pad, cv.height - 16 * k);
          cv.toBlob(function (b) { var a = el("a"); a.href = URL.createObjectURL(b); a.download = filename + ".png"; a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000); res(); }, "image/png");
        }; img.src = x[0];
      });
    });
  }
  function emb(host, spec, opts) {
    return vegaEmbed(host, spec, opts).then(function (r) {
      host._view = r.view;
      if (!host.dataset.hasSave && host.parentNode) {
        host.dataset.hasSave = "1";
        var b = el("button", "btn small ghost", "Save chart as image"); b.type = "button";
        b.addEventListener("click", function () { savePng(host, host._view, "chart-" + (ui.tab || "story").toLowerCase().replace(/\W+/g, "-")); });
        var row = el("div", "actions chartsave"); row.appendChild(b); host.parentNode.insertBefore(row, host.nextSibling);
      }
      return r;
    });
  }
  function baseConfig() { var c = t(), f = "Figtree, system-ui, sans-serif";
    return { font: f, view: { stroke: null }, axis: { labelColor: c.muted, titleColor: c.muted, domainColor: c.grid, tickColor: c.grid, gridColor: c.grid, labelFont: f, titleFont: f, labelFontSize: 12, titleFontSize: 12 },
      legend: { labelColor: c.text, labelFont: f, labelFontSize: 13, symbolStrokeWidth: 3, titleColor: c.text } }; }
  function dayChart(host) {
    var s = D.series[ui.c], c = t(), N = { a: "What happened", m: "Model forecast", b: "Simple guess", o: "Grid operators' forecast" }, rows = [], wide = [];
    for (var h = 0; h < 24; h++) {
      var y = s.y[ui.d][h], m = s.model[ui.d][h], b = s.base[ui.d][h], o = s.op[ui.d][h];
      wide.push({ h: h, lo: s.lo[ui.d][h], hi: s.hi[ui.d][h], t_a: fmt(y) + " MW", t_m: fmt(m) + ", off by " + fmt(Math.abs(m - y)), t_b: fmt(b) + ", off by " + fmt(Math.abs(b - y)), t_o: fmt(o) + ", off by " + fmt(Math.abs(o - y)) });
      rows.push({ h: h, s: N.a, v: y }, { h: h, s: N.m, v: m }, { h: h, s: N.b, v: b }, { h: h, s: N.o, v: o });
    }
    var X = { field: "h", type: "quantitative", title: "hour of the day, UTC", axis: { tickCount: 8, grid: false, labelExpr: "datum.value + ':00'" }, scale: { domain: [0, 23], nice: false } };
    var spec = { $schema: "https://vega.github.io/schema/vega-lite/v5.json", width: "container", height: 320, background: "transparent", config: baseConfig(),
      description: "Line chart of electricity demand by hour for " + ui.c + ".", layer: [
        { data: { values: wide }, mark: { type: "area", opacity: c.band, color: "#4CD7F6" }, encoding: { x: X, y: { field: "lo", type: "quantitative", title: "megawatts" }, y2: { field: "hi" } } },
        { data: { values: rows }, mark: { type: "line", strokeWidth: 2.2 }, encoding: { x: X, y: { field: "v", type: "quantitative", title: "megawatts", scale: { zero: false } },
          color: { field: "s", type: "nominal", scale: { domain: [N.a, N.m, N.b, N.o], range: [c.actual, c.model, c.base, c.op] }, legend: { orient: "bottom", title: null, columns: innerWidth < 640 ? 2 : 0 } },
          strokeDash: { field: "s", type: "nominal", legend: null, scale: { domain: [N.a, N.m, N.b, N.o], range: [[1, 0], [1, 0], [5, 4], [2, 3]] } } } },
        { data: { values: wide }, params: [{ name: "pick", select: { type: "point", nearest: true, on: "pointerover", fields: ["h"], clear: "pointerout" } }], mark: { type: "rule", color: c.text },
          encoding: { x: { field: "h", type: "quantitative" }, opacity: { condition: { param: "pick", empty: false, value: 0.9 }, value: 0 },
            tooltip: [{ field: "h", title: "Hour (UTC)" }, { field: "t_a", title: N.a }, { field: "t_m", title: N.m }, { field: "t_b", title: N.b }, { field: "t_o", title: N.o }] } }] };
    emb(host, spec, { actions: false, renderer: "svg", tooltip: { theme: dark ? "dark" : "light" } });
    return rows;
  }
  function dayTable(rows) {
    var d = el("details", "gloss"); d.appendChild(el("summary", null, "Read this chart as a table"));
    var wrap = el("div", "tablewrap"), tb = el("table", "dt"), hd = el("thead"), hr = el("tr"), body = el("tbody"), by = {};
    ["Hour (UTC)", "What happened", "Model forecast", "Simple guess", "Operators' forecast"].forEach(function (x) { hr.appendChild(el("th", null, x)); }); hd.appendChild(hr); tb.appendChild(hd);
    rows.forEach(function (r) { (by[r.h] = by[r.h] || []).push(r.v); });
    Object.keys(by).forEach(function (h) { var tr = el("tr"); tr.appendChild(el("td", null, h + ":00")); by[h].forEach(function (v) { tr.appendChild(el("td", "num", fmt(v))); }); body.appendChild(tr); });
    tb.appendChild(body); wrap.appendChild(tb); d.appendChild(wrap); return d;
  }
  function upClose(main, interactive) {
    section(main, interactive ? "Pick a country and a day" : "A forecast, up close");
    main.appendChild(plain([(interactive ? "" : "Here is " + D.countries[0].name + " on " + D.days[D.days.length - 1].label + ", the last day I tested. ") + "At midnight, the night before, the model had to guess demand for every hour of the day. <b>The solid dark line is what really happened.</b> The blue line is the model. The dashed gray line is the simple guess, and the dotted green line is the grid operators' own forecast. The light blue band is the range the model expected most hours to land in."]));
    var tools = el("div", "tools"), selC, selD;
    if (interactive) {
      tools.appendChild(select("Country", D.countries.map(function (c) { return { value: c.code, label: c.name }; }), ui.c, function (v) { ui.c = v; draw(); }));
      tools.appendChild(select("Day", D.days.map(function (d, i) { return { value: i, label: d.label }; }), ui.d, function (v) { ui.d = +v; draw(); }));
      main.appendChild(tools); selC = tools.querySelectorAll("select")[0]; selD = tools.querySelectorAll("select")[1];
    } else { ui.c = D.countries[0].code; ui.d = D.days.length - 1; }
    main.appendChild(tipPill("Hover over the chart to read the numbers."));
    var host = el("div", "chart"), tbl = el("div"), take = el("p", "takeaway"); take.setAttribute("aria-live", "polite");
    main.appendChild(host); main.appendChild(tbl); main.appendChild(take); reveal(host);
    function draw() {
      if (interactive) { selC.value = ui.c; selD.value = String(ui.d); }
      var rows = dayChart(host); tbl.replaceChildren(dayTable(rows));
      var s = D.series[ui.c], e = function (a) { var sum = 0; for (var h = 0; h < 24; h++) sum += Math.abs(a[ui.d][h] - s.y[ui.d][h]); return sum / 24; };
      var m = e(s.model), b = e(s.base), o = e(s.op), who = m < b ? "The model beat the simple guess" : "The simple guess beat the model";
      take.textContent = who + " on this day (average miss " + fmt(m) + " MW against " + fmt(b) + "). The grid operators' forecast missed by " + fmt(o) + " MW. One day proves nothing; the overall result is at the top of the page.";
      host.setAttribute("role", "img"); host.setAttribute("aria-label", "Electricity demand by hour for " + ui.c + " on " + D.days[ui.d].label + ". " + take.textContent);
    }
    draw();
  }

  /* ---- when in the week it misses ---- */
  function heat(main) {
    section(main, "When in the week it misses");
    var WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], num = [], den = [], cnt = [0, 0, 0, 0, 0, 0, 0], i, h;
    for (i = 0; i < 7; i++) { num.push(new Array(24).fill(0)); den.push(new Array(24).fill(0)); }
    D.days.forEach(function (d, k) {
      var w = (new Date(d.iso + "T00:00:00Z").getUTCDay() + 6) % 7; cnt[w]++;
      D.countries.forEach(function (c) { var s = D.series[c.code]; for (var h = 0; h < 24; h++) { num[w][h] += Math.abs(s.model[k][h] - s.y[k][h]); den[w][h] += s.y[k][h]; } });
    });
    var v = num.map(function (r, w) { return r.map(function (x, h) { return den[w][h] ? 100 * x / den[w][h] : null; }); }), flat = [].concat.apply([], v).filter(function (x) { return x != null; });
    var lo = Math.min.apply(null, flat), hi = Math.max.apply(null, flat), wi = 0, wh = 0, bi = 0, bh = 0;
    v.forEach(function (r, w) { r.forEach(function (x, h) { if (x === hi) { wi = w; wh = h; } if (x === lo) { bi = w; bh = h; } }); });
    var used = cnt.filter(function (x) { return x; });
    main.appendChild(plain(["Each square is the model's average miss, as a share of demand, for one weekday and hour, pooled over the " + D.countries.length + " countries. Darker means a bigger miss. Each weekday has only " + Math.min.apply(null, used) + " to " + Math.max.apply(null, used) + " test days behind it, so read this as a hint, not a rule."]));
    var g = el("div", "hm"), read = el("p", "takeaway"); read.setAttribute("aria-live", "polite");
    g.appendChild(el("span", "hm-h", ""));
    for (h = 0; h < 24; h++) g.appendChild(el("span", "hm-h", h % 6 === 0 ? String(h) : ""));
    function say(w, hh) { read.textContent = WD[w] + " " + hh + ":00 UTC: the model missed by " + v[w][hh].toFixed(1) + "% on average."; }
    v.forEach(function (r, w) {
      g.appendChild(el("span", "hm-d", WD[w]));
      r.forEach(function (x, hh) { var c = el("span", "hm-c"); if (x != null) { var tgt = String(0.12 + 0.88 * (hi === lo ? 1 : (x - lo) / (hi - lo))); c.dataset.o = tgt; c.dataset.h = hh; c.style.opacity = reduced ? tgt : "0"; c.title = WD[w] + " " + hh + ":00, miss " + x.toFixed(1) + "%"; c.addEventListener("mouseenter", function () { say(w, hh); }); c.addEventListener("click", function () { say(w, hh); }); } g.appendChild(c); });
    });
    g.setAttribute("role", "img"); g.setAttribute("aria-label", "Heat map of model error by weekday and hour. Largest on " + WD[wi] + " at " + wh + ":00 UTC, " + hi.toFixed(1) + "%. Smallest on " + WD[bi] + " at " + bh + ":00 UTC, " + lo.toFixed(1) + "%.");
    read.textContent = "Largest miss: " + WD[wi] + " " + wh + ":00 UTC at " + hi.toFixed(1) + "%. Smallest: " + WD[bi] + " " + bh + ":00 UTC at " + lo.toFixed(1) + "%. Hover or tap a square for the rest.";
    main.appendChild(g); main.appendChild(read);
    if (!reduced) {
      var fire = function () { g.querySelectorAll(".hm-c[data-o]").forEach(function (c) { c.style.transition = "opacity .45s ease " + (c.dataset.h * 16) + "ms"; c.style.opacity = c.dataset.o; }); };
      if ("IntersectionObserver" in window) { var io2 = new IntersectionObserver(function (e) { if (e[0].isIntersecting) { io2.disconnect(); fire(); } }, { threshold: 0, rootMargin: "0px 0px -6% 0px" }); io2.observe(g); setTimeout(fire, 6000); } else fire();
    }
  }

  /* ---- your turn: draw tomorrow, then compare ---- */
  var G = { you: 0, model: 0, n: 0 };
  function game(main) {
    section(main, "Draw tomorrow's demand");
    main.appendChild(plain(["Each round hides one test day. The dashed gray line is the day before. <b>Click or drag across the chart</b> to draw your guess for all 24 hours, then check it against what happened."]));
    var box = el("div", "chart gamebox"), out = el("p", "takeaway"), tally = el("p", "caption"), btns = el("div", "tools");
    out.setAttribute("aria-live", "polite");
    var go = el("button", "btn", "Check my guess"), nx = el("button", "btn ghost", "New day"); go.type = "button"; nx.type = "button";
    btns.appendChild(go); btns.appendChild(nx); main.appendChild(box); main.appendChild(btns); main.appendChild(out); main.appendChild(tally);
    var W = 1000, Hh = 320, st = {}, gl;
    function setTally() { tally.textContent = G.n ? "This visit: you were closer in " + G.you + " of " + G.n + " rounds, the model in " + G.model + ". A few rounds say little either way." : ""; }
    function X(i) { return 50 + i * (W - 70) / 23; }
    function Y(v) { return Hh - 30 - (v - st.lo) / (st.hi - st.lo) * (Hh - 50); }
    function V(y) { return st.lo + (Hh - 30 - y) / (Hh - 50) * (st.hi - st.lo); }
    function pts(a) { return a.map(function (v, i) { return X(i) + "," + Y(v); }).join(" "); }
    function line(svg, a, col, w, dash) { return sv("polyline", { points: pts(a), fill: "none", stroke: col, "stroke-width": w, "stroke-linejoin": "round", "stroke-linecap": "round", "stroke-dasharray": dash || "none" }, svg); }
    function newRound() {
      var c = D.countries[Math.floor(Math.random() * D.countries.length)], k = 1 + Math.floor(Math.random() * (D.days.length - 1)), s = D.series[c.code], all = [].concat.apply([], s.y), prev = s.y[k - 1];
      var lo = Math.min.apply(null, all), hi = Math.max.apply(null, all), pad = (hi - lo) * 0.08, mean = prev.reduce(function (a, b) { return a + b; }, 0) / 24;
      st = { c: c, k: k, s: s, lo: lo - pad, hi: hi + pad, guess: new Array(24).fill(mean), done: false, touched: false };
      out.textContent = ""; go.disabled = false; draw();
    }
    function draw() {
      box.replaceChildren(); var C = t(), svg = sv("svg", { viewBox: "0 0 " + W + " " + Hh, "class": "gsvg", role: "img", "aria-label": "Drawing area for your 24 hour demand guess for " + st.c.name }, box); svg.style.touchAction = "none";
      for (var h = 0; h < 24; h += 6) { sv("line", { x1: X(h), x2: X(h), y1: 10, y2: Hh - 30, stroke: C.grid }, svg); var tx = sv("text", { x: X(h), y: Hh - 8, fill: C.muted, "font-size": 15, "text-anchor": "middle" }, svg); tx.textContent = h + ":00"; }
      line(svg, st.s.y[st.k - 1], C.base, 2.5, "6 6");
      if (st.done) { drawOn(line(svg, st.s.y[st.k], C.actual, 4), 0); drawOn(line(svg, st.s.model[st.k], C.model, 3.5), 0.35); }
      gl = line(svg, st.guess, "var(--taxi)", 4.5);
      if (!st.touched && !st.done) { var hint = sv("text", { x: W / 2, y: 36, fill: C.muted, "font-size": 20, "text-anchor": "middle" }, svg); hint.textContent = "Drag here to draw your guess"; svg.hint = hint; }
      box.appendChild(el("p", "caption", st.c.name + ", the day after " + D.days[st.k - 1].label + ". Vertical axis: demand from " + fmt(st.lo) + " to " + fmt(st.hi) + " MW. Times are UTC." + (st.done ? " Cyan is you, white is what happened, blue is the model." : "")));
      var down = false;
      function at(e) { if (st.done) return; var r = svg.getBoundingClientRect(), x = (e.clientX - r.left) / r.width * W, y = (e.clientY - r.top) / r.height * Hh, i = Math.max(0, Math.min(23, Math.round((x - 50) * 23 / (W - 70)))); var val = Math.max(st.lo, Math.min(st.hi, V(y))), from = (st.last == null ? i : st.last), a = Math.min(from, i), b = Math.max(from, i), fv = (st.lastv == null ? val : st.lastv); for (var j = a; j <= b; j++) st.guess[j] = b === a ? val : fv + (val - fv) * (j - from) / (i - from); st.last = i; st.lastv = val; st.touched = true; gl.setAttribute("points", pts(st.guess)); if (svg.hint) { svg.hint.remove(); svg.hint = null; } }
      svg.addEventListener("pointerdown", function (e) { down = true; st.last = null; st.lastv = null; svg.setPointerCapture(e.pointerId); at(e); });
      svg.addEventListener("pointermove", function (e) { if (down) at(e); });
      svg.addEventListener("pointerup", function () { down = false; st.last = null; st.lastv = null; });
    }
    go.addEventListener("click", function () {
      if (st.done) return; if (!st.touched) { out.textContent = "Draw a guess first: click or drag across the chart."; return; }
      st.done = true; go.disabled = true;
      var y = st.s.y[st.k], e = function (a) { var z = 0; for (var h = 0; h < 24; h++) z += Math.abs(a[h] - y[h]); return z / 24; }, you = e(st.guess), mod = e(st.s.model[st.k]), base = e(st.s.base[st.k]);
      G.n++; if (you < mod) G.you++; else G.model++;
      out.textContent = "You missed by " + fmt(you) + " MW on average. The model missed by " + fmt(mod) + " MW. The simple guess missed by " + fmt(base) + " MW. " + (you < mod ? "You were closer than the model on this one." : "The model was closer on this one.");
      setTally(); draw();
    });
    nx.addEventListener("click", newRound); setTally(); newRound();
  }

  /* ---- does weather help ---- */
  function weatherTab(main) {
    var Wx = D.weather; section(main, "Does weather help?");
    main.appendChild(el("p", "verdict small", Wx.verdict)); main.appendChild(plain(Wx.plain));
    main.appendChild(grid(Wx.cards.map(function (c) { return card(c.big, c.lab, c.sub); })));
    section(main, "Country by country");
    main.appendChild(plain(["Average miss as a share of demand on the " + Wx.n_days + " days, " + Wx.window + ". Lower is better. Operator figures for flagged countries are shown but not compared."]));
    main.appendChild(sortTable(Wx.countries.map(function (c) { return [c.name, c.without, c.withw, c.base, c.op, c.flagged ? "Operator series looks off" : (c.withw < c.without ? "Weather helped" : (c.withw > c.without ? "Weather hurt" : "No change"))]; }),
      ["Country", "Without weather, %", "With weather, %", "Simple guess, %", "Operators, %", "Note"], [null, 2, 2, 2, 2, null]));
    section(main, "What this does not show");
    var ul = el("ul", "list"); Wx.caveats.forEach(function (x) { ul.appendChild(el("li", null, x)); }); main.appendChild(ul);
    main.appendChild(el("p", "caption", Wx.data_note));
  }

  /* ---- country by country ---- */
  function countryChart(host) {
    var c = t(), vals = [];
    D.countries.forEach(function (x) {
      vals.push({ name: x.name, who: "Model", v: x.mape_model, fl: false }, { name: x.name, who: "Simple guess", v: x.mape_base, fl: false }, { name: x.name, who: "Grid operators' forecast", v: x.mape_op, fl: x.flagged });
    });
    var order = D.countries.map(function (x) { return x.name; }), W = ["Model", "Simple guess", "Grid operators' forecast"];
    emb(host, { $schema: "https://vega.github.io/schema/vega-lite/v5.json", width: "container", height: 28 * order.length + 60, background: "transparent", config: baseConfig(),
      description: "Average percentage error by country for the model, the simple guess and the grid operators' forecast.", data: { values: vals },
      mark: { type: "point", filled: true, size: 120 }, encoding: { y: { field: "name", type: "nominal", sort: order, title: null },
        x: { field: "v", type: "quantitative", title: "average miss, % of demand (lower is better)", scale: { zero: true } },
        color: { field: "who", type: "nominal", scale: { domain: W, range: [c.model, c.base, c.op] }, legend: { orient: "bottom", title: null, columns: innerWidth < 640 ? 1 : 0 } },
        shape: { field: "who", type: "nominal", scale: { domain: W, range: ["circle", "square", "diamond"] }, legend: null },
        opacity: { condition: { test: "datum.fl", value: 0.3 }, value: 1 },
        tooltip: [{ field: "name", title: "Country" }, { field: "who", title: "Forecast" }, { field: "v", type: "quantitative", title: "Average miss, %", format: ".2f" }] } }, { actions: false, renderer: "svg", tooltip: { theme: dark ? "dark" : "light" } });
  }
  function sortTable(rows, heads, dec) {
    var wrap = el("div", "tablewrap"), tb = el("table", "dt"), thead = el("thead"), tr = el("tr"), body = el("tbody"), st = { c: -1, asc: false };
    function fill() {
      var r = rows.slice(); if (st.c >= 0) r.sort(function (a, b) { var x = a[st.c], y = b[st.c]; if (x == null) return 1; if (y == null) return -1; return (typeof x === "string" ? x.localeCompare(y) : x - y) * (st.asc ? 1 : -1); });
      body.replaceChildren(); r.forEach(function (row) { var q = el("tr"); row.forEach(function (v, i) { q.appendChild(el("td", i ? "num" : null, v == null ? "" : dec[i] == null ? v : (dec[i] === 0 ? fmt(v) : v.toFixed(dec[i])))); }); body.appendChild(q); });
    }
    heads.forEach(function (h, i) {
      var th = el("th", i && i < heads.length - 1 ? "num" : null), b = el("button", null, h); b.type = "button";
      b.addEventListener("click", function () { st.asc = st.c === i ? !st.asc : i === 0; st.c = i; th.parentNode.querySelectorAll("th").forEach(function (x) { x.removeAttribute("aria-sort"); }); th.setAttribute("aria-sort", st.asc ? "ascending" : "descending"); fill(); });
      th.appendChild(b); tr.appendChild(th);
    });
    thead.appendChild(tr); tb.appendChild(thead); tb.appendChild(body); wrap.appendChild(tb); fill(); return wrap;
  }
  function byCountry(main) {
    section(main, "Country by country");
    main.appendChild(plain(["Average miss as a share of demand, on the " + D.compare.n_days + " held-out days. <b>Left is better.</b> A faded green diamond means that country's operator forecast looks like it measures something different from the measured load, so that comparison is not fair."]));
    var host = el("div", "chart"); main.appendChild(host); countryChart(host); reveal(host);
    main.appendChild(el("p", "zone-note", "Busiest country first; click a column header to sort. Miss means the average gap between forecast and what happened, on held-out days."));
    main.appendChild(sortTable(D.countries.map(function (c) { return [c.name, c.mean_load, c.mape_model, c.mape_base, c.mape_op, c.flagged ? "Operator series looks off (about " + c.op_year_err + "% error every year)" : ""]; }),
      ["Country", "Average demand, MW", "Model miss, %", "Simple guess miss, %", "Operators miss, %", "Note"], [null, 0, 2, 2, 2, null]));
  }
  function dailyChart(main) {
    var c = t(), vals = []; D.daily.forEach(function (d) { vals.push({ day: d.label, who: "Model", v: d.model }, { day: d.label, who: "Simple guess", v: d.base }, { day: d.label, who: "Grid operators' forecast", v: d.op }); });
    var W = ["Model", "Simple guess", "Grid operators' forecast"], host = el("div", "chart"); main.appendChild(host); reveal(host);
    emb(host, { $schema: "https://vega.github.io/schema/vega-lite/v5.json", width: "container", height: 300, background: "transparent", config: baseConfig(), description: "Average miss in megawatts for each held-out day.", data: { values: vals },
      mark: { type: "line", strokeWidth: 2.2, point: true }, encoding: { x: { field: "day", type: "ordinal", sort: D.daily.map(function (d) { return d.label; }), title: null, axis: { labelAngle: -60, labelLimit: 120, labelOverlap: "parity" } },
        y: { field: "v", type: "quantitative", title: "average miss, MW (lower is better)" },
        color: { field: "who", type: "nominal", scale: { domain: W, range: [c.model, c.base, c.op] }, legend: { orient: "bottom", title: null, columns: innerWidth < 640 ? 1 : 0 } },
        tooltip: [{ field: "day", title: "Day" }, { field: "who", title: "Forecast" }, { field: "v", type: "quantitative", title: "Average miss, MW", format: ",.0f" }] } }, { actions: false, renderer: "svg", tooltip: { theme: dark ? "dark" : "light" } });
  }
  function worst(main) {
    section(main, "Every day, side by side");
    main.appendChild(plain(["Average miss for each of the " + D.daily.length + " held-out days. Lower is better."]));
    dailyChart(main);
    section(main, "Where it missed most");
    main.appendChild(plain(["These are the three days with the largest average miss. I did not look up why they were hard, so I will not guess a cause."]));
    var cap = el("p", "takeaway"), host = el("div", "chart");
    cap.setAttribute("aria-live", "polite"); host.style.display = "none"; cap.textContent = "Press Replay this day on any card to redraw that day here.";
    function replay(w) {
      ui.c = w.worst_code; ui.d = w.i; host.style.display = ""; dayChart(host); reveal(host);
      var s = D.series[ui.c], miss = 0; for (var h = 0; h < 24; h++) miss += Math.abs(s.model[ui.d][h] - s.y[ui.d][h]);
      cap.textContent = "Showing " + D.countries.filter(function (c) { return c.code === ui.c; })[0].name + " on " + D.days[ui.d].label + ": the model missed by " + fmt(miss / 24) + " MW on average.";
      host.setAttribute("role", "img"); host.setAttribute("aria-label", cap.textContent);
      host.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "center" });
    }
    main.appendChild(grid(D.worst.map(function (w) {
      var c = card(w.times_typical + "x", w.date, "Average miss " + fmt(w.day_mae) + " MW, about " + w.times_typical + "x a typical day. Worst country that day: " + w.worst_country + " at " + w.worst_country_pct + "%.");
      var b = el("button", "btn small replay", "Replay this day"); b.type = "button"; b.addEventListener("click", function () { replay(w); }); c.appendChild(b); return c;
    })));
    main.appendChild(cap); main.appendChild(host); heat(main);
  }

  var HINTS = { "Forecast": "Pick any country and any of the held-out days.", "Countries": "Click a column header in the table to sort it.", "Worst days": "Every held-out day, the three that went worst, and when in the week it misses.", "Weather": "A second test: the same model with temperature added.", "Your turn": "Draw tomorrow's demand yourself, then see how you did.", "Method and limits": "How the test was kept honest, and what it cannot show." };
  function syncUrl() { var p = new URLSearchParams(location.search); p.set("view", ui.view); if (dark) p.set("dark", "1"); else p.delete("dark"); if (ui.view === "Dashboard") p.set("tab", ui.tab); else p.delete("tab"); history.replaceState(null, "", "?" + p.toString()); }
  function footer() {
    var f = $("#footer"); f.replaceChildren(); f.appendChild(el("p", null, D.data_note)); var p = el("p", null, "Made by Vikram. ");
    D.links.forEach(function (l, i) { var u = safeUrl(l.url); if (!u) return; if (i) p.appendChild(document.createTextNode(" ")); var x = el("a", null, l.name); x.href = u; x.target = "_blank"; x.rel = "noopener noreferrer"; p.appendChild(x); }); f.appendChild(p);
  }
  function story(main) {
    main.appendChild(el("p", "verdict", D.verdict)); main.appendChild(plain(D.plain));
    main.appendChild(grid(D.findings.map(function (c) { return card(c.big, c.lab, c.sub); })));
    upClose(main, false);
    europeDay(main);
    if (D.weather) {
      section(main, "Does weather help?");
      main.appendChild(el("p", "verdict small", D.weather.verdict));
      main.appendChild(plain(["Tested on a separate window of " + D.weather.n_days + " days that was never used for tuning, with <b>measured</b> temperature standing in for a forecast. That makes it the most weather could add, not what a live system would get."]));
      var wb = el("button", "btn ghost", "See the weather test"); wb.type = "button"; wb.addEventListener("click", function () { ui.view = "Dashboard"; ui.tab = "Weather"; render(); window.scrollTo(0, 0); }); main.appendChild(wb);
    }
    if (D.evidence && D.evidence.length) {
      section(main, "Is this a real problem?");
      main.appendChild(plain(["Fair question. Here is what others have published about why day-ahead electricity demand gets forecast at all, and what happens when it is missed. These show the problem is real and studied. They do not show my model works; the held-out result at the top of the page does that."]));
      main.appendChild(grid(D.evidence.map(news)));
    }
    if (D.mind && D.mind.length) {
      section(main, "What would change my mind");
      main.appendChild(plain(["A result is only worth something if it could have failed. Each line is something that has to be true for my claim to stand. If one fails, I change my mind. The numbers come from the held-out days."]));
      var mm = el("div", "mind"), chips = []; D.mind.forEach(function (c) { var r = el("div", "mind-row"), t1 = el("div"), ch = el("span", "chip " + String(c.status).toLowerCase(), c.status); chips.push(ch); r.appendChild(ch); t1.appendChild(el("b", null, c.title)); t1.appendChild(el("span", null, c.detail)); r.appendChild(t1); mm.appendChild(r); });
      main.appendChild(mm);
      /* the status stamps onto its row the first time the row scrolls into view, one after another, as on the ride-hail page */
      if ("IntersectionObserver" in window && !reduced) {
        chips.forEach(function (c) { c.classList.add("pre"); });
        var io3 = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { var i = chips.indexOf(e.target); setTimeout(function () { e.target.classList.remove("pre"); }, i * 160); io3.unobserve(e.target); } }); }, { threshold: 0.6 });
        chips.forEach(function (c) { io3.observe(c); });
        setTimeout(function () { chips.forEach(function (c) { c.classList.remove("pre"); }); }, 12000);
      }
    }
    section(main, "What this does not prove");
    var ul = el("ul", "list"); D.limits.slice(0, 3).forEach(function (x) { ul.appendChild(el("li", null, x)); }); main.appendChild(ul);
    if (D.fleet) {
      section(main, "Taking this into a real grid"); main.appendChild(el("p", "intro", D.fleet.intro));
      var fg = el("div", "fleet"); D.fleet.columns.forEach(function (c) { var col = el("div", "fleetcol"); col.appendChild(el("h3", null, c.title)); col.appendChild(el("p", "fsub", c.sub)); var ul2 = el("ul", "list"); c.items.forEach(function (x) { ul2.appendChild(el("li", null, x)); }); col.appendChild(ul2); fg.appendChild(col); });
      main.appendChild(fg);
    }
    var go = el("button", "btn", "Open the dashboard"); go.type = "button"; go.addEventListener("click", function () { ui.view = "Dashboard"; render(); window.scrollTo(0, 0); });
    var more = el("button", "btn ghost", "All the limits and the method"); more.type = "button"; more.addEventListener("click", function () { ui.view = "Dashboard"; ui.tab = "Method and limits"; render(); window.scrollTo(0, 0); });
    var ab = el("div", "actions"); ab.appendChild(go); ab.appendChild(more); main.appendChild(ab);
  }
  function tabBody(panel) {
    if (HINTS[ui.tab]) panel.appendChild(el("p", "tabhint", HINTS[ui.tab]));
    if (ui.tab === "Forecast") upClose(panel, true);
    else if (ui.tab === "Countries") byCountry(panel);
    else if (ui.tab === "Worst days") worst(panel);
    else if (ui.tab === "Weather") weatherTab(panel);
    else if (ui.tab === "Your turn") game(panel);
    else {
      section(panel, "How it was tested");
      var tl = D.timeline, line = el("div", "timeline"), a = el("div", "train", "Development, " + tl.dev + " daily forecasts"), h = el("div", "held", "Held out, " + tl.held + " days");
      a.style.flex = String(tl.dev); h.style.flex = String(Math.max(tl.held, tl.dev * 0.25)); line.appendChild(a); line.appendChild(h); panel.appendChild(line);
      panel.appendChild(grid(D.steps.map(function (s, i) { return card(String(i + 1), s.lab, s.sub); })));
      section(panel, "The test in 60 seconds");
      var ol = el("ol", "list steps60"); D.method.forEach(function (x) { ol.appendChild(el("li", null, x)); }); panel.appendChild(ol);
      section(panel, "What this does not prove");
      var ul = el("ul", "list"); D.limits.forEach(function (x) { ul.appendChild(el("li", null, x)); }); panel.appendChild(ul);
      var g = el("details", "gloss"); g.appendChild(el("summary", null, "Words used on this page"));
      D.glossary.forEach(function (x) { var p = el("p"); p.appendChild(el("b", null, x[0] + ".")); p.appendChild(document.createTextNode(" " + x[1])); g.appendChild(p); }); panel.appendChild(g);
    }
  }
  function dashboard(main) {
    var bar = el("div", "tabs"); bar.setAttribute("role", "tablist"); var panel = el("section", "tabpanel"); panel.setAttribute("role", "tabpanel");
    function show() {
      panel.replaceChildren(); tabBody(panel); syncUrl();
      bar.querySelectorAll("button").forEach(function (b) { var on = b.dataset.tab === ui.tab; b.setAttribute("aria-selected", String(on)); b.tabIndex = on ? 0 : -1; });
    }
    TABS.forEach(function (n) {
      var b = el("button", null, n); b.type = "button"; b.dataset.tab = n; b.setAttribute("role", "tab");
      b.addEventListener("click", function () { ui.tab = n; show(); });
      b.addEventListener("keydown", function (e) { var i = TABS.indexOf(ui.tab); if (e.key === "ArrowRight") i = (i + 1) % TABS.length; else if (e.key === "ArrowLeft") i = (i + TABS.length - 1) % TABS.length; else return; ui.tab = TABS[i]; show(); bar.querySelector('[aria-selected="true"]').focus(); });
      bar.appendChild(b);
    });
    main.appendChild(bar); main.appendChild(panel); show();
  }
  function render() {
    applyTheme(); if (TABS.indexOf(ui.tab) < 0) ui.tab = "Forecast";
    document.querySelectorAll(".seg button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.view === ui.view)); });
    var main = $("#main"); main.replaceChildren(); hero(ui.view === "Dashboard");
    if (ui.view === "Dashboard") dashboard(main); else story(main);
    syncUrl(); footer();
  }
  $("#dark").addEventListener("click", function () { dark = !dark; store("dark", dark ? "1" : "0"); if (D) render(); else applyTheme(); });
  fetch("data/elec/elec.json").then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (d) {
    D = d; TABS = D.weather ? TABS_ALL : TABS_ALL.filter(function (x) { return x !== "Weather"; }); ui.c = D.countries[0].code; ui.d = D.days.length - 1; document.querySelectorAll(".seg button").forEach(function (b) { b.addEventListener("click", function () { ui.view = b.dataset.view; render(); window.scrollTo(0, 0); }); }); render();
  }).catch(function () {
    applyTheme(); var m = $("#main"), b = el("div", "errbox"); b.setAttribute("role", "alert"); b.appendChild(el("p", null, "Could not load the electricity results. Check your connection, then try again."));
    var r = el("button", "btn small", "Try again"); r.type = "button"; r.addEventListener("click", function () { location.reload(); }); b.appendChild(r); m.appendChild(b);
  });
})();
