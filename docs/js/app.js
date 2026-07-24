import { searchWorks, searchSources, resolveVenue } from "./openalex.js";
import { CURATED_VENUES } from "./venues.js";
import { FORMATS, download } from "./exporters.js";

// ---------- State ----------
const state = {
  venues: [],             // [{ id, name, chip? }] — one or more selected venues
  results: [],            // loaded papers
  selected: new Map(),    // id -> paper
  page: 0,
  total: 0,
  hasMore: false,
  loading: false,
  lastFilters: null,
};

const settings = {
  mailto: localStorage.getItem("mailto") || "",
  perPage: Number(localStorage.getItem("perPage")) || 25,
  exportCap: Number(localStorage.getItem("exportCap")) || 500,
  theme: localStorage.getItem("theme") || "auto",
};

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html != null) n.innerHTML = html;
  return n;
};
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// ---------- Toast ----------
let toastTimer;
function toast(msg, isError = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show" + (isError ? " error" : "");
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.className = "toast"), 2600);
}

// ---------- Theme ----------
function applyTheme() {
  document.documentElement.setAttribute("data-theme", settings.theme);
}
$("#theme-toggle").addEventListener("click", () => {
  const order = ["auto", "light", "dark"];
  // Toggle simply flips between light and dark based on current effective theme.
  const isDark =
    settings.theme === "dark" ||
    (settings.theme === "auto" && matchMedia("(prefers-color-scheme: dark)").matches);
  settings.theme = isDark ? "light" : "dark";
  localStorage.setItem("theme", settings.theme);
  applyTheme();
});

// ---------- Settings modal ----------
function openSettings() {
  $("#mailto").value = settings.mailto;
  $("#per-page").value = String(settings.perPage);
  $("#export-cap").value = String(settings.exportCap);
  $("#settings-modal").hidden = false;
}
function closeSettings() { $("#settings-modal").hidden = true; }
$("#settings-btn").addEventListener("click", openSettings);
$("#settings-modal").addEventListener("click", (e) => {
  if (e.target.hasAttribute("data-close")) {
    settings.mailto = $("#mailto").value.trim();
    settings.perPage = Number($("#per-page").value);
    settings.exportCap = Number($("#export-cap").value);
    localStorage.setItem("mailto", settings.mailto);
    localStorage.setItem("perPage", String(settings.perPage));
    localStorage.setItem("exportCap", String(settings.exportCap));
    closeSettings();
  }
});

// ---------- Venue combobox ----------
const venueInput = $("#venue-input");
const suggestions = $("#venue-suggestions");
let venueDebounce, activeSuggestion = -1;

function renderChips() {
  const wrap = $("#venue-chips");
  wrap.innerHTML = "";
  CURATED_VENUES.forEach((v) => {
    const chip = el("button", "chip", esc(v.label));
    chip.type = "button";
    if (state.venues.some((sv) => sv.chip === v.label)) chip.classList.add("active");
    chip.addEventListener("click", () => selectCuratedVenue(v, chip));
    wrap.appendChild(chip);
  });
}

// Render the currently selected venues as removable pills.
function renderSelectedVenues() {
  const wrap = $("#venue-selected");
  wrap.innerHTML = "";
  state.venues.forEach((v) => {
    const pill = el("span", "venue-pill");
    pill.innerHTML = `<span class="vp-name">${esc(v.name)}</span>`;
    const x = el("button", null, "&times;");
    x.type = "button";
    x.title = "Remove venue";
    x.setAttribute("aria-label", `Remove ${v.name}`);
    x.addEventListener("click", () => removeVenue(v.id));
    pill.appendChild(x);
    wrap.appendChild(pill);
  });
}

function addVenue(v) {
  if (state.venues.some((sv) => sv.id === v.id)) {
    toast(`"${v.name}" is already added`);
    return;
  }
  state.venues.push(v);
  renderSelectedVenues();
  renderChips();
  hideSuggestions();
}

