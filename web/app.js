// Last Bus Out — front end. All coverage math here mirrors app/engine.py (tract_status).
const $ = (id) => document.getElementById(id);
const COLORS = { both: "#1a9850", toOnly: "#f39c12", none: "#cfd5da" };

let map, tractLayer, siteMarker, siteStopsLayer;
let samples = [];
let current = { lat: null, lon: null, label: null, employer: null, reach: null, fallbackSite: null };

const fmt = (m) => {
  m = ((Math.round(m) % 1440) + 1440) % 1440;
  const h = Math.floor(m / 60), mm = m % 60;
  return `${h % 12 || 12}:${String(mm).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
};
const hhmmToMin = (s) => { const [h, m] = s.split(":").map(Number); return h * 60 + m; };
const minToHHMM = (m) => { m = ((m % 1440) + 1440) % 1440; return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`; };
const num = (n) => Number(n).toLocaleString();

async function api(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  if (!r.ok) { let d; try { d = (await r.json()).detail; } catch { d = r.statusText; } throw new Error(d); }
  return r.json();
}

function setStatus(msg) { $("status").textContent = msg || ""; }

async function init() {
  map = L.map("map", { zoomControl: true }).setView([42.39, -83.1], 10);
  L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
    attribution: "Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors", maxZoom: 16,
  }).addTo(map);
  map.on("click", (e) => { if (current.reach !== undefined) placeSite(e.latlng.lat, e.latlng.lng, "Map pin"); });

  try {
    const h = await api("/api/health");
    $("version").textContent = `v${h.version}`;
    if (!h.data_loaded) { $("dataInfo").textContent = "data not built yet"; setStatus("Run scripts/fetch_data.py and scripts/build_index.py first."); }
    else {
      const f = h.meta.feeds || {};
      $("dataInfo").textContent = Object.entries(f).map(([a, v]) => `${a} schedule for ${v.weekday?.date ?? "?"}`).join(" · ") + ` · ACS ${h.meta.acs_year}`;
    }
  } catch (e) { $("version").textContent = "v?"; }

  try {
    const gj = await api("/api/tracts");
    tractLayer = L.geoJSON(gj, { style: () => styleFor("none"), onEachFeature: (f, l) => l.bindTooltip(() => tooltipFor(f), { sticky: true }) }).addTo(map);
  } catch (e) { /* data not built */ }

  samples = await api("/api/samples").catch(() => []);
  samples.forEach((s) => {
    const b = document.createElement("button");
    b.textContent = s.title;
    b.onclick = () => { $("posting").value = s.text; current.fallbackSite = s.fallback_site; };
    $("samples").appendChild(b);
  });

  $("go").onclick = run;
  $("rawToggle").onclick = () => { $("raw").hidden = !$("raw").hidden; };
  $("start").oninput = $("end").oninput = () => { updateLabels(); render(); };
  $("start").onchange = $("end").onchange = debounceMemo;
  $("dayType").onchange = async () => { if (current.lat != null) await loadReach(); };
}

function styleFor(status, zc = 0) {
  const fill = COLORS[status];
  return { color: "#ffffff", weight: 0.5, fillColor: fill, fillOpacity: status === "none" ? 0.35 : 0.55 + Math.min(zc / 800, 0.35) };
}

function rules() { return current.reach?.rules || { arrive_buffer_min: 5, max_early_min: 60, max_wait_home_min: 45 }; }

function tractStatus(opts, start, end) {
  const r = rules();
  if (!opts) return { status: "none" };
  const lo = start - r.max_early_min, hi = start - r.arrive_buffer_min;
  const there = (opts.in || []).find((o) => o[0] >= lo && o[0] <= hi);
  const home = (opts.out || []).find((o) => o[0] >= end && o[0] <= end + r.max_wait_home_min);
  return { status: there && home ? "both" : there ? "toOnly" : "none", there, home };
}

function shiftTimes() {
  const start = Number($("start").value);
  let end = Number($("end").value);
  if (end <= start) end += 1440;
  return { start, end };
}

function tooltipFor(f) {
  const p = f.properties;
  let s = `<b>${p.name}</b><br>${num(p.zc)} car-free households`;
  if (current.reach) {
    const { start, end } = shiftTimes();
    const t = tractStatus(current.reach.tracts[p.i], start, end);
    const route = (o) => current.reach.routes?.[o[1]] ?? "bus";
    if (t.there) s += `<br>To work: ${route(t.there)}, arrives ${fmt(t.there[0])} (${t.there[2]} min door to door)`;
    if (t.home) s += `<br>Home: ${route(t.home)} leaves ${fmt(t.home[0])}, ${t.home[0] - end} min after shift`;
    else if (t.there) s += `<br><b>No bus home within ${rules().max_wait_home_min} min of shift end</b>`;
  }
  return s;
}

