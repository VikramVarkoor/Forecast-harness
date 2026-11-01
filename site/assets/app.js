/* Story page. Every number and sentence comes from data/story.json, written by src/make_site.py. */
(function () {
  "use strict";
  var $ = function (s) { return document.querySelector(s); };

  /* ---- safe helpers: data is never put in through innerHTML ---- */
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  /* Text with at most <b> in it. Parse it, keep text and <b>, drop everything else. */
  function rich(parent, html) {
    var doc = new DOMParser().parseFromString("<body>" + html + "</body>", "text/html");
    (function walk(src, dst) {
      src.childNodes.forEach(function (n) {
        if (n.nodeType === 3) dst.appendChild(document.createTextNode(n.nodeValue));
        else if (n.nodeName === "B") { var b = el("b"); dst.appendChild(b); walk(n, b); }
        else walk(n, dst);
      });
    })(doc.body, parent);
    return parent;
  }
  function safeUrl(u) { try { var x = new URL(u); return x.protocol === "https:" ? x.href : null; } catch (e) { return null; } }
  function safeImg(u) { var s = safeUrl(u); return s && !/["'()<>\\ ;{}]/.test(s) ? s : null; }
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) {} return null; }

  /* ---- state: view and dark mode, kept in the address bar so links share ---- */
  var qp = new URLSearchParams(location.search);
  var state = {
    view: qp.get("view") === "Dashboard" ? "Dashboard" : "Story",
    dark: qp.has("dark") ? qp.get("dark") === "1" : store("dark") === "1",
    focus: qp.get("focus") === "1" && qp.get("view") === "Dashboard"      /* one chart on its own, from a shared link */
  };
  var data, theme;

  function syncUrl() {
    var p = new URLSearchParams(location.search);       // keep tab, zone and day set by the dashboard
    p.set("view", state.view);
    if (state.dark) p.set("dark", "1"); else p.delete("dark");
    if (state.view === "Story") { p.delete("tab"); p.delete("zone"); p.delete("day"); state.focus = false; }
    if (!state.focus) p.delete("focus");
    history.replaceState(null, "", "?" + p.toString());
  }
  function applyTheme() {
    document.documentElement.dataset.theme = state.dark ? "dark" : "light";
    var s = $("#dark"); s.setAttribute("aria-checked", String(state.dark));
    if (theme) {
      var t = theme.themes[state.dark ? "dark" : "light"], r = document.documentElement.style;
      Object.keys(t).forEach(function (k) { if (typeof t[k] === "string" && t[k][0] === "#") r.setProperty("--t-" + k, t[k]); });
    }
  }
  function render() {
    syncUrl();
    document.querySelectorAll(".seg button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.view === state.view)); });
    var compact = state.view === "Dashboard";
    renderHero(compact);
    var main = $("#main"); main.replaceChildren();
    followScroll(true);
    document.documentElement.classList.toggle("focus", !!(state.focus && compact));
    if (state.focus && compact) {
      var fb = el("div", "focusbar"); fb.appendChild(el("span", null, "One chart from a day-ahead ride-hail forecast project."));
      var open = el("button", "btn small", "Open the full dashboard"); open.type = "button";
      open.addEventListener("click", function () { state.focus = false; render(); window.scrollTo(0, 0); }); fb.appendChild(open); main.appendChild(fb);
    }
    if (compact) renderDashboardStub(main); else renderStory(main);
    renderFooter();
  }

  /* ---- hero: road, taxi meter, numbers ---- */
  var TAXI = '<svg viewBox="0 0 46 20" aria-hidden="true"><path d="M3 9 Q3 7 6 7 L12 7 L16 2 L31 2 L36 7 L42 7 Q44 7 44 9 L44 15 L3 15 Z" fill="#FFC72C"/>' +
    '<path d="M17.5 3.5 L30 3.5 L33.6 7 L14.6 7 Z" fill="#9FB3C8"/><rect x="21" y="0" width="6" height="2.4" rx="1" fill="#fff"/>' +
    '<path d="M3 11 H44" stroke="#111" stroke-width="1.6" stroke-dasharray="2 2"/>' +
    '<circle cx="13" cy="15.5" r="3.4" fill="#111" stroke="#ddd" stroke-width="1.3"/><circle cx="34" cy="15.5" r="3.4" fill="#111" stroke="#ddd" stroke-width="1.3"/></svg>';
  var TRAFFIC = [["up", "east", 22, -3], ["up", "east", 22, -11], ["up", "east", 22, -17], ["down", "west", 27, -6], ["down", "west", 27, -20]];

  var EXTRA = [["up", "east", 19, -8], ["up", "east", 25, -14], ["down", "west", 21, -3], ["down", "west", 24, -13]];
  function road() {
    var r = el("div", "road"); r.setAttribute("aria-hidden", "true");
    r.appendChild(el("div", "trail"));
    var lead = el("div", "cab lead"); lead.innerHTML = TAXI; r.appendChild(lead);
    TRAFFIC.concat(EXTRA).forEach(function (c, n) {
      var d = el("div", "cab " + c[0] + (n >= TRAFFIC.length ? " extra" : ""));
      d.style.setProperty("--dir", c[1]); d.style.setProperty("--dur", c[2] + "s"); d.style.setProperty("--delay", c[3] + "s");
      d.innerHTML = TAXI;                      // constant markup written above, no data in it
      r.appendChild(d);
    });
    return r;
  }
  /* Progress along the road: 0 to 1. The page decides what it means (scroll on the Story, the day on the dashboard). */
  var progress = 0;
  function setProgress(p) { progress = Math.max(0, Math.min(1, p)); document.querySelectorAll(".road, .miniroad").forEach(function (r) { r.style.setProperty("--p", String(progress)); }); }
  var scrollOn = false;
  function onScroll() { var h = document.documentElement.scrollHeight - innerHeight; setProgress(h > 0 ? scrollY / h : 0); }
  function followScroll(on) { if (on && !scrollOn) { addEventListener("scroll", onScroll, { passive: true }); onScroll(); } else if (!on && scrollOn) removeEventListener("scroll", onScroll); scrollOn = on; }
  function meter(text) {
    var box = el("div", "meter"); box.setAttribute("role", "img"); box.setAttribute("aria-label", text);
    var inn = el("div", "meter-in"); inn.setAttribute("aria-hidden", "true");
    text.split("").forEach(function (c, i) {
      if (c === ".") inn.appendChild(el("span", "dot", "."));
      else if (/\d/.test(c)) {
        var d = el("span", "d"), s = el("i", "strip");
        s.style.setProperty("--end", String(+c + 10)); s.style.setProperty("--i", String(i));
        for (var n = 0; n < 20; n++) s.appendChild(el("b", null, String(n % 10)));
        d.appendChild(s); inn.appendChild(d);
      } else inn.appendChild(el("span", null, c));
    });
    box.appendChild(inn); return box;
  }
  function renderHero(compact) {
    var c = compact ? data.hero_compact : data.hero, h = $("#hero");
    h.className = "hero" + (compact ? " compact" : "");
    h.replaceChildren(road()); setProgress(progress);
    if (window.H.motion) h.appendChild(window.H.motion.rushButton());
    var wrap = el("div", "wrap"), inn = el("div", "hero-in"), left = el("div");
    left.appendChild(el("p", "hero-kicker" + (compact ? "" : " lead"), c.kicker));
    if (c.pct) { var mt = meter(c.pct); left.appendChild(mt); if (window.H.motion) window.H.motion.meter(mt); }
    if (c.cap) { left.appendChild(el("p", "hero-cap", c.cap)); left.appendChild(el("p", "hero-fine", c.fine)); }
    inn.appendChild(left);
    if (c.side && c.side.length) {
      var side = el("div", "hero-side");
      c.side.forEach(function (s) { var d = el("div", null, s[0]); d.appendChild(el("b", null, s[1])); d.appendChild(el("span", null, s[2])); side.appendChild(d); });
      inn.appendChild(side);
    }
    wrap.appendChild(inn); h.appendChild(wrap);
    if (window.H.motion) window.H.motion.sync();
  }

  /* ---- cards ---- */
  function card(big, lab, sub) {
    var c = el("div", "card");
    c.appendChild(el("p", "big" + (big.length > 6 && !/\d/.test(big) ? " word" : ""), big));
    c.appendChild(el("i", "tear"));
    c.appendChild(el("p", "lab", lab));
    c.appendChild(rich(el("p", "sub"), sub));
    return c;
  }
  function grid(items) { var g = el("div", "cards"); items.forEach(function (i) { g.appendChild(i); }); return g; }
  function plain(paras) { var d = el("div", "plain"); paras.forEach(function (p) { d.appendChild(rich(el("p"), p)); }); return d; }

  function news(e) {
    var url = safeUrl(e.url);
    var a = el(url ? "a" : "div", "news");
    if (url) { a.href = url; a.target = "_blank"; a.rel = "noopener noreferrer"; }
    var img = safeImg(e.image), top = el("span", "news-img" + (img ? "" : " none"));
    if (img) top.style.backgroundImage = 'url("' + img + '")';
    top.appendChild(el("span", "news-date", e.date));
    if (img && e.credit) top.appendChild(el("span", "news-credit", e.credit));
    a.appendChild(top);
    a.appendChild(el("i", "tear"));
    var body = el("span", "news-body");
    body.appendChild(el("span", "news-src", e.outlet + (e.host ? " (" + e.host + ")" : "")));
    body.appendChild(el("span", "news-title", e.title));
    body.appendChild(el("span", "news-why", e.why));
    if (url) body.appendChild(el("span", "news-go", "Read it"));
    a.appendChild(body); return a;
  }

  /* ---- the up-close chart ---- */
  function tipPill(text) {
    var p = el("span", "tip");
    p.innerHTML = '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M2 1 L2 11 L4.8 8.6 L6.6 12.6 L8.4 11.8 L6.6 7.9 L10.2 7.9 Z" fill="currentColor"/></svg>';
    p.appendChild(document.createTextNode(text)); return p;
  }
  /* Every chart has its numbers in a table too, for screen readers and for anyone who wants to check. */
  function rowsTable(rows) {
    var d = el("details", "gloss"); d.appendChild(el("summary", null, "Read this chart as a table"));
    var wrap = el("div", "tablewrap"), t = el("table", "dt"), th = el("thead"), hr = el("tr"), tb = el("tbody");
    ["Hour", "What happened", "Model forecast", "Simple rule"].forEach(function (h) { hr.appendChild(el("th", null, h)); });
    th.appendChild(hr); t.appendChild(th);
    rows.forEach(function (r) {
      var tr = el("tr"); tr.appendChild(el("td", null, r.ts.slice(11, 16)));
      [r.y, r.lgbm, r.base].forEach(function (v) { tr.appendChild(el("td", "num", v == null ? "" : String(Math.round(v)))); }); tb.appendChild(tr);
    });
    t.appendChild(tb); wrap.appendChild(t); d.appendChild(wrap); return d;
  }
  /* The up-close lines draw themselves the first time the chart scrolls into view. */
  function drawIn(host) {
    if (!("IntersectionObserver" in window) || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    var svg = host.querySelector("svg"); if (!svg) return;
    var paths = Array.prototype.slice.call(svg.querySelectorAll(".mark-line.role-mark path")), dashed = function (p) { var d = p.getAttribute("stroke-dasharray"); return d && !/^1[, ]+0$/.test(d); };
    var notes = Array.prototype.slice.call(svg.querySelectorAll(".mark-text.role-mark, .mark-symbol.role-mark, .mark-rule.role-mark path, .mark-rule.role-mark line")).filter(function (n) { return !n.closest(".mark-rule") || n.getAttribute("stroke-dasharray"); });
    paths.forEach(function (p) {
      if (dashed(p)) { p.style.opacity = 0; return; }
      var len = p.getTotalLength(); p.style.strokeDasharray = len; p.style.strokeDashoffset = len;
    });
    var areas = Array.prototype.slice.call(svg.querySelectorAll(".mark-area.role-mark path"));
    notes.forEach(function (n) { n.style.opacity = 0; }); areas.forEach(function (a) { a.style.opacity = 0; });
    var io = new IntersectionObserver(function (es) {
      if (!es[0].isIntersecting) return; io.disconnect(); var i = 0, step = 1.15;
      /* what happened first, then the model, then the simple rule, then the misses between them */
      paths.forEach(function (p) {
        var d = (i++) * step + "s";
        if (dashed(p)) { p.style.transition = "opacity .8s ease " + d; p.style.opacity = 1; return; }
        p.style.transition = "stroke-dashoffset 1.1s cubic-bezier(.4,.1,.2,1) " + d; p.style.strokeDashoffset = 0;
      });
      areas.forEach(function (a) { a.style.transition = "opacity .9s ease " + (i * step) + "s"; a.style.opacity = ""; });
      notes.forEach(function (n) { n.style.transition = "opacity .5s ease " + (i * step + 0.6) + "s"; n.style.opacity = 1; });
    }, { threshold: 0.5 });
    io.observe(host);
  }
  function baseConfig(t) {
    var font = "Figtree";
    return { font: font, view: { stroke: null },
      axis: { labelColor: t.muted, titleColor: t.muted, domainColor: t.grid, tickColor: t.grid, gridColor: t.grid, labelFont: font, titleFont: font, labelFontSize: 12, titleFontSize: 12 },
      legend: { labelColor: t.text, labelFont: font, labelFontSize: 13, symbolStrokeWidth: 3, titleColor: t.text } };
  }
  function curTheme() { return theme.themes[state.dark ? "dark" : "light"]; }
  function embed(host, spec) {
    spec.$schema = "https://vega.github.io/schema/vega-lite/v5.json"; spec.description = spec.description || "Chart. The same numbers are available as a table on this page."; spec.background = "transparent"; spec.width = "container";
    spec.config = baseConfig(curTheme());
    return vegaEmbed(host, spec, { actions: false, renderer: "svg", tooltip: { theme: state.dark ? "dark" : "light" } });
  }
  window.H = { el: el, rich: rich, safeUrl: safeUrl, state: state, grid: grid, card: card, tipPill: tipPill, theme: curTheme, embed: embed, setProgress: function () {}, rowsTable: rowsTable, drawIn: drawIn, taxi: function () { return TAXI; },
    data: function () { return data; }, rerender: function () { render(); } };
  function chart(host, rows) {
    var t = theme.themes[state.dark ? "dark" : "light"];
    var N = { a: "What happened", m: "Model forecast", r: "Simple rule" };
    var f = function (v) { return Math.round(v).toLocaleString("en-US"); };
    var wide = rows.map(function (r) {
      return { ts: r.ts, a: r.y, m: r.lgbm, r: r.base,
        t_a: f(r.y) + " ride requests", t_m: f(r.lgbm) + ", off by " + f(Math.abs(r.lgbm - r.y)), t_r: f(r.base) + ", off by " + f(Math.abs(r.base - r.y)) };
    });
    var long = [];
    wide.forEach(function (w) { long.push({ ts: w.ts, s: N.a, v: w.a }, { ts: w.ts, s: N.m, v: w.m }, { ts: w.ts, s: N.r, v: w.r }); });
    var ymax = Math.max.apply(null, long.map(function (d) { return d.v; }));
    var worst = 0; wide.forEach(function (w, i) { if (Math.abs(w.m - w.a) > Math.abs(wide[worst].m - wide[worst].a)) worst = i; });
    var w = wide[worst], hr = new Date(w.ts).getHours();
    var ann = [{ ts: w.ts, y: w.a, top: ymax * 1.2, label: "Biggest miss, " + String(hr).padStart(2, "0") + ":" + String(new Date(w.ts).getMinutes()).padStart(2, "0") +
      ": model " + f(w.m) + ", actual " + f(w.a) }];
    var font = "Figtree";
    var spec = {
      $schema: "https://vega.github.io/schema/vega-lite/v5.json", background: "transparent", width: "container", height: 260,
      config: { font: font, view: { stroke: null }, axis: { labelColor: t.muted, titleColor: t.muted, domainColor: t.grid, tickColor: t.grid, gridColor: t.grid, labelFont: font, titleFont: font, labelFontSize: 12, titleFontSize: 12 },
        legend: { labelColor: t.text, labelFont: font, labelFontSize: 13, symbolStrokeWidth: 3 } },
      layer: [
        { data: { values: wide }, mark: { type: "area", color: t.base, opacity: 0.16, interactive: false },
          encoding: { x: { field: "ts", type: "temporal" }, y: { field: "r", type: "quantitative", title: "ride requests per hour", scale: { domain: [0, ymax * 1.3] } }, y2: { field: "a" } } },
        { data: { values: wide }, mark: { type: "area", color: t.model, opacity: 0.22, interactive: false },
          encoding: { x: { field: "ts", type: "temporal" }, y: { field: "m", type: "quantitative", title: "ride requests per hour", scale: { domain: [0, ymax * 1.3] } }, y2: { field: "a" } } },
        { data: { values: long },
          mark: { type: "line", strokeWidth: 2.2 },
          encoding: {
            x: { field: "ts", type: "temporal", title: "hour of the day", axis: { format: "%H:%M", tickCount: 8, grid: false } },
            y: { field: "v", type: "quantitative", title: "ride requests per hour", scale: { domain: [0, ymax * 1.3] } },
            color: { field: "s", type: "nominal", scale: { domain: [N.a, N.m, N.r], range: [t.actual, t.model, t.base] }, legend: { orient: "bottom", title: null } },
            strokeDash: { field: "s", type: "nominal", legend: null, scale: { domain: [N.a, N.m, N.r], range: [[1, 0], [1, 0], [5, 4]] } } } },
        { data: { values: wide }, params: [{ name: "pick", select: { type: "point", nearest: true, on: "pointerover", fields: ["ts"], clear: "pointerout" } }],
          mark: { type: "rule", color: t.text },
          encoding: { x: { field: "ts", type: "temporal" }, opacity: { condition: { param: "pick", empty: false, value: 0.9 }, value: 0 },
            tooltip: [{ field: "ts", type: "temporal", title: "Hour", format: "%H:%M" }, { field: "t_a", type: "nominal", title: N.a },
              { field: "t_m", type: "nominal", title: N.m }, { field: "t_r", type: "nominal", title: N.r }] } },
        { data: { values: ann }, mark: { type: "rule", color: t.warn, strokeWidth: 1.5, strokeDash: [3, 3] },
          encoding: { x: { field: "ts", type: "temporal" }, y: { field: "y", type: "quantitative" }, y2: { field: "top" } } },
        { data: { values: ann }, mark: { type: "point", size: 170, filled: false, color: t.warn, strokeWidth: 2.5 },
          encoding: { x: { field: "ts", type: "temporal" }, y: { field: "y", type: "quantitative" } } },
        { data: { values: ann }, mark: { type: "text", color: t.warn, align: hr < 12 ? "left" : "right", dx: hr < 12 ? 8 : -8, fontSize: 13, fontWeight: 700, font: font },
          encoding: { x: { field: "ts", type: "temporal" }, y: { field: "top", type: "quantitative" }, text: { field: "label" } } }
      ]
    };
    vegaEmbed(host, spec, { actions: false, renderer: "svg", tooltip: { theme: state.dark ? "dark" : "light" } }).then(function () { drawIn(host); });
  }


  /* ---- your turn: draw tomorrow's curve, then see the model and the simple rule ---- */
  var NS = "http://www.w3.org/2000/svg";
  function sv(tag, attrs, parent) { var n = document.createElementNS(NS, tag); Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); }); if (parent) parent.appendChild(n); return n; }
  var round = 0;
  function scores(add) { var a = []; try { a = JSON.parse(store("fh_game") || "[]"); } catch (e) { a = []; } if (add) { a.push(add); a = a.slice(-60); store("fh_game", JSON.stringify(a)); } return a; }
  function renderGame(main, g, info) {
    var small = matchMedia("(max-width: 600px)").matches, fs = small ? 21 : 12, W = 720, Hh = small ? 430 : 300, L = small ? 62 : 46, R = 12, T = 12, B = small ? 40 : 30, pw = W - L - R, ph = Hh - T - B;
    var ymax = Math.ceil(Math.max.apply(null, g.rows.map(function (r) { return Math.max(r.y, r.lgbm, r.base); }).concat(g.yesterday)) * 1.2 / 40) * 40;
    var X = function (h) { return L + (h + 0.5) * pw / 24; }, Y = function (v) { return T + ph * (1 - v / ymax); }, V = function (py) { return Math.max(0, Math.min(ymax, (T + ph - py) / ph * ymax)); };
    var guess = new Array(24).fill(null), revealed = false, hint = false, cursor = 12;
    section(main, info && info.n > 1 ? "Your turn, round " + (info.i + 1) + " of " + info.n : "Your turn");
    main.appendChild(plain(["It is midnight and you need tomorrow's rides for " + g.place + ", hour by hour. The gray line is what happened yesterday. " +
      "Draw your forecast by dragging across the chart, or click the chart and use the arrow keys. Then see how you did against the model and the simple rule."]));
    var bar = el("div", "chartbar"), hintBtn = el("button", "btn small ghost", "Show the simple rule as a hint"); hintBtn.type = "button"; hintBtn.setAttribute("aria-pressed", "false");
    var clear = el("button", "btn small ghost", "Start over"); clear.type = "button";
    var acts = el("div", "actions"); acts.appendChild(hintBtn); acts.appendChild(clear);
    bar.appendChild(tipPill("Drag across the chart to draw your guess.")); bar.appendChild(acts); main.appendChild(bar);
    var box = el("div", "game"), svg = sv("svg", { viewBox: "0 0 " + W + " " + Hh, role: "application", tabindex: "0",
      "aria-label": "Forecast drawing area for " + g.date + ". Use left and right arrows to pick an hour and up and down to set your guess." }, box);
    var live = el("p", "sr"); live.setAttribute("aria-live", "polite"); box.appendChild(live);
    var gl = sv("g", {}, svg);
    for (var k = 0; k <= 4; k++) { var v = ymax * k / 4; sv("line", { x1: L, x2: W - R, y1: Y(v), y2: Y(v), stroke: "var(--t-grid)" }, gl); var tx = sv("text", { x: L - 8, y: Y(v) + 4, "text-anchor": "end", fill: "var(--t-muted)", "font-size": fs }, gl); tx.textContent = String(Math.round(v)); }
    [0, 3, 6, 9, 12, 15, 18, 21].forEach(function (h) { var t = sv("text", { x: X(h), y: Hh - 10, "text-anchor": "middle", fill: "var(--t-muted)", "font-size": fs }, gl); t.textContent = String(h).padStart(2, "0") + ":00"; });
    var line = function (vals, col, w, dash) { return sv("polyline", { points: vals.map(function (v, h) { return v == null ? null : X(h) + "," + Y(v); }).filter(Boolean).join(" "), fill: "none", stroke: col, "stroke-width": w, "stroke-linejoin": "round", "stroke-linecap": "round", "stroke-dasharray": dash || "none" }, svg); };
    var layerY = line(g.yesterday, "var(--t-muted)", 2, "2 5");
    var layerH = sv("g", {}, svg), layerR = sv("g", {}, svg), layerG = sv("g", {}, svg), cur = sv("rect", { y: T, height: ph, width: pw / 24, fill: "var(--taxi)", opacity: 0.35 }, svg);
    var res = el("div"); main.appendChild(box); main.appendChild(res);
    function draw() {
      layerG.replaceChildren(); var pts = guess.map(function (v, h) { return v == null ? null : X(h) + "," + Y(v); }).filter(Boolean);
      if (pts.length > 1) sv("polyline", { points: pts.join(" "), fill: "none", stroke: "var(--t-text)", "stroke-width": 5, "stroke-linecap": "round", "stroke-linejoin": "round" }, layerG), sv("polyline", { points: pts.join(" "), fill: "none", stroke: "var(--taxi)", "stroke-width": 2.5, "stroke-linecap": "round", "stroke-linejoin": "round" }, layerG);
      guess.forEach(function (v, h) { if (v != null) sv("circle", { cx: X(h), cy: Y(v), r: small ? 8 : 4.5, fill: "var(--taxi)", stroke: "var(--t-text)", "stroke-width": 2 }, layerG); });
      cur.setAttribute("x", X(cursor) - pw / 48); cur.style.display = revealed ? "none" : "";
      layerH.replaceChildren(); if (hint) { sv("polyline", { points: g.rows.map(function (r) { return X(r.hour) + "," + Y(r.base); }).join(" "), fill: "none", stroke: "var(--t-base)", "stroke-width": 2, "stroke-dasharray": "5 4" }, layerH); }
      var n = guess.filter(function (v) { return v != null; }).length; go.disabled = n < 6; go.textContent = n < 6 ? "Draw at least 6 hours (" + n + " so far)" : "Reveal what happened";
    }
    function setAt(px, py) { var r = svg.getBoundingClientRect(), sx = (px - r.left) * W / r.width, sy = (py - r.top) * Hh / r.height; var h = Math.max(0, Math.min(23, Math.floor((sx - L) / pw * 24))); guess[h] = V(sy); cursor = h; draw(); }
    var down = false;
    svg.addEventListener("pointerdown", function (e) { if (revealed) return; down = true; svg.setPointerCapture(e.pointerId); svg.focus(); setAt(e.clientX, e.clientY); });
    svg.addEventListener("pointermove", function (e) { if (down && !revealed) setAt(e.clientX, e.clientY); });
    svg.addEventListener("pointerup", function () { down = false; });
    svg.addEventListener("keydown", function (e) {
      if (revealed) return; var step = ymax / (e.shiftKey ? 10 : 40);
      if (e.key === "ArrowLeft") cursor = Math.max(0, cursor - 1); else if (e.key === "ArrowRight") cursor = Math.min(23, cursor + 1);
      else if (e.key === "ArrowUp" || e.key === "ArrowDown") { var base = guess[cursor] != null ? guess[cursor] : (guess[cursor - 1] != null ? guess[cursor - 1] : g.yesterday[cursor]); guess[cursor] = Math.max(0, Math.min(ymax, base + (e.key === "ArrowUp" ? step : -step))); }
      else return; e.preventDefault(); draw(); live.textContent = String(cursor).padStart(2, "0") + ":00, " + (guess[cursor] == null ? "no guess yet" : "your guess " + Math.round(guess[cursor]) + " rides");
    });
    hintBtn.addEventListener("click", function () { hint = !hint; hintBtn.setAttribute("aria-pressed", String(hint)); draw(); });
    var go = el("button", "btn", "Draw at least 6 hours"); go.type = "button"; go.disabled = true; main.insertBefore(go, res);
    function fill() {  /* hours left blank follow a straight line between the drawn ones; the ends hold their nearest drawn value */
      var idx = []; guess.forEach(function (v, h) { if (v != null) idx.push(h); }); return guess.map(function (v, h) {
        if (v != null) return v; var a = idx.filter(function (i) { return i < h; }).pop(), b = idx.filter(function (i) { return i > h; })[0];
        if (a == null) return guess[b]; if (b == null) return guess[a]; return guess[a] + (guess[b] - guess[a]) * (h - a) / (b - a); });
    }
    go.addEventListener("click", function () {
      revealed = true; var full = fill(), mae = function (f) { var s = 0; g.rows.forEach(function (r, h) { s += Math.abs(f(r, h) - r.y); }); return s / 24; };
      var me = mae(function (r, h) { return full[h]; }), mo = mae(function (r) { return r.lgbm; }), ru = mae(function (r) { return r.base; });
      layerH.replaceChildren(); var reduce = matchMedia("(prefers-reduced-motion: reduce)").matches, lag = reduce ? 0 : 1.1;
      if (!reduce) {
        var ghost = sv("polyline", { points: "", fill: "none", stroke: "var(--taxi)", "stroke-width": 3, "stroke-linejoin": "round", "stroke-linecap": "round" }, layerR), t0 = performance.now();
        (function morph(now) {
          var k = Math.min(1, (now - t0) / 1000), e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
          ghost.setAttribute("points", g.rows.map(function (r, h) { return X(h) + "," + Y(full[h] + (r.lgbm - full[h]) * e); }).join(" "));
          if (k < 1) requestAnimationFrame(morph); else { ghost.style.transition = "opacity .4s"; ghost.style.opacity = 0; setTimeout(function () { ghost.remove(); }, 450); }
        })(t0);
      }
      [[g.rows.map(function (r) { return r.base; }), "var(--t-base)", 2, "5 4"], [g.rows.map(function (r) { return r.lgbm; }), "var(--t-model)", 2.6, null], [g.rows.map(function (r) { return r.y; }), "var(--t-actual)", 3, null]].forEach(function (l, i) {
        var pl = sv("polyline", { points: l[0].map(function (v, h) { return X(h) + "," + Y(v); }).join(" "), fill: "none", stroke: l[1], "stroke-width": l[2], "stroke-linejoin": "round", "stroke-dasharray": l[3] || "none" }, layerR);
        if (!reduce && !l[3]) { var len = pl.getTotalLength(); pl.style.strokeDasharray = len; pl.style.strokeDashoffset = len; pl.getBoundingClientRect(); pl.style.transition = "stroke-dashoffset 1.1s ease " + (lag + i * 0.25) + "s"; pl.style.strokeDashoffset = 0; }
      });
      cur.style.display = "none"; go.remove(); hintBtn.disabled = true;
      var cards = el("div", "cards minis"); cards.appendChild(card(me.toFixed(1), "You: average miss", "rides per hour")); cards.appendChild(card(mo.toFixed(1), "The model: average miss", "rides per hour")); cards.appendChild(card(ru.toFixed(1), "The simple rule: average miss", "rides per hour"));
      var line1 = me < Math.min(mo, ru) ? "You beat both the model and the simple rule on this day." : me < ru ? "You beat the simple rule but not the model." : me < mo ? "You beat the model but not the simple rule." : "Both the model and the simple rule beat you on this day.";
      var lg = el("p", "takeaway"); lg.textContent = g.date + ": " + line1;
      var key = el("p", "caption", "Black is what happened, blue is the model, dashed gray is the simple rule, yellow is you. The model also had the past weeks of data, not only yesterday. One day proves nothing; the held-out result at the top of the page is the test."); 
      var all = scores({ me: me, mo: mo, ru: ru }), nr = all.length, br = all.filter(function (s) { return s.me < s.ru; }).length, bm = all.filter(function (s) { return s.me < s.mo; }).length;
      var hist = el("p", "caption", "Your rounds so far in this browser: " + nr + ". You beat the simple rule in " + br + " and the model in " + bm + ".");
      var strip = el("div", "hist"); strip.setAttribute("role", "list"); strip.setAttribute("aria-label", "Your last rounds, newest on the right");
      all.slice(-10).forEach(function (x) {
        var k = x.me < Math.min(x.mo, x.ru) ? ["both", "Beat both"] : x.me < x.ru ? ["rule", "Beat the rule"] : x.me < x.mo ? ["model", "Beat the model"] : ["none", "Missed"];
        var chip = el("span", "chip " + k[0], k[1]); chip.setAttribute("role", "listitem"); chip.title = "You " + x.me.toFixed(1) + ", model " + x.mo.toFixed(1) + ", rule " + x.ru.toFixed(1); strip.appendChild(chip);
      });
      res.replaceChildren(cards, lg, key, hist, strip); live.textContent = line1;
      if (window.H.motion) { window.H.motion.countUp(cards); if (me < Math.min(mo, ru)) setTimeout(function () { window.H.motion.honk(2); }, 1200); }
      var again = el("button", "btn small ghost", info && info.n > 1 ? "Next round" : "Try another go"); again.type = "button"; again.addEventListener("click", restart); res.appendChild(again);
    });
    function restart() { round += 1; var m = $("#main"); m.replaceChildren(); renderStory(m); var gm = m.querySelector(".game"); if (gm) gm.scrollIntoView({ block: "center" }); }
    clear.addEventListener("click", function () { if (revealed) { restart(); return; } guess.fill(null); draw(); });
    draw();
  }

  /* ---- the Story page, top to bottom ---- */
  function section(main, title) { var h = el("h2", null, title); main.appendChild(h); }
  function renderStory(main) {
    var d = data;
    main.appendChild(rich(el("p", "verdict"), d.verdict));
    main.appendChild(plain(d.plain));
    var u = d.up_close;
    if (u && u.rows.length) {
      section(main, "A forecast, up close");
      var p = el("div", "plain"), q = el("p");
      q.appendChild(document.createTextNode("Here is " + u.place + ", the busiest zone, on " + u.date + ", the last day I tested. The night before, at midnight, the model had to guess how many rides people would request in every hour of that day, without seeing any of it. "));
      var b1 = el("b", "ln", "The solid dark line is what really happened."); b1.style.color = "var(--t-actual)";
      var b2 = el("b", "ln", "The blue line is the model's guess."); b2.style.color = "var(--t-model)";
      q.appendChild(b1); q.appendChild(document.createTextNode(" ")); q.appendChild(b2);
      q.appendChild(document.createTextNode(" The dashed gray line is the simple rule of thumb. Move your mouse over any hour to read the numbers."));
      p.appendChild(q); main.appendChild(p);
      main.appendChild(tipPill("Hover over the chart to read the numbers."));
      var host = el("div", "chart"); main.appendChild(host); chart(host, u.rows);
      host.setAttribute("role", "img"); host.setAttribute("aria-label", "Line chart of ride requests by hour for " + u.place + " on " + u.date + ". " + u.takeaway);
      main.appendChild(rowsTable(u.rows));
      main.appendChild(rich(el("p", "takeaway"), u.takeaway));
      main.appendChild(el("p", "caption", "The shaded areas are the misses: blue between the model and what happened, gray between the simple rule and what happened."));
      main.appendChild(el("p", "caption", u.note));
    }
    var list = d.games && d.games.length ? d.games : (d.game ? [d.game] : []);
    if (list.length) renderGame(main, list[round % list.length], { i: round % list.length, n: list.length });
    if (d.evidence && d.evidence.length) {
      section(main, "Is this a real problem?");
      main.appendChild(plain(["Fair question. Here is what other people have published about why ride-hail demand gets forecast at all. These show the problem is real and studied. They do not show my model works; the held-out result at the top of the page does that."]));
      main.appendChild(grid(d.evidence.map(news)));
    }
    var g = el("details", "gloss"); g.appendChild(el("summary", null, "Words used on this page"));
    d.glossary.forEach(function (x) { var pp = el("p"); pp.appendChild(el("b", null, x[0] + ".")); pp.appendChild(document.createTextNode(" " + x[1])); g.appendChild(pp); });
    main.appendChild(g);
    if (d.findings.length) { var fg = grid(d.findings.map(function (c) { return card(c.big, c.lab, c.sub); })); main.appendChild(fg); if (window.H.motion) window.H.motion.stormCard(fg); }
    if (d.mind.length) {
      section(main, "What would change my mind");
      main.appendChild(plain(["A result is only worth something if it could have failed. Each line is something that has to be true for my claim to stand. If one fails, I change my mind. The numbers come from the held-out days."]));
      var m = el("div", "mind"), chips = [];
      d.mind.forEach(function (c) {
        var r = el("div", "mind-row"), cls = String(c.status).toLowerCase().replace(/[^a-z]/g, "");
        var chip = el("span", "chip " + cls, c.status); r.appendChild(chip); chips.push(chip);
        var t = el("div"); t.appendChild(el("b", null, c.title)); t.appendChild(rich(el("span"), c.detail)); r.appendChild(t); m.appendChild(r);
      });
      main.appendChild(m);
      if ("IntersectionObserver" in window && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
        chips.forEach(function (c) { c.classList.add("pre"); });
        var io = new IntersectionObserver(function (es) {
          es.forEach(function (e) { if (e.isIntersecting) { var i = chips.indexOf(e.target); setTimeout(function () { e.target.classList.remove("pre"); }, i * 160); io.unobserve(e.target); } });
        }, { threshold: 0.6 });
        chips.forEach(function (c) { io.observe(c); });
      }
    }
    section(main, "How it was tested");
    main.appendChild(el("p", "intro", "Forecasts are easy to flatter by accident, mostly by letting a model peek at the future. Here is how I prevented that."));
    var tl = d.timeline;
    if (tl.dev && tl.held) {
      var line = el("div", "timeline"), a = el("div", "train", "Rolling backtest, " + tl.dev + " daily forecasts"), h = el("div", "held", "Held out, " + tl.held + " days");
      a.style.flex = String(tl.dev); h.style.flex = String(Math.max(tl.held, tl.dev * 0.25)); line.appendChild(a); line.appendChild(h); main.appendChild(line);
    }
    main.appendChild(grid(d.steps.map(function (s, i) { return card(String(i + 1), s.lab, s.sub); })));
    section(main, "What I would do next");
    main.appendChild(grid(d.next_steps.map(function (s) { return card(s.big, s.lab, s.sub); })));
    if (data.fleet) {
      section(main, "Taking this into a real fleet"); main.appendChild(el("p", "intro", data.fleet.intro));
      var fg = el("div", "fleet");
      data.fleet.columns.forEach(function (c) { var col = el("div", "fleetcol"); col.appendChild(el("h3", null, c.title)); col.appendChild(el("p", "fsub", c.sub)); var ul = el("ul", "list"); c.items.forEach(function (x) { ul.appendChild(el("li", null, x)); }); col.appendChild(ul); fg.appendChild(col); });
      main.appendChild(fg);
    }
    var go = el("button", "btn", "Open the dashboard"); go.type = "button";
    go.addEventListener("click", function () { state.view = "Dashboard"; render(); window.scrollTo(0, 0); });
    var rc = el("button", "btn ghost", "Save the result card (image)"); rc.type = "button"; rc.addEventListener("click", saveResultCard);
    var ab = el("div", "actions"); ab.appendChild(go); if (/[?&]card=1\b/.test(location.search)) ab.appendChild(rc); main.appendChild(ab);
  }
  /* A 1200x630 image of the headline result, drawn from the same hero text the page shows, so it can never disagree with the page. */
  function saveResultCard() {
    var c = data.hero; if (!c || !c.pct) return;
    var W = 1200, Hh = 630, cv = document.createElement("canvas"); cv.width = W; cv.height = Hh; var g = cv.getContext("2d");
    function wrap(text, x, y, maxw, lh) { var words = text.split(" "), line = ""; words.forEach(function (w) { var t = line ? line + " " + w : w; if (g.measureText(t).width > maxw && line) { g.fillText(line, x, y); y += lh; line = w; } else line = t; }); g.fillText(line, x, y); return y; }
    var zn = /(\d+) New York zones/.exec(c.fine || ""), dn = /Tested on (\d+) days/.exec(c.fine || "");
    var scope = (zn ? zn[1] + " NYC zones" : "NYC zones") + (dn ? ", " + dn[1] + " held-out days" : "");
    return Promise.all([document.fonts.load("800 60px Figtree"), document.fonts.load("700 40px Fraunces")].map(function (p) { return p.catch(function () {}); })).then(function () {
      g.fillStyle = "#FFC72C"; g.fillRect(0, 0, W, Hh);
      g.fillStyle = "#111"; g.fillRect(0, 36, W, 56); g.fillStyle = "#FFC72C"; for (var x = 10; x < W; x += 70) g.fillRect(x, 62, 36, 4);
      g.fillStyle = "#111"; g.textBaseline = "alphabetic"; g.font = "800 38px Figtree"; wrap(c.kicker, 60, 148, 640, 42);
      var x0 = 60; g.font = "900 140px Figtree";
      c.pct.split("").forEach(function (ch) { var w = Math.max(g.measureText(ch).width + 30, ch === "." ? 46 : 0); g.fillStyle = "#111"; g.beginPath(); g.roundRect(x0, 215, w, 175, 20); g.fill(); g.fillStyle = "#FFC72C"; g.fillText(ch, x0 + (w - g.measureText(ch).width) / 2, 345); x0 += w + 9; });
      g.fillStyle = "#111"; g.font = "800 40px Figtree"; g.fillText(c.cap, 60, 450);
      g.font = "600 26px Figtree"; g.fillText(scope + ", scored once.", 60, 496);
      g.font = "700 22px Figtree"; g.fillText("Made by Vikram" + (/^(localhost|127\.|\[::1\])/.test(location.hostname) ? "" : "  |  " + location.host), 60, 590);
      /* right column: one real day, drawn from the page's own up-close rows */
      var u = data.up_close, rx = 740, rw = 400;
      if (u && u.rows && u.rows.length > 1) {
        g.fillStyle = "#111"; g.beginPath(); g.roundRect(rx, 128, rw, 210, 18); g.fill();
        var ys = u.rows.reduce(function (m, r) { return Math.max(m, r.y, r.lgbm, r.base); }, 1), px = rx + 22, pw = rw - 44, py = 190, ph = 124, n = u.rows.length;
        var line = function (key, col, w, dash) { g.beginPath(); g.setLineDash(dash || []); g.strokeStyle = col; g.lineWidth = w; u.rows.forEach(function (r, k) { var X = px + pw * k / (n - 1), Y = py + ph * (1 - r[key] / ys); if (k) g.lineTo(X, Y); else g.moveTo(X, Y); }); g.stroke(); g.setLineDash([]); };
        g.fillStyle = "#FFC72C"; var tt = "One zone, one day: " + (u.date || ""), fz = 18; do { g.font = "700 " + fz + "px Figtree"; fz--; } while (g.measureText(tt).width > pw && fz > 11); g.fillText(tt, px, 160);
        line("base", "#9aa0a6", 2.5, [6, 5]); line("lgbm", "#FFC72C", 4); line("y", "#fff", 2.5);
        g.font = "600 15px Figtree"; g.fillStyle = "#fff"; g.fillText("actual", px, 330); g.fillStyle = "#FFC72C"; g.fillText("model", px + 70, 330); g.fillStyle = "#9aa0a6"; g.fillText("simple guess", px + 140, 330);
      }
      (c.side || []).forEach(function (sd, i) { var y = 392 + i * 112; g.fillStyle = "#111"; g.font = "600 22px Figtree"; g.fillText(sd[0], rx, y); g.font = "800 58px Fraunces"; g.fillText(sd[1], rx, y + 56); g.font = "500 18px Figtree"; g.fillText(sd[2], rx, y + 80); });
      cv.toBlob(function (b) { var a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "nyc-ride-hail-forecast-result.png"; a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000); }, "image/png");
    });
  }
  function renderDashboardStub(main) {
    if (window.renderDashboard) window.renderDashboard(main);
  }
  function renderFooter() {
    var f = $("#footer"); f.replaceChildren();
    f.appendChild(document.createTextNode("Made by Vikram. "));
    data.links.forEach(function (l, i) {
      var u = safeUrl(l.url); if (!u) return;
      if (i) f.appendChild(document.createTextNode(" "));
      var a = el("a", null, l.name); a.href = u; a.target = "_blank"; a.rel = "noopener noreferrer"; f.appendChild(a);
    });
  }

  /* A thin road pinned to the top of the window once the banner scrolls away, so the lead cab is still visible. */
  (function () {
    var mini = el("div", "miniroad"); mini.setAttribute("aria-hidden", "true"); mini.appendChild(el("div", "trail"));
    var c = el("div", "cab lead"); c.innerHTML = TAXI; mini.appendChild(c); document.body.appendChild(mini); mini.style.setProperty("--p", String(progress));
    if ("IntersectionObserver" in window) new IntersectionObserver(function (es) { mini.classList.toggle("on", !es[0].isIntersecting); }).observe($("#hero"));
  })();

  /* ---- start ---- */
  document.querySelectorAll(".seg button").forEach(function (b) {
    b.addEventListener("click", function () { state.view = b.dataset.view; render(); window.scrollTo(0, 0); });
  });
  $("#dark").addEventListener("click", function () {
    var flip = function () { state.dark = !state.dark; store("dark", state.dark ? "1" : "0"); applyTheme(); render(); };
    if (window.H.motion) window.H.motion.wipe($("#dark"), flip); else flip();
  });
  Promise.all([fetch("data/story.json").then(function (r) { return r.json(); }), fetch("data/theme.json").then(function (r) { return r.json(); })])
    .then(function (x) { data = x[0]; theme = x[1]; applyTheme(); render(); })
    .catch(function () { $("#main").textContent = "Could not load data/story.json. Run: python -m src.make_site"; });
})();
