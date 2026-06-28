# scrape-Claude — Agent Bootstrap

## Purpose
Scrape `https://www.markdown.engineering/learn-claude-code/`, mirror as Markdown + enhanced HTML.

## Critical: Read Before Acting
1. Check `docs/` for PRD, ADR, TDD, acceptance criteria before writing any code.
2. Never install to global Python — always use `.venv/`.
3. Activate venv: `source .venv/bin/activate`
4. Never commit `.venv/`, scraped content, or credentials.

## Locked Decisions (see `docs/ADR.md` for rationale)
| Decision | Value |
|---|---|
| Scrape scope | `markdown.engineering/learn-claude-code/*` (full crawl) |
| JS gate | Playwright simulates keypress on landing |
| Language | Python 3.11.6 + Playwright + BeautifulSoup4 + markdownify |
| Venv | `.venv/` inside project root |
| Output structure | Mirror URL paths exactly |
| Markdown output | Per-page `.md` at mirrored path + root `README.md` |
| Mermaid | Sitemap tree + nav flow diagram in `README.md` |
| HTML output | Static HTML + original CSS + custom sidebar/nav/search layer |

## Project Structure
```
scrape-Claude/
├── CLAUDE.md              ← you are here
├── README.md              ← generated sitemap + mermaid diagrams
├── .venv/                 ← Python venv (never commit)
├── docs/
│   ├── PRD.md
│   ├── ADR.md
│   ├── TDD.md
│   └── ACCEPTANCE.md
├── scripts/
│   ├── scraper.py         ← crawl + extract
│   ├── to_markdown.py     ← HTML → Markdown conversion
│   ├── to_html.py         ← generate enhanced HTML
│   └── build_readme.py    ← generate README + mermaid
├── output/
│   ├── markdown/          ← mirrored .md files
│   └── html/              ← mirrored enhanced .html files
└── assets/                ← downloaded CSS + images
```

## Build Order (strict)
1. `scripts/scraper.py` → crawl, save raw HTML + assets
2. `scripts/to_markdown.py` → convert raw HTML to `.md`
3. `scripts/to_html.py` → generate enhanced HTML
4. `scripts/build_readme.py` → generate `README.md` with mermaid

## Current Status (2026-06-28)
All 4 scripts implemented and working. 51 pages cloned offline successfully.
- Issues #1–#5 closed via merged PRs.
- Issue #6 (QA) still open — acceptance checklist not formally run yet.
- `output/html/` = pixel-perfect offline clone of the site.
- Browse: `python3 -m http.server 8765 --directory output/html`

## Next Tasks
1. Run QA checklist (`docs/ACCEPTANCE.md`) and close Issue #6.
2. Test internal navigation links between lesson pages work offline.
3. Verify index page boot animation still functions offline.
4. Optional: add `--force` flag to scraper to re-scrape existing pages.

## Acceptance Gate
Run `docs/ACCEPTANCE.md` checklist before marking any task done.