function render() {
  if (!tractLayer || !current.reach) return;
  const { start, end } = shiftTimes();
  let hhBoth = 0, hhTo = 0;
  tractLayer.eachLayer((l) => {
    const p = l.feature.properties;
    const t = tractStatus(current.reach.tracts[p.i], start, end);
    if (t.status === "both") hhBoth += p.zc; else if (t.status === "toOnly") hhTo += p.zc;
    l.setStyle(styleFor(t.status, p.zc));
  });
  const total = current.reach.zero_car_hh_total || 1;
  $("pct").textContent = `${(100 * hhBoth / total).toFixed(1)}%`;
  $("nGreen").textContent = num(hhBoth);
  $("nAmber").textContent = num(hhTo);
  $("result").hidden = false;
}

function updateLabels() {
  const { start, end } = shiftTimes();
  $("startLabel").textContent = fmt(start);
  $("endLabel").textContent = fmt(end) + (end >= 1440 ? " (next day)" : "");
}

async function run() {
  const text = $("posting").value.trim();
  if (!text) { setStatus("Paste a job posting first, or pick a sample."); return; }
  $("go").disabled = true;
  try {
    setStatus("Granite is reading the posting…");
    const p = await api("/api/parse", { text });
    showParsed(p);
    const post = p.posting;
    const shift = post.shifts?.[0];
    if (shift) {
      $("start").value = hhmmToMin(shift.start);
      let e = hhmmToMin(shift.end); if (e <= hhmmToMin(shift.start)) e += 1440;
      $("end").value = e;
      const days = shift.days || [];
      $("dayType").value = days.some((d) => ["Mon", "Tue", "Wed", "Thu", "Fri"].includes(d)) || !days.length ? "weekday" : days.includes("Sat") ? "saturday" : "sunday";
    }
    updateLabels();
    $("controls").hidden = false;
    current.employer = post.employer;

    let site = null;
    if (post.address) {
      setStatus(`Finding ${post.address}…`);
      site = await api("/api/geocode", { address: post.address }).catch(() => null);
      if (site) site.label = site.matched || post.address;
    }
    if (!site && current.fallbackSite) site = current.fallbackSite;
    if (!site) { setStatus("Couldn't find the address. Click the map where the job is."); return; }
    await placeSite(site.lat, site.lon, site.label || post.address);
  } catch (e) {
    setStatus(`Error: ${e.message}`);
  } finally {
    $("go").disabled = false;
  }
}

function showParsed(p) {
  const post = p.posting, s = post.shifts?.[0];
  const rows = [["Employer", post.employer], ["Job", post.job_title], ["Address", post.address],
    ["Shift", s ? `${fmt(hhmmToMin(s.start))} – ${fmt(hhmmToMin(s.end))}` : "not found"],
    ["Days", s?.days?.join(", ")], ["Other shifts", (post.shifts || []).slice(1).map((x) => `${x.start}–${x.end}`).join(", ")],
    ["Notes", (post.notes || []).join("; ")]];
  $("fields").innerHTML = rows.filter(([, v]) => v).map(([k, v]) => `<dt>${k}</dt><dd>${escapeHtml(v)}</dd>`).join("");
  $("raw").textContent = p.raw;
  $("provider").textContent = p.provider;
  $("provider").className = "badge" + (p.fallback ? " warn" : "");
  $("parsed").hidden = false;
}

async function placeSite(lat, lon, label) {
  current.lat = lat; current.lon = lon; current.label = label;
  if (siteMarker) siteMarker.remove();
  siteMarker = L.marker([lat, lon]).addTo(map).bindPopup(`<b>Job site</b><br>${escapeHtml(label || "")}`);
  map.setView([lat, lon], 11);
  await loadReach();
}

async function loadReach() {
  setStatus("Checking every scheduled bus…");
  current.reach = await api("/api/reach", { lat: current.lat, lon: current.lon, day_type: $("dayType").value });
  if (siteStopsLayer) siteStopsLayer.remove();
  siteStopsLayer = L.layerGroup((current.reach.site_stops || []).map((s) =>
    L.circleMarker([s.lat, s.lon], { radius: 4, color: "#0f62fe", weight: 2 }).bindTooltip(`${s.agency} stop: ${s.name} (${s.dist_m} m)`))).addTo(map);
  const n = Object.keys(current.reach.tracts).length;
  setStatus(current.reach.site_stops.length ? `${current.reach.site_stops.length} bus stops within a half-mile walk · ${n} tracts have a one-seat ride` :
    "No bus stops within a half-mile walk of this site.");
  render();
  debounceMemo();
}

let memoTimer;
function debounceMemo() { clearTimeout(memoTimer); memoTimer = setTimeout(loadMemo, 500); }

async function loadMemo() {
  if (current.lat == null) return;
  const { start, end } = shiftTimes();
  $("memo").textContent = "Granite is writing the memo…";
  try {
    const m = await api("/api/memo", { lat: current.lat, lon: current.lon, day_type: $("dayType").value,
      start: minToHHMM(start), end: minToHHMM(end), site_label: current.label || "this location", employer: current.employer });
    $("memo").textContent = m.memo;
    $("memoMeta").textContent = `${m.provider} · ✓ every number checked against the schedule data` +
      (m.rejected_numbers?.length ? ` (rejected invented numbers: ${m.rejected_numbers.join(", ")})` : "");
  } catch (e) { $("memo").textContent = `Memo unavailable: ${e.message}`; }
}

function escapeHtml(s) { return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

init();
