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
on("records", (el) => { location.hash = "#/records/" + encodeURIComponent(el.value); });
on("almanac", (el) => { location.hash = "#/almanac/" + el.value; });

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
      <div class="line meta">${p.team ? esc(p.team.name) : "Own car"} · ${money(p.funding)} budget</div>
      ${p.owned_team ? `<div class="line meta">Owner: <a class="link" href="#/team/${p.owned_team.id}">${esc(p.owned_team.name)}</a></div>` : ""}</div>`;
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
    if (r.player_race && until === "race") {        // straight to the green flag
      if (S.status.phase === "offseason") toast(`Season ${before.year} complete: watch your last race, then on to the off-season.`);
      location.hash = `#/watch/${encodeURIComponent(r.player_race.key)}/${r.player_race.event}/${r.player_race.year}`;
      return;
    }
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
  { key: "top10", label: "T10", num: true },
  { key: "avg_finish", label: "Avg", num: true },
  { key: "winnings", label: "Won", num: true, render: (r) => (r.winnings ? money(r.winnings) : "—") },
  { key: "points", label: "Pts", num: true, render: (r) => `${r.points ?? "—"}${r.champion ? " 🏆" : ""}${r.playoff === "alive" ? ' <span class="badge good" title="Alive in the playoffs">P</span>' : r.playoff === "out" ? ' <span class="badge" title="Eliminated from the playoffs">E</span>' : ""}` },
  { key: "behind", label: "Behind", num: true, render: (r) => (r.behind ? "−" + r.behind : r.behind === 0 ? "—" : "") },
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
    ], js)}</div>
    ${js.some((j) => (j.real_winners || []).length) ? `<div class="card" style="margin-top:16px"><h3>Real history before your career began</h3>
      <div class="grid g3">${js.filter((j) => (j.real_winners || []).length).map((j) => `<div><b>${esc(j.name)}</b><ul class="timeline small">${j.real_winners.map((r) => `<li>${r.year} — ${esc(r.name)}</li>`).join("")}</ul></div>`).join("")}</div></div>` : ""}`);
}

async function driverPage(id) {
  const d = await api("driver/" + id);
  const r = d.ratings;
  const traits = ["consistency", "racecraft", "aggression", "feedback", "adaptability", "marketability", "professionalism", "determination"];
  const fin = d.finances || {};
  const histCols = [
    { key: "year", label: "Year", num: true },
    { key: "age", label: "Age", num: true },
    { key: "series_name", label: "Series", render: (h) => `<span style="display:inline-block;min-width:170px">${tierBadge(h.tier)} ${h.series ? seriesLink(h.series) : esc(h.series_name)}</span>` },
    { key: "team", label: "Team", render: (h) => teamLink(h.team), sort: (h) => h.team?.name || "" },
    { key: "starts", label: "St", num: true },
    { key: "wins", label: "W", num: true },
    { key: "top5", label: "T5", num: true },
    { key: "top10", label: "T10", num: true, render: (h) => h.top10 || "" },
    { key: "poles", label: "Poles", num: true, render: (h) => h.poles || "" },
    { key: "laps_led", label: "Led", num: true, render: (h) => h.laps_led || "" },
    { key: "dnfs", label: "DNF", num: true, render: (h) => h.dnfs || "" },
    { key: "avg_start", label: "Avg st", num: true, render: (h) => h.avg_start ?? "" },
    { key: "avg_finish", label: "Avg fin", num: true },
    { key: "rating", label: "Rating", num: true, render: (h) => h.rating ?? "" },
    { key: "par", label: "PAR", num: true, render: (h) => (h.par == null ? "" : (h.par > 0 ? "+" : "") + h.par.toFixed(1)) },
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
          ${["aggression", "adaptability", "marketability"].filter((t) => r[t] !== undefined).map((t) => `<div class="row"><span>${t[0].toUpperCase() + t.slice(1)}</span>${rating(r[t])}</div>`).join("")}
        </div>
        ${r.skills ? `<table class="tbl skills" style="margin-top:10px"><thead><tr><th>Skill</th><th class="num">Now</th><th class="num">Pot</th></tr></thead><tbody>
          ${Object.values(r.skills).map((k) => `<tr title="${esc(k.about)}"><td>${esc(k.label)}</td><td class="num">${rating(k.now)}</td><td class="num muted">${k.pot}</td></tr>`).join("")}</tbody></table>` : ""}
        ${r.tracks ? `<h4>Track experience</h4><div class="ratings-grid">${Object.values(r.tracks).map((t) => `<div class="row"><span>${esc(t.label)}</span><span class="statbar" style="display:inline-block;width:90px"><i style="width:${t.exp}%"></i></span></div>`).join("")}</div>` : ""}
        <p class="muted small" style="margin:10px 0 0">20–80 scale (50 = average at the top level). ${r.exact ? "Your own driver: you know exactly where you stand." : "Scouts' view: 5-point steps, and only as accurate as how much they've seen of this driver."}</p>
      </div>
      ${r.personality ? `<div class="card"><h3>Personality</h3><dl class="kv">${r.personality.map((p) => `<dt title="${esc(p.about)}">${esc(p.label)}</dt><dd>${p.value != null ? p.value + " · " : ""}${esc(p.word)}</dd>`).join("")}</dl>
        <p class="muted small">${r.exact ? "You know yourself." : "Paddock impressions, not numbers."} Work ethic and intelligence drive development; loyalty, greed and desire to win shape contract decisions; temper shows on track.</p>
        ${r.mood ? `<h4>Mood</h4><dl class="kv"><dt>Morale</dt><dd>${r.mood.morale != null ? r.mood.morale + " · " : ""}${esc(r.mood.word)}</dd>
          ${r.mood.goal ? `<dt>Owner's goal</dt><dd>${esc(r.mood.goal.label)} <span class="muted small">(${r.mood.goal.year})</span>${r.mood.goal.result ? ` · <b>${esc(r.mood.goal.result)}</b>${r.mood.goal.pos ? ` (P${r.mood.goal.pos})` : ""}` : ""}</dd>` : ""}
          ${r.mood.security_word ? `<dt>Job security</dt><dd>${r.mood.security != null ? r.mood.security + " · " : ""}${esc(r.mood.security_word)}</dd>` : ""}
          ${r.mood.suspension ? `<dt>Suspended</dt><dd>${r.mood.suspension} race${r.mood.suspension === 1 ? "" : "s"}</dd>` : ""}
          <dt>Rivals</dt><dd>${r.mood.rivals.length ? r.mood.rivals.map((x) => `${driverLink(x.id, x.name)} <span class="muted small">(${esc(x.word)})</span>`).join(", ") : "<span class=\"muted\">none</span>"}</dd></dl>
          <p class="muted small">Confident drivers are a little faster and develop faster. Get wrecked and you remember who did it.</p>` : ""}</div>` : ""}
      <div class="card"><h3>Profile</h3>
        <dl class="kv">
          <dt>Born</dt><dd>${d.birth_year} (age ${d.age})</dd>
          <dt>Home</dt><dd>${esc(d.home_name)}, ${esc(d.country)}</dd>
          <dt>Category</dt><dd>${esc(d.category)} <span class="muted small">(sports-car rating)</span></dd>
          <dt>Best level</dt><dd>${tierBadge(d.max_tier)}</dd>
          <dt>Starts / wins</dt><dd>${d.starts} / ${d.wins}</dd>
          ${d.fans ? `<dt>Fans</dt><dd>${esc(d.fans.label)}${d.fans.rank ? ` <span class="muted small">(#${d.fans.rank})</span>` : ""}</dd>` : ""}
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
      <div class="grid"><div class="card flush"><h3>Career history</h3>${table("hist", histCols, d.history.slice().reverse(), { empty: "No completed seasons yet." })}
        <p class="muted small" style="padding:0 16px 12px">PAR: positions above replacement - how much better they finished than a replacement-level driver would in the same cars (1 PAR ≈ 80 positions in a 40-car field, scaled to a 30-race season). A solid regular is worth 2-4; a great season 6-9.</p></div>
        ${(d.splits || []).length ? `<div class="card flush"><h3>By track type <span class="muted small">(touring and national)</span></h3>${table("splits", [
          { key: "type", label: "Track type" }, { key: "starts", label: "St", num: true }, { key: "wins", label: "W", num: true },
          { key: "top5", label: "T5", num: true }, { key: "avg_finish", label: "Avg fin", num: true }, { key: "laps_led", label: "Led", num: true }], d.splits)}</div>` : ""}</div>
      <div class="grid"><div class="card"><h3>Career log</h3>
        ${d.titles_list.length ? `<div class="chips" style="margin-bottom:10px">${d.titles_list.map((t) => `<span class="chip">🏆 ${esc(t)}</span>`).join("")}</div>` : ""}
        ${(d.awards || []).length ? `<div class="chips" style="margin-bottom:10px">${d.awards.map((t) => `<span class="chip">🏅 ${esc(t)}</span>`).join("")}</div>` : ""}
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
  const ownSeat = o.choices.find((c) => c.kind === "own_team");
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
        ${ownSeat ? `<div class="card"><h3>Your own team</h3><p>Drive for ${teamLink(ownSeat.team)} in the ${seriesLink(ownSeat.series)}. The car is yours: no salary, and any losses come out of your savings.</p>
          <button class="primary" data-act="choose" data-id="own_team">Drive my own car</button></div>` : ""}
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
            ${a.options ? `<select id="act-arg-${esc(a.id)}" ${a.used ? "disabled" : ""}>${a.options.map((x) => `<option value="${esc(x.value)}" ${x.selected ? "selected" : ""}>${esc(x.label)}</option>`).join("")}</select>` : ""}
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
  const argEl = $("#act-arg-" + id);
  const arg = id === "relocate" ? $("#relocate-to").value : argEl ? argEl.value : undefined;
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
  const tabs = [["standings", "Standings"], ["schedule", "Schedule & results"], ["field", s.template.team_based ? "Teams" : "Field"], ["power", "Power rankings"], ["champions", "Champions"], ["about", "About"]];
  const body = {
    standings: () => `<div class="card flush">${table("ser-st", standingCols(), s.standings, { rowClass: (r) => (r.is_player ? "me" : ""), empty: "No standings yet." })}</div>`,
    schedule: () => `<div class="card flush">${scheduleTable("ser-sch", s.schedule, s, true)}</div>`,
    field: () => t.team_based
      ? `<div class="grid g2">${s.teams.map((tm) => `<div class="card"><div class="card-head"><div><b>${teamLink(tm)}</b> ${tm.manufacturer ? `<span class="badge">${esc(tm.manufacturer)}</span>` : ""}</div>${rating(Math.round(20 + tm.equipment * 0.6), { title: "Equipment" })}</div>
          <div class="muted small">${tm.cars} car${tm.cars > 1 ? "s" : ""} · raises ${money(tm.funding_per_seat)}/seat · ${esc(tm.owner_type)} owner</div>
          ${tm.roster.length ? tm.roster.map((r) => `<div class="small" style="margin-top:4px">${driverLink(r.id, r.name, r.is_player)} <span class="muted">(${r.age})</span> ${rating(r.overall)} ${r.funded ? "" : '<span class="badge warn">pay</span>'}</div>`).join("") : '<div class="muted small">Empty seat</div>'}
        </div>`).join("")}</div>`
      : `<div class="card flush">${driversTable("ser-field", s.drivers)}</div>`,
    power: () => `<div class="card flush">${table("ser-pw", [
        { key: "rank", label: "#", num: true }, { key: "name", label: "Driver", render: (r) => driverLink(r.id, r.name, r.is_player, r.real) },
        { key: "team", label: "Team", render: (r) => teamLink(r.team), sort: (r) => r.team?.name || "" },
        { key: "media", label: "Media rating", num: true, render: (r) => rating(r.media) },
        { key: "form", label: "Form", num: true, render: (r) => (r.form == null ? "—" : r.form + "%") },
        { key: "reputation", label: "Rep", num: true }], s.power || [], { empty: "Nobody to rank yet." })}
      <p class="muted small" style="padding:0 16px 12px">The media's view: results shown, name and this season's form. Everyone sees this; your scouts' reports are on each driver's page.</p></div>`,
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
  const hasBox = r.results.some((x) => x.box);
  const b = (x, k) => (x.box ? x.box[k] : "");
  const rc = r.race;
  const cols = [
    { key: "pos", label: "Pos", num: true, render: (x) => posCell(x.pos) },
    ...(hasBox ? [{ key: "start", label: "St", num: true, sort: (x) => b(x, "start"), render: (x) => b(x, "start") }] : []),
    { key: "name", label: "Driver", render: (x) => `${driverLink(x.driver_id, x.name, x.is_player)}${x.co_drivers.length ? ` <span class="muted small">/ ${x.co_drivers.map((c) => esc(c.name)).join(", ")}</span>` : ""}` },
    { key: "team", label: "Team", render: (x) => teamLink(x.team), sort: (x) => x.team?.name || "" },
    ...(hasBox ? [
      { key: "laps", label: "Laps", num: true, sort: (x) => b(x, "laps"), render: (x) => b(x, "laps") },
      { key: "led", label: "Led", num: true, sort: (x) => b(x, "led"), render: (x) => (b(x, "led") || "") + (x.box && x.box.most_led ? " ★" : "") },
      { key: "status", label: "Status", sort: (x) => b(x, "status"), render: (x) => (x.box && x.box.status !== "running" ? `<span class="badge bad">${esc(x.box.status)}</span>` : '<span class="muted small">running</span>') },
      { key: "arp", label: "Avg run", num: true, sort: (x) => b(x, "arp"), render: (x) => b(x, "arp") },
      { key: "passes", label: "Passes", num: true, sort: (x) => b(x, "passes"), render: (x) => b(x, "passes") },
      { key: "fast", label: "Fast laps", num: true, sort: (x) => b(x, "fast_laps"), render: (x) => b(x, "fast_laps") || "" },
      { key: "pits", label: "Pits", num: true, sort: (x) => b(x, "pits"), render: (x) => b(x, "pits") },
      { key: "rating", label: "Rating", num: true, sort: (x) => b(x, "rating"), render: (x) => b(x, "rating") },
    ] : [
      { key: "tier", label: "Usual tier", num: true, render: (x) => tierBadge(x.tier) },
      { key: "dnf", label: "", render: (x) => (x.dnf ? '<span class="badge bad">DNF</span>' : "") },
    ]),
  ];
  view(`<h1>${esc(r.jewel || (r.series && r.series.name) || "Race")}</h1>
    ${r.has_replay ? `<a class="btn primary" href="#/watch/${encodeURIComponent(key)}/${ev}/${year || S.status.year}">▶ Watch the race</a>` : ""}
    <p class="sub">${trackLink(r.track_id, r.track)} · ${esc(r.label)}${rc ? ` · ${rc.laps}${rc.scheduled && rc.scheduled > rc.laps ? ` of ${rc.scheduled}` : ""} laps${rc.weather ? ` · ${esc(rc.weather)}` : ""} · ${rc.cautions} caution${rc.cautions === 1 ? "" : "s"} for ${rc.caution_laps} laps · ${rc.lead_changes} lead change${rc.lead_changes === 1 ? "" : "s"} among ${rc.leaders} leader${rc.leaders === 1 ? "" : "s"}${rc.margin ? ` · margin ${rc.margin.toFixed(3)}s` : ""}` : ""}</p>
    <div class="card flush">${table("race", cols, r.results, { rowClass: (x) => (x.is_player ? "me" : "") })}</div>
    ${r.log && r.log.length ? `<div class="card" style="margin-top:16px"><h3>Lap by lap</h3><ul class="timeline">${r.log.map((l) => `<li><b>Lap ${l[0]}</b> ${esc(l[1])}</li>`).join("")}</ul></div>` : ""}`);
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
    </div>
    ${(t.staff || []).length ? `<div class="card flush" style="margin-top:16px"><h3 style="padding:14px 16px 0">The people</h3>${staffTable("team-staff", t.staff, true)}</div>` : ""}
    ${t.finance ? financeCard(t) : ""}`);
}
const FIN_LABELS = { sponsors: "Sponsors", charter: "Charter money", owner: "Owner's money", pay_drivers: "Drivers' money",
  purse: "Purses and points fund", merchandise: "Merchandise", manufacturer: "Manufacturer support",
  running: "Running the cars", staff: "Staff", driver_salaries: "Driver salaries" };
function financeCard(t) {
  const f = t.finance, b = f.last;
  const ix = (x) => (x && x.idx) || undefined;        // each season's books in that season's dollars
  const rows = (o) => Object.entries(o).filter(([, v]) => v).map(([k, v]) => `<dt>${esc(FIN_LABELS[k] || k)}</dt><dd>${money(v, ix(b))}</dd>`).join("");
  const sum = (o) => Object.values(o).reduce((a, x) => a + x, 0);
  return `<div class="grid g3" style="margin-top:16px">
    <div class="card"><h3>${b.year} revenue</h3><dl class="kv">${rows(b.revenue)}<dt><b>Total</b></dt><dd><b>${money(sum(b.revenue), ix(b))}</b></dd></dl></div>
    <div class="card"><h3>${b.year} costs</h3><dl class="kv">${rows(b.costs)}<dt><b>Total</b></dt><dd><b>${money(sum(b.costs), ix(b))}</b></dd></dl>
      <p class="muted small">Spending level ${Math.round(b.spend * 100)}% of the series' full-season cost per car. What a team spends this year is next year's speed.</p></div>
    <div class="card"><h3>The owner's books</h3><dl class="kv"><dt>Result</dt><dd style="color:var(${b.net < 0 ? "--bad" : "--good"})">${money(b.net, ix(b))}</dd><dt>Cash</dt><dd>${money(f.cash)}</dd>
      ${f.charters ? `<dt>Charters</dt><dd>${f.charters}</dd>` : ""}<dt>Fans (drivers)</dt><dd>${esc(t.fans)}</dd></dl>
      ${f.history.length > 1 ? `<h4>Seasons</h4><ul class="timeline">${f.history.slice().reverse().slice(0, 8).map((h) => `<li><b>${h.year}</b> revenue ${money(h.revenue, ix(h))} · result ${money(h.net, ix(h))}</li>`).join("")}</ul>` : ""}
      <p class="muted small">Most teams lose money; owners cover part of it. Run dry and the team changes hands.</p></div></div>`;
}

// ---- staff (crew chiefs, spotters, pit crews, ...)
const staffLink = (s) => `<a class="link" href="#/staff/${s.id}">${esc(s.name)}</a>`;
function staffRatings(r) {
  return Object.values(r).map((x) => `<span class="nowrap small" style="margin-right:8px">${esc(x.label)} ${rating(x.value)}</span>`).join("");
}
function staffTable(id, rows, teamView) {
  return table(id, [
    { key: "role", label: "Role", render: (s) => `${esc(s.role_label)}${s.car != null && teamView ? ` <span class="muted small">car ${s.car + 1}</span>` : ""}`, sort: (s) => s.role_label },
    { key: "name", label: "Name", render: (s) => `${staffLink(s)}${s.former_driver ? ' <span class="badge" title="Former driver">ex-driver</span>' : ""}`, sort: (s) => s.name },
    ...(teamView ? [] : [{ key: "team", label: "Team", render: (s) => (s.team ? `<a class="link" href="#/team/${s.team.id}">${esc(s.team.name)}</a>` : '<span class="muted">free agent</span>'), sort: (s) => s.team?.name || "" }]),
    { key: "age", label: "Age", num: true },
    { key: "overall", label: "Overall", num: true, render: (s) => rating(s.overall) },
    { key: "ratings", label: "Ratings", nosort: true, render: (s) => staffRatings(s.ratings) },
    { key: "style", label: "Style", nosort: true, render: (s) => (s.style && s.style.preference ? `<span class="small">${s.style.aggression >= 65 ? "aggressive" : s.style.aggression <= 35 ? "conservative" : "balanced"} calls · likes it ${esc(s.style.preference)}</span>` : "") },
    { key: "wins", label: "Wins", num: true },
    { key: "titles", label: "Titles", num: true },
  ], rows);
}
async function staffPage(id) {
  const s = await api("staff/" + id);
  view(`<div class="card hero"><div class="avatar">${initials(s.name)}</div>
    <div><h1>${esc(s.name)}</h1><div class="sub">${esc(s.role_label)} · age ${s.age} · ${s.team ? `<a class="link" href="#/team/${s.team.id}">${esc(s.team.name)}</a>` : "free agent"}${s.retired ? " · retired" : ""}</div>
      ${s.former_driver ? `<div class="sub">Former driver: <a class="link" href="#/driver/${s.former_driver}">${esc(s.former_driver_name || "profile")}</a></div>` : ""}</div>
    <div class="kpis"><div class="kpi"><div class="v">${rating(s.overall)}</div><div class="l">Overall</div></div>
      <div class="kpi"><div class="v">${s.reputation}</div><div class="l">Reputation</div></div>
      <div class="kpi"><div class="v">${s.wins}</div><div class="l">Wins</div></div><div class="kpi"><div class="v">${s.titles}</div><div class="l">Titles</div></div></div></div>
    <div class="grid g2" style="margin-top:16px"><div class="card"><h3>Ratings</h3><p class="muted small">${esc(s.about)}</p>
      <div class="ratings-grid">${Object.values(s.ratings).map((r) => `<div class="row"><span>${esc(r.label)}</span>${rating(r.value)}</div>`).join("")}</div>
      ${s.style && s.style.preference ? `<p class="small">Strategy style: <b>${s.style.aggression >= 65 ? "aggressive" : s.style.aggression <= 35 ? "conservative" : "balanced"}</b> (${s.style.aggression}). Likes the car <b>${esc(s.style.preference)}</b>: drivers who like it the same way go faster with this crew chief.</p>` : ""}
      ${s.salary != null ? `<p class="small">Salary ${money(s.salary)} · ${s.contract_years} more season${s.contract_years === 1 ? "" : "s"}</p>` : ""}</div>
    <div class="card flush"><h3 style="padding:14px 16px 0">Career</h3>${table("staff-hist", [{ key: "year", label: "Year", num: true }, { key: "team", label: "Team" }, { key: "series", label: "Series" }, { key: "wins", label: "Wins", num: true }, { key: "titles", label: "Titles", num: true }], s.history.slice().reverse(), { empty: "No completed seasons yet." })}</div></div>`);
}
async function staffDirPage(role = "") {
  const d = await api("staff" + (role ? "?role=" + encodeURIComponent(role) : ""));
  view(`<h1>Staff</h1><p class="muted">Crew chiefs, spotters, pit crews, technical directors, engine builders, driver coaches and medical staff. The best teams hire first; poor results cost crew chiefs their jobs.</p>
    <div class="tabs"><button class="${role ? "" : "on"}" data-act="staffrole" data-role="">All</button>${d.roles.map((r) => `<button class="${r.key === role ? "on" : ""}" data-act="staffrole" data-role="${r.key}" title="${esc(r.about)}">${esc(r.label)}</button>`).join("")}</div>
    <div class="card flush">${staffTable("staff-dir", d.staff, false)}</div>`);
}
on("staffrole", (el) => staffDirPage(el.dataset.role));

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
        ${(t.winners || []).length ? `<h3 style="margin-top:12px">Winners here</h3>${t.winners.slice(0, 20).map((x) => `<div class="small"><b>${x.year}</b> ${driverLink(x.id, x.name)} <span class="muted">${esc(x.event)}</span></div>`).join("")}` : ""}
        ${f.lat !== null && f.lon > -128 && f.lon < -56 && f.lat > 23.5 && f.lat < 56 ? `<div style="margin-top:12px">${mapSvg([{ ...f, id: t.id, name: t.name, type: f.track_type, prestige: p.prestige }], { big: true })}</div>` : ""}</div>
    </div>`);
}

// ---------------------------------------------------------------- long memory: records, almanac, Hall of Fame
const who = (x) => driverLink(x.id, x.name, x.me, x.real);
async function recordsPage(sid) {
  const r = await api("records" + (sid ? "/" + encodeURIComponent(sid) : ""));
  if (!r.series.length) { view('<div class="card empty">No touring or national seasons have been completed yet. Records start after the first season.</div>'); return; }
  const cur = r.series.find((x) => x.id === r.current);
  const pick = `<select data-change="records">${r.series.map((x) => `<option value="${esc(x.id)}" ${x.id === r.current ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select>`;
  const box = (b, season) => `<div class="card"><h3>${esc(b.label)}</h3>${b.rows.length ? `<ol class="small" style="margin:0;padding-left:20px">${b.rows.map((x) => `<li>${who(x)} <b>${typeof x.value === "number" && !Number.isInteger(x.value) ? x.value.toFixed(1) : x.value}</b>${season ? ` <span class="muted">${x.year}</span>` : ""}</li>`).join("")}</ol>` : '<div class="muted">—</div>'}</div>`;
  view(`<div class="card hero"><div><h1>Records book</h1><div class="sub">${cur ? tierBadge(cur.tier) + " " + esc(cur.name) : ""}</div></div><div>${pick}</div></div>
    <h2 style="margin:16px 0 8px">Career</h2><div class="grid g3">${Object.values(r.career).filter((b) => b.rows.length).map((b) => box(b, false)).join("")}</div>
    <h2 style="margin:16px 0 8px">Single season</h2><div class="grid g3">${Object.values(r.season).filter((b) => b.rows.length).map((b) => box(b, true)).join("")}</div>
    <p class="muted small">Seasons imported from real history carry wins, top fives, starts and titles; poles, laps led, ratings and PAR are kept from the seasons simulated in this world.</p>`);
}
async function almanacPage(year) {
  const a = await api("almanac" + (year ? "/" + year : ""));
  if (!a.years.length) { view('<div class="card empty">The almanac starts after the first completed season.</div>'); return; }
  const years = `<select data-change="almanac">${a.years.map((y) => `<option ${y === a.year ? "selected" : ""}>${y}</option>`).join("")}</select>`;
  const list = (rows, fn) => rows.length ? `<ul class="timeline">${rows.map((x) => `<li>${fn(x)}</li>`).join("")}</ul>` : '<div class="muted">—</div>';
  view(`<div class="card hero"><div><h1>${a.year} almanac</h1><div class="sub">Champions, awards and milestones</div></div><div>${years}</div></div>
    <div class="grid g3" style="margin-top:16px">
      <div class="card"><h3>Champions</h3>${list(a.champions, (x) => `${tierBadge(x.tier)} ${esc(x.series)}: ${who(x)}`)}</div>
      <div class="card"><h3>Awards</h3>${list(a.awards, (x) => `<b>${esc(x.award)}</b> <span class="muted">${esc(x.series)}</span>: ${who(x)}${x.note ? ` <span class="muted small">${esc(x.note)}</span>` : ""}`)}</div>
      <div class="card"><h3>Most valuable (PAR, national level)</h3>${list(a.par, (x) => `${who(x)} <b>${x.par > 0 ? "+" : ""}${x.par.toFixed(1)}</b> <span class="muted small">${esc(x.series)}</span>`)}</div>
      <div class="card"><h3>Crown jewels</h3>${list(a.jewels, (x) => `💎 ${esc(x.event)}: ${who(x)}`)}</div>
      <div class="card"><h3>Hall of Fame class</h3>${list(a.hof, (x) => who(x))}</div>
      <div class="card"><h3>Milestones</h3>${list(a.milestones, (x) => esc(x.text))}</div>
    </div>`);
}
async function settingsPage() {
  const r = await api("settings");
  const row = (x) => `<div style="margin:14px 0"><div><b>${esc(x.label)}</b> <span class="muted small">${esc(x.about)}</span></div>
    <input type="range" min="${x.min}" max="${x.max}" step="0.05" value="${x.value}" data-setting="${esc(x.key)}" style="width:320px">
    <span class="num" id="set-${esc(x.key)}">${x.value.toFixed(2)}×</span></div>`;
  view(`<div class="card hero"><div><h1>Settings</h1><div class="sub">Realism: 1.00× is the calibrated default. Changes apply from the next race.</div></div></div>
    <div class="card" style="margin-top:16px">${r.settings.map(row).join("")}
      <button class="primary" data-act="save-settings">Save settings</button> <button data-act="reset-settings">Defaults</button></div>`);
}
document.addEventListener("input", (e) => {
  const k = e.target.dataset && e.target.dataset.setting;
  if (k) $("#set-" + k).textContent = Number(e.target.value).toFixed(2) + "×";
});
on("save-settings", async () => {
  const values = {};
  $$("[data-setting]").forEach((el) => { values[el.dataset.setting] = Number(el.value); });
  await api("settings", { values });
  settingsPage();
});
on("reset-settings", async () => {
  const values = {};
  $$("[data-setting]").forEach((el) => { values[el.dataset.setting] = 1; });
  await api("settings", { values });
  settingsPage();
});

async function hofPage() {
  const h = await api("hof");
  view(`<div class="card hero"><div><h1>Hall of Fame</h1><div class="sub">Drivers become eligible ${h.wait} seasons after their last; the strongest cases are inducted each winter (at most three).</div></div></div>
    <div class="card flush" style="margin-top:16px">${table("hof", [
      { key: "year", label: "Class", num: true }, { key: "name", label: "Driver", render: (x) => who(x) },
      { key: "career", label: "Career" }, { key: "case", label: "The case" }, { key: "score", label: "Score", num: true }], h.inductees,
      { empty: "Nobody has been inducted yet. The first ballots come a few seasons into a world." })}</div>`);
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
const NEW = { age: 10, discipline: "karting", background: "middle", talent: "unknown", region: "NC", scale: "0.4", seed: "", start_year: 2026 };
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
          <label class="field">World size<select data-change="newf" data-k="scale"><option value="0.25" ${NEW.scale === "0.25" ? "selected" : ""}>Small (fast, ~15k drivers)</option><option value="0.4" ${NEW.scale === "0.4" ? "selected" : ""}>Standard (~25k drivers)</option><option value="0.7" ${NEW.scale === "0.7" ? "selected" : ""}>Large (~40k drivers, slower)</option></select></label>
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

// ---------------------------------------------------------------- garage (own car, class rules, money)
function usd(x, idx) {
  if (x === null || x === undefined) return "—";
  const k = idx !== undefined ? idx : (S.status && S.status.price_index) || 1;
  const v = Math.round(x * k);
  return (v < 0 ? "−$" : "$") + Math.abs(v).toLocaleString();
}
const bar = (v, color) => `<span class="statbar" style="display:inline-block;width:90px;vertical-align:middle"><i style="width:${Math.max(0, Math.min(100, v))}%;${color ? `background:${color}` : ""}"></i></span>`;
const health = (v) => bar(v, v >= 75 ? "var(--good)" : v >= 45 ? "var(--warn)" : "var(--bad)");
function srcLinks(list) {
  return (list || []).map((s) => s.url ? `<a class="link small" target="_blank" rel="noopener" href="${esc(s.url)}">${esc(s.name)} ↗</a>` : `<span class="small">${esc(s.name)}</span>`).join(" · ");
}
async function garagePage() { renderGarage(await api("garage")); }
function renderGarage(g) {
  if (!g.available) { view(`<h1>Garage</h1><div class="card empty">${esc(g.why || "No garage.")}</div>`); return; }
  const c = g.class, car = g.car, yr = g.year;
  const optRow = (kind, o, current) => `<tr class="${current ? "me" : ""}"><td>${esc(o.label)}${o.sealed ? ' <span class="badge">sealed</span>' : ""}${o.claim_usd ? ` <span class="badge warn" title="Claim rule">claim ${usd(o.claim_usd)}</span>` : ""}${!o.legal ? ' <span class="badge bad">not legal ' + yr + "</span>" : ""}
      ${o.note ? `<div class="muted small">${esc(o.note)}</div>` : ""}</td>
    <td class="num">${usd(o.usd)}</td><td class="num">${o.quality}</td>
    <td class="num small">${kind === "engines" ? (o.rebuild_races ? `${usd(o.rebuild_usd)} / ${o.rebuild_races} races` : "—") : kind === "chassis" ? (o.age ? `${o.age} yrs old` : "new") : ""}</td>
    <td>${car && !current && o.legal ? `<button class="small" data-act="garage" data-a="${kind === "engines" ? "engine" : kind}" data-k="${esc(o.key)}">Buy</button>` : current ? '<span class="badge good">fitted</span>' : ""}</td></tr>`;
  const optTable = (kind, title, list, cur) => list.length ? `<div class="card flush"><h3 style="padding:14px 16px 0">${title}</h3><div class="table-wrap"><table class="tbl"><thead><tr><th>Option</th><th class="num">Price</th><th class="num">Quality</th><th class="num">Upkeep</th><th></th></tr></thead>
    <tbody>${list.map((o) => optRow(kind, o, cur === o.key || cur === o.label)).join("")}</tbody></table></div></div>` : "";
  const t = c.tires;
  const rulesCard = `<div class="card"><div class="card-head"><h3>Class rules · ${esc(c.label)}</h3>${CONF(c.confidence)}</div>
    <dl class="kv">
      ${c.min_weight_lb ? `<dt>Minimum weight</dt><dd>${Math.round(c.min_weight_lb).toLocaleString()} lb</dd>` : ""}
      <dt>Tires</dt><dd>${esc(t.spec || "—")} · ${usd(t.usd)} each · ${t.max_new != null ? `max ${t.max_new} new per night` : "no limit on new tires"} · ~${t.life_races} nights of life</dd>
      ${t.rule ? `<dt>Tire rule</dt><dd>${esc(t.rule)}</dd>` : ""}
      <dt>Per night</dt><dd>entry & pit passes ${usd(c.per_race.entry)} · fuel ${usd(c.per_race.fuel)} · consumables ${usd(c.per_race.misc)}</dd>
      <dt>Chassis life</dt><dd>~${c.chassis_life} seasons · typical wreck ≈ ${Math.round(c.repair_frac * 100)}% of a new chassis</dd>
      <dt>Rules spread</dt><dd>${c.spread < 0.7 ? "Tight spec class: money buys little speed" : c.spread < 0.95 ? "Controlled class: parts rules limit spending" : "Open class: money buys speed"}</dd>
    </dl>
    ${c.rules.length ? `<ul class="timeline">${c.rules.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>` : ""}
    ${c.claims.length ? `<h4>Claim rules</h4><ul class="timeline">${c.claims.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>` : ""}
    ${c.history.length ? `<h4>How the rules got here</h4><ul class="timeline">${c.history.map((h) => `<li><b>${h.year}</b> ${esc(h.fact)}</li>`).join("")}</ul>` : ""}
    ${c.notes ? `<p class="muted small">${esc(c.notes)}</p>` : ""}
    <div class="muted small" style="margin-top:8px">Sources: ${srcLinks(c.sources) || "—"}</div></div>`;
  let carCard = "";
  if (car) {
    const e = car.engine, ch = car.chassis, ti = car.tires;
    carCard = `<div class="card"><div class="card-head"><h3>Your ${esc(c.label.toLowerCase())}</h3><span>${rating(car.rating, { title: esc("Car rating at " + (g.track || "an average track")) })}</span></div>
      <p class="muted small" style="margin-top:0">Car rating ${g.track ? "at " + esc(g.track) : "at an average track"}: 50 is a typical competitive car in this class. Share of the car's speed at this track — chassis ${Math.round(ch.weight * 100)}%, engine ${Math.round(e.weight * 100)}%, tires ${Math.round(ti.weight * 100)}%, shocks ${Math.round(car.shocks.weight * 100)}%.</p>
      <dl class="kv">
        <dt>Chassis</dt><dd><b>${esc(ch.label)}</b> · quality ${ch.quality} · ${ch.age} season${ch.age === 1 ? "" : "s"} old<br>condition ${health(ch.condition)} ${ch.condition}%${ch.condition < 100 ? ` <button class="small" data-act="garage" data-a="repair">Repair (${usd(ch.repair_usd)})</button>` : ""}</dd>
        <dt>Engine</dt><dd><b>${esc(e.label)}</b> · quality ${e.quality}${e.sealed ? ' · <span class="badge">sealed</span>' : ""}<br>
          ${e.interval ? `${e.runs}/${e.interval} races since freshen ${bar(100 * Math.min(1, e.runs / e.interval), e.runs > e.interval ? "var(--bad)" : e.runs > 0.8 * e.interval ? "var(--warn)" : "var(--good)")}` : `${e.runs} races`}
          · health ${health(e.health)} ${e.health}%
          <button class="small" data-act="garage" data-a="rebuild">${e.health <= 0 ? "Rebuild" : "Freshen"} (${usd(e.rebuild_usd)}${e.health < 100 ? "+" : ""})</button></dd>
        <dt>Shocks</dt><dd><b>${esc(car.shocks.label)}</b> · quality ${car.shocks.quality}</dd>
        <dt>Tires</dt><dd>set wear ${bar(100 - ti.wear * 100)} ${Math.round(ti.wear * 100)}% worn · each night wears ~${Math.round(ti.wear_per_race * 100)}%<br>
          New tires each night: <select data-change="tires">${Array.from({ length: ti.max_new + 1 }, (_, i) => `<option ${i === ti.new_per_night ? "selected" : ""}>${i}</option>`).join("")}</select>
          <span class="muted small">(${usd(t.usd)} each; rating with this policy ≈ ${car.rating_fresh_tires})</span></dd>
        <dt>Automatic</dt><dd><label class="small"><input type="checkbox" data-change="auto" data-k="auto_rebuild" ${car.auto_rebuild ? "checked" : ""}> freshen engine at interval</label>
          <label class="small" style="margin-left:10px"><input type="checkbox" data-change="auto" data-k="auto_repair" ${car.auto_repair ? "checked" : ""}> repair wrecks</label></dd>
        <dt>Resale value</dt><dd>${usd(car.resale)}</dd>
      </dl></div>`;
  } else {
    carCard = `<div class="card"><h3>You need a car</h3><p>${g.old_car ? `Your ${esc(g.old_car.class)} isn't legal here; it trades in for about ${usd(g.old_car.resale)}.` : "You don't own a car for this class yet."} Pick a package (or the season will start with the best car the budget allows).</p></div>`;
  }
  const pk = `<div class="card"><h3>${car ? "Replace the whole car" : "Car packages"}</h3><div class="offers">${g.packages.map((p) => `<div class="offer">
      <div class="top"><div class="team">${esc(p.label)}</div><div>${rating(p.rating)}</div></div>
      <div class="small">${p.parts.map(esc).join("<br>")}</div><div><b>${usd(p.usd)}</b></div>
      <button class="small" data-act="garage" data-a="new_car" data-k="${esc(p.key)}">Buy package</button></div>`).join("")}</div></div>`;
  const money = car ? `<div class="card"><h3>Racing money</h3><dl class="kv">
      ${car.account !== null ? `<dt>Racing account</dt><dd><b>${usd(car.account)}</b></dd>` : `<dt>Next season's budget</dt><dd><b>${usd(g.money.available)}</b></dd>`}
      <dt>Savings</dt><dd>${usd(g.money.savings)}</dd>
      <dt>Each night</dt><dd>${usd(car.night_cost)} entry, fuel & tires + engine wear ${usd(car.engine_wear_per_race)}${car.overhead_per_night ? ` + crew, hauler, practice & spares ${usd(car.overhead_per_night)}` : ""}</dd>
      <dt>${car.remaining_races} races left</dt><dd>≈ ${usd(car.season_running)} running costs (before travel, wrecks and purses)</dd></dl>
      ${car.ledger.length ? `<h4>Ledger</h4><div class="table-wrap" style="max-height:340px;overflow:auto"><table class="tbl"><tbody>${car.ledger.slice().reverse().map((l) => `<tr><td class="muted small nowrap">${l[3] || ""} ${l[0] === 99 ? "end" : l[0] ? "wk " + l[0] : ""}</td><td class="small">${esc(l[1])}</td><td class="num ${l[2] < 0 ? "neg" : "pos"}">${usd(l[2], 1)}</td></tr>`).join("")}</tbody></table></div>` : ""}</div>` : "";
  view(`<h1>Garage <span class="muted small">${esc(g.series.name)}</span></h1>
    ${g.message ? `<div class="callout">${esc(g.message)}</div>` : ""}
    ${g.hint ? `<div class="callout">${esc(g.hint)}</div>` : ""}
    <div class="grid g-main"><div class="grid">${carCard}${pk}
      ${optTable("chassis", "Chassis", c.chassis, car && car.chassis.label)}
      ${optTable("engines", "Engines (rules " + yr + ")", c.engines, car && car.engine.label)}
      ${optTable("shocks", "Shocks", c.shocks, car && car.shocks.label)}</div>
      <div class="grid">${money}${crewCard(g)}${rulesCard}</div></div>`);
}
function crewCard(g) {
  if (!g.crew) return "";
  return `<div class="card"><h3>Your crew</h3><p class="muted small">Hire people for the season: a crew chief (setup, strategy, adjustments), a spotter (keeps you out of wrecks, helps restarts) and a pit crew. Freelancers leave at season end.</p>
    ${g.crew.roles.map((r) => `<h4>${esc(r.label)}</h4>
      ${r.hired ? `<div class="small">${staffLink(r.hired)} · ${staffRatings(r.hired.ratings)} <button class="small" data-act="garage" data-a="release" data-k="${r.role}">Let go</button></div>` : `<div class="muted small">Nobody: friends and family help out (average).</div>`}
      <div class="table-wrap"><table class="tbl"><tbody>${r.candidates.map((c) => `<tr><td class="small">${staffLink(c)} <span class="muted">${c.age}</span></td><td class="small">${staffRatings(c.ratings)}</td><td class="num small">${usd(c.cost)}</td><td><button class="small" data-act="garage" data-a="hire" data-k="${c.id}">Hire</button></td></tr>`).join("")}</tbody></table></div>`).join("")}</div>`;
}
on("tires", async (el) => {
  try { const r = await api("garage", { action: "tires", value: parseInt(el.value, 10) }); renderGarage(r); toast(r.message); }
  catch (e) { toast(e.message, true); }
});
on("auto", async (el) => {
  try { const r = await api("garage", { action: el.dataset.k, value: el.checked ? 1 : 0 }); renderGarage(r); toast(r.message); }
  catch (e) { toast(e.message, true); }
});
on("garage", async (el) => {
  el.classList.add("busy");
  try { const r = await api("garage", { action: el.dataset.a, key: el.dataset.k }); renderGarage(r); toast(r.message); refreshStatus(); }
  catch (e) { toast(e.message, true); el.classList.remove("busy"); }
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
  [/^#\/watch\/([^/]+)\/(\d+)(?:\/(\d+))?$/, (m) => watchPage(decodeURIComponent(m[1]), m[2], m[3]), true],
  [/^#\/jewels$/, () => jewelsPage(), true],
  [/^#\/garage$/, () => garagePage(), true],
  [/^#\/shop$/, () => shopPage(), true],
  [/^#\/pyramid$/, () => pyramidPage(), true],
  [/^#\/instances\/(.+)$/, (m) => instancesPage(m[1]), true],
  [/^#\/drivers$/, () => driversPage(), true],
  [/^#\/team\/(\d+)$/, (m) => teamPage(m[1]), true],
  [/^#\/staff\/(\d+)$/, (m) => staffPage(m[1]), true],
  [/^#\/staff$/, () => staffDirPage(), true],
  [/^#\/tracks$/, () => tracksPage(), true],
  [/^#\/track\/(.+)$/, (m) => trackPage(decodeURIComponent(m[1])), true],
  [/^#\/news$/, () => newsPage(), true],
  [/^#\/records(?:\/(.+))?$/, (m) => recordsPage(m[1] && decodeURIComponent(m[1])), true],
  [/^#\/almanac(?:\/(\d+))?$/, (m) => almanacPage(m[1]), true],
  [/^#\/hof$/, () => hofPage(), true],
  [/^#\/settings$/, () => settingsPage(), true],
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
const KTABS = [["overview", "Overview"], ["series", "Series"], ["paths", "Career paths"], ["bodies", "Sanctioning bodies"], ["classes", "Car classes"], ["rules", "Rules & money"], ["factors", "What drives careers"], ["sources", "Sources"]];
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
  if (tab === "rules" && arg) return rulesClassPage(arg, head);
  if (tab === "rules") {
    const r = await api("knowledge/rules");
    const pointsLine = (p) => p.table && p.table.length ? p.table.join(", ") + (p.table.length >= 12 ? " …" : "")
      : p.step ? `${p.step.first} to win, −${p.step.step} per position (min ${p.step.min})` : "—";
    view(`${head}<p class="muted">What racers actually build, buy and race for: researched class rules (track house rules and sanctioning rulebooks), part prices and lifespans, points systems, purses and fees. The game's garage, points and payouts are built from these records.</p>
      <div class="card"><div class="kpis" style="flex-wrap:wrap">${Object.entries(r.counts).map(([k, v]) => `<div class="kpi"><div class="v">${v}</div><div class="l">${esc(k.replace(/_/g, " "))}</div></div>`).join("")}<div class="kpi"><div class="v">${r.sources}</div><div class="l">sources</div></div></div></div>
      <div class="card flush" style="margin-top:16px"><h3>Car classes in the game</h3>${table("rcl", [
        { key: "label", label: "Class", render: (c) => `<a class="link" href="#/encyclopedia/rules/${encodeURIComponent(c.key)}">${esc(c.label)}</a>` },
        { key: "discipline", label: "Discipline" }, { key: "records", label: "Research records", num: true },
        { key: "confidence", label: "Confidence", render: (c) => CONF(c.confidence) }], r.classes)}</div>
      <div class="card flush" style="margin-top:16px"><h3>Points systems</h3>${table("rpts", [
        { key: "label", label: "System", render: (p) => `<b>${esc(p.label)}</b>${p.note ? `<div class="muted small">${esc(p.note)}</div>` : ""}` },
        { key: "table", label: "Feature points", nosort: true, render: (p) => `<span class="small">${esc(pointsLine(p))}</span>` },
        { key: "bonus", label: "Bonuses", nosort: true, render: (p) => `<span class="small">${[p.win_bonus && `win +${p.win_bonus}`, p.led_lap && `led a lap +${p.led_lap}`, p.most_led && `most laps led +${p.most_led}`, p.stages && `${p.stages} stages (${p.stage.join("-")})`, p.heat && p.heat.length && `heats ${p.heat.join("-")}`, p.show_up && `show-up ${p.show_up}`].filter(Boolean).join(" · ") || "—"}</span>` },
        { key: "confidence", label: "Conf.", render: (p) => CONF(p.confidence) },
        { key: "src", label: "Sources", nosort: true, render: (p) => srcLinks(p.sources) }], r.points)}</div>
      <div class="card flush" style="margin-top:16px"><h3>Championship formats</h3>${table("rfmt", [
        { key: "label", label: "Format", render: (f) => `<b>${esc(f.label)}</b>${f.note ? `<div class="muted small">${esc(f.note)}</div>` : ""}` },
        { key: "kind", label: "Kind" }, { key: "drivers", label: "Drivers", num: true }, { key: "races", label: "Races", num: true },
        { key: "confidence", label: "Conf.", render: (f) => CONF(f.confidence) }, { key: "src", label: "Sources", nosort: true, render: (f) => srcLinks(f.sources) }], r.formats)}</div>
      <div class="card flush" style="margin-top:16px"><h3>Purses</h3>${table("rpay", [
        { key: "label", label: "Payout", render: (t) => `<b>${esc(t.label)}</b>${t.note ? `<div class="muted small">${esc(t.note)}</div>` : ""}` },
        { key: "year", label: "Year", num: true },
        { key: "win", label: "To win", num: true, sort: (t) => t.by_position[0] || 0, render: (t) => t.by_position.length ? "$" + Math.round(t.by_position[0]).toLocaleString() : "—" },
        { key: "top", label: "Top 10", nosort: true, render: (t) => `<span class="small">${t.by_position.map((x) => "$" + Math.round(x).toLocaleString()).join(", ")}</span>` },
        { key: "to_start", label: "To start", num: true, render: (t) => t.to_start ? "$" + Math.round(t.to_start).toLocaleString() : "—" },
        { key: "confidence", label: "Conf.", render: (t) => CONF(t.confidence) }, { key: "src", label: "Sources", nosort: true, render: (t) => srcLinks(t.sources) }], r.payouts)}
        <p class="muted small" style="padding:0 16px 12px">Purses are shown in the dollars of the year they were published. In the game, weekly purses keep most of their nominal value across eras, as they did in real life, while costs rise.</p></div>
      <div class="card" style="margin-top:16px"><h3>How the rules changed</h3><ul class="timeline">${r.history.slice().sort((a, b) => (a.year || 0) - (b.year || 0)).map((h) => `<li><b>${h.year || ""}</b> ${esc(h.topic || "")}: ${esc(h.fact || "")} ${CONF(h.confidence)} ${srcLinks(h.sources)}</li>`).join("")}</ul></div>`);
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
async function rulesClassPage(key, head) {
  const r = await api("knowledge/rules/" + encodeURIComponent(key));
  const c = r.class, ev = r.evidence;
  const rng = (x) => (x && typeof x === "object" ? factText(x) : esc(x ?? "—"));
  const recs = ev.class_rules.map((x) => `<div class="card" style="margin-bottom:12px"><div class="card-head"><h3>${esc(x.body || "")} <span class="muted small">${esc(x.region || "")} · ${x.year || ""}</span></h3>${CONF(x.confidence)}</div>
    <dl class="kv">${x.min_weight_lb ? `<dt>Min weight</dt><dd>${rng(x.min_weight_lb)}${x.weight_notes ? ` <span class="muted small">${esc(x.weight_notes)}</span>` : ""}</dd>` : ""}
      ${(x.engines || []).map((e) => `<dt>Engine</dt><dd><b>${esc(e.name)}</b> <span class="badge">${esc(e.type || "")}</span> ${e.hp ? "· " + rng(e.hp) : ""} ${e.purchase_usd ? "· buy " + rng(e.purchase_usd) : ""} ${e.rebuild_usd ? "· rebuild " + rng(e.rebuild_usd) : ""} ${e.rebuild_interval ? "every " + rng(e.rebuild_interval) : ""} ${e.claim_usd ? "· claim " + rng(e.claim_usd) : ""}${e.notes ? `<div class="muted small">${esc(e.notes)}</div>` : ""}</dd>`).join("")}
      ${x.tires ? `<dt>Tires</dt><dd>${esc([x.tires.brand, x.tires.compound].filter(Boolean).join(" "))} ${x.tires.rule ? "· " + esc(x.tires.rule) : ""} ${x.tires.per_tire_usd ? "· " + rng(x.tires.per_tire_usd) + " each" : ""} ${x.tires.new_per_night ? "· new per night " + rng(x.tires.new_per_night) : ""}${x.tires.notes ? `<div class="muted small">${esc(x.tires.notes)}</div>` : ""}</dd>` : ""}
      ${x.chassis && x.chassis.rule ? `<dt>Chassis</dt><dd>${esc(x.chassis.rule)} ${x.chassis.purchase_usd ? "· " + rng(x.chassis.purchase_usd) : ""}</dd>` : ""}
      ${x.shocks && x.shocks.rule ? `<dt>Shocks</dt><dd>${esc(x.shocks.rule)}</dd>` : ""}
      ${x.fuel ? `<dt>Fuel</dt><dd>${esc(x.fuel)}</dd>` : ""}
      ${(x.claims || []).map((cl) => `<dt>Claim</dt><dd>${esc(cl.item || "")} ${rng(cl.usd)} ${cl.notes ? `<span class="muted small">${esc(cl.notes)}</span>` : ""}</dd>`).join("")}
      ${x.season_cost_usd ? `<dt>Season cost</dt><dd>${rng(x.season_cost_usd)}</dd>` : ""}</dl>
    ${(x.other || []).length ? `<ul class="timeline">${x.other.map((o) => `<li>${esc(o)}</li>`).join("")}</ul>` : ""}
    <div class="muted small">${srcLinks(x.sources)}</div></div>`).join("");
  view(`${head}<h2>${esc(c ? c.label : key)}</h2>
    <div class="grid g-main"><div>${recs || '<div class="card empty">No rulebook records for this class yet.</div>'}</div>
    <div class="grid">${c ? `<div class="card"><h3>In the game</h3><dl class="kv"><dt>Tires</dt><dd>${esc(c.tires.spec)} · $${Math.round(c.tires.usd)} · ${c.tires.max_new != null ? "max " + c.tires.max_new + " new/night" : "open"}</dd>
      <dt>Engines</dt><dd>${c.engines.map((e) => `${esc(e.label)} ($${Math.round(e.usd).toLocaleString()}${e.years ? `, ${e.years[0]}–${e.years[1] > 2030 ? "" : e.years[1]}` : ""})`).join("<br>")}</dd>
      <dt>Chassis</dt><dd>${c.chassis.map((o) => `${esc(o.label)} ($${Math.round(o.usd).toLocaleString()})`).join("<br>")}</dd>
      <dt>Per night</dt><dd>$${Math.round(c.per_race.entry + c.per_race.fuel + c.per_race.misc)} before tires</dd></dl>
      <p class="muted small">Game values are 2025 dollars, taken from the research ranges at left.</p></div>` : ""}
      ${ev.parts.length ? `<div class="card flush"><h3>Parts & prices</h3>${table("rparts", [{ key: "part", label: "Part" }, { key: "item", label: "Item", render: (p) => `<span class="small">${esc(p.item)}</span>` }, { key: "usd", label: "Price", sort: (p) => p.usd?.min, render: (p) => rng(p.usd) }, { key: "life", label: "Life", nosort: true, render: (p) => rng(p.life) }, { key: "src", label: "", nosort: true, render: (p) => srcLinks(p.sources) }], ev.parts)}</div>` : ""}
      ${ev.payouts.length ? `<div class="card"><h3>Purses</h3><ul class="timeline">${ev.payouts.map((p) => `<li><b>${esc(p.body || "")}</b> ${p.year || ""} ${p.to_win_usd ? "· to win " + rng(p.to_win_usd) : ""} ${p.to_start_usd ? "· to start " + rng(p.to_start_usd) : ""} ${p.entry_fee_usd ? "· entry " + rng(p.entry_fee_usd) : ""} ${srcLinks(p.sources)}</li>`).join("")}</ul></div>` : ""}
      ${ev.points_systems.length ? `<div class="card"><h3>Points</h3><ul class="timeline">${ev.points_systems.map((p) => `<li><b>${esc(p.body || "")}</b> ${p.year || ""}: ${esc(typeof p.feature_points === "string" ? p.feature_points : JSON.stringify(p.feature_points))} ${srcLinks(p.sources)}</li>`).join("")}</ul></div>` : ""}
      ${ev.race_formats.length ? `<div class="card"><h3>Race night</h3><ul class="timeline">${ev.race_formats.map((f) => `<li><b>${esc(f.body || "")}</b>: ${esc(f.format || "")} ${srcLinks(f.sources)}</li>`).join("")}</ul></div>` : ""}
    </div></div>`);
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
