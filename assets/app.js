// InventoryForge dashboard — reads data/latest.json and renders one filterable page.
const state = { items: [], filtered: [] };

const el = (id) => document.getElementById(id);

function relTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso), now = new Date(), s = Math.round((now - d) / 1000);
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

function statusClass(status) {
  const s = (status || "").toLowerCase();
  if (/(in stock|available|in-store|limited)/.test(s)) return "in";
  if (/(out|sold out|unavailable|not available)/.test(s)) return "out";
  if (/(soon|preorder|pre-order|coming)/.test(s)) return "soon";
  return "unknown";
}
function isInStock(status) { return statusClass(status) === "in"; }

async function load() {
  try {
    const res = await fetch(`data/latest.json?t=${Date.now()}`);
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    render(data);
  } catch (e) {
    el("updated").textContent = "no data yet — run the collector";
    el("empty").hidden = false;
  }
}

function render(data) {
  state.items = data.items || [];
  if (data.region) el("region").textContent = data.region;

  // freshness
  el("updated").textContent = data.updatedAt ? `Updated ${relTime(data.updatedAt)}` : "—";
  const ageMin = data.updatedAt ? (Date.now() - new Date(data.updatedAt)) / 60000 : Infinity;
  const dot = el("freshdot");
  dot.className = "dot " + (ageMin < 45 ? "fresh" : "stale");

  // watchlist chips
  const kws = (data.watchlist || []).map((k) => (typeof k === "string" ? k : k.label || k.match));
  el("watchlist").innerHTML = kws.map((k) => `<span class="chip">${esc(k)}</span>`).join("") ||
    `<span class="chip">everything</span>`;

  renderSources(data.sources);

  // filter dropdowns
  fillSelect("retailer", uniq(state.items.map((i) => i.retailer)));
  fillSelect("store", uniq(state.items.map((i) => i.store)));

  // recently restocked strip
  const recent = state.items
    .filter((i) => i.lastRestock && isInStock(i.status))
    .sort((a, b) => new Date(b.lastRestock) - new Date(a.lastRestock))
    .slice(0, 8);
  if (recent.length) {
    el("restocks-wrap").hidden = false;
    el("restocks").innerHTML = recent.map((i) => `
      <div class="restock-card">
        <div class="t">${esc(i.title)}</div>
        <div class="m">${esc(i.retailer)} · ${esc(i.store)} · ${relTime(i.lastRestock)}</div>
      </div>`).join("");
  }
  apply();
}

function renderSources(sources) {
  const wrap = el("sources");
  if (!sources || !Object.keys(sources).length) { wrap.innerHTML = ""; return; }
  wrap.innerHTML = Object.entries(sources).map(([name, s]) => {
    const cls = s.status === "ok" ? "ok" : s.status === "unreachable" ? "warn" : "muted";
    let note = "";
    if (s.status === "unreachable") note = ` · couldn't check${s.lastOkAt ? " — last ok " + relTime(s.lastOkAt) : ""}`;
    else if (s.status === "skipped") note = " · skipped";
    return `<span class="source ${cls}"><span class="sdot"></span>${esc(name)}${note}</span>`;
  }).join("");
}

function fillSelect(id, values) {
  const sel = el(id), cur = sel.value;
  const label = id === "retailer" ? "All retailers" : "All stores";
  sel.innerHTML = `<option value="">${label}</option>` +
    values.sort().map((v) => `<option>${esc(v)}</option>`).join("");
  sel.value = cur;
}

function apply() {
  const q = el("q").value.trim().toLowerCase();
  const r = el("retailer").value, st = el("store").value, inOnly = el("instock").checked;
  state.filtered = state.items.filter((i) => {
    if (q && !(i.title || "").toLowerCase().includes(q)) return false;
    if (r && i.retailer !== r) return false;
    if (st && i.store !== st) return false;
    if (inOnly && !isInStock(i.status)) return false;
    return true;
  });
  // in-stock first, then by retailer/title
  state.filtered.sort((a, b) =>
    (isInStock(b.status) - isInStock(a.status)) ||
    (a.retailer || "").localeCompare(b.retailer) ||
    (a.title || "").localeCompare(b.title));
  paint();
}

function paint() {
  const rows = state.filtered.map((i) => {
    const sc = statusClass(i.status);
    const staleCls = i.stale ? " stale" : "";
    const staleTag = i.stale ? ' <span class="stale-tag">stale</span>' : "";
    const url = i.url ? `<a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.title)}</a>` : esc(i.title);
    return `<tr class="${sc === "in" ? "in" : ""}${staleCls}">
      <td class="title-cell">${url}</td>
      <td class="retailer-tag">${esc(i.retailer)}</td>
      <td>${esc(i.store)}</td>
      <td><span class="badge ${sc}">${esc(i.status || "Unknown")}</span>${staleTag}</td>
      <td>${i.price != null ? "$" + Number(i.price).toFixed(2) : "—"}</td>
      <td>${relTime(i.lastRestock)}</td>
    </tr>`;
  }).join("");
  el("rows").innerHTML = rows;
  el("empty").hidden = state.filtered.length > 0;
  el("count").textContent = `${state.filtered.length} / ${state.items.length} shown`;
}

const uniq = (a) => [...new Set(a.filter(Boolean))];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

["q", "retailer", "store", "instock"].forEach((id) =>
  el(id).addEventListener("input", apply));

load();
setInterval(load, 60000); // re-read the JSON every minute
