/* racingsim race viewer: watch a race you ran, lap by lap.
 *
 * The engine records a frame per step (racingsim/sim/engine.py `_frame`): the running order with each
 * car's gap to the leader in tenths of a second (laps down included) and a code (pitted, out). The
 * viewer animates between frames: the leader goes round the track once a lap and every car sits its
 * gap behind, so passes, pit cycles, cautions bunching the field and lapped traffic all show up.
 */
"use strict";

const W = { timer: null, gen: 0 };   // the running animation (one viewer at a time) and which page owns it

// ---------------------------------------------------------------- track shapes
function trackShape(type, seed) {
  const pts = [];
  let start = 0;   // raw position of the start/finish line
  const N = 480;
  const cx = 400, cy = 230;
  if (type === "road") {
    // A winding road course: a closed curve with a few seeded harmonics (always the same for a track).
    let s = seed || 7;
    const rnd = () => { s = (s * 9301 + 49297) % 233280; return s / 233280; };
    const harm = [2, 3, 4, 5].map((k) => ({ k, a: (0.05 + rnd() * 0.11) / (k / 2), p: rnd() * Math.PI * 2 }));
    for (let i = 0; i < N; i++) {
      const t = (i / N) * Math.PI * 2;
      let r = 1;
      for (const h of harm) r += h.a * Math.cos(h.k * t + h.p);
      pts.push([cx + Math.cos(t) * 300 * r, cy + Math.sin(t) * 165 * r]);
    }
  } else {
    // Ovals: two turns joined by straights; longer straights for bigger tracks; a dogleg front
    // stretch on intermediates and superspeedways (tri-ovals).
    const straight = { short: 150, dirt: 120, intermediate: 230, superspeedway: 300 }[type] ?? 180;
    const rad = { short: 135, dirt: 140, intermediate: 150, superspeedway: 155 }[type] ?? 140;
    const tri = type === "intermediate" || type === "superspeedway" ? 34 : 0;
    const per = 2 * straight + 2 * Math.PI * rad;
    start = straight / 2 / per;   // the middle of the front stretch
    for (let i = 0; i < N; i++) {
      let d = (i / N) * per;
      let x, y;
      if (d < straight) {                                       // front stretch (bottom), right to left
        const u = d / straight;
        x = cx + straight / 2 - d; y = cy + rad + tri * Math.sin(Math.PI * u);
      } else if ((d -= straight) < Math.PI * rad) {             // turns 1-2 (left)
        const a = Math.PI / 2 + d / rad;
        x = cx - straight / 2 + Math.cos(a) * rad; y = cy + Math.sin(a) * rad;
      } else if ((d -= Math.PI * rad) < straight) {             // back stretch (top), left to right
        x = cx - straight / 2 + d; y = cy - rad;
      } else {                                                   // turns 3-4 (right)
        d -= straight;
        const a = -Math.PI / 2 + d / rad;
        x = cx + straight / 2 + Math.cos(a) * rad; y = cy + Math.sin(a) * rad;
      }
      pts.push([x, y]);
    }
  }
  // Even spacing by distance, so a car's speed along the drawing is steady.
  const cum = [0];
  for (let i = 1; i <= N; i++) {
    const [ax, ay] = pts[i - 1], [bx, by] = pts[i % N];
    cum.push(cum[i - 1] + Math.hypot(bx - ax, by - ay));
  }
  const total = cum[N];
  // Cars turn left: run the drawing backwards (counter-clockwise on screen) from the start/finish line.
  const at = (f) => {
    f = (((start - f) % 1) + 1) % 1;
    const target = f * total;
    let lo = 0, hi = N;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (cum[m] <= target) lo = m; else hi = m; }
    const [ax, ay] = pts[lo], [bx, by] = pts[(lo + 1) % N];
    const u = (target - cum[lo]) / Math.max(1e-6, cum[lo + 1] - cum[lo]);
    return [ax + (bx - ax) * u, ay + (by - ay) * u];
  };
  // Inside line (pit road) for cars stopping.
  const inner = (f, by) => {
    const [x, y] = at(f), [x2, y2] = at(f + 0.002);
    const dx = x2 - x, dy = y2 - y, l = Math.hypot(dx, dy) || 1;
    return [x + (dy / l) * by, y - (dx / l) * by];   // the inside of a left-turning track
  };
  const d = "M" + pts.map((p) => p[0].toFixed(1) + "," + p[1].toFixed(1)).join("L") + "Z";
  return { d, at, inner };
}

