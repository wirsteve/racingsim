/* racingsim UI — vanilla JS single-page app talking to the local Python server. */
"use strict";

// ---------------------------------------------------------------- utilities
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const S = { status: null, setup: null, handlers: {}, tables: {}, route: "" };

async function api(path, body) {
  const opt = body !== undefined
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : {};
  const r = await fetch("/api/" + path, opt);
  let j = {};
  try { j = await r.json(); } catch (_) { /* ignore */ }
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}

// Internal values are 2025 dollars; show the season's nominal dollars.
function money(x, idx) {
  if (x === null || x === undefined) return "—";
  const k = idx !== undefined ? idx : (S.status && S.status.price_index) || 1;
  x = x * k;
  const a = Math.abs(x);
  if (a >= 1e6) return `$${(x / 1e6).toFixed(a >= 1e7 ? 0 : 1)}M`;
  if (a >= 1e3) return `$${Math.round(x / 1e3)}k`;
  return `$${Math.round(x)}`;
}
const pct = (x) => `${Math.round(x * 100)}%`;
const initials = (n) => n.split(" ").map((p) => p[0]).join("").slice(0, 2).toUpperCase();
const TIER_COLORS = ["#8a94a6", "#6b7a99", "#4f6aa8", "#3d5fc4", "#6b4fc4", "#a1449c", "#c23d6b", "#d6402b"];
const DISC_LABEL = { karting: "Karting", stock_car: "Stock car", dirt_oval: "Dirt oval", open_wheel: "Open wheel",
  sports_car: "Sports car", touring_car: "Touring car", club_road: "Club road" };
const discColor = (d) => `var(--d-${d})`;

function tierBadge(t, name) {
  if (t === null || t === undefined) return `<span class="badge">—</span>`;
  return `<span class="badge tier" style="background:${TIER_COLORS[t]}" title="${esc(name || "Tier " + t)}">T${t}</span>`;
}
const discBadge = (d) => d ? `<span class="badge disc" style="background:${discColor(d)}">${esc(DISC_LABEL[d] || d)}</span>` : "";
function ratingColor(v) {
  if (v >= 65) return "#7c4dff"; if (v >= 55) return "#2a6fd6"; if (v >= 45) return "#1f9d55";
  if (v >= 35) return "#c98a12"; return "#c4352b";
}
function rating(v, opts = {}) {
  if (v === null || v === undefined) return "—";
  const w = Math.max(4, Math.min(100, ((v - 20) / 60) * 100));
  return `<span class="rating" title="${opts.title || "20-80 scale"}"><b>${v}</b><span class="bar"><i style="width:${w}%;background:${ratingColor(v)}"></i></span></span>`;
}
const driverLink = (id, name, me, real) => `<a class="link" href="#/driver/${id}">${esc(name)}</a>${me ? ' <span class="badge warn">YOU</span>' : ""}${real ? ' <span class="badge" title="Real driver">R</span>' : ""}`;
const seriesLink = (s) => s ? `<a class="link" href="#/series/${encodeURIComponent(s.id)}">${esc(s.name)}</a>` : `<span class="muted">—</span>`;
const teamLink = (t) => t ? (t.id == null ? esc(t.name) : `<a class="link" href="#/team/${t.id}">${esc(t.name)}</a>`) : `<span class="muted">own car</span>`;
const trackLink = (id, name) => `<a class="link" href="#/track/${encodeURIComponent(id)}">${esc(name)}</a>`;
function posCell(p, field) {
  if (!p) return "—";
  const cls = p === 1 ? "pos-1" : p <= 5 ? "pos-top5" : "";
  return `<span class="${cls}">P${p}</span>${field ? `<span class="muted small">/${field}</span>` : ""}`;
}
function statusBadge(s) {
  const m = { active: ["good", "Active"], part_time: ["warn", "Part-time"], sidelined: ["bad", "Sidelined"], retired: ["", "Retired"] };
  const [cls, label] = m[s] || ["", s];
  return `<span class="badge ${cls}">${label}</span>`;
}

function toast(msg, isError = false, ms = 4200) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = isError ? "error" : "";
  t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.hidden = true), ms);
}

// Sortable client-side table. cols: {key,label,render,sort,num}
function table(id, cols, rows, opts = {}) {
  S.tables[id] = { cols, rows, opts, sortKey: opts.sortKey || null, dir: opts.dir || 1 };
  return `<div class="table-wrap ${opts.tall ? "tall" : ""}" id="tbl-${id}">${renderTable(id)}</div>`;
}
function renderTable(id) {
  const T = S.tables[id];
  let rows = T.rows.slice();
  if (T.sortKey) {
    const c = T.cols.find((c) => c.key === T.sortKey);
    const f = c.sort || ((r) => r[c.key]);
    rows.sort((a, b) => {
      const x = f(a), y = f(b);
      if (x === y) return 0;
      if (x === null || x === undefined) return 1;
      if (y === null || y === undefined) return -1;
      return (x > y ? 1 : -1) * T.dir;
    });
  }
  if (!rows.length) return `<div class="empty">${T.opts.empty || "Nothing here yet."}</div>`;
  const head = T.cols.map((c) => `<th class="${c.num ? "num" : ""} ${c.nosort ? "" : "sortable"}" data-sort="${id}:${c.key}">${c.label}${T.sortKey === c.key ? (T.dir > 0 ? " ▲" : " ▼") : ""}</th>`).join("");
  const body = rows.map((r) => `<tr class="${T.opts.rowClass ? T.opts.rowClass(r) : ""}">${T.cols.map((c) => `<td class="${c.num ? "num" : ""} ${c.cls || ""}">${c.render ? c.render(r) : esc(r[c.key] ?? "—")}</td>`).join("")}</tr>`).join("");
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}
document.addEventListener("click", (e) => {
  const th = e.target.closest("th[data-sort]");
  if (th) {
    const [id, key] = th.dataset.sort.split(":");
    const T = S.tables[id];
    if (!T || T.cols.find((c) => c.key === key)?.nosort) return;
    T.dir = T.sortKey === key ? -T.dir : (T.cols.find((c) => c.key === key)?.num ? -1 : 1);
    T.sortKey = key;
    $("#tbl-" + id).innerHTML = renderTable(id);
    return;
  }
  const a = e.target.closest("[data-act]");
  if (a && S.handlers[a.dataset.act]) {
    e.preventDefault();
    S.handlers[a.dataset.act](a, e);
  }
});
document.addEventListener("change", (e) => {
  const a = e.target.closest("[data-change]");
  if (a && S.handlers[a.dataset.change]) S.handlers[a.dataset.change](a, e);
});

function view(html) { $("#view").innerHTML = html; window.scrollTo(0, 0); }
function on(name, fn) { S.handlers[name] = fn; }

// ---------------------------------------------------------------- chrome
async function refreshStatus() {
  S.status = await api("status");
  renderChrome();
}

function renderChrome() {
  const st = S.status || { phase: "none" };
  const clock = $("#clock"), ctl = $("#sim-controls"), pc = $("#player-card");
  const inGame = st.phase !== "none";
  $$("#nav a").forEach((a) => {
    const n = a.dataset.nav;
    a.style.display = !inGame && !["new", "saves", "encyclopedia"].includes(n) ? "none" : "";
  });
  $("#nav-offseason").classList.toggle("attention", st.phase === "offseason");
  if (!inGame) {
    clock.innerHTML = `<span class="year">racingsim</span><span class="wk">No career loaded</span>`;
    ctl.innerHTML = `<a class="btn primary" href="#/new">New career</a>`;
    pc.innerHTML = "";
    return;
  }
  if (st.phase === "season") {
    const prog = Math.round((st.week / st.weeks) * 100);
    clock.innerHTML = `<span class="year">${st.year}</span><span class="wk">${esc(st.label)}</span>
      <span class="progress" title="${st.week}/${st.weeks} weeks"><i style="width:${prog}%"></i></span>`;
    const nr = st.player && st.player.next_race_week;
    ctl.innerHTML = `
      <button data-act="sim" data-until="week">Next week</button>
      <button data-act="sim" data-until="race" ${nr ? "" : "disabled"} title="${nr ? "Your next race: week " + nr : "No more races for you this season"}">Next race ▸</button>
      <button class="primary" data-act="sim" data-until="season">Sim to season end ▸▸</button>`;
  } else {
    clock.innerHTML = `<span class="year">${st.year}</span><span class="wk">Off-season · silly season</span>`;
    ctl.innerHTML = `<a class="btn primary" href="#/offseason">Make off-season decisions →</a>`;
  }
  const p = st.player;
  if (p) {
    pc.innerHTML = `<div class="pc"><div class="name">${esc(p.name)}</div>
      <div class="meta">Age ${p.age} · ${statusBadge(p.status)}</div>
      <div class="line">${p.series ? `${tierBadge(p.series.tier, p.series.tier_name)} ${esc(p.series.name)}` : '<span class="meta">No ride</span>'}</div>
      <div class="line meta">${p.team ? esc(p.team.name) : "Own car"} · ${money(p.funding)} budget</div></div>`;
  } else pc.innerHTML = "";
}

on("sim", async (el) => {
  const until = el.dataset.until;
  $$("#sim-controls button").forEach((b) => b.classList.add("busy"));
  const before = S.status;
  try {
    const r = await api("sim", { until });
    S.status = r.status;
    renderChrome();
    if (S.status.phase === "offseason") {
      toast(`Season ${before.year} complete. Time for the silly season.`);
      location.hash = "#/offseason";
      if (S.route === "#/offseason") route();
      return;
    }
    const news = await api("news?kind=player&limit=1");
    if (until !== "week" && news[0]) toast(news[0].text);
    route();
  } catch (err) {
    toast(err.message, true);
  } finally {
    $$("#sim-controls button").forEach((b) => b.classList.remove("busy"));
  }
});

