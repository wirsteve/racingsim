/* racingsim Race Shop: the hauler, the shop, the fleet, the engine stand and the classifieds. */
"use strict";

// Side-on drawings of each rig (120 x 44 units): tow vehicle + trailer.
function haulerSvg(key, w = 240) {
  const car = (x, y, s = 1, c = "#c23d6b") => `<g transform="translate(${x},${y}) scale(${s})"><path d="M0 8 L4 3 L13 1 L21 3 L26 8 Z" fill="${c}"/><circle cx="6" cy="8.5" r="2.2" fill="#222"/><circle cx="20" cy="8.5" r="2.2" fill="#222"/></g>`;
  const wheel = (x, y = 38, r = 3.4) => `<circle cx="${x}" cy="${y}" r="${r}" fill="#1b1f27" stroke="#888" stroke-width="0.8"/>`;
  const pickup = (x) => `<path d="M${x} 36 L${x} 26 L${x + 8} 26 L${x + 12} 19 L${x + 22} 19 L${x + 24} 26 L${x + 30} 27 L${x + 30} 36 Z" fill="#4f6aa8"/><path d="M${x + 13} 21 L${x + 21} 21 L${x + 22} 25 L${x + 11} 25 Z" fill="#cfe3ff"/>${wheel(x + 6)}${wheel(x + 24)}`;
  const dually = (x) => `<path d="M${x} 36 L${x} 24 L${x + 9} 24 L${x + 13} 16 L${x + 25} 16 L${x + 27} 24 L${x + 34} 25 L${x + 34} 36 Z" fill="#2b2f3a"/><path d="M${x + 14} 18 L${x + 24} 18 L${x + 25} 23 L${x + 12} 23 Z" fill="#cfe3ff"/>${wheel(x + 7)}${wheel(x + 27)}`;
  const tractor = (x) => `<path d="M${x} 37 L${x} 12 L${x + 14} 12 L${x + 20} 20 L${x + 26} 22 L${x + 26} 37 Z" fill="#c4352b"/><rect x="${x + 2}" y="14" width="9" height="7" fill="#cfe3ff"/><rect x="${x + 22}" y="4" width="2" height="10" fill="#999"/>${wheel(x + 6)}${wheel(x + 21)}`;
  let body = "";
  if (key === "open") body = `${pickup(88)}<rect x="22" y="33" width="64" height="2" fill="#777"/><rect x="84" y="32" width="6" height="2" fill="#777"/>${car(32, 22, 1.5)}${wheel(48)}${wheel(57)}`;
  else if (key === "enclosed") body = `${pickup(88)}<rect x="14" y="12" width="72" height="23" rx="2" fill="#e8ebf2" stroke="#99a" stroke-width="0.8"/><rect x="84" y="31" width="6" height="2" fill="#777"/><text x="50" y="27" text-anchor="middle" font-size="7" fill="#c23d6b" font-weight="700">RACING</text>${wheel(44)}${wheel(53)}`;
  else if (key === "race_trailer") body = `${dually(84)}<path d="M4 10 L74 10 L74 6 L92 6 L92 14 L74 14 L74 35 L4 35 Z" fill="#f4f6fa" stroke="#99a" stroke-width="0.8"/><rect x="4" y="18" width="70" height="4" fill="#c23d6b"/><rect x="8" y="12" width="10" height="4" fill="#cfe3ff"/>${wheel(30)}${wheel(39)}${wheel(48)}`;
  else if (key === "stacker") body = `${dually(84)}<path d="M2 4 L76 4 L76 2 L94 2 L94 12 L76 12 L76 35 L2 35 Z" fill="#20242e"/><rect x="2" y="16" width="74" height="3" fill="#ffb400"/>${car(8, 6, 1.3, "#ffb400")}${car(40, 6, 1.3, "#2a6fd6")}<rect x="6" y="22" width="66" height="11" fill="#2b303c"/>${wheel(22)}${wheel(31)}${wheel(40)}`;
  else body = `${tractor(92)}<rect x="0" y="4" width="92" height="31" rx="1.5" fill="#f4f6fa" stroke="#99a" stroke-width="0.8"/><path d="M0 22 L92 12 L92 18 L0 28 Z" fill="#c23d6b"/><path d="M0 28 L92 18 L92 21 L0 31 Z" fill="#ffb400"/><text x="44" y="12" text-anchor="middle" font-size="6" fill="#20242e" font-weight="800" letter-spacing="1">RACE TEAM</text>${wheel(10)}${wheel(19)}`;
  return `<svg class="rig" viewBox="0 0 120 44" width="${w}" height="${(w * 44) / 120}" aria-hidden="true"><rect x="0" y="41.5" width="120" height="1" fill="#556"/>${body}</svg>`;
}