function removeVenue(id) {
  state.venues = state.venues.filter((v) => v.id !== id);
  renderSelectedVenues();
  renderChips();
}

async function selectCuratedVenue(v, chipEl) {
  chipEl.classList.add("loading");
  const prev = chipEl.textContent;
  chipEl.textContent = v.label + " …";
  try {
    const resolved = await resolveVenue(v.query, { mailto: settings.mailto });
    addVenue({ ...resolved, chip: v.label });
  } catch (e) {
    toast(e.message, true);
  } finally {
    chipEl.textContent = prev;
    chipEl.classList.remove("loading");
  }
}

// The inline clear button just empties the typed text (venues are pills now).
function clearVenueInput() {
  venueInput.value = "";
  $("#venue-clear").hidden = true;
  hideSuggestions();
  venueInput.focus();
}
$("#venue-clear").addEventListener("click", clearVenueInput);

function hideSuggestions() {
  suggestions.hidden = true;
  suggestions.innerHTML = "";
  activeSuggestion = -1;
  venueInput.setAttribute("aria-expanded", "false");
}

function showSuggestionsLoading() {
  suggestions.innerHTML = `<li class="s-loading">Searching venues…</li>`;
  suggestions.hidden = false;
}

async function runVenueSearch(q) {
  try {
    const matches = await searchSources(q, { mailto: settings.mailto });
    if (venueInput.value.trim() !== q) return; // stale
    if (!matches.length) {
      suggestions.innerHTML = `<li class="s-empty">No venues found</li>`;
      suggestions.hidden = false;
      return;
    }
    suggestions.innerHTML = "";
    matches.forEach((m, i) => {
      const li = el("li");
      li.setAttribute("role", "option");
      li.dataset.index = i;
      li.innerHTML =
        `<span class="s-name">${esc(m.name)}</span>` +
        `<span class="s-meta">${m.worksCount.toLocaleString()} works${m.type ? " · " + esc(m.type) : ""}</span>`;
      li.addEventListener("click", () => {
        addVenue({ id: m.id, name: m.name });
        clearVenueInput();
      });
      suggestions.appendChild(li);
    });
    suggestions.hidden = false;
    venueInput.setAttribute("aria-expanded", "true");
  } catch (e) {
    hideSuggestions();
    toast(e.message, true);
  }
}

venueInput.addEventListener("input", () => {
  const q = venueInput.value.trim();
  $("#venue-clear").hidden = !q;
  clearTimeout(venueDebounce);
  if (q.length < 2) { hideSuggestions(); return; }
  showSuggestionsLoading();
  venueDebounce = setTimeout(() => runVenueSearch(q), 320);
});

venueInput.addEventListener("keydown", (e) => {
  const items = [...suggestions.querySelectorAll("li[role=option]")];
  if (!items.length) return;
  if (e.key === "ArrowDown") { e.preventDefault(); activeSuggestion = Math.min(activeSuggestion + 1, items.length - 1); }
  else if (e.key === "ArrowUp") { e.preventDefault(); activeSuggestion = Math.max(activeSuggestion - 1, 0); }
  else if (e.key === "Enter" && activeSuggestion >= 0) { e.preventDefault(); items[activeSuggestion].click(); return; }
  else if (e.key === "Escape") { hideSuggestions(); return; }
  items.forEach((it, i) => it.setAttribute("aria-selected", i === activeSuggestion));
});

document.addEventListener("click", (e) => {
  if (!e.target.closest(".venue-combo")) hideSuggestions();
  if (!e.target.closest(".export-menu")) $("#export-dropdown").hidden = true;
});

// ---------- Search ----------
function currentFilters() {
  const yf = $("#year-from").value.trim();
  const yt = $("#year-to").value.trim();
  return {
    query: $("#query").value.trim(),
    venueIds: state.venues.map((v) => v.id),
    yearFrom: yf ? Number(yf) : null,
    yearTo: yt ? Number(yt) : null,
    openAccessOnly: $("#oa-only").checked,
    sort: $("#sort").value,
  };
}

