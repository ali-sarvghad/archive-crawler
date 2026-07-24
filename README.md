# archive-crawler

Scrape scholarly **paper metadata** — abstract, introduction, keywords, authors,
and publication year — from a **database (venue) you define**, such as ACM CHI.

This repo has two parts:

1. **🌐 Web app** (`docs/`) — a modern, shareable browser UI to search & export
   papers. Runs on **GitHub Pages** with no server. **[See below](#-web-app-github-pages).**
2. **🐍 Python crawler** (`archive_crawler/`) — a CLI + library for scripted,
   large-scale crawls. **[Jump to it](#-python-crawler-cli--library).**

---

## 🌐 Web app (GitHub Pages)

A static single-page app that searches OpenAlex **directly from the browser**
(OpenAlex is CORS-enabled, so no backend is needed — which is exactly why it can
live on GitHub Pages). Share it as a plain URL.

**Features**

- 🔎 Full-text search within any venue, with a live **venue autocomplete** plus
  one-click chips (ACM CHI, UIST, CSCW, DIS, IEEE VIS, NeurIPS, ICML, ACL, CVPR…)
- 🗓 Year-range and **open-access-only** filters; sort by relevance / date / citations
- 🃏 Rich result cards: abstract (expandable), keyword tags, authors, venue,
  citation count, and DOI / landing-page / open-access links
- ✅ Select individual papers or everything, then **export to CSV, JSON, BibTeX,
  or RIS** (import straight into Zotero / Mendeley / EndNote)
- 📦 "Fetch all matching results" to export an entire query, not just what's on screen
- 🔗 **Shareable search links** — the URL captures your query & filters, so a
  collaborator opens the exact same results
- 🌗 Light/dark theme, responsive, keyboard-friendly; settings (contact email for
  the API "polite pool") stored locally in the browser

**Deploy it (2 minutes)**

Once this branch is on GitHub, pick either option:

- **Option A — Deploy from a branch (simplest):** repo **Settings → Pages →
  Build and deployment → Source: _Deploy from a branch_**, choose your branch and
  the **`/docs`** folder, Save. Your site appears at
  `https://<user>.github.io/<repo>/`.
- **Option B — GitHub Actions:** **Settings → Pages → Source: _GitHub Actions_**.
  The included [`deploy-pages.yml`](.github/workflows/deploy-pages.yml) workflow
  publishes `docs/` on every push.

**Run it locally**

```bash
cd docs && python3 -m http.server 8000   # then open http://localhost:8000
```

(A static server is needed because the app uses ES modules; opening `index.html`
via `file://` won't load them.)

---

## 🐍 Python crawler (CLI & library)

### Why it works this way (please read)

Directly scraping the ACM Digital Library's web pages **violates its Terms of
Service** and is blocked by anti-bot protection and login walls. Instead, this
crawler uses **free, open, official scholarly-metadata APIs** that are designed
to be queried and cover essentially the same papers:

| Backend    | Abstract | Keywords            | Authors | Year | Venue filter | Key needed |
|------------|:--------:|:-------------------:|:-------:|:----:|:------------:|:----------:|
| **OpenAlex** (default) | ✅ | ✅ (keywords/concepts) | ✅ | ✅ | ✅ | no |
| Crossref (alternate)   | ⚠️ when deposited | ⚠️ (`subject`) | ✅ | ✅ | substring | no |

- **Abstracts, keywords, authors, year, venue** come straight from the API.
- **Introductions** are only available from *open-access* full text, so the
  `--fulltext` option is **best-effort**: it downloads the open-access PDF/HTML
  when one exists and slices out the Introduction section. Paywalled papers keep
  `introduction` empty rather than guessing.

Supplying `--mailto you@example.com` opts into each API's faster "polite pool"
and is strongly recommended.

## Install

```bash
pip install -r requirements.txt          # requests, PyYAML, (optional) pypdf
# or, as a package with the CLI entry point:
pip install -e .
```

Python 3.9+.

## Quick start

```bash
# List the venues defined in databases.yaml
archive-crawler --list-databases

# Crawl up to 50 recent ACM CHI papers to JSONL
archive-crawler --database acm_chi --year-from 2020 --limit 50 \
                --mailto you@example.com -o chi.jsonl

# Search within CHI, export CSV
archive-crawler --database acm_chi --query "haptic feedback" -f csv -o haptics.csv

# Also try to pull the Introduction from open-access full text
archive-crawler --database acm_chi --limit 20 --fulltext -o chi_full.jsonl

# Ad-hoc venue without editing the config
archive-crawler --venue "Proceedings of the CHI Conference" --source openalex --limit 10
```

> Running from a source checkout without installing? Use
> `python -m archive_crawler.cli ...` in place of `archive-crawler`.

## Defining your own database

Databases live in [`databases.yaml`](databases.yaml). Add an entry and use its
key with `--database`:

```yaml
databases:
  my_venue:
    label: "My Venue"
    source: openalex
    # A name OpenAlex resolves to a venue, or an explicit id like "S4306420956".
    venue: "Proceedings of the CHI Conference on Human Factors in Computing Systems"
    year_from: 2015          # optional defaults
```

Finding the exact OpenAlex venue id (most reliable):

```bash
curl "https://api.openalex.org/sources?search=CHI%20conference"
# copy the "id" (e.g. .../S4306420956) into `venue:`
```

Point at a different config file with `--config path/to/file.yaml` (`.json` also
supported).

## Output

- `--format jsonl` (default): one JSON object per line, streamed — best for
  large crawls and easy to load in pandas (`pd.read_json(path, lines=True)`).
- `--format json`: a single pretty-printed array.
- `--format csv`: flat table; authors and keywords joined with `; `.

Each record contains: `title`, `authors` (name/affiliation/orcid), `year`,
`abstract`, `introduction`, `keywords`, `doi`, `venue`, `url`,
`open_access_url`, `citation_count`, `source`.

## Use as a library

```python
from archive_crawler import Crawler, get_database

crawler = Crawler(get_database("acm_chi"), mailto="you@example.com")
for paper in crawler.crawl(year_from=2022, limit=100):
    print(paper.year, paper.title)
    print(paper.abstract)
```

## Architecture

```
archive_crawler/
  models.py           Paper / Author dataclasses
  config.py           load user-defined "databases" from databases.yaml
  sources/
    base.py           Source ABC: polite throttling, retries w/ backoff
    openalex.py       default backend (abstract, keywords, authors, year)
    crossref.py       alternate backend
  fulltext.py         best-effort Introduction extraction (open access only)
  crawler.py          orchestration: config + source + dedup + full text
  writers.py          jsonl / json / csv output
  cli.py              command-line interface
```

Add a new backend by subclassing `Source`, implementing `search(...)`, and
registering it in `sources/__init__.py`.

## Being a good citizen

- Requests are throttled and retried with exponential backoff.
- Use `--mailto` for the polite pool.
- Respect the [OpenAlex](https://docs.openalex.org/) and
  [Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)
  usage policies, and each publisher's terms when downloading full text.

## Tests

```bash
pip install pytest
pytest            # fully offline — network is mocked
```

## License

MIT