const pips = (lv, n) => `<span class="pips">${Array.from({ length: n }, (_, i) => `<i class="${i <= lv ? "on" : ""}"></i>`).join("")}</span>`;

async function shopPage() { renderShop(await api("shop")); }

function renderShop(g) {
  if (!g.available) { view(`<h1>Race Shop</h1><div class="card empty">${esc(g.why || "No shop.")}</div>`); return; }
  const h = g.hauler, cur = h.options.find((o) => o.current);
  const money = `<div class="shop-money">
      <div><span class="k">Savings</span><b>${usd(g.money.savings)}</b></div>
      ${g.money.account !== null ? `<div><span class="k">Racing account</span><b>${usd(g.money.account)}</b></div>` : `<div><span class="k">Next season's money</span><b>${usd(g.money.available)}</b></div>`}
      <div><span class="k">Rig & shop upkeep / season</span><b>${usd(g.upkeep)}</b>${g.typical_upkeep !== undefined ? `<span class="muted small">a typical ${esc(g.series ? g.series.name : "")} racer: ${usd(g.typical_upkeep)} (already in the class budget)</span>` : ""}</div>
      <div><span class="k">Cars kept</span><b>${g.capacity.kept} / ${g.capacity.cars}</b><span class="muted small">${g.capacity.spares} / ${g.capacity.engines} spare engines</span></div></div>`;
  const rig = `<div class="card"><h2>The rig</h2>
    <div class="rig-hero">${haulerSvg(cur.key, 360)}<div><h3>${esc(cur.label)}</h3><div class="muted small">${cur.age ? "" : ""}${esc(cur.about)}</div>
      <div class="small" style="margin-top:6px">${esc(cur.effect)} · ${h.age} season${h.age === 1 ? "" : "s"} old · trade-in ${usd(h.trade)}</div></div></div>
    <div class="rig-grid">${h.options.filter((o) => !o.current).map((o) => `<div class="rig-card">${haulerSvg(o.key, 200)}
      <div class="t">${esc(o.label)}</div><div class="muted small">${esc(o.about)}</div>
      <div class="small">${esc(o.effect)}</div>
      <div class="small">Price ${usd(o.usd)} · upkeep ${usd(o.upkeep)}/season</div>
      <button class="small" data-act="shop" data-a="hauler" data-k="${o.key}" data-confirm="${esc(o.usd >= h.trade ? `Buy the ${o.label.toLowerCase()} for ${usd(o.usd - h.trade)} after the trade-in?` : `Trade down to the ${o.label.toLowerCase()}?`)}">${o.usd >= h.trade ? `Buy (${usd(o.usd - h.trade)} after trade-in)` : `Trade down (${usd(h.trade - o.usd)} back)`}</button></div>`).join("")}</div></div>`;
  const facs = `<div class="card"><h2>The shop</h2><div class="fac-grid">${g.facilities.map((f) => {
    const lv = f.levels[f.level], nx = f.levels[f.level + 1];
    return `<div class="fac"><div class="fac-head"><b>${esc(f.label)}</b>${pips(f.level, f.levels.length)}</div>
      <div class="t">${esc(lv.label)}</div><div class="muted small">${esc(lv.about)}</div><div class="small eff">${esc(lv.effect)}</div>
      ${nx ? `<div class="fac-next"><div class="small"><b>Next: ${esc(nx.label)}</b> — ${usd(nx.usd)}, upkeep ${usd(nx.upkeep)}/season</div><div class="small muted">${esc(nx.effect)}</div>
        <button class="small primary" data-act="shop" data-a="upgrade" data-k="${f.key}">Upgrade</button></div>` : `<div class="small ok-text">Top of the line.</div>`}
      ${f.level > 0 ? `<button class="small ghost" data-act="shop" data-a="downgrade" data-k="${f.key}" title="Sell it off for 40% of what it cost" data-confirm="Sell off the ${esc(lv.label.toLowerCase())} for 40% of what it cost?">Sell off</button>` : ""}</div>`;
  }).join("")}</div></div>`;
  let fleet = "";
  if (g.class) {
    const carCard = (c) => `<div class="car-card ${c.primary ? "primary" : ""}"><div class="car-head"><span class="carnum">${esc(c.tag.replace("Car ", "#"))}</span><b>${esc(c.tag)}</b>${c.primary ? ' <span class="badge good">primary</span>' : ""}<span class="car-rating">${rating(c.rating, { title: "Car rating at your home track" })}</span></div>
      <dl class="kv small"><dt>Chassis</dt><dd>${esc(c.chassis)} · q${c.quality} · ${c.age} seasons</dd>
        <dt>Body</dt><dd>${health(c.condition)} ${c.condition}%</dd>
        <dt>Engine</dt><dd>${esc(c.engine)}${c.sealed ? ' <span class="badge">sealed</span>' : ""} · ${c.runs}${c.interval ? "/" + c.interval : ""} races</dd>
        <dt>Engine health</dt><dd>${health(c.health)} ${c.health}%</dd>
        <dt>Shocks</dt><dd>${esc(c.shocks)}</dd><dt>Worth</dt><dd>${usd(c.resale)}</dd></dl>
      ${c.primary ? `<a class="btn small" href="#/garage">Work on it in the Garage</a>` : `<button class="small" data-act="shop" data-a="primary" data-k="${c.idx}">Make primary</button> <button class="small ghost" data-act="shop" data-a="sell_car" data-k="${c.idx}" data-confirm="Sell ${esc(c.tag)} for about ${usd(c.resale)}?">Sell (${usd(c.resale)})</button>`}</div>`;
    const proj = g.projects.map((p) => `<div class="car-card building"><div class="car-head"><span class="carnum">${esc(p.tag.replace("Car ", "#"))}</span><b>${esc(p.tag)}</b> <span class="badge warn">on the jig</span></div>
      <div class="small">${esc(p.chassis)} · chassis quality ${p.quality}</div><div class="small muted">${g.in_season ? `ready week ${p.ready_week}` : "ready for opening night"}</div></div>`).join("");
    const b = g.build;
    const sel = (id, opts) => `<select id="${id}" data-change="buildcost">${opts.map((o) => `<option value="${esc(o.key)}" data-usd="${o.usd}">${esc(o.label)} — ${usd(o.usd)} (q${o.quality})</option>`).join("")}</select>`;
    const build = `<div class="card"><h2>Build a car</h2>${b.allowed
      ? `<p class="muted small">Buy a bare chassis kit and build it in your shop (${b.weeks} weeks${b.bonus ? `, ${b.bonus > 0 ? "+" : ""}${b.bonus} chassis quality from your fabrication` : ""}). The car joins the fleet as a backup.</p>
        <div class="build-form"><label>Chassis kit ${sel("b-ch", b.chassis)}</label><label>Engine ${sel("b-en", b.engines)}</label><label>Shocks ${sel("b-sh", b.shocks)}</label>
        <div><span id="b-total" class="big"></span> <button class="primary" data-act="shopbuild">Start the build</button></div></div>`
      : `<p class="muted">You need a welder and a tube bender (Fabrication, level 1) to build your own cars. Until then, buy turnkey packages in the Garage or a used car below.</p>`}</div>`;
    const engines = `<div class="card"><h2>Engine stand</h2>
      ${g.engines.length ? `<div class="table-wrap"><table><thead><tr><th>Spare engine</th><th class="num">Races</th><th>Health</th><th></th></tr></thead><tbody>${g.engines.map((e) => `<tr><td>${esc(e.label)}${e.sealed ? ' <span class="badge">sealed</span>' : ""}</td><td class="num">${e.runs}</td><td>${health(e.health)} ${e.health}%</td>
        <td><button class="small" data-act="shop" data-a="swap_engine" data-k="${e.idx}">Swap into primary</button> <button class="small" data-act="shop" data-a="freshen_engine" data-k="${e.idx}" ${e.runs === 0 && e.health >= 100 ? "disabled" : ""}>Freshen (${usd(e.freshen)})</button> <button class="small ghost" data-act="shop" data-a="sell_engine" data-k="${e.idx}">Sell (${usd(e.value)})</button></td></tr>`).join("")}</tbody></table></div>` : `<p class="muted small">No spare engines. A spare on the stand means a blown engine doesn't cost you the next race.</p>`}
      <div class="toolbar"><select id="new-engine">${g.new_engines.map((e) => `<option value="${esc(e.key)}">${esc(e.label)} — ${usd(e.usd)}${e.sealed ? " (sealed)" : ""}</option>`).join("")}</select>
      <button class="small" data-act="shopengine">Buy a spare engine</button></div></div>`;
    const market = `<div class="card"><h2>Classifieds: used ${esc(g.class.label.toLowerCase())}s</h2>
      <p class="muted small">Listings turn over every few weeks. Condition is what you can tell from looking: ±${g.market[0] ? g.market[0].spread : "?"}% with your tools${g.market[0] && g.market[0].spread > 5 ? " (a chassis jig lets you measure a car before you buy it)" : ""}.</p>
      <div class="ads">${g.market.map((m) => `<div class="ad"><div class="ad-price">${usd(m.price)}</div><div class="t">${esc(m.chassis)}</div>
        <div class="small">${m.age} seasons · body about ${m.condition}% · ${esc(m.engine)}, ${m.runs} races since a freshen, about ${m.health}% · ${esc(m.shocks)}</div>
        <div class="small muted">From ${esc(m.seller)} · rates about ${m.rating} at your track</div>
        <button class="small" data-act="shop" data-a="buy_used" data-k="${m.id}">Buy it</button></div>`).join("") || '<div class="muted">Nothing for sale right now.</div>'}</div></div>`;
    fleet = `<div class="card"><h2>The fleet <span class="muted small">${esc(g.class.label)}</span></h2><div class="fleet">${g.fleet.map(carCard).join("")}${proj}</div></div>${build}${engines}${market}`;
  } else {
    fleet = `<div class="card empty">${esc(g.why || "")}</div>`;
  }
  let team = "";
  if (g.team) {
    const t = g.team;
    team = `<div class="card"><h2>${esc(t.name)}: team headquarters</h2>
      <div class="muted small">Team cash ${usd(t.cash)} · equipment ${t.equipment} · facilities upkeep ${usd(t.upkeep)}/season · facilities would sell for ${usd(t.value)}. Upgrades come out of the team's cash first, then your savings.</div>
      <div class="fac-grid">${t.facilities.map((f) => `<div class="fac"><div class="fac-head"><b>${esc(f.label)}</b>${pips(f.level, 4)}</div><div class="muted small">${esc(f.about)}</div>
        <div class="small eff">Now: ${esc(f.effect)}</div>
        ${f.next !== null ? `<div class="small">Next level ${usd(f.next)} · +${usd(f.upkeep)}/season</div><button class="small primary" data-act="shop" data-a="team_upgrade" data-k="${f.key}">Invest</button>` : '<div class="small ok-text">Top of the line.</div>'}</div>`).join("")}</div></div>`;
  }
  view(`<h1>Race Shop</h1>${money}${team}${fleet}${rig}${facs}`);
  buildCost();
}

function buildCost() {
  const t = $("#b-total");
  if (!t) return;
  const v = (id) => parseFloat($(`#${id}`).selectedOptions[0]?.dataset.usd || 0);
  t.textContent = "Parts: " + usd(v("b-ch") + v("b-en") + v("b-sh"));
}
on("buildcost", buildCost);
async function shopDo(body, el) {
  if (el) el.classList.add("busy");
  try { const r = await api("shop", body); renderShop(r); toast(r.message, r.ok === false); refreshStatus(); }
  catch (e) { toast(e.message, true); if (el) el.classList.remove("busy"); }
}
on("shop", (el) => {
  if (el.dataset.confirm && !confirm(el.dataset.confirm)) return;
  shopDo({ action: el.dataset.a, key: el.dataset.k }, el);
});
on("shopbuild", (el) => shopDo({ action: "build", key: `${$("#b-ch").value}|${$("#b-en").value}|${$("#b-sh").value}` }, el));
on("shopengine", (el) => shopDo({ action: "buy_engine", key: $("#new-engine").value }, el));