function setStatus(html) { $("#status").innerHTML = html; }
function clearStatus() { $("#status").innerHTML = ""; }

function showSkeletons(n = 4) {
  $("#results-list").innerHTML = Array.from({ length: n })
    .map(() =>
      `<div class="skeleton-card"><div class="sk sk-title"></div>
       <div class="sk sk-line"></div><div class="sk sk-line"></div><div class="sk sk-line short"></div></div>`)
    .join("");
}

async function doSearch(reset = true) {
  const filters = currentFilters();
  if (!filters.query && !filters.venueIds.length) {
    toast("Enter search terms or add a venue first", true);
    return;
  }
  if (reset) {
    state.results = [];
    state.selected.clear();
    state.page = 0;
    state.lastFilters = filters;
    updateHash(filters);
    showSkeletons();
    clearStatus();
    $("#results-toolbar").hidden = true;
    $("#load-more-wrap").hidden = true;
  }
  state.loading = true;
  $("#load-more").disabled = true;
  try {
    const res = await searchWorks(state.lastFilters, {
      mailto: settings.mailto,
      page: state.page + 1,
      perPage: settings.perPage,
    });
    state.page = res.page;
    state.total = res.total;
    state.hasMore = res.hasMore;
    state.results.push(...res.papers);

    if (reset) $("#results-list").innerHTML = "";
    if (state.results.length === 0) {
      renderEmpty();
    } else {
      appendCards(res.papers);
      renderToolbar();
    }
  } catch (e) {
    if (reset) $("#results-list").innerHTML = "";
    renderError(e.message);
  } finally {
    state.loading = false;
    $("#load-more").disabled = false;
    $("#load-more-wrap").hidden = !state.hasMore;
  }
}

function renderEmpty() {
  setStatus(`
    <div class="state">
      <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
      <h3>No papers found</h3>
      <p>Try broadening your terms, widening the year range, or removing the venue filter.</p>
    </div>`);
}

function renderError(msg) {
  setStatus(`<div class="error-banner">
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>
    <div><strong>Something went wrong.</strong><br>${esc(msg)}</div></div>`);
}

// ---------- Rendering cards ----------
function authorLine(authors) {
  if (!authors.length) return "";
  const names = authors.slice(0, 6).map((a) => esc(a.name));
  let line = names.join(", ");
  if (authors.length > 6) line += ` <span class="more" title="${esc(authors.map(a=>a.name).join(', '))}">+${authors.length - 6} more</span>`;
  return line;
}

function cardHTML(p) {
  const isSel = state.selected.has(p.id);
  const meta = [];
  if (p.year) meta.push(esc(p.year));
  if (p.venue) meta.push(esc(p.venue));
  if (p.type) meta.push(esc(p.type.replace(/-/g, " ")));
  const metaLine = meta.join(' <span class="dot">·</span> ');

  const badges = [];
  if (p.isOpenAccess) badges.push(`<span class="badge badge-oa">● Open access</span>`);
  if (p.citationCount != null) badges.push(`<span class="badge badge-cite">${p.citationCount.toLocaleString()} citations</span>`);

  const abstract = p.abstract
    ? `<p class="abstract clamped">${esc(p.abstract)}</p><button class="abstract-toggle" type="button">Show more</button>`
    : `<p class="no-abstract">No abstract available for this record.</p>`;

  const keywords = (p.keywords || []).length
    ? `<div class="keywords">${p.keywords.slice(0, 12).map((k) => `<span class="kw">${esc(k)}</span>`).join("")}</div>`
    : "";

  const links = [];
  if (p.doi) links.push(`<a href="https://doi.org/${esc(p.doi)}" target="_blank" rel="noopener">DOI ↗</a>`);
  if (p.url) links.push(`<a href="${esc(p.url)}" target="_blank" rel="noopener">Landing page ↗</a>`);
  if (p.openAccessUrl) links.push(`<a href="${esc(p.openAccessUrl)}" target="_blank" rel="noopener">Full text (OA) ↗</a>`);

  return `
    <div class="card-top">
      <label class="card-check"><input type="checkbox" ${isSel ? "checked" : ""} aria-label="Select paper"></label>
      <div class="card-main">
        <h3 class="card-title"><a href="${esc(p.url || '#')}" target="_blank" rel="noopener">${esc(p.title)}</a></h3>
        <div class="card-meta">${metaLine}${badges.length ? " " + badges.join(" ") : ""}</div>
        ${p.authors.length ? `<div class="authors">${authorLine(p.authors)}</div>` : ""}
        ${abstract}
        ${keywords}
        ${links.length ? `<div class="card-links">${links.join("")}</div>` : ""}
      </div>
    </div>`;
}

