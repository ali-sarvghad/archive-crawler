// OpenAlex client — runs entirely in the browser (OpenAlex is CORS-enabled).
// Mirrors the Python `archive_crawler` OpenAlex source: builds filtered queries,
// reconstructs abstracts from the inverted index, and normalizes papers.

const API_BASE = "https://api.openalex.org";

// Only fetch the fields we actually render — keeps responses small and fast.
const SELECT_FIELDS = [
  "id", "doi", "display_name", "title", "publication_year", "publication_date",
  "type", "authorships", "abstract_inverted_index", "keywords", "concepts",
  "primary_location", "best_oa_location", "open_access", "cited_by_count",
].join(",");

function mailtoParam(mailto) {
  return mailto ? `&mailto=${encodeURIComponent(mailto)}` : "";
}

/** Rebuild a plain-text abstract from OpenAlex's inverted index. */
export function reconstructAbstract(inverted) {
  if (!inverted) return null;
  const positions = [];
  for (const [word, idxs] of Object.entries(inverted)) {
    for (const i of idxs) positions.push([i, word]);
  }
  if (!positions.length) return null;
  positions.sort((a, b) => a[0] - b[0]);
  return positions.map((p) => p[1]).join(" ");
}

function cleanDoi(doi) {
  if (!doi) return null;
  return doi.replace("https://doi.org/", "").trim() || null;
}

/** Normalize a raw OpenAlex "work" into our paper shape. */
export function parseWork(work) {
  const authors = (work.authorships || []).map((a) => {
    const author = a.author || {};
    const inst = (a.institutions || [])[0];
    return {
      name: author.display_name || "Unknown",
      affiliation: inst ? inst.display_name : null,
      orcid: author.orcid || null,
    };
  });

  let keywords = (work.keywords || [])
    .map((k) => k.display_name)
    .filter(Boolean);
  if (!keywords.length) {
    keywords = (work.concepts || [])
      .filter((c) => c.display_name && (c.score || 0) >= 0.3)
      .map((c) => c.display_name);
  }

  const primary = work.primary_location || {};
  const source = primary.source || {};
  const bestOa = work.best_oa_location || {};
  const oaUrl =
    (work.open_access || {}).oa_url ||
    bestOa.pdf_url ||
    bestOa.landing_page_url ||
    null;

  return {
    id: work.id,
    title: work.display_name || work.title || "Untitled",
    authors,
    year: work.publication_year || null,
    date: work.publication_date || null,
    type: work.type || null,
    abstract: reconstructAbstract(work.abstract_inverted_index),
    keywords,
    doi: cleanDoi(work.doi),
    venue: source.display_name || null,
    url: primary.landing_page_url || work.id,
    openAccessUrl: oaUrl,
    isOpenAccess: !!(work.open_access || {}).is_oa,
    citationCount: work.cited_by_count ?? null,
    source: "openalex",
  };
}

const _sourceCache = new Map();

/** Search OpenAlex "sources" (venues/journals) by name. */
export async function searchSources(query, { mailto, perPage = 15 } = {}) {
  if (!query || !query.trim()) return [];
  const url =
    `${API_BASE}/sources?search=${encodeURIComponent(query)}` +
    `&per-page=${perPage}&select=id,display_name,works_count,type,host_organization_name` +
    mailtoParam(mailto);
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Venue lookup failed (HTTP ${resp.status})`);
  const data = await resp.json();
  return (data.results || []).map((s) => ({
    id: s.id.split("/").pop(),
    name: s.display_name,
    worksCount: s.works_count || 0,
    type: s.type,
    publisher: s.host_organization_name || null,
  }));
}

/** Resolve a free-text venue name to the highest-works-count source id. */
export async function resolveVenue(name, opts = {}) {
  if (/^S\d+$/.test(name)) return { id: name, name };
  if (_sourceCache.has(name)) return _sourceCache.get(name);
  const matches = await searchSources(name, { ...opts, perPage: 25 });
  if (!matches.length) throw new Error(`No venue matched "${name}"`);
  const best = matches.reduce((a, b) => (b.worksCount > a.worksCount ? b : a));
  const resolved = { id: best.id, name: best.name };
  _sourceCache.set(name, resolved);
  return resolved;
}

/**
 * Search works. Returns { papers, total, page, perPage, hasMore }.
 * `filters` supports: query, venueId, yearFrom, yearTo, openAccessOnly, sort.
 */
export async function searchWorks(filters = {}, { mailto, page = 1, perPage = 25 } = {}) {
  const {
    query,
    venueId,
    yearFrom,
    yearTo,
    openAccessOnly = false,
    sort = "relevance",
  } = filters;

  const filterParts = [];
  if (venueId) filterParts.push(`primary_location.source.id:${venueId}`);
  if (yearFrom) filterParts.push(`from_publication_date:${yearFrom}-01-01`);
  if (yearTo) filterParts.push(`to_publication_date:${yearTo}-12-31`);
  if (openAccessOnly) filterParts.push("open_access.is_oa:true");

  const sortMap = {
    relevance: query ? "relevance_score:desc" : "cited_by_count:desc",
    newest: "publication_date:desc",
    oldest: "publication_date:asc",
    citations: "cited_by_count:desc",
  };

  const params = new URLSearchParams();
  params.set("per-page", String(perPage));
  params.set("page", String(page));
  params.set("select", SELECT_FIELDS);
  params.set("sort", sortMap[sort] || sortMap.relevance);
  if (filterParts.length) params.set("filter", filterParts.join(","));
  if (query && query.trim()) params.set("search", query.trim());

  let url = `${API_BASE}/works?${params.toString()}${mailtoParam(mailto)}`;

  const resp = await fetch(url);
  if (!resp.ok) {
    let detail = "";
    try {
      detail = (await resp.json()).message || "";
    } catch (_) { /* ignore */ }
    throw new Error(`Search failed (HTTP ${resp.status})${detail ? ": " + detail : ""}`);
  }
  const data = await resp.json();
  const total = (data.meta || {}).count || 0;
  const papers = (data.results || []).map(parseWork);
  return {
    papers,
    total,
    page,
    perPage,
    hasMore: page * perPage < total,
  };
}