// ---------------------------------------------------------------- pages
async function dashboardPage() {
  const d = await api("dashboard");
  const me = d.driver;
  if (!me) { view(`<div class="card empty">No player driver. <a class="link" href="#/new">Start a career</a>.</div>`); return; }
  const st = d.status;
  const standings = d.standings || [];
  const mine = d.my_standing;
  const stRows = standings.slice();
  if (mine && !stRows.find((r) => r.is_player)) stRows.push(mine);
  const retired = me.status === "retired";
  const callout = retired ? `<div class="callout">You've hung up the helmet. The world keeps turning — follow the drivers you raced with, or <a class="link" href="#/new">start a new career</a>.</div>`
    : !me.series ? `<div class="callout">You don't have a ride this season. Use the off-season to find one — or pitch sponsors to afford one.</div>` : "";
  view(`
    ${callout}
    ${heroCard(me)}
    <div class="grid g-main" style="margin-top:16px">
      <div class="grid">
        <div class="card flush">
          <div class="card-head" style="padding:14px 16px 0"><h3>Standings · ${me.series ? esc(me.series.name) : "—"}</h3>
          ${me.series ? `<a class="link small" href="#/series/${encodeURIComponent(me.series.id)}">Full series →</a>` : ""}</div>
          ${me.series ? table("dash-st", standingCols(), stRows, { rowClass: (r) => (r.is_player ? "me" : ""), empty: "No races run yet — standings appear after the first race." }) : '<div class="empty">—</div>'}
        </div>
        <div class="grid g2">
          <div class="card flush"><h3>Coming up</h3>${scheduleTable("dash-up", d.upcoming || [], me.series, false)}</div>
          <div class="card flush"><h3>Recent races</h3>${scheduleTable("dash-recent", (d.recent || []).slice().reverse(), me.series, true)}</div>
        </div>
      </div>
      <div class="grid">
        ${(d.advice || []).length ? `<div class="card"><h3>Paddock talk</h3><ul class="timeline">${d.advice.map((a) => `<li>${esc(a)}</li>`).join("")}</ul></div>` : ""}
        ${d.status.phase === "season" && !retired ? `<div class="card"><h3>Combines & shootouts</h3><p class="muted small" style="margin-top:0">Apply now; they run at the end of the season. An application guarantees an invite — you still have to win.</p>
          ${(d.opportunities || []).map((o) => `<div class="news-item"><div style="flex:1"><div><b>${esc(o.name)}</b></div>
            <div class="muted small">${o.winners > 1 ? `Top ${o.winners} each get` : "Winner gets"} ${money(o.award)} toward the ${esc(o.target || "next step")} · ages ${o.min_age}–${o.max_age}</div>
            ${o.eligible ? `<label class="small" style="display:flex;gap:6px;align-items:center;margin-top:4px"><input type="checkbox" data-change="apply" data-key="${o.key}" ${o.applied ? "checked" : ""}> Apply</label>`
              : `<div class="muted small">Needs ${esc(o.why_not)}</div>`}</div></div>`).join("")}</div>` : ""}
        <div class="card"><div class="card-head"><h3>Crown jewels</h3><a class="link small" href="#/jewels">All →</a></div>
          ${(() => { const up = d.jewels.filter((j) => !j.done); const el = up.filter((j) => j.eligible);
            return jewelList(el.slice(0, 5), true) + (!retired && up.length > el.length ? `<div class="muted small" style="margin-top:8px">${up.length - el.length} more this season you can't enter yet.</div>` : ""); })()}</div>
        <div class="card"><div class="card-head"><h3>News wire</h3><a class="link small" href="#/news">All →</a></div>${newsList(d.news.slice(0, 14))}</div>
      </div>
    </div>`);
}

function heroCard(me) {
  const r = me.ratings;
  const where = me.series ? `${seriesLink(me.series)} · ${teamLink(me.team)}` : `<span class="muted">No ride</span>`;
  return `<div class="card hero">
    <div class="avatar">${initials(me.name)}</div>
    <div><h1>${esc(me.name)} ${me.is_player ? '<span class="badge warn">YOU</span>' : ""}${me.real ? ` <span class="badge good">real driver</span>${me.wiki ? ` <a class="link small" target="_blank" rel="noopener" href="https://en.wikipedia.org/wiki/${encodeURIComponent(me.wiki)}">Wikipedia ↗</a>` : ""}` : ""}</h1>
      <div class="sub">Age ${me.age} · ${esc(me.home_name)} · ${statusBadge(me.status)} ${me.series ? tierBadge(me.series.tier, me.series.tier_name) + " " + discBadge(me.series.discipline) : ""}</div>
      <div class="sub" style="margin-top:4px">${where}</div></div>
    <div class="kpis">
      <div class="kpi"><div class="v">${rating(r.overall)}</div><div class="l">Overall${r.exact ? "" : " (scouted)"}</div></div>
      <div class="kpi"><div class="v">${rating(r.potential)}</div><div class="l">Potential</div></div>
      <div class="kpi"><div class="v">${me.reputation}</div><div class="l">Reputation</div></div>
      <div class="kpi"><div class="v">${me.exposure}</div><div class="l">Exposure</div></div>
      <div class="kpi"><div class="v">${me.wins}</div><div class="l">Wins</div></div>
      <div class="kpi"><div class="v">${me.titles}</div><div class="l">Titles</div></div>
      ${me.finances && me.finances.available !== undefined ? `<div class="kpi"><div class="v">${money(me.finances.available)}</div><div class="l">Budget</div></div>` : ""}
    </div></div>`;
}

const standingCols = () => [
  { key: "pos", label: "Pos", num: true, render: (r) => posCell(r.pos) },
  { key: "name", label: "Driver", render: (r) => driverLink(r.driver_id, r.name, r.is_player) },
  { key: "team", label: "Team", render: (r) => teamLink(r.team), sort: (r) => r.team?.name || "" },
  { key: "starts", label: "St", num: true },
  { key: "wins", label: "W", num: true },
  { key: "top5", label: "T5", num: true },
  { key: "avg_finish", label: "Avg", num: true },
  { key: "points", label: "Pts", num: true, render: (r) => (r.points ?? (r.champion ? "🏆" : "—")) },
];

function scheduleTable(id, rows, series, results) {
  const cols = [
    { key: "week", label: "When", render: (r) => `<span class="nowrap">${esc(r.label)}</span>`, num: false },
    { key: "track", label: "Track", render: (r) => `${trackLink(r.track_id, r.track)} <span class="muted small">${esc(r.city || "")}${r.region ? ", " + esc(r.region) : ""}</span>` },
  ];
  if (results) {
    cols.push({ key: "winner", label: "Winner", render: (r) => (r.winner ? driverLink(r.winner.id, r.winner.name) : "—"), sort: (r) => r.winner?.name });
    cols.push({ key: "player_pos", label: "You", num: true, render: (r) => posCell(r.player_pos) });
    cols.push({ key: "x", label: "", nosort: true, render: (r) => (r.winner && r.has_results && series ? `<a class="link small" href="#/race/${encodeURIComponent(series.id)}/${r.event}">Results</a>` : "") });
  }
  return table(id, cols, rows, { empty: results ? "No races yet." : "No more races this season." });
}

function newsList(items) {
  if (!items.length) return `<div class="empty">Quiet so far.</div>`;
  return items.map((n) => `<div class="news-item k-${esc(n.kind)}"><div class="when">${n.year} · ${esc(n.label)}</div>
    <div class="txt">${n.driver_id ? `<a href="#/driver/${n.driver_id}">${esc(n.text)}</a>` : esc(n.text)}</div></div>`).join("");
}

function jewelList(items, compact) {
  if (!items.length) return `<div class="empty">No crown jewels you can enter right now.</div>`;
  return items.map((j) => `<div class="news-item"><div class="when">${esc(j.label)}</div>
    <div style="flex:1"><div><b>${esc(j.name)}</b> ${discBadge(Object.keys(DISC_LABEL).find((k) => DISC_LABEL[k] === j.discipline))}</div>
    <div class="muted small">${trackLink(j.track_id, j.track)} · ${money(j.purse_win)} to win · tiers ${j.min_tier}–${j.max_tier}</div>
    ${j.winner ? `<div class="small">Winner: ${driverLink(j.winner.id, j.winner.name)}${j.player_pos ? ` · you P${j.player_pos}` : ""}</div>` : ""}
    ${!j.done && j.eligible !== undefined ? (j.eligible
      ? `<label class="small" style="display:flex;gap:6px;align-items:center;margin-top:4px"><input type="checkbox" data-change="jewel" data-key="${j.key}" ${j.entered ? "checked" : ""}> Enter (≈${money(j.cost)} travel & entry)</label>`
      : `<div class="muted small">Needs ${esc(j.why_not || "eligibility")}</div>`) : ""}
    </div></div>`).join("");
}
on("jewel", async (el) => {
  try {
    await api("jewels", { key: el.dataset.key, enter: el.checked });
    toast(el.checked ? "Entered. Good luck." : "Entry withdrawn.");
  } catch (e) { el.checked = false; toast(e.message, true); }
});

on("apply", async (el) => {
  try { await api("apply", { key: el.dataset.key, apply: el.checked }); toast(el.checked ? "Application sent." : "Application withdrawn."); }
  catch (e) { toast(e.message, true); }
});

async function jewelsPage() {
  const js = await api("jewels");
  view(`<h1>Crown jewels</h1><p class="muted">The big one-off races where local racers can get noticed by national teams. Enter up to three a season — results here carry far more weight with scouts than a weekly feature. If it isn't your usual discipline you'll be in a rented car.</p>
    <div class="card flush">${table("jewels", [
      { key: "week", label: "When", render: (j) => esc(j.label), num: false },
      { key: "name", label: "Event", render: (j) => `<b>${esc(j.name)}</b>` },
      { key: "track", label: "Track", render: (j) => trackLink(j.track_id, j.track) },
      { key: "discipline", label: "Type" },
      { key: "purse_win", label: "To win", num: true, render: (j) => money(j.purse_win) },
      { key: "min_tier", label: "Tiers", render: (j) => `${j.min_tier}–${j.max_tier}` },
      { key: "entrants", label: "Field", num: true },
      { key: "winner", label: "Winner", render: (j) => (j.winner ? driverLink(j.winner.id, j.winner.name) : "—"), sort: (j) => j.winner?.name },
      { key: "player_pos", label: "You", num: true, render: (j) => posCell(j.player_pos) },
      { key: "entered", label: "Enter", nosort: true, render: (j) => (j.done ? "" : j.eligible
        ? `<label class="small nowrap"><input type="checkbox" data-change="jewel" data-key="${j.key}" ${j.entered ? "checked" : ""}> ${money(j.cost)}</label>`
        : `<span class="muted small">needs ${esc(j.why_not || "eligibility")}</span>`) },
    ], js)}</div>`);
}

async function driverPage(id) {
  const d = await api("driver/" + id);
  const r = d.ratings;
  const traits = ["consistency", "racecraft", "aggression", "feedback", "adaptability", "marketability", "professionalism", "determination"];
  const fin = d.finances || {};
  const histCols = [
    { key: "year", label: "Year", num: true },
    { key: "age", label: "Age", num: true },
    { key: "series_name", label: "Series", render: (h) => `${tierBadge(h.tier)} ${h.series ? seriesLink(h.series) : esc(h.series_name)}` },
    { key: "team", label: "Team", render: (h) => teamLink(h.team), sort: (h) => h.team?.name || "" },
    { key: "starts", label: "St", num: true },
    { key: "wins", label: "W", num: true },
    { key: "top5", label: "T5", num: true },
    { key: "avg_finish", label: "Avg", num: true },
    { key: "pos", label: "Pos", num: true, render: (h) => `${posCell(h.pos, h.field)}${h.champion ? " 🏆" : ""}` },
  ];
  view(`
    ${heroCard(d)}
    <div class="grid g3" style="margin-top:16px">
      <div class="card"><div class="card-head"><h3>${r.exact ? "Ratings" : "Scouting report"}</h3>
        ${r.exact ? '<span class="badge good">exact</span>' : `<span class="badge">confidence: ${esc(r.confidence)}</span>`}</div>
        <div class="ratings-grid">
          <div class="row"><span>Overall</span>${rating(r.overall)}</div>
          <div class="row"><span>Potential</span>${rating(r.potential)}</div>
          ${traits.map((t) => `<div class="row"><span>${t[0].toUpperCase() + t.slice(1)}</span>${rating(r[t])}</div>`).join("")}
        </div>
        <p class="muted small" style="margin:10px 0 0">20–80 scale. ${r.exact ? "Your own driver: you know exactly where you stand." : "Accuracy improves with the driver's exposure — scouts only know what they've seen."}</p>
      </div>
      <div class="card"><h3>Profile</h3>
        <dl class="kv">
          <dt>Born</dt><dd>${d.birth_year} (age ${d.age})</dd>
          <dt>Home</dt><dd>${esc(d.home_name)}, ${esc(d.country)}</dd>
          <dt>Category</dt><dd>${esc(d.category)} <span class="muted small">(sports-car rating)</span></dd>
          <dt>Best level</dt><dd>${tierBadge(d.max_tier)}</dd>
          <dt>Starts / wins</dt><dd>${d.starts} / ${d.wins}</dd>
          <dt>Momentum</dt><dd>${d.momentum > 5 ? "📈 hot" : d.momentum < -5 ? "📉 cold" : "steady"} (${d.momentum})</dd>
          ${d.program ? `<dt>Program</dt><dd><span class="badge good">${esc(d.program)} development</span></dd>` : ""}
          ${d.contract_years !== null && d.contract_years !== undefined ? `<dt>Contract</dt><dd>${d.contract_years} yr left · ${d.funded ? "funded seat" : "driver-funded"}</dd>` : ""}
          ${d.injury_races > 0 ? `<dt>Injury</dt><dd><span class="badge bad">out ${d.injury_races} races</span></dd>` : ""}
          ${d.veteran ? `<dt>Status</dt><dd>Ex-national driver racing locally</dd>` : ""}
        </dl>
        <h3 style="margin-top:14px">Experience by discipline</h3>
        ${Object.entries(d.proficiency).sort((a, b) => b[1] - a[1]).map(([k, v]) => `<div class="culture"><span>${esc(k)}</span><span class="b"><i style="width:${v}%;background:var(--accent)"></i></span></div>`).join("") || '<span class="muted">—</span>'}
      </div>
      <div class="card"><h3>${d.is_player ? "Money" : "Backers"}</h3>
        ${d.is_player ? `<dl class="kv">
          <dt>Family / personal</dt><dd>${money(fin.family_budget)} / season</dd>
          <dt>Sponsors</dt><dd>${money((fin.sponsors || []).reduce((a, s) => a + s.amount, 0))} / season</dd>
          <dt>Savings</dt><dd>${money(fin.savings)}</dd>
          <dt>Scholarship / program</dt><dd>${money(fin.scholarship)}</dd>
          <dt>Salary</dt><dd>${money(fin.salary)}</dd>
          <dt><b>Available</b></dt><dd><b>${money(fin.available)}</b></dd></dl>` : ""}
        <h3 style="margin-top:12px">Sponsors</h3>
        ${(fin.sponsors || []).length ? `<ul class="timeline">${fin.sponsors.map((s) => `<li>${esc(s.name)}${s.amount ? ` — ${money(s.amount)}/yr, ${s.years_left} yr left` : ""}</li>`).join("")}</ul>` : '<div class="muted">None</div>'}
        <h3 style="margin-top:12px">Connections</h3>
        ${d.connections.length ? d.connections.map((c) => `<div class="culture"><span class="small">${esc(c.name)}</span><span class="b"><i style="width:${c.strength * 100}%;background:var(--d-open_wheel)"></i></span></div>`).join("") : '<div class="muted">Nobody in the paddock knows you yet.</div>'}
      </div>
    </div>
    <div class="grid g-main" style="margin-top:16px">
      <div class="card flush"><h3>Career history</h3>${table("hist", histCols, d.history.slice().reverse(), { empty: "No completed seasons yet." })}</div>
      <div class="grid"><div class="card"><h3>Career log</h3>
        ${d.titles_list.length ? `<div class="chips" style="margin-bottom:10px">${d.titles_list.map((t) => `<span class="chip">🏆 ${esc(t)}</span>`).join("")}</div>` : ""}
        ${d.jewels_list.length ? `<div class="chips" style="margin-bottom:10px">${d.jewels_list.map((t) => `<span class="chip">💎 ${esc(t)}</span>`).join("")}</div>` : ""}
        ${d.events.length ? `<ul class="timeline">${d.events.slice(0, 40).map((e) => `<li>${esc(e)}</li>`).join("")}</ul>` : '<div class="muted">Nothing notable yet.</div>'}
      </div>
      ${(d.news || []).length ? `<div class="card"><h3>In the news</h3>${newsList(d.news.slice(0, 12))}</div>` : ""}</div>
    </div>`);
}

async function offseasonPage() {
  if (S.status.phase !== "offseason") {
    view(`<h1>Off-season</h1><div class="card"><p>The ${S.status.year} season is underway (${esc(S.status.label)}). Decisions open when the season ends.</p>
      <button class="primary" data-act="sim" data-until="season">Sim to season end ▸▸</button></div>`);
    return;
  }
  const o = await api("offseason");
  renderOffseason(o);
}

function renderOffseason(o) {
  const teams = o.choices.filter((c) => c.kind === "team");
  const selfs = o.choices.filter((c) => c.kind === "self");
  const stay = o.choices.find((c) => c.kind === "stay");
  const s = o.season;
  const me = o.driver;
  const recap = s ? `<div class="callout"><b>${S.status.year} season:</b> P${s.pos} of ${s.field} in the ${esc(s.series.name)} — ${s.wins} wins, ${s.top5} top-5s in ${s.starts} starts (avg finish ${s.avg_finish}).${s.champion ? " <b>Champion!</b> 🏆" : ""}</div>`
    : `<div class="callout">No full season on record this year.</div>`;
  const offerCard = (c) => `<div class="offer">
      <div class="top"><div><div class="team">${esc(c.team.name)}</div><div class="small">${seriesLink(c.series)}</div></div>
        <div>${tierBadge(c.tier, c.series.tier_name)}</div></div>
      <div class="chips">${discBadge(c.discipline)} ${c.own_team ? '<span class="badge good">your team</span>' : ""}
        ${c.manufacturer ? `<span class="badge">${esc(c.manufacturer)}</span>` : ""} ${c.role === "am" ? '<span class="badge">amateur seat</span>' : ""}</div>
      <div class="small">Equipment ${rating(Math.round(20 + c.equipment * 0.6), { title: "Car quality" })}</div>
      <div class="small">${c.funded
        ? `<span class="badge good">${c.absorbed ? "Team found the money" : "Funded seat"}</span>${c.salary ? ` salary ${money(c.salary)}` : ""}`
        : `<span class="badge warn">Bring ${money(c.bring)}</span> of ${money(c.gap)} needed${c.coverage < 1 ? ` (covers ${pct(c.coverage)} — car will be under-funded)` : ""}`}</div>
      <button class="primary" data-act="choose" data-id="${esc(c.id)}">Sign</button></div>`;
  const readiness = (r) => (r < -8 ? '<span class="badge bad">out of depth</span>' : r < -2 ? '<span class="badge warn">a stretch</span>' : r < 4 ? '<span class="badge good">ready</span>' : '<span class="badge">comfortable</span>');
  view(`
    <h1>Off-season — silly season ${S.status.year}</h1>
    ${recap}
    ${o.message ? `<div class="callout">${esc(o.message)}</div>` : ""}
    <div class="grid g-main">
      <div class="grid">
        ${stay ? `<div class="card"><h3>Your contract</h3><p>You're under contract with ${teamLink(stay.team)} in the ${seriesLink(stay.series)} (${stay.contract_years} more season${stay.contract_years > 1 ? "s" : ""}). Only a promotion will pry you loose.</p>
          <button class="primary" data-act="choose" data-id="stay">Stay put</button></div>` : ""}
        <div class="card"><div class="card-head"><h3>Team offers (${teams.length})</h3><span class="muted small">Owners who would pick you over the competition right now</span></div>
          ${teams.length ? `<div class="offers">${teams.map(offerCard).join("")}</div>` : `<div class="empty">No team wants you yet. Win, get seen at crown jewels, bring money, or build connections.</div>`}
        </div>
        <div class="card flush"><div class="card-head" style="padding:14px 16px 0"><h3>Run your own program</h3><span class="muted small">Cost includes travel from ${esc(me.home_name)}</span></div>
          ${table("selfrun", [
            { key: "tier", label: "Tier", num: true, render: (c) => tierBadge(c.tier, c.series.tier_name) },
            { key: "name", label: "Series", render: (c) => `${seriesLink(c.series)}${c.current ? ' <span class="badge">current</span>' : ""}`, sort: (c) => c.series.name },
            { key: "discipline", label: "Type", render: (c) => discBadge(c.discipline) },
            { key: "cost", label: "Season cost", num: true, render: (c) => money(c.cost) },
            { key: "afford", label: "Affordability", num: true, render: (c) => `<span class="statbar" style="display:inline-block;width:70px;vertical-align:middle"><i style="width:${Math.min(100, c.afford * 70)}%;background:${c.afford >= 0.8 ? "var(--good)" : "var(--warn)"}"></i></span> ${c.part_time ? '<span class="badge warn">part-time</span>' : ""}` },
            { key: "readiness", label: "Readiness", num: true, render: (c) => readiness(c.readiness) },
            { key: "go", label: "", nosort: true, render: (c) => `<button class="small" data-act="choose" data-id="${esc(c.id)}">Run this</button>` },
          ], selfs, { empty: "You can't afford any programme right now." })}
        </div>
        <div class="card"><h3>Other options</h3>
          <button data-act="choose" data-id="sit_out">Sit out next season</button>
          <button data-act="retire">Retire from driving</button></div>
      </div>
      <div class="grid">
        <div class="card"><h3>Off-season actions</h3><p class="muted small">One of each per off-season. Do these before choosing a ride — owners re-evaluate you.</p>
          ${o.actions.map((a) => `<div style="margin:10px 0"><div><b>${esc(a.label)}</b></div><div class="muted small">${esc(a.detail)}</div>
            ${a.id === "relocate" ? `<select id="relocate-to" ${a.used ? "disabled" : ""}>${o.regions.map((r) => `<option value="${r.code}" ${r.code === me.home ? "selected" : ""}>${esc(r.name)}${Object.keys(r.hubs || {}).length ? " ★ hub" : ""}</option>`).join("")}</select>` : ""}
            <button class="small" style="margin-top:6px" data-act="action" data-id="${a.id}" ${a.used ? "disabled" : ""}>${a.used ? "Done" : "Do it"}</button></div>`).join("")}
        </div>
        <div class="card"><h3>Where you stand</h3>
          <dl class="kv"><dt>Overall</dt><dd>${rating(me.ratings.overall)}</dd><dt>Potential</dt><dd>${rating(me.ratings.potential)}</dd>
          <dt>Reputation</dt><dd>${me.reputation}</dd><dt>Exposure</dt><dd>${me.exposure}</dd>
          <dt>Budget</dt><dd><b>${money(me.finances.available)}</b></dd><dt>Age next season</dt><dd>${me.age + 1}</dd></dl></div>
      </div>
    </div>`);
}
on("choose", async (el) => {
  const id = el.dataset.id;
  if (id === "sit_out" && !confirm("Sit out a whole season? Scouts forget quickly.")) return;
  el.classList.add("busy");
  try {
    const r = await api("offseason", { choice: id });
    S.status = r.status;
    renderChrome();
    toast(r.message);
    location.hash = "#/";
  } catch (e) { toast(e.message, true); el.classList.remove("busy"); }
});
on("retire", async () => {
  if (!confirm("Retire from driving? Your career ends, but the world keeps going.")) return;
  try { const r = await api("offseason", { choice: "retire" }); S.status = r.status; renderChrome(); toast(r.message); location.hash = "#/career"; }
  catch (e) { toast(e.message, true); }
});
on("action", async (el) => {
  const id = el.dataset.id;
  const arg = id === "relocate" ? $("#relocate-to").value : undefined;
  el.classList.add("busy");
  try {
    const r = await api("offseason", { action: id, arg });
    renderOffseason(r);
    toast(r.message);
    refreshStatus();
  } catch (e) { toast(e.message, true); el.classList.remove("busy"); }
});

async function seriesPage(id, tab = "standings") {
  const s = await api("series/" + encodeURIComponent(id));
  const t = s.template;
  const chip = (l, v) => `<span class="chip">${l} <b>${v}</b></span>`;
  const tabs = [["standings", "Standings"], ["schedule", "Schedule & results"], ["field", s.template.team_based ? "Teams" : "Field"], ["champions", "Champions"], ["about", "About"]];
  const body = {
    standings: () => `<div class="card flush">${table("ser-st", standingCols(), s.standings, { rowClass: (r) => (r.is_player ? "me" : ""), empty: "No standings yet." })}</div>`,
    schedule: () => `<div class="card flush">${scheduleTable("ser-sch", s.schedule, s, true)}</div>`,
    field: () => t.team_based
      ? `<div class="grid g2">${s.teams.map((tm) => `<div class="card"><div class="card-head"><div><b>${teamLink(tm)}</b> ${tm.manufacturer ? `<span class="badge">${esc(tm.manufacturer)}</span>` : ""}</div>${rating(Math.round(20 + tm.equipment * 0.6), { title: "Equipment" })}</div>
          <div class="muted small">${tm.cars} car${tm.cars > 1 ? "s" : ""} · raises ${money(tm.funding_per_seat)}/seat · ${esc(tm.owner_type)} owner</div>
          ${tm.roster.length ? tm.roster.map((r) => `<div class="small" style="margin-top:4px">${driverLink(r.id, r.name, r.is_player)} <span class="muted">(${r.age})</span> ${rating(r.overall)} ${r.funded ? "" : '<span class="badge warn">pay</span>'}</div>`).join("") : '<div class="muted small">Empty seat</div>'}
        </div>`).join("")}</div>`
      : `<div class="card flush">${driversTable("ser-field", s.drivers)}</div>`,
    champions: () => `<div class="card flush">${table("ser-ch", [{ key: "year", label: "Year", num: true }, { key: "name", label: "Champion", render: (c) => driverLink(c.driver_id, c.name) }], s.champions, { empty: "No champions crowned yet in this save." })}</div>`,
    about: () => `<div class="card"><p>${esc(t.note || "")}</p><p class="muted small">Series names are fictional abstractions of real-world ladders. See MOTORSPORTS_RESEARCH.md for the research behind each rung.</p></div>`,
  };
  view(`<div class="card"><div class="hero"><div><h1>${esc(s.name)}</h1>
      <div class="sub">${tierBadge(s.tier, s.tier_name)} ${esc(s.tier_name)} · ${discBadge(s.discipline)} · ${esc(s.scope === "track" ? "weekly track division" : s.scope === "region" ? "regional series" : "national series")}</div></div></div>
    <div class="chips" style="margin-top:12px">${chip("Season cost", money(t.cost))}${chip("Events", s.dormant ? t.events : (s.schedule || []).length || t.events)}${chip("Field", t.field)}
      ${chip("Prestige", t.prestige)}${chip("Scout visibility", t.visibility)}${chip("Min age", t.min_age)}${t.max_age ? chip("Max age", t.max_age) : ""}
      ${t.full_age ? chip("Big-oval age", t.full_age) : ""}${t.purse_win ? chip("Purse to win", money(t.purse_win)) : ""}
      ${t.scholarship ? chip("Champion scholarship", money(t.scholarship)) : ""}${t.team_based ? chip("Seats", "team-based") : chip("Cars", "self-run")}
      ${t.pro ? chip("Pros", "paid") : ""}${s.real_schedule ? chip("Calendar", "real " + S.status.year + " schedule") : ""}${t.license_min_tier ? chip("Licence", `T${t.license_min_tier}+ & ${t.license_min_starts} starts`) : ""}</div></div>
    <div class="tabs">${tabs.map(([k, l]) => `<button class="${k === tab ? "on" : ""}" data-act="stab" data-tab="${k}" data-id="${esc(id)}">${l}</button>`).join("")}</div>
    ${body[tab]()}`);
}
on("stab", (el) => seriesPage(el.dataset.id, el.dataset.tab));

function driversTable(id, rows, opts = {}) {
  return table(id, [
    { key: "name", label: "Driver", render: (r) => driverLink(r.id, r.name, r.is_player, r.real), sort: (r) => r.name },
    { key: "age", label: "Age", num: true },
    { key: "home", label: "Home" },
    { key: "tier", label: "Tier", num: true, render: (r) => tierBadge(r.tier) },
    { key: "series", label: "Series", render: (r) => seriesLink(r.series), sort: (r) => r.series?.name || "" },
    { key: "team", label: "Team", render: (r) => (r.series ? teamLink(r.team) : "—"), sort: (r) => r.team?.name || "" },
    { key: "overall", label: "OVR", num: true, render: (r) => rating(r.overall) },
    { key: "potential", label: "POT", num: true, render: (r) => rating(r.potential) },
    { key: "reputation", label: "Rep", num: true },
    { key: "wins", label: "Wins", num: true },
    { key: "titles", label: "Titles", num: true },
  ], rows, { rowClass: (r) => (r.is_player ? "me" : ""), ...opts });
}

async function racePage(key, ev, year) {
  const r = await api(`race/${encodeURIComponent(key)}/${ev}${year ? "?year=" + year : ""}`);
  view(`<h1>${esc(r.jewel || (r.series && r.series.name) || "Race")}</h1>
    <p class="sub">${trackLink(r.track_id, r.track)} · ${esc(r.label)}</p>
    <div class="card flush">${table("race", [
      { key: "pos", label: "Pos", num: true, render: (x) => posCell(x.pos) },
      { key: "name", label: "Driver", render: (x) => `${driverLink(x.driver_id, x.name, x.is_player)}${x.co_drivers.length ? ` <span class="muted small">/ ${x.co_drivers.map((c) => esc(c.name)).join(", ")}</span>` : ""}` },
      { key: "team", label: "Team", render: (x) => teamLink(x.team), sort: (x) => x.team?.name || "" },
      { key: "tier", label: "Usual tier", num: true, render: (x) => tierBadge(x.tier) },
      { key: "dnf", label: "", render: (x) => (x.dnf ? '<span class="badge bad">DNF</span>' : "") },
    ], r.results, { rowClass: (x) => (x.is_player ? "me" : "") })}</div>`);
}

async function pyramidPage() {
  const tiers = await api("pyramid");
  const maxD = Math.max(...tiers.map((t) => t.drivers), 1);
  view(`<h1>The racing pyramid</h1>
    <p class="muted">Every championship in the world, from weekly divisions at real local tracks up to the premier series. Band width shows how many drivers race at each level. Click a series to explore it.</p>
    <div class="legend" style="margin:10px 0 16px">${Object.entries(DISC_LABEL).map(([k, v]) => `<span><i style="background:${discColor(k)}"></i>${v}</span>`).join("")}</div>
    ${tiers.map((t) => `<div class="pyr-row"><div class="pyr-label"><div class="t">${tierBadge(t.tier)} ${esc(t.name)}</div><div class="muted small">${t.drivers.toLocaleString()} drivers</div></div>
      <div class="pyr-body"><div class="pyr-band" style="width:${22 + 78 * Math.sqrt(t.drivers / maxD)}%">
        ${t.templates.map((s) => `<div class="pyr-chip" style="background:${discColor(s.discipline)}" data-act="pyr" data-key="${s.key}" data-single="${s.single_id || ""}"
          title="${esc(s.name)} — ${money(s.cost)}/season, ${s.events} events, min age ${s.min_age}${s.max_age ? ", max " + s.max_age : ""}">
          ${esc(s.name)}<small>${s.instances > 1 ? `${s.instances} ${s.scope === "track" ? "tracks" : "regions"} · ` : ""}${s.drivers} drivers · ${money(s.cost)}</small></div>`).join("")}
      </div></div></div>`).join("")}`);
}
on("pyr", (el) => { location.hash = el.dataset.single ? `#/series/${encodeURIComponent(el.dataset.single)}` : `#/instances/${el.dataset.key}`; });

async function instancesPage(key) {
  const rows = await api("instances/" + key);
  view(`<h1>${esc(rows[0] ? rows[0].type : key)}</h1>
    <p class="muted">${rows.length} championships of this type. Local divisions are named after their real track.</p>
    <div class="toolbar"><input id="inst-q" placeholder="Filter by name or state…" data-change="instq"></div>
    <div class="card flush">${table("inst", [
      { key: "name", label: "Championship", render: (r) => seriesLink(r) },
      { key: "region", label: "Region" },
      { key: "drivers", label: "Drivers", num: true },
    ], rows, { tall: true })}</div>`);
  on("instq", (el) => {
    const q = el.value.toLowerCase();
    S.tables.inst.rows = rows.filter((r) => r.name.toLowerCase().includes(q) || (r.region || "").toLowerCase().includes(q));
    $("#tbl-inst").innerHTML = renderTable("inst");
  });
}

const DRV_Q = { status: "active", sort: "reputation", offset: 0, limit: 100 };
async function driversPage() {
  if (!S.setup) S.setup = await api("setup");
  const q = DRV_Q;
  const qs = new URLSearchParams(Object.entries(q).filter(([, v]) => v !== "" && v !== undefined)).toString();
  const res = await api("drivers?" + qs);
  const sel = (name, opts, cur) => `<select data-change="drvq" data-k="${name}">${opts.map(([v, l]) => `<option value="${v}" ${String(cur ?? "") === String(v) ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>`;
  view(`<h1>Drivers</h1>
    <div class="toolbar">
      <input placeholder="Search name…" value="${esc(q.q || "")}" data-change="drvq" data-k="q">
      ${sel("status", [["active", "Racing"], ["free", "Without a ride"], ["retired", "Retired"], ["all", "Everyone"]], q.status)}
      ${sel("tier", [["", "All tiers"], ...[7, 6, 5, 4, 3, 2, 1, 0].map((t) => [t, "Tier " + t])], q.tier)}
      ${sel("discipline", [["", "All disciplines"], ...Object.entries(DISC_LABEL)], q.discipline)}
      ${sel("region", [["", "All regions"], ...S.setup.regions.map((r) => [r.code, r.name])], q.region)}
      ${sel("sort", [["reputation", "Sort: reputation"], ["overall", "Sort: overall (scouted)"], ["potential", "Sort: potential"], ["wins", "Sort: wins"], ["titles", "Sort: titles"], ["age", "Sort: youngest"], ["tier", "Sort: tier"], ["name", "Sort: name"]], q.sort)}
      <span class="muted small">Age</span><input type="number" style="width:64px" value="${q.min_age || ""}" placeholder="min" data-change="drvq" data-k="min_age">
      <input type="number" style="width:64px" value="${q.max_age || ""}" placeholder="max" data-change="drvq" data-k="max_age">
    </div>
    <div class="card flush">${driversTable("drivers", res.rows)}
      <div class="pager"><span class="muted small">${res.total.toLocaleString()} drivers · ${res.total ? `showing ${q.offset + 1}–${Math.min(q.offset + q.limit, res.total)}` : "no matches"}</span>
      <button class="small" data-act="drvpage" data-d="-1" ${q.offset === 0 ? "disabled" : ""}>‹ Prev</button>
      <button class="small" data-act="drvpage" data-d="1" ${q.offset + q.limit >= res.total ? "disabled" : ""}>Next ›</button></div></div>`);
}
on("drvq", (el) => { DRV_Q[el.dataset.k] = el.value; DRV_Q.offset = 0; driversPage(); });
on("drvpage", (el) => { DRV_Q.offset = Math.max(0, DRV_Q.offset + Number(el.dataset.d) * DRV_Q.limit); driversPage(); });

async function teamPage(id) {
  const t = await api("team/" + id);
  view(`<div class="card hero"><div class="avatar" style="background:${TIER_COLORS[t.series.tier]}">${initials(t.name)}</div>
    <div><h1>${esc(t.name)}</h1><div class="sub">${seriesLink(t.series)} · ${tierBadge(t.series.tier)} · ${esc(t.owner_type)} owner · based in ${esc(t.home)}${t.manufacturer ? ` · ${esc(t.manufacturer)}` : ""}</div></div>
    <div class="kpis"><div class="kpi"><div class="v">${rating(Math.round(20 + t.equipment * 0.6))}</div><div class="l">Equipment</div></div>
      <div class="kpi"><div class="v">${t.cars}</div><div class="l">Cars</div></div>
      <div class="kpi"><div class="v">${money(t.funding_per_seat)}</div><div class="l">Raises / seat</div></div></div></div>
    <div class="grid g-main" style="margin-top:16px">
      <div class="card flush"><h3>Drivers</h3>${driversTable("team-roster", t.roster)}</div>
      <div class="card"><h3>What this owner values</h3>
        ${Object.entries(t.weights).map(([k, v]) => `<div class="culture"><span>${k}</span><span class="b"><i style="width:${v * 100}%;background:var(--accent)"></i></span></div>`).join("")}
        <p class="muted small">Teams that raise less money themselves lean on drivers who bring it.</p></div>
    </div>`);
}

// ---- tracks + map
const TRK_Q = {};
function trackColor(t) {
  if (t.type === "kart_circuit") return "var(--d-karting)";
  if (t.type === "road_course" || t.type === "roval") return "var(--d-sports_car)";
  if (t.type === "street_circuit") return "var(--d-touring_car)";
  if (t.surface === "dirt" || t.surface === "clay") return "var(--d-dirt_oval)";
  return "var(--d-stock_car)";
}
function mapSvg(tracks, opts = {}) {
  const W = 1000, H = 560, lon0 = -128, lon1 = -56, lat0 = 23.5, lat1 = 56;
  const k = Math.cos((40 * Math.PI) / 180);
  const sx = W / ((lon1 - lon0) * k), sy = H / (lat1 - lat0);
  const s = Math.min(sx, sy);
  const X = (lon) => (lon - lon0) * k * s, Y = (lat) => (lat1 - lat) * s;
  const pts = tracks.filter((t) => t.lat !== null && t.lon !== null && t.lon > lon0 && t.lon < lon1 && t.lat > lat0 && t.lat < lat1);
  let grid = "";
  for (let lo = -125; lo <= -60; lo += 5) grid += `<line x1="${X(lo)}" y1="0" x2="${X(lo)}" y2="${H}" stroke="var(--line)" stroke-width=".5"/>`;
  for (let la = 25; la <= 55; la += 5) grid += `<line x1="0" y1="${Y(la)}" x2="${W}" y2="${Y(la)}" stroke="var(--line)" stroke-width=".5"/><text x="4" y="${Y(la) - 3}" font-size="10" fill="var(--muted)">${la}°N</text>`;
  const dots = pts.sort((a, b) => a.prestige - b.prestige).map((t) => `<circle cx="${X(t.lon).toFixed(1)}" cy="${Y(t.lat).toFixed(1)}" r="${(opts.big ? 7 : 2.6 + t.prestige / 22).toFixed(1)}" fill="${trackColor(t)}" opacity="${t.active === false ? 0.35 : 0.88}" data-act="gotrack" data-id="${esc(t.id)}"><title>${esc(t.name)} — ${esc(t.city || "")}, ${esc(t.region || "")}</title></circle>`).join("");
  return `<svg class="map" viewBox="0 0 ${W} ${Math.round(H)}" role="img" aria-label="Map of tracks">${grid}${dots}</svg>`;
}
on("gotrack", (el) => { location.hash = `#/track/${encodeURIComponent(el.dataset.id)}`; });

async function tracksPage() {
  if (!S.setup) S.setup = await api("setup");
  const q = TRK_Q;
  const qs = new URLSearchParams(Object.entries(q).filter(([, v]) => v)).toString();
  const rows = await api("tracks?" + qs);
  const sel = (name, opts) => `<select data-change="trkq" data-k="${name}">${opts.map(([v, l]) => `<option value="${v}" ${(q[name] || "") === v ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>`;
  const intl = rows.filter((t) => t.country !== "USA" && t.country !== "CAN").length;
  view(`<h1>Tracks</h1><p class="muted">${rows.length} real venues${intl ? ` (${intl} outside North America, not on the map)` : ""}. Facts are sourced; simulation ratings are the game's own model.</p>
    <div class="toolbar">
      <input placeholder="Search track or city…" value="${esc(q.q || "")}" data-change="trkq" data-k="q">
      ${sel("region", [["", "All regions"], ...S.setup.regions.map((r) => [r.code, r.name])])}
      ${sel("surface", [["", "Any surface"], ["paved", "Paved"], ["dirt", "Dirt / clay"]])}
      ${sel("type", [["", "Any type"], ["oval", "Oval"], ["road_course", "Road course"], ["street_circuit", "Street circuit"], ["roval", "Roval"], ["kart_circuit", "Kart circuit"]])}
      ${sel("level", [["", "Any level"], ["local", "Local"], ["regional", "Regional"], ["national", "National"], ["international", "International"]])}
    </div>
    <div class="card">${mapSvg(rows)}
      <div class="legend" style="margin-top:8px"><span><i style="background:var(--d-stock_car)"></i>Paved oval</span><span><i style="background:var(--d-dirt_oval)"></i>Dirt oval</span>
        <span><i style="background:var(--d-sports_car)"></i>Road course</span><span><i style="background:var(--d-touring_car)"></i>Street circuit</span><span><i style="background:var(--d-karting)"></i>Kart</span><span>Dot size = prestige</span></div></div>
    <div class="card flush" style="margin-top:16px">${table("tracks", [
      { key: "name", label: "Track", render: (t) => `${trackLink(t.id, t.name)}${t.active === false ? ' <span class="badge">closed</span>' : ""}` },
      { key: "city", label: "Location", render: (t) => `${esc(t.city || "")}, ${esc(t.region || t.country)}`, sort: (t) => (t.region || "") + (t.city || "") },
      { key: "type", label: "Type", render: (t) => `<span class="small">${esc(t.size_class.replace(/_/g, " "))}</span>` },
      { key: "surface", label: "Surface" },
      { key: "length", label: "Length", num: true, render: (t) => (t.length ? `${t.length.toFixed(3)} mi` : "—") },
      { key: "banking", label: "Banking", num: true, render: (t) => (t.banking !== null ? `${t.banking}°` : "—") },
      { key: "opened", label: "Opened", num: true },
      { key: "level", label: "Level" },
      { key: "prestige", label: "Prestige", num: true },
    ], rows, { tall: true })}</div>`);
}
on("trkq", (el) => { TRK_Q[el.dataset.k] = el.value; tracksPage(); });

async function trackPage(id) {
  const t = await api("track/" + encodeURIComponent(id));
  const f = t.facts, p = t.profile, s = t.sim;
  const label = (k) => k.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
  const factRows = [["City", f.city], ["Region", f.region], ["Country", f.country], ["Type", f.track_type], ["Surface", f.surface ?? "not documented"],
    ["Length", f.length_mi ? `${f.length_mi} mi` : "not documented"], ["Configuration", f.configuration], ["Turns", f.turns],
    ["Banking (turns)", f.banking_deg_turns !== null ? `${f.banking_deg_turns}°` : "not documented"], ["Banking (straights)", f.banking_deg_straights !== null ? `${f.banking_deg_straights}°` : null],
    ["Opened", f.opened], ["Status", f.active === false ? "closed / inactive" : f.active === null ? "unconfirmed" : "active"], ["Level", f.level],
    ["Disciplines", (f.disciplines || []).join(", ")], ["Note", f.notable_note], ["Also known as", (f.aliases || []).join(", ")]].filter(([, v]) => v !== null && v !== undefined && v !== "");
  const simKeys = Object.keys(s).filter((k) => k !== "derivation");
  const mp = (x) => `<div class="culture" style="grid-template-columns:190px 1fr 30px"><span>${label(x)}</span><span class="b"><i style="width:${s[x]}%;background:var(--accent)"></i></span><span class="num small">${s[x]}</span></div>`;
  view(`<div class="card hero"><div><h1>${esc(t.name)}</h1><div class="sub">${esc(f.city || "")}, ${esc(f.region || "")} ${esc(f.country)} · ${esc(p.size_class.replace(/_/g, " "))} · prestige ${p.prestige}</div></div></div>
    <div class="grid g3" style="margin-top:16px">
      <div class="card"><div class="card-head"><h3>Facts</h3><span class="badge good">sourced</span></div>
        <dl class="kv">${factRows.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
        <h3 style="margin-top:12px">Sources</h3>${(f.sources || []).map((u) => `<div class="small"><a class="link" href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace(/^https?:\/\//, "").slice(0, 60))}</a></div>`).join("")}</div>
      <div class="card"><div class="card-head"><h3>Game ratings</h3><span class="badge">internal model · ${esc(s.derivation)}</span></div>${simKeys.map(mp).join("")}</div>
      <div class="card"><h3>Profile</h3><dl class="kv">
        <dt>Climate</dt><dd>${esc(p.weather.climate.replace(/_/g, " "))}</dd><dt>Season</dt><dd>month ${p.weather.season_start_month}–${p.weather.season_end_month}</dd>
        <dt>Rain risk</dt><dd>${p.weather.rain_risk}</dd><dt>Heat</dt><dd>${p.weather.heat_index}</dd><dt>Attendance potential</dt><dd>${p.attendance_potential}</dd></dl>
        <h3 style="margin-top:12px">Raced here in this world</h3>
        ${t.jewels.length ? `<div class="chips" style="margin-bottom:8px">${t.jewels.map((j) => `<span class="chip">💎 ${esc(j)}</span>`).join("")}</div>` : ""}
        ${t.series.length ? t.series.slice(0, 20).map((x) => `<div class="small">${tierBadge(x.tier)} ${seriesLink(x)}</div>`).join("") : '<div class="muted">No series in this world race here.</div>'}
        ${f.lat !== null && f.lon > -128 && f.lon < -56 && f.lat > 23.5 && f.lat < 56 ? `<div style="margin-top:12px">${mapSvg([{ ...f, id: t.id, name: t.name, type: f.track_type, prestige: p.prestige }], { big: true })}</div>` : ""}</div>
    </div>`);
}

async function newsPage(kind = "") {
  const items = await api("news?limit=300" + (kind ? "&kind=" + kind : ""));
  view(`<h1>News wire</h1>
    <div class="toolbar"><select data-change="newsk">${[["", "Everything"], ["player", "You"], ["title", "Championships"], ["jewel", "Crown jewels"], ["race", "Premier races"], ["move", "Moves & signings"], ["injury", "Injuries"]].map(([v, l]) => `<option value="${v}" ${v === kind ? "selected" : ""}>${l}</option>`).join("")}</select></div>
    <div class="card">${newsList(items)}</div>`);
}
on("newsk", (el) => newsPage(el.value));

async function savesPage() {
  const saves = await api("saves");
  const inGame = S.status && S.status.phase !== "none";
  view(`<h1>Save / Load</h1>
    <div class="grid g2">
      <div class="card"><h3>Save current game</h3>${inGame ? `<div class="toolbar"><input id="save-name" placeholder="Save name" value="${esc((S.status.player ? S.status.player.name.split(" ").pop() : "world") + "_" + S.status.year)}"><button class="primary" data-act="save">Save</button></div>` : '<div class="muted">No game loaded.</div>'}
        <p class="muted small">Saves live in the <code>saves/</code> folder of the project.</p></div>
      <div class="card flush"><h3>Saved games</h3>${table("saves", [
        { key: "name", label: "Name", render: (s) => `<b>${esc(s.name)}</b>` },
        { key: "modified", label: "Saved", num: true, render: (s) => new Date(s.modified * 1000).toLocaleString() },
        { key: "size", label: "Size", num: true, render: (s) => `${(s.size / 1e6).toFixed(1)} MB` },
        { key: "load", label: "", nosort: true, render: (s) => `<button class="small" data-act="load" data-name="${esc(s.name)}">Load</button>` },
      ], saves, { empty: "No saves yet." })}</div>
    </div>`);
}
on("save", async () => {
  try { const r = await api("save", { name: $("#save-name").value }); toast(`Saved as ${r.saved}`); savesPage(); } catch (e) { toast(e.message, true); }
});
on("load", async (el) => {
  try { S.status = await api("load", { name: el.dataset.name }); renderChrome(); toast("Loaded."); location.hash = "#/"; } catch (e) { toast(e.message, true); }
});

// ---- new career wizard
const NEW = { age: 10, discipline: "karting", background: "middle", talent: "unknown", region: "NC", scale: "0.6", seed: "", start_year: 2026 };
async function newPage() {
  if (!S.setup) S.setup = await api("setup");
  const st = S.setup;
  const reg = st.regions.find((r) => r.code === NEW.region) || st.regions[0];
  const cards = (key, items, label = (i) => i.label, detail = (i) => i.detail) =>
    `<div class="choice-cards">${items.map((i) => `<div class="choice-card ${NEW[key] === i.id ? "on" : ""}" data-act="pick" data-k="${key}" data-v="${i.id}"><div class="t">${esc(label(i))}</div><div class="d">${detail(i)}</div></div>`).join("")}</div>`;
  const disc = st.disciplines.find((x) => x.id === NEW.discipline) || st.disciplines[0];
  const fits = (x) => NEW.age >= x.min_age && NEW.age <= x.max_age;
  const open = (disc.classes || []).filter((c) => NEW.age >= c.min_age && (c.max_age == null || NEW.age <= c.max_age)).map((c) => c.name);
  const ageHint = fits(disc) ? `${disc.label.split(" (")[0]} at ${NEW.age}: ${open.join(", ") || "entry classes"}` : `${disc.label.split(" (")[0]} entry classes take ages ${disc.min_age}-${disc.max_age} — pick another discipline or age.`;
  view(`<h1>Start a racing career</h1>
    <p class="muted">Every career starts somewhere. Pick where you grew up, how old you are when you start, and how much money your family can put into it. Talent is hidden unless you choose otherwise.</p>
    <div class="grid g-main">
      <div class="card">
        <div class="form-grid">
          <label class="field">First name<input id="nf-first" value="${esc(NEW.first || "")}" placeholder="First"></label>
          <label class="field">Last name<input id="nf-last" value="${esc(NEW.last || "")}" placeholder="Last"></label>
          <label class="field">Start year<select data-change="newf" data-k="start_year">${st.years.slice().reverse().map((y) => `<option value="${y}" ${Number(NEW.start_year) === y ? "selected" : ""}>${y}${st.history_years.includes(y) ? " · real national rosters" : ""}</option>`).join("")}</select>
            <span class="muted small">Born ${NEW.start_year - NEW.age}. ${st.history_years.includes(Number(NEW.start_year)) ? "The national series start with that season's real teams and drivers." : "National series start with generated drivers."}</span></label>
          <label class="field">Home<select data-change="newf" data-k="region">${st.regions.map((r) => `<option value="${r.code}" ${r.code === NEW.region ? "selected" : ""}>${esc(r.name)}${r.country === "CAN" ? " (Canada)" : ""}</option>`).join("")}</select></label>
          <label class="field">Starting age: <b>${NEW.age}</b><input type="range" min="5" max="50" value="${NEW.age}" data-change="newf" data-k="age"><span class="muted small">${ageHint}</span></label>
        </div>
        <h3 style="margin-top:18px">Where you start racing</h3>${cards("discipline", st.disciplines, (i) => i.label.split(" (")[0], (i) => esc((i.label.match(/\((.*)\)/) || [, ""])[1]) + `<br><span class="${fits(i) ? "muted" : "warn-text"}">ages ${i.min_age}-${i.max_age}</span>`)}
        <h3 style="margin-top:18px">Family background</h3>${cards("background", st.backgrounds, (i) => i.label, (i) => `${esc(i.detail)}<br><b>${money(i.budget, st.price_index[NEW.start_year])}</b>/season <span class="muted">(${NEW.start_year} dollars)</span>`)}
        <h3 style="margin-top:18px">Talent</h3>${cards("talent", st.talents, (i) => i.label, (i) => esc(i.detail))}
        <h3 style="margin-top:18px">World</h3>
        <div class="form-grid">
          <label class="field">World size<select data-change="newf" data-k="scale"><option value="0.4" ${NEW.scale === "0.4" ? "selected" : ""}>Small (fast)</option><option value="0.6" ${NEW.scale === "0.6" ? "selected" : ""}>Standard</option><option value="1.0" ${NEW.scale === "1.0" ? "selected" : ""}>Large (~12k drivers)</option></select></label>
          <label class="field">Random seed<input id="nf-seed" value="${esc(NEW.seed)}" placeholder="random"></label>
        </div>
        <div style="margin-top:20px"><button class="primary" data-act="start">Start career →</button> <span class="muted small" id="new-msg"></span></div>
      </div>
      <div class="card"><h3>${esc(reg.name)}</h3>
        <p class="muted small">${esc(reg.description || "")}</p>
        <h3 style="margin-top:12px">Local racing culture</h3>
        <div class="culture">${Object.entries(reg.culture).sort((a, b) => b[1] - a[1]).map(([k, v]) => `<span>${esc(DISC_LABEL[k] || k)}</span><span class="b"><i style="width:${v}%;background:${discColor(k)}"></i></span>`).join("")}</div>
        ${Object.keys(reg.hubs || {}).length ? `<p class="small" style="margin-top:12px">★ Industry hub for ${Object.keys(reg.hubs).map((k) => DISC_LABEL[k] || k).join(", ")} — teams and scouts are close by.</p>` : `<p class="muted small" style="margin-top:12px">No major racing industry here. Getting noticed means travelling — or moving.</p>`}
      </div>
    </div>`);
}
on("pick", (el) => { NEW[el.dataset.k] = el.dataset.v; keepNames(); newPage(); });
on("newf", (el) => { NEW[el.dataset.k] = ["age", "start_year"].includes(el.dataset.k) ? Number(el.value) : el.value; keepNames(); newPage(); });
function keepNames() { NEW.first = $("#nf-first")?.value ?? NEW.first; NEW.last = $("#nf-last")?.value ?? NEW.last; NEW.seed = $("#nf-seed")?.value ?? NEW.seed; }
on("start", async (el) => {
  keepNames();
  el.classList.add("busy");
  $("#new-msg").textContent = "Building the world: tracks, series, thousands of drivers…";
  try {
    const seed = NEW.seed ? Number(NEW.seed) : Math.floor(Math.random() * 1e6);
    S.status = await api("new", { ...NEW, seed, scale: Number(NEW.scale) });
    renderChrome();
    location.hash = "#/";
  } catch (e) { toast(e.message, true); $("#new-msg").textContent = ""; el.classList.remove("busy"); }
});

// ---------------------------------------------------------------- router
const ROUTES = [
  [/^#?\/?$/, () => dashboardPage(), true],
  [/^#\/career$/, () => driverPage(S.status.player.id), true],
  [/^#\/driver\/(\d+)$/, (m) => driverPage(m[1]), true],
  [/^#\/offseason$/, () => offseasonPage(), true],
  [/^#\/myseries$/, () => (S.status.player && S.status.player.series ? seriesPage(S.status.player.series.id) : view('<div class="card empty">You are not entered in a series.</div>')), true],
  [/^#\/series\/(.+)$/, (m) => seriesPage(decodeURIComponent(m[1])), true],
  [/^#\/race\/([^/]+)\/(\d+)(?:\/(\d+))?$/, (m) => racePage(decodeURIComponent(m[1]), m[2], m[3]), true],
  [/^#\/jewels$/, () => jewelsPage(), true],
  [/^#\/pyramid$/, () => pyramidPage(), true],
  [/^#\/instances\/(.+)$/, (m) => instancesPage(m[1]), true],
  [/^#\/drivers$/, () => driversPage(), true],
  [/^#\/team\/(\d+)$/, (m) => teamPage(m[1]), true],
  [/^#\/tracks$/, () => tracksPage(), true],
  [/^#\/track\/(.+)$/, (m) => trackPage(decodeURIComponent(m[1])), true],
  [/^#\/news$/, () => newsPage(), true],
  [/^#\/encyclopedia(?:\/([a-z]+))?(?:\/(.+))?$/, (m) => encyclopediaPage(m[1] || "overview", m[2] && decodeURIComponent(m[2])), false],
  [/^#\/saves$/, () => savesPage(), false],
  [/^#\/new$/, () => newPage(), false],
];

async function route() {
  const h = location.hash || "#/";
  S.route = h;
  if (!S.status) await refreshStatus();
  const inGame = S.status.phase !== "none";
  for (const [re, fn, needsGame] of ROUTES) {
    const m = h.match(re);
    if (!m) continue;
    if (needsGame && !inGame) { location.hash = "#/new"; return; }
    $$("#nav a").forEach((a) => a.classList.toggle("active", a.getAttribute("href") === h || (h === "#/" && a.dataset.nav === "dashboard")));
    try { await fn(m); } catch (e) { view(`<div class="card"><h2>Something went wrong</h2><p class="muted">${esc(e.message)}</p></div>`); }
    return;
  }
  view(`<div class="card empty">Page not found. <a class="link" href="#/">Dashboard</a></div>`);
}

// ---------------------------------------------------------------- theme + boot
(function theme() {
  let t = null;
  try { t = localStorage.getItem("rs-theme"); } catch (_) { /* storage may be blocked */ }
  if (t) document.documentElement.dataset.theme = t;
  $("#theme-toggle").addEventListener("click", () => {
    const cur = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("rs-theme", next); } catch (_) { /* ignore */ }
  });
})();
window.addEventListener("hashchange", route);
refreshStatus().then(route).catch((e) => view(`<div class="card"><h2>Can't reach the game server</h2><p class="muted">${esc(e.message)}</p></div>`));

// ---------------------------------------------------------------- encyclopedia (knowledge layer)
const CONF = (c) => c ? `<span class="badge ${c === "high" ? "good" : c === "medium" ? "warn" : ""}" title="confidence">${esc(c)}</span>` : `<span class="muted small">unrated</span>`;
function factText(f) {
  if (!f) return "—";
  if (f.category) return esc(f.category);
  const unit = f.unit ? ` <span class="muted small">${esc(f.unit)}</span>` : "";
  const n = (x) => (typeof x === "number" ? (Math.abs(x) >= 1000 ? Math.round(x).toLocaleString() : String(+x.toFixed(2))) : esc(x));
  if (f.min != null && f.max != null && f.min !== f.max) return `${n(f.min)}–${n(f.max)}${unit}`;
  const v = f.value ?? f.min ?? f.max;
  return v == null ? "—" : `${typeof v === "object" ? esc(JSON.stringify(v)) : n(v)}${unit}`;
}
const KTABS = [["overview", "Overview"], ["series", "Series"], ["paths", "Career paths"], ["bodies", "Sanctioning bodies"], ["classes", "Car classes"], ["factors", "What drives careers"], ["sources", "Sources"]];
async function encyclopediaPage(tab = "overview", arg) {
  const tabs = `<div class="tabs">${KTABS.map(([k, l]) => `<button class="${k === tab ? "on" : ""}" data-act="ktab" data-tab="${k}">${l}</button>`).join("")}</div>`;
  const head = `<h1>Racing Encyclopedia</h1><p class="muted">The real-world racing ladder the game is built on: researched series, career paths, money and sources. Every number carries a confidence level and its sources.</p>${tabs}`;
  if (tab === "overview") {
    const k = await api("knowledge");
    const c = k.counts;
    const kv = (l, v) => `<div class="kpi"><div class="v">${(v ?? 0).toLocaleString()}</div><div class="l">${l}</div></div>`;
    view(`${head}<div class="card"><div class="kpis" style="flex-wrap:wrap">${kv("series profiles", c.series_profiles)}${kv("career paths", c.career_paths)}${kv("tracks", c.tracks)}${kv("historical drivers", c.historical_drivers)}${kv("historical seasons", c.history_seasons)}${kv("races", c.history_races)}${kv("sources", c.sources)}${kv("ranged facts", c.ranged_facts)}</div></div>
      <div class="grid g2" style="margin-top:16px"><div class="card flush"><h3>Confidence by category</h3>${table("kconf", [{ key: "cat", label: "Category" }, { key: "high", label: "High", num: true }, { key: "medium", label: "Medium", num: true }, { key: "low", label: "Low", num: true }, { key: "unrated", label: "Unrated", num: true }],
        Object.entries(k.confidence).map(([cat, v]) => ({ cat, high: v.high || 0, medium: v.medium || 0, low: v.low || 0, unrated: v.unrated || 0 })))}</div>
      <div class="card"><h3>Known gaps</h3>${k.gaps.length ? `<ul class="timeline">${k.gaps.map((g) => `<li>${esc(g)}</li>`).join("")}</ul>` : '<p class="muted">None recorded.</p>'}</div></div>`);
    return;
  }
  if (tab === "series" && arg) return knowledgeSeriesPage(arg, head);
  if (tab === "series") {
    const rows = await api("knowledge/series");
    view(`${head}<div class="toolbar"><input id="ks-q" placeholder="Filter series…" data-change="ksq"></div><div class="card flush">${table("ks", [
      { key: "name", label: "Series", render: (r) => `<a class="link" href="#/encyclopedia/series/${encodeURIComponent(r.id)}">${esc(r.name)}</a>` },
      { key: "tier", label: "Tier", num: true, render: (r) => (r.tier != null ? tierBadge(r.tier, "") : "—") },
      { key: "discipline", label: "Discipline", render: (r) => esc((r.discipline || "").replace(/_/g, " ")) },
      { key: "level", label: "Level" },
      { key: "regions", label: "Region", render: (r) => esc((r.regions || []).slice(0, 6).join(", ")) },
      { key: "cost", label: "Season cost", sort: (r) => r.annual_cost_usd?.min, render: (r) => factText(r.annual_cost_usd) },
      { key: "age", label: "Typical age", sort: (r) => r.typical_age?.min, render: (r) => factText(r.typical_age) },
      { key: "confidence", label: "Confidence", render: (r) => CONF(r.confidence) },
    ], rows, { tall: true })}</div>`);
    on("ksq", (el) => { const q = el.value.toLowerCase(); S.tables.ks.rows = rows.filter((r) => (r.name + " " + r.discipline + " " + (r.regions || []).join(" ")).toLowerCase().includes(q)); $("#tbl-ks").innerHTML = renderTable("ks"); });
    return;
  }
  if (tab === "paths") {
    const paths = await api("knowledge/paths");
    view(`${head}${paths.length ? "" : '<div class="card empty">No career paths yet.</div>'}${paths.map((p) => `<div class="card" style="margin-bottom:16px"><div class="card-head"><h3>${esc(p.name)}</h3>${CONF(p.confidence)}</div>
      <p class="muted">${esc(p.description || "")}</p>
      <div class="ladder">${(p.steps || []).map((s, i) => `<div class="ladder-step"><div class="t">${i + 1}. ${esc(s.stage || "")}</div>
        <div class="small">${(s.series_names || []).map((x) => (x.id && String(x.id).startsWith("series:") ? `<a class="link" href="#/encyclopedia/series/${encodeURIComponent(x.id)}">${esc(x.name)}</a>` : esc(x.name || x))).join(" · ")}</div>
        <div class="muted small">age ${factText(s.typical_age)} · ${factText(s.typical_years)} yrs · moves up ${s.advance_share ? factText({ ...s.advance_share, min: s.advance_share.min != null ? Math.round(s.advance_share.min * 100) : null, max: s.advance_share.max != null ? Math.round(s.advance_share.max * 100) : null, unit: "%" }) : "—"}</div>
        ${s.gating ? `<div class="gating">${Object.entries(s.gating).map(([k, v]) => `<span title="${esc(k)} ${Math.round((+v || 0) * 100)}%">${esc(k)} <i style="width:${Math.max(2, Math.round((+v || 0) * 90))}px"></i></span>`).join("")}</div>` : ""}
        ${s.notes ? `<div class="small" style="margin-top:4px">${esc(s.notes)}</div>` : ""}</div>`).join('<div class="ladder-arrow">↓</div>')}</div>
      ${(p.crossovers || []).length ? `<h3 style="margin-top:12px">Crossovers</h3><ul class="timeline">${p.crossovers.map((c) => `<li>${esc(c.from_name || c.from || "")} → ${esc(c.to_name || c.to || "")} <span class="muted">(${esc(c.frequency || "")})</span> ${esc(c.notes || "")}</li>`).join("")}</ul>` : ""}
      ${(p.dead_ends || []).length ? `<h3 style="margin-top:12px">Dead ends</h3><ul class="timeline">${p.dead_ends.map((d) => `<li>${esc(typeof d === "string" ? d : JSON.stringify(d))}</li>`).join("")}</ul>` : ""}
      ${(p.examples || []).length ? `<h3 style="margin-top:12px">Real examples</h3><ul class="timeline">${p.examples.map((e) => `<li><b>${esc((e.driver || "").replace(/^driver:/, "").replace(/_/g, " "))}</b> ${esc(e.route || e.notes || "")}</li>`).join("")}</ul>` : ""}
    </div>`).join("")}`);
    return;
  }
  if (tab === "bodies" || tab === "classes") {
    const rows = await api(tab === "bodies" ? "knowledge/bodies" : "knowledge/classes");
    const cols = tab === "bodies"
      ? [{ key: "name", label: "Body" }, { key: "abbrev", label: "Abbrev." }, { key: "scope", label: "Scope", render: (r) => esc(typeof r.scope === "string" ? r.scope : JSON.stringify(r.scope || "")) }, { key: "founded", label: "Founded", num: true }, { key: "website", label: "Website", render: (r) => (r.website ? `<a class="link" href="${esc(r.website)}" target="_blank" rel="noopener">${esc(r.website.replace(/^https?:\/\//, ""))}</a>` : "") }, { key: "confidence", label: "Confidence", render: (r) => CONF(r.confidence) }]
      : [{ key: "name", label: "Class" }, { key: "discipline", label: "Discipline" }, { key: "drivetrain", label: "Layout", render: (r) => esc(typeof r.drivetrain === "string" ? r.drivetrain : r.drivetrain?.category || "") }, { key: "hp", label: "Horsepower", sort: (r) => r.horsepower?.min, render: (r) => factText(r.horsepower) }, { key: "wt", label: "Weight", sort: (r) => r.weight_lb?.min, render: (r) => factText(r.weight_lb) }, { key: "cost", label: "New car", sort: (r) => r.new_car_cost_usd?.min, render: (r) => factText(r.new_car_cost_usd) }, { key: "confidence", label: "Confidence", render: (r) => CONF(r.confidence) }];
    view(`${head}<div class="card flush">${table("kb", cols, rows, { tall: true })}</div>`);
    return;
  }
  if (tab === "factors") {
    const [factors, stages] = await Promise.all([api("knowledge/factors"), api("knowledge/stages")]);
    const tiers = [0, 1, 2, 3, 4, 5, 6, 7];
    view(`${head}<div class="card flush"><h3>How much each factor drives advancement, by tier</h3>${table("kf", [
      { key: "name", label: "Factor", render: (r) => `<b>${esc(r.name || r.id)}</b><div class="muted small">${esc(typeof r.description === "string" ? r.description : "")}</div>` },
      ...tiers.map((t) => ({ key: "t" + t, label: "T" + t, num: true, render: (r) => { const w = (r.weight_by_level || {})[t] ?? (r.weight_by_level || {})["T" + t] ?? (r.weight_by_level || {})[String(t)]; return w ? factText(typeof w === "object" ? w : { value: w }) : "—"; } })),
      { key: "confidence", label: "Conf.", render: (r) => CONF(r.confidence) }], factors)}</div>
      <div class="card flush" style="margin-top:16px"><h3>Career stages</h3>${table("kst", [
      { key: "name", label: "Stage" }, { key: "age", label: "Ages", render: (r) => factText(r.age_range) }, { key: "dur", label: "Typical years", render: (r) => factText(r.typical_duration_years) },
      { key: "exits", label: "Exits", render: (r) => esc((r.exits || []).map((e) => `${e.outcome}: ${e.share ? factText(e.share).replace(/<[^>]+>/g, "") : "?"}`).join(" · ")) },
      { key: "confidence", label: "Conf.", render: (r) => CONF(r.confidence) }], stages)}</div>`);
    return;
  }
  if (tab === "sources") {
    const k = await api("knowledge/sources");
    view(`${head}<div class="card flush"><h3>Sources (${k.sources.length})</h3>${table("ksrc", [
      { key: "name", label: "Source", render: (r) => (r.url && /^https?:/.test(r.url) ? `<a class="link" href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.name || r.id)}</a>` : esc(r.name || r.id)) },
      { key: "kind", label: "Kind" }, { key: "reliability", label: "Reliability" }, { key: "license", label: "License" }, { key: "accessed", label: "Accessed" }, { key: "uses", label: "Ledger entries", num: true }], k.sources, { tall: true })}</div>
      <div class="card flush" style="margin-top:16px"><h3>Sources skipped (automated access restricted)</h3>${table("kun", [{ key: "source", label: "Source" }, { key: "reason", label: "Reason" }, { key: "replacement", label: "Replaced by" }, { key: "checked", label: "Checked" }], k.unavailable)}</div>
      <div class="card flush" style="margin-top:16px"><h3>Public datasets evaluated</h3>${table("kds", [{ key: "name", label: "Dataset", render: (r) => (r.url ? `<a class="link" href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.name)}</a>` : esc(r.name)) }, { key: "coverage", label: "Coverage" }, { key: "license", label: "License" }, { key: "usefulness", label: "Usefulness" }, { key: "decision", label: "Decision" }], k.datasets, { tall: true })}</div>`);
  }
}
async function knowledgeSeriesPage(id, head) {
  const s = await api("knowledge/series/" + encodeURIComponent(id));
  const facts = s.facts || [];
  const link = (x) => `<a class="link" href="#/encyclopedia/series/${encodeURIComponent(x.id)}">${esc(x.name)}</a>`;
  const feeders = (s.links || []).filter((l) => l.kind === "feeder").concat((s.linked_from || []).filter((l) => l.kind === "next"));
  const nexts = (s.links || []).filter((l) => l.kind === "next").concat((s.linked_from || []).filter((l) => l.kind === "feeder"));
  const uniq = (a) => a.filter((x, i) => a.findIndex((y) => y.id === x.id) === i);
  const text = (v) => (v == null ? "" : typeof v === "string" ? v : v.category || v.value || JSON.stringify(v));
  view(`${head}<div class="card hero"><div><h1>${esc(s.name)}</h1><div class="sub">${s.game_tier != null ? tierBadge(s.game_tier, "") : ""} ${esc(s.level || "")} · ${esc((s.discipline || "").replace(/_/g, " "))} · ${esc((s.regions || []).join(", "))} ${CONF(s.confidence)}</div>
    ${s.body_detail ? `<div class="small">Sanctioned by ${esc(s.body_detail.name)}</div>` : ""}</div></div>
    <div class="grid g2" style="margin-top:16px">
      <div class="card"><h3>Profile</h3><dl class="kv">
        ${[["Experience", s.experience_level], ["Team structure", s.team_structure], ["Equipment", s.equipment_ownership], ["Licensing", s.licensing], ["Prerequisites", s.prerequisites], ["Dead ends", s.dead_ends], ["Notes", s.notes]].filter(([, v]) => v).map(([k, v]) => `<dt>${k}</dt><dd>${esc(text(v))}</dd>`).join("")}
        ${s.advancement_drivers ? `<dt>Advancement driven by</dt><dd>${esc(Object.entries(s.advancement_drivers).filter(([k]) => !["confidence", "sources", "notes"].includes(k)).map(([k, v]) => `${k} ${Math.round(v * 100)}%`).join(" · "))}</dd>` : ""}
      </dl>
      ${feeders.length ? `<h3 style="margin-top:12px">Feeds from</h3>${uniq(feeders).map(link).join(" · ")}` : ""}
      ${nexts.length ? `<h3 style="margin-top:12px">Next steps</h3>${uniq(nexts).map(link).join(" · ")}` : ""}
      ${s.car_class_detail ? `<h3 style="margin-top:12px">Car</h3><p class="small">${esc(s.car_class_detail.name)} — ${esc(text(s.car_class_detail.chassis))} ${esc(text(s.car_class_detail.drivetrain))}; ${factText(s.car_class_detail.horsepower)} hp, ${factText(s.car_class_detail.weight_lb)} lb</p>` : ""}
      ${s.seasons && s.seasons.length ? `<h3 style="margin-top:12px">Seasons in the database</h3><p class="small">${s.seasons.length} (${s.seasons[0].year}–${s.seasons[s.seasons.length - 1].year})</p>` : ""}</div>
      <div class="card flush"><h3>Facts</h3>${table("kfacts", [{ key: "attribute", label: "Attribute", render: (r) => esc(r.attribute.replace(/_/g, " ")) }, { key: "v", label: "Value", render: (r) => factText(r) }, { key: "confidence", label: "Conf.", render: (r) => CONF(r.confidence) }, { key: "sources", label: "Sources", render: (r) => esc((r.sources || []).map((x) => x.replace(/^src:/, "")).join(", ")) }], facts)}</div>
    </div>
    <div class="card" style="margin-top:16px"><h3>Sources</h3>${(s.source_detail || []).map((x) => `<div class="small">${x.url && /^https?:/.test(x.url) ? `<a class="link" href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.name)}</a>` : esc(x.name)} <span class="muted">${esc(x.kind || "")} · ${esc(x.reliability || "")}</span></div>`).join("") || '<span class="muted">—</span>'}</div>`);
}
on("ktab", (el) => { location.hash = `#/encyclopedia/${el.dataset.tab}`; });