function appendCards(papers) {
  const list = $("#results-list");
  papers.forEach((p) => {
    const card = el("div", "card" + (state.selected.has(p.id) ? " selected" : ""));
    card.innerHTML = cardHTML(p);
    // checkbox
    card.querySelector(".card-check input").addEventListener("change", (e) => {
      if (e.target.checked) state.selected.set(p.id, p);
      else state.selected.delete(p.id);
      card.classList.toggle("selected", e.target.checked);
      updateSelectionUI();
    });
    // abstract expand
    const toggle = card.querySelector(".abstract-toggle");
    if (toggle) {
      toggle.addEventListener("click", () => {
        const a = card.querySelector(".abstract");
        const clamped = a.classList.toggle("clamped");
        toggle.textContent = clamped ? "Show more" : "Show less";
      });
    }
    list.appendChild(card);
  });
}

// ---------- Toolbar & selection ----------
function renderToolbar() {
  $("#results-toolbar").hidden = false;
  const shown = state.results.length;
  $("#result-count").innerHTML =
    `${state.total.toLocaleString()} result${state.total === 1 ? "" : "s"} <span class="muted">· ${shown} loaded</span>`;
  updateSelectionUI();
}

function updateSelectionUI() {
  const n = state.selected.size;
  $("#selected-count").textContent = n ? `${n} selected` : "";
  $("#export-btn").disabled = state.results.length === 0;
  const allLoaded = state.results.length > 0 && state.results.every((p) => state.selected.has(p.id));
  const selAll = $("#select-all");
  selAll.checked = allLoaded;
  selAll.indeterminate = n > 0 && !allLoaded;
  $("#export-scope").textContent = n ? `${n} selected` : `${state.results.length} loaded`;
}

$("#select-all").addEventListener("change", (e) => {
  if (e.target.checked) state.results.forEach((p) => state.selected.set(p.id, p));
  else state.selected.clear();
  document.querySelectorAll(".card").forEach((card, i) => {
    const cb = card.querySelector(".card-check input");
    if (cb) { cb.checked = e.target.checked; card.classList.toggle("selected", e.target.checked); }
  });
  updateSelectionUI();
});

$("#search-btn").addEventListener("click", () => doSearch(true));
$("#query").addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(true); });
[$("#year-from"), $("#year-to")].forEach((i) =>
  i.addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(true); }));
$("#load-more").addEventListener("click", () => doSearch(false));

// ---------- Export ----------
$("#export-btn").addEventListener("click", (e) => {
  e.stopPropagation();
  const dd = $("#export-dropdown");
  dd.hidden = !dd.hidden;
  updateSelectionUI();
});

$("#export-dropdown").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-fmt]");
  if (!btn) return;
  const fmt = btn.dataset.fmt;
  const fetchAll = $("#export-all-matching").checked;
  $("#export-dropdown").hidden = true;
  await runExport(fmt, fetchAll);
});

