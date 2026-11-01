/* Motion helpers. Everything here is decoration on top of numbers that are already on the page,
   and every effect checks the reduced-motion setting first. Only transform and opacity are animated. */
(function () {
  "use strict";
  var H = window.H; if (!H) return;
  var still = function () { return matchMedia("(prefers-reduced-motion: reduce)").matches; };
  var watchers = [];

  function onVisible(host, fn, threshold) {
    if (!("IntersectionObserver" in window)) { fn(); return; }
    var io = new IntersectionObserver(function (es) { if (es[0].isIntersecting) { io.disconnect(); fn(); } }, { threshold: threshold || 0.4 });
    io.observe(host); watchers.push(io);
  }
  function reset() { watchers.splice(0).forEach(function (w) { try { w.disconnect(); } catch (e) {} }); }

  /* ---- traffic: storm slows it, rush hour speeds it up and adds cars ---- */
  var speed = { storm: 1, rush: 1 }, level = null, manual = false;
  function applyRate() {
    var r = speed.storm * speed.rush;
    try { document.querySelectorAll(".road .cab:not(.lead)").forEach(function (c) { c.getAnimations().forEach(function (a) { a.updatePlaybackRate(r); }); }); } catch (e) {}
  }
  function sync() {
    var l = manual ? 1 : (level == null ? 0 : level), road = document.querySelector(".road");
    speed.rush = 1 + 0.9 * l; if (road) road.classList.toggle("rush", l > 0.55);
    var b = document.querySelector(".rush-btn"); if (b) b.setAttribute("aria-pressed", String(manual));
    applyRate();
  }
  function setStorm(r) { speed.storm = r; applyRate(); }
  function traffic(l) { level = l; sync(); }
  function rushButton() {
    var b = H.el("button", "rush-btn", "Rush hour"); b.type = "button"; b.setAttribute("aria-pressed", String(manual));
    b.addEventListener("click", function () { manual = !manual; sync(); if (manual) honk(3); });
    return b;
  }

  /* ---- a few cars honk (a text bubble, no sound): when rush hour starts and when you beat the model ---- */
  function honk(n) {
    var road = document.querySelector(".road"); if (!road) return;
    var rr = road.getBoundingClientRect(), cabs = Array.prototype.filter.call(road.querySelectorAll(".cab:not(.lead)"), function (c) {
      var r = c.getBoundingClientRect(); return r.right > rr.left + 20 && r.left < rr.right - 60 && getComputedStyle(c).opacity > 0.5; });
    cabs.slice(0, n).forEach(function (cab, k) {
      setTimeout(function () {
        var cr = cab.getBoundingClientRect(), b = H.el("span", "beep", "Beep!"); b.style.left = Math.min(rr.width - 50, cr.right - rr.left + 3) + "px"; b.style.top = (cr.top - rr.top + 3) + "px";
        road.appendChild(b); setTimeout(function () { b.remove(); }, 900);
        if (still()) return; cab.classList.remove("honk"); void cab.offsetWidth; cab.classList.add("honk"); setTimeout(function () { cab.classList.remove("honk"); }, 650);
      }, k * 260);
    });
  }

  /* ---- picking a zone: the lead cab pulls over and a pickup pin pops ---- */
  function ping() {
    var c = document.querySelector(".cab.lead"); if (!c || still()) return;
    var pin = c.querySelector(".pin"); if (!pin) { pin = H.el("span", "pin"); c.appendChild(pin); }
    c.classList.remove("park"); void c.offsetWidth; c.classList.add("park"); setTimeout(function () { c.classList.remove("park"); }, 1500);
  }

  /* ---- the headline meter spins again when clicked ---- */
  function meter(box) {
    box.classList.add("replay");
    box.addEventListener("click", function () {
      box.querySelectorAll(".strip").forEach(function (s) { s.style.animation = "none"; void s.offsetWidth; s.style.animation = ""; });
    });
  }

  /* ---- numbers count up from zero ---- */
  function countUp(root) {
    if (still()) return;
    root.querySelectorAll(".big").forEach(function (n) {
      var m = /^(-?\d+(?:\.\d+)?)(.*)$/.exec(n.textContent); if (!m) return;
      var end = parseFloat(m[1]), dec = (m[1].split(".")[1] || "").length, suffix = m[2], t0 = performance.now(), D = 1100;
      (function step(now) {
        var k = Math.min(1, (now - t0) / D), e = 1 - Math.pow(1 - k, 3);
        n.textContent = (end * e).toFixed(dec) + suffix; if (k < 1) requestAnimationFrame(step);
      })(t0);
    });
  }

  /* ---- light snow over an element for a few seconds ---- */
  function snow(host, ms) {
    if (still()) return;
    var cv = document.createElement("canvas"); cv.className = "snowfx"; cv.setAttribute("aria-hidden", "true"); host.appendChild(cv);
    var w = host.clientWidth, h = host.clientHeight, dpr = Math.min(2, devicePixelRatio || 1); cv.width = w * dpr; cv.height = h * dpr;
    var g = cv.getContext("2d"), fl = [], i; g.scale(dpr, dpr);
    for (i = 0; i < 40; i++) fl.push({ x: Math.random() * w, y: Math.random() * h, r: 1 + Math.random() * 2, v: 0.5 + Math.random() * 1.1, d: Math.random() * 6 });
    var t0 = performance.now();
    (function step(now) {
      var k = (now - t0) / ms; g.clearRect(0, 0, w, h); g.fillStyle = "rgba(120,150,210,.85)";
      fl.forEach(function (f) { f.y += f.v; f.x += Math.sin(now / 700 + f.d) * 0.4; if (f.y > h) { f.y = -4; f.x = Math.random() * w; } g.beginPath(); g.arc(f.x, f.y, f.r, 0, 6.3); g.fill(); });
      cv.style.opacity = k > 0.7 ? Math.max(0, (1 - k) / 0.3) : 1;
      if (k < 1) requestAnimationFrame(step); else cv.remove();
    })(t0);
  }

  /* ---- the storm finding: bars of a normal day against the storm day, with snow, when it scrolls into view ---- */
  function stormCard(root) {
    root.querySelectorAll(".card").forEach(function (c) {
      var big = c.querySelector(".big"), lab = c.querySelector(".lab");
      if (!big || !lab || !/storm/i.test(lab.textContent)) return;
      var n = parseFloat(big.textContent); if (!isFinite(n) || n <= 1 || !/x\s*$/i.test(big.textContent)) return;
      var wrap = H.el("div", "stormbars"); wrap.setAttribute("aria-hidden", "true");
      [["typical day", 100 / n, "ty"], ["storm day", 100, "st"]].forEach(function (b) {
        var col = H.el("div", "sbcol"), bar = H.el("div", "sb " + b[2]); bar.style.height = b[1] + "%"; col.appendChild(bar); col.appendChild(H.el("span", null, b[0])); wrap.appendChild(col);
      });
      c.appendChild(wrap);
      if (still()) return;
      var bars = wrap.querySelectorAll(".sb"); bars.forEach(function (b) { b.style.opacity = 0; });
      onVisible(c, function () {
        bars.forEach(function (b, i) { b.style.opacity = 1; b.animate([{ transform: "scaleY(0)" }, { transform: "scaleY(1)" }], { duration: 700, delay: 250 + i * 350, easing: "cubic-bezier(.2,.8,.2,1)", fill: "backwards" }); });
        snow(c, 3400); countUp(c);
      }, 0.6);
    });
  }

  /* ---- bars grow in order; zero-based charts grow out from the zero line ---- */
  function bars(host, view, zero) {
    if (still()) return;
    var svg = host.querySelector("svg"); if (!svg) return;
    var items = Array.prototype.slice.call(svg.querySelectorAll(".mark-rect.role-mark path, .mark-rect.role-mark rect"));
    var sx = zero != null && view ? view.scale("x")(zero) : null;
    items.forEach(function (p) {
      var bb = p.getBBox(); p.style.transformBox = "fill-box";
      p.style.transformOrigin = sx == null ? "0 50%" : Math.max(0, Math.min(100, (sx - bb.x) / (bb.width || 1) * 100)) + "% 50%";
      p.style.opacity = 0;
    });
    setTimeout(function () { items.forEach(function (p) { p.style.opacity = 1; }); }, 9000);
    onVisible(host, function () {
      items.forEach(function (p, i) { p.style.opacity = 1; p.animate([{ transform: "scaleX(0)" }, { transform: "scaleX(1)" }], { duration: 520, delay: i * 55, easing: "cubic-bezier(.2,.8,.2,1)", fill: "backwards" }); });
    }, 0.3);
  }

  /* ---- heatmap wipes in left to right ---- */
  function sweep(host) {
    if (still()) return;
    var g = host.querySelector(".mark-rect.role-mark"); if (!g) return;
    g.style.opacity = 0; setTimeout(function () { g.style.opacity = 1; }, 9000);
    onVisible(host, function () {
      g.style.opacity = 1; g.animate([{ clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0 0 0)" }], { duration: 1300, easing: "cubic-bezier(.4,.1,.2,1)", fill: "backwards" });
    }, 0.3);
  }

  /* ---- the scoreboard receipt prints out line by line, with the numbers counting up ---- */
  function print(rc) {
    if (still()) return;
    rc.animate([{ clipPath: "inset(0 0 100% 0)" }, { clipPath: "inset(0 0 0 0)" }], { duration: 1500, easing: "steps(22, end)", fill: "backwards" });
    rc.querySelectorAll(".rc-row").forEach(function (r, i) {
      r.animate([{ opacity: 0, transform: "translateY(-6px)" }, { opacity: 1, transform: "none" }], { duration: 260, delay: 250 + i * 150, easing: "ease-out", fill: "backwards" });
      var b = r.querySelector("b"); if (!b) return; var end = parseFloat(b.textContent); if (!isFinite(end)) return; var dec = (b.textContent.split(".")[1] || "").length, t0 = performance.now() + 250 + i * 150;
      (function step(now) { var k = Math.max(0, Math.min(1, (now - t0) / 700)); b.textContent = (end * (1 - Math.pow(1 - k, 3))).toFixed(dec); if (k < 1) requestAnimationFrame(step); })(performance.now());
    });
  }

  /* ---- dispatch log: lines are typed out one after another when it scrolls into view ---- */
  function dispatch(panel) {
    if (still()) return;
    var lines = panel.querySelectorAll(".dl-line"); lines.forEach(function (l) { l.style.opacity = 0; });
    onVisible(panel, function () {
      lines.forEach(function (l, i) {
        l.style.opacity = 1;
        l.animate([{ clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0 0 0)" }], { duration: 900, delay: i * 700, easing: "steps(32, end)", fill: "backwards" });
      });
    }, 0.4);
    setTimeout(function () { lines.forEach(function (l) { l.style.opacity = 1; }); }, 9000);
  }

  /* ---- map zones breathe in proportion to demand (busy zones faster and stronger) ---- */
  function pulse(host, values, ref) {
    if (still()) return;
    var svg = host.querySelector("svg"); if (!svg) return;
    var paths = svg.querySelectorAll(".mark-shape.role-mark path"), top = ref || Math.max.apply(null, values.concat([1e-9]));
    paths.forEach(function (p, i) {
      var v = values[i]; if (v == null) return; var k = v / top;
      p.style.animation = "zpulse " + (3.4 - 2.2 * k).toFixed(2) + "s ease-in-out " + ((i * 137) % 900) + "ms infinite alternate";
      p.style.setProperty("--lo", String((1 - 0.45 * k).toFixed(2))); if (k >= 0.75) p.classList.add("hot");
    });
    host.classList.add("pulsing");
    if ("IntersectionObserver" in window) { var io = new IntersectionObserver(function (es) { host.classList.toggle("off", !es[0].isIntersecting); }); io.observe(host); watchers.push(io); }
  }

  /* ---- table rows slide to their new places when re-sorted ---- */
  function flip(before, rows, keyOf) {
    if (still()) return;
    rows.forEach(function (r) {
      var k = keyOf(r), old = before[k]; if (old == null) return;
      var d = old - r.getBoundingClientRect().top; if (Math.abs(d) < 1) return;
      r.animate([{ transform: "translateY(" + d + "px)" }, { transform: "none" }], { duration: 380, easing: "cubic-bezier(.2,.7,.2,1)" });
    });
  }

  /* ---- dark mode: a circular wipe out from the switch ---- */
  function wipe(from, change) {
    if (!document.startViewTransition || still()) { change(); return; }
    var r = from.getBoundingClientRect(), s = document.documentElement.style;
    s.setProperty("--vx", Math.round(r.left + r.width / 2) + "px"); s.setProperty("--vy", Math.round(r.top + r.height / 2) + "px");
    try { document.startViewTransition(function () { change(); return new Promise(function (ok) { setTimeout(ok, 320); }); }); } catch (e) { change(); }
  }

  H.motion = { reset: reset, setStorm: setStorm, traffic: traffic, sync: sync, rushButton: rushButton, print: print, dispatch: dispatch, honk: honk, ping: ping, meter: meter, countUp: countUp,
    snow: snow, stormCard: stormCard, bars: bars, sweep: sweep, pulse: pulse, flip: flip, wipe: wipe, still: still };
})();
