// Export normalized papers to JSON, CSV, BibTeX, and RIS.

function csvEscape(value) {
  const s = value == null ? "" : String(value);
  if (/[",\n\r]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
  return s;
}

export function toJSON(papers) {
  return JSON.stringify(papers, null, 2);
}

export function toCSV(papers) {
  const cols = [
    "title", "authors", "year", "venue", "keywords", "abstract",
    "doi", "url", "openAccessUrl", "citationCount", "source",
  ];
  const header = cols.join(",");
  const rows = papers.map((p) => {
    const flat = {
      ...p,
      authors: p.authors.map((a) => a.name).join("; "),
      keywords: (p.keywords || []).join("; "),
    };
    return cols.map((c) => csvEscape(flat[c])).join(",");
  });
  return [header, ...rows].join("\r\n");
}

// A stable, human-readable citation key: firstAuthorLastName + year + word.
function citeKey(p, index) {
  const first = (p.authors[0]?.name || "anon").split(/\s+/).pop().toLowerCase();
  const word = (p.title || "").split(/\s+/).find((w) => w.length > 3) || "paper";
  const clean = (s) => s.replace(/[^a-z0-9]/gi, "");
  return `${clean(first)}${p.year || ""}${clean(word.toLowerCase())}` || `ref${index}`;
}

function bibType(p) {
  const t = (p.type || "").toLowerCase();
  if (t.includes("article") || t.includes("journal")) return "article";
  if (t.includes("book")) return "book";
  return "inproceedings";
}

export function toBibTeX(papers) {
  return papers
    .map((p, i) => {
      const fields = [
        ["title", p.title],
        ["author", p.authors.map((a) => a.name).join(" and ")],
        ["year", p.year],
        [bibType(p) === "article" ? "journal" : "booktitle", p.venue],
        ["keywords", (p.keywords || []).join(", ")],
        ["doi", p.doi],
        ["url", p.url],
        ["abstract", p.abstract],
      ].filter(([, v]) => v);
      const body = fields
        .map(([k, v]) => `  ${k} = {${String(v).replace(/[{}]/g, "")}}`)
        .join(",\n");
      return `@${bibType(p)}{${citeKey(p, i)},\n${body}\n}`;
    })
    .join("\n\n");
}

export function toRIS(papers) {
  const risType = (p) => {
    const t = bibType(p);
    return t === "article" ? "JOUR" : t === "book" ? "BOOK" : "CONF";
  };
  return papers
    .map((p) => {
      const lines = [`TY  - ${risType(p)}`];
      lines.push(`TI  - ${p.title || ""}`);
      for (const a of p.authors) lines.push(`AU  - ${a.name}`);
      if (p.year) lines.push(`PY  - ${p.year}`);
      if (p.venue) lines.push(`T2  - ${p.venue}`);
      for (const k of p.keywords || []) lines.push(`KW  - ${k}`);
      if (p.abstract) lines.push(`AB  - ${p.abstract}`);
      if (p.doi) lines.push(`DO  - ${p.doi}`);
      if (p.url) lines.push(`UR  - ${p.url}`);
      lines.push("ER  - ");
      return lines.join("\r\n");
    })
    .join("\r\n");
}

export const FORMATS = {
  json: { label: "JSON", ext: "json", mime: "application/json", fn: toJSON },
  csv: { label: "CSV", ext: "csv", mime: "text/csv", fn: toCSV },
  bibtex: { label: "BibTeX", ext: "bib", mime: "application/x-bibtex", fn: toBibTeX },
  ris: { label: "RIS", ext: "ris", mime: "application/x-research-info-systems", fn: toRIS },
};

/** Trigger a browser download of `content` as a file. */
export function download(content, filename, mime) {
  const blob = new Blob([content], { type: mime + ";charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