// ---------------------------------------------------------------- page
async function watchPage(key, ev, year) {
  if (W.timer) { cancelAnimationFrame(W.timer); W.timer = null; }
  const gen = ++W.gen;
  const r = await api(`replay/${encodeURIComponent(key)}/${ev}${year ? "?year=" + year : ""}`);
  if (gen !== W.gen) return;          // another race was opened while this one loaded
  const rp = r.replay;
  const cars = rp.cars;
  const frames = rp.frames;
  const lapS = rp.lap_s;
  const type = rp.track_type;
  const shape = trackShape(type, r.seed);
  const surface = type === "dirt" ? "#7a4b2a" : "#3b3f46";
  const infield = type === "road" ? "#2f6a3a" : "#2c5e35";
  const me = cars.findIndex((c) => c.me);
  const log = (r.log || []).slice().sort((a, b) => a[0] - b[0]);
  const lastLap = frames.length ? frames[frames.length - 1][0] : rp.laps;
  const color = (c) => (c.me ? "#ffd400" : `hsl(${c.hue},72%,48%)`);
  // Yellows, limes and cyans are light: they get dark numbers.
  const ink = (c) => (c.me || (c.hue >= 40 && c.hue <= 200) ? "#111" : "#fff");

  view(`<div class="watch">
    <div class="watch-head">
      <div><div class="watch-series">${esc(r.jewel || (r.series && r.series.name) || "Race")}</div>
        <div class="watch-track">${esc(r.track)} <span class="muted">· ${esc(r.label)}${r.length_mi ? ` · ${r.length_mi} mi` : ""}${r.race && r.race.weather ? ` · ${esc(r.race.weather)}` : ""}</span></div></div>
      <div class="watch-lap"><span id="w-lap">0</span><span class="muted"> / ${rp.laps}${rp.scheduled > rp.laps ? ` (${rp.scheduled} scheduled)` : ""}</span><div class="muted small">LAP</div></div>
      <div id="w-flag" class="flag green" role="status" aria-live="polite">GREEN</div>
    </div>
    <div class="watch-body">
      <div class="watch-track-box">
        <svg viewBox="0 0 800 460" id="w-svg" role="img" aria-label="Track map with cars">
          <rect width="800" height="460" fill="${infield}" rx="14"/>
          <path d="${shape.d}" fill="none" stroke="#1e2126" stroke-width="40" stroke-linejoin="round"/>
          <path d="${shape.d}" fill="none" stroke="${surface}" stroke-width="34" stroke-linejoin="round"/>
          <path d="${shape.d}" fill="none" stroke="rgba(255,255,255,.25)" stroke-width="1" stroke-dasharray="6 10"/>
          <g id="w-sf"></g>
          <g id="w-cars"></g>
        </svg>
        <div class="watch-controls">
          <button data-act="w-play" id="w-play" class="primary">❚❚ Pause</button>
          <select id="w-speed" title="Laps per second" aria-label="Playback speed">
            ${[[0.25, "Slow"], [1, "Normal"], [3, "Fast"], [10, "Very fast"], [30, "Flat out"]].map(([v, l]) => `<option value="${v}">${l} (${v} lap/s)</option>`).join("")}
          </select>
          <input type="range" id="w-scrub" min="0" max="${lastLap}" step="0.1" value="0" style="flex:1" aria-label="Race position (lap)">
          <button data-act="w-end">Finish ⏭</button>
        </div>
        <div id="w-ticker" class="watch-ticker"></div>
      </div>
      <div class="watch-board"><div class="watch-board-head"><span>POS</span><span>CAR</span><span>DRIVER</span><span>GAP</span></div><div id="w-board"></div>
        <div id="w-final"></div></div>
    </div>
  </div>`);

  // start/finish line
  const [sx, sy] = shape.at(0), [tx, ty] = shape.at(0.004);
  const nx = -(ty - sy), ny = tx - sx, nl = Math.hypot(nx, ny) || 1;
  $("#w-sf").innerHTML = `<line x1="${sx + (nx / nl) * 20}" y1="${sy + (ny / nl) * 20}" x2="${sx - (nx / nl) * 20}" y2="${sy - (ny / nl) * 20}" stroke="#fff" stroke-width="5" stroke-dasharray="4 4"/>`;
  // The player's car is drawn last, on top of the pack.
  const order = cars.map((c, i) => i).sort((a, b) => (cars[a].me ? 1 : 0) - (cars[b].me ? 1 : 0));
  $("#w-cars").innerHTML = order.map((i) => { const c = cars[i]; return `<g id="wc-${i}" class="wcar${c.me ? " me" : ""}"><circle r="${c.me ? 10 : 8}" fill="${color(c)}" stroke="${c.me ? "#000" : "rgba(0,0,0,.55)"}" stroke-width="${c.me ? 2.5 : 1.2}"/><text text-anchor="middle" dy="3.5" font-size="${c.me ? 10 : 9}" font-weight="700" fill="${ink(c)}">${c.num}</text></g>`; }).join("")
    + `<g id="w-pace" style="display:none"><rect x="-9" y="-6" width="18" height="12" rx="3" fill="#ffd400" stroke="#000"/><text text-anchor="middle" dy="3.5" font-size="7" font-weight="700">PACE</text></g>`;
  const carEls = cars.map((_, i) => $(`#wc-${i}`));
  const defaultSpeed = Math.max(0.25, Math.min(10, rp.laps / 90));
  const speedSel = $("#w-speed");
  speedSel.value = [0.25, 1, 3, 10, 30].reduce((a, b) => (Math.abs(b - defaultSpeed) < Math.abs(a - defaultSpeed) ? b : a));

  const st = { t: 0, playing: true, last: performance.now(), drag: false, board: "", flag: "", title: "" };
  // Before the green: the field in its starting order, a few tenths apart.
  const grid = [0, "G", cars.map((c, i) => [i, Math.round((c.start || i) * 3), 0]).sort((a, b) => a[1] - b[1])];

  // frame index whose lap is the first >= t
  const frameAt = (t) => {
    let lo = 0, hi = frames.length - 1;
    while (lo < hi) { const m = (lo + hi) >> 1; if (frames[m][0] < t) lo = m + 1; else hi = m; }
    return lo;
  };
  const gapsOf = (fr) => { const g = {}; fr[2].forEach((row, i) => { g[row[0]] = { gap: row[1], code: row[2], pos: i }; }); return g; };

  function draw() {
    if (!frames.length) return;
    const t = Math.min(st.t, lastLap);
    const bi = frameAt(t);
    const B = frames[bi], A = bi > 0 ? frames[bi - 1] : grid;
    const span = Math.max(1e-6, B[0] - A[0]);
    const u = Math.min(1, Math.max(0, (t - A[0]) / span));
    const ga = gapsOf(A), gb = gapsOf(B);
    const leadFrac = t % 1;
    // A frame is flagged at the end of its step: the caution comes out after the crash, part way round.
    const yellow = B[1] === "Y" && (A[1] === "Y" || u > 0.6);
    const done = st.t >= lastLap;
    cars.forEach((c, i) => {
      const a = ga[i], b = gb[i];
      const el = carEls[i];
      if (!b || b.gap < 0) {   // out of the race: parked in the infield
        const k = B[2].findIndex((row) => row[0] === i) - B[2].filter((row) => row[1] >= 0).length;
        el.setAttribute("transform", `translate(${30 + (k % 20) * 19},${442 - Math.floor(k / 20) * 19})`);
        el.style.opacity = 0.35;
        return;
      }
      const gapA = a && a.gap >= 0 ? a.gap : b.gap;
      const gap = (gapA + (b.gap - gapA) * u) / 10;
      let f = leadFrac - gap / lapS;
      if (done) f = -(b.pos * 0.012);                // the field lines up behind the checkered flag
      const [x, y] = b.code === 1 && !done ? shape.inner(f, 26) : shape.at(f);
      el.setAttribute("transform", `translate(${x.toFixed(1)},${y.toFixed(1)})`);
      el.style.opacity = b.code === 1 ? 0.75 : 1;
    });
    const pace = $("#w-pace");
    if (yellow && !done) {
      const [px, py] = shape.at(leadFrac + 0.03);
      pace.setAttribute("transform", `translate(${px.toFixed(1)},${py.toFixed(1)})`);
      pace.style.display = "";
    } else pace.style.display = "none";
    // flag, lap counter
    const flag = $("#w-flag");
    const lapNow = Math.min(rp.laps, Math.max(1, Math.ceil(t)));
    $("#w-lap").textContent = done ? lastLap : lapNow;
    const [fc, ft] = done ? ["checkered", "CHECKERED"] : yellow ? ["yellow", "CAUTION"]
      : rp.laps - lapNow === 0 ? ["white", "WHITE FLAG"] : ["green", "GREEN"];
    if (st.flag !== fc) { st.flag = fc; flag.className = "flag " + fc; flag.textContent = ft; }
    if (!st.drag) $("#w-scrub").value = t.toFixed(1);
    // leaderboard and ticker: only when the frame changes
    const boardKey = `${bi}:${done}:${yellow}:${Math.floor(t)}`;
    if (boardKey === st.board) { if (done) showFinal(); return; }
    st.board = boardKey;
    const rows = B[2].filter((row) => row[1] >= 0);
    const out = B[2].filter((row) => row[1] < 0);
    const lead = rows.length ? rows[0][1] : 0;
    $("#w-board").innerHTML = rows.map((row, k) => {
      const c = cars[row[0]];
      const gapS = (row[1] - lead) / 10;
      const down = Math.floor(gapS / lapS);
      const gtxt = k === 0 ? "LEADER" : down >= 1 ? `−${down} lap${down > 1 ? "s" : ""}` : `+${gapS.toFixed(1)}`;
      return `<div class="wrow${c.me ? " me" : ""}"><span>${k + 1}</span><span class="wnum" style="background:${color(c)};color:${ink(c)}">${c.num}</span><span class="wname">${esc(c.name)}${row[2] === 1 ? ' <span class="wpit">PIT</span>' : ""}</span><span class="wgap">${gtxt}</span></div>`;
    }).join("") + (out.length ? `<div class="wout">OUT: ${out.map((row) => `${esc(cars[row[0]].name)} (${row[2] === 2 ? "crash" : "mechanical"})`).join(", ")}</div>` : "");
    // ticker
    // Under a fresh caution the ticker already says why (the crash is logged at the end of the step).
    const lines = log.filter((l) => l[0] <= (done ? 1e9 : yellow ? Math.max(t, B[0]) : t)).slice(-7).reverse();
    $("#w-ticker").innerHTML = lines.map((l) => `<div><b>${l[0] ? "Lap " + l[0] : "Pre-race"}</b> ${esc(l[1])}</div>`).join("") || '<div class="muted">Drivers, start your engines.</div>';
    if (me >= 0) {
      const p = rows.findIndex((row) => row[0] === me);
      const title = p >= 0 ? `You're running P${p + 1}` : "";
      if (title !== st.title) { st.title = title; $("#w-play").title = title; }
    }
    if (done) showFinal();
  }

  function showFinal() {
    const box = $("#w-final");
    if (box.dataset.shown) return;
    box.dataset.shown = "1";
    const myPos = rp.finish.indexOf(me) + 1;
    box.innerHTML = `<div class="watch-final"><b>🏁 ${esc(cars[rp.finish[0]].name)} wins</b>${me >= 0 ? `<div>You finished <b>P${myPos}</b> of ${cars.length}</div>` : ""}
      <a class="link" href="#/race/${encodeURIComponent(key)}/${ev}${year ? "/" + year : ""}">Full box score →</a></div>`;
    st.playing = false;
    $("#w-play").textContent = "▶ Replay";
  }

  function tick(now) {
    if (gen !== W.gen || !document.getElementById("w-svg")) { if (gen === W.gen) W.timer = null; return; }   // navigated away
    const dt = Math.min(0.1, (now - st.last) / 1000);
    st.last = now;
    if (st.playing) st.t = Math.min(lastLap, st.t + dt * Number(speedSel.value));
    draw();
    W.timer = requestAnimationFrame(tick);
  }
  on("w-play", () => {
    if (st.t >= lastLap) { st.t = 0; $("#w-final").innerHTML = ""; delete $("#w-final").dataset.shown; }
    st.playing = !st.playing;
    $("#w-play").textContent = st.playing ? "❚❚ Pause" : "▶ Play";
  });
  on("w-end", () => { st.t = lastLap; });
  const scrub = $("#w-scrub");
  scrub.addEventListener("pointerdown", () => { st.drag = true; });
  ["pointerup", "pointercancel", "change", "blur"].forEach((ev2) => scrub.addEventListener(ev2, () => { st.drag = false; }));
  scrub.addEventListener("input", (e) => {
    st.t = Number(e.target.value);
    if (st.t < lastLap && $("#w-final").dataset.shown) {
      $("#w-final").innerHTML = ""; delete $("#w-final").dataset.shown;
      $("#w-play").textContent = st.playing ? "❚❚ Pause" : "▶ Play";
    }
  });
  W.timer = requestAnimationFrame(tick);
}