async function runExport(fmt, fetchAll) {
  let papers;
  if (state.selected.size > 0) {
    papers = [...state.selected.values()];
  } else if (fetchAll) {
    papers = await fetchAllMatching();
    if (!papers) return; // cancelled/failed
  } else {
    papers = state.results;
  }
  if (!papers.length) { toast("Nothing to export", true); return; }

  const f = FORMATS[fmt];
  const content = f.fn(papers);
  const stamp = new Date().toISOString().slice(0, 10);
  const venueSlug = state.venues.length
    ? "-" + state.venues[0].name.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 24)
    : "";
  download(content, `papers${venueSlug}-${stamp}.${f.ext}`, f.mime);
  toast(`Exported ${papers.length} paper${papers.length === 1 ? "" : "s"} as ${f.label}`);
}

async function fetchAllMatching() {
  const cap = Math.min(settings.exportCap, state.total || settings.exportCap);
  const perPage = 200; // OpenAlex max page size
  const all = [];
  const seen = new Set();
  let page = 0;
  setStatus(`<p class="progress-note">Fetching all matching results… 0/${cap}</p>`);
  try {
    // Re-page from the start at the max page size so numbering stays consistent.
    while (all.length < cap) {
      page += 1;
      const res = await searchWorks(state.lastFilters, { mailto: settings.mailto, page, perPage });
      if (!res.papers.length) break;
      for (const p of res.papers) {
        if (!seen.has(p.id)) { seen.add(p.id); all.push(p); }
      }
      setStatus(`<p class="progress-note">Fetching all matching results… ${Math.min(all.length, cap)}/${cap}</p>`);
      if (!res.hasMore) break;
    }
    clearStatus();
    return all.slice(0, cap);
  } catch (e) {
    renderError(e.message);
    return null;
  }
}

// ---------- Shareable URL state ----------
function updateHash(f) {
  const params = new URLSearchParams();
  if (f.query) params.set("q", f.query);
  if (state.venues.length) {
    // Compact, comma-safe encoding: "id:name;;id:name".
    params.set("venues", state.venues.map((v) => `${v.id}:${v.name}`).join(";;"));
  }
  if (f.yearFrom) params.set("from", f.yearFrom);
  if (f.yearTo) params.set("to", f.yearTo);
  if (f.openAccessOnly) params.set("oa", "1");
  if (f.sort && f.sort !== "relevance") params.set("sort", f.sort);
  const hash = params.toString();
  history.replaceState(null, "", hash ? "#" + hash : location.pathname);
}

function loadFromHash() {
  const params = new URLSearchParams(location.hash.slice(1));
  if (![...params.keys()].length) return false;
  $("#query").value = params.get("q") || "";
  if (params.get("venues")) {
    params.get("venues").split(";;").forEach((entry) => {
      const idx = entry.indexOf(":");
      if (idx > 0) addVenue({ id: entry.slice(0, idx), name: entry.slice(idx + 1) });
    });
  } else if (params.get("vid")) {
    // Backward compatibility with older single-venue links.
    addVenue({ id: params.get("vid"), name: params.get("vname") || params.get("vid") });
  }
  if (params.get("from")) $("#year-from").value = params.get("from");
  if (params.get("to")) $("#year-to").value = params.get("to");
  if (params.get("oa")) $("#oa-only").checked = true;
  if (params.get("sort")) $("#sort").value = params.get("sort");
  return true;
}

// ---------- Init ----------
function init() {
  applyTheme();
  renderChips();
  // Wire repo link if hosted on github.io
  const host = location.hostname;
  if (host.endsWith("github.io")) {
    const user = host.split(".")[0];
    const repo = location.pathname.split("/").filter(Boolean)[0];
    if (repo) $("#repo-link").href = `https://github.com/${user}/${repo}`;
  } else {
    $("#repo-link").href = "https://github.com/";
  }

  const initialState = () =>
    setStatus(`
      <div class="state">
        <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
        <h3>Start exploring</h3>
        <p>Pick a venue (e.g. ACM CHI) or type search terms, then hit <strong>Search papers</strong>.</p>
      </div>`);

  if (loadFromHash()) {
    doSearch(true);
  } else {
    initialState();
  }

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { closeSettings(); hideSuggestions(); $("#export-dropdown").hidden = true; }
  });
}

init();
