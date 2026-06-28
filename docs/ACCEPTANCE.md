# Acceptance Criteria

Run this checklist before marking any implementation task done.

## Phase 1: Scraper (`scripts/scraper.py`)
- [ ] `.venv/` exists and all deps installed (`playwright`, `beautifulsoup4`, `markdownify`, `tqdm`)
- [ ] `playwright install chromium` completed
- [ ] Script runs without error: `python scripts/scraper.py`
- [ ] `output/raw/` contains at least one subdirectory mirroring a URL path
- [ ] `output/raw/index.html` exists (root page)
- [ ] `assets/` contains at least one `.css` file
- [ ] `output/errors.log` created (empty = perfect, entries = investigate)
- [ ] Re-running script skips already-scraped pages (check log output says "skipping")

## Phase 2: Markdown (`scripts/to_markdown.py`)
- [ ] `output/markdown/` mirrors same structure as `output/raw/`
- [ ] Each `.md` file contains readable text (not just HTML tags)
- [ ] `output/metadata.json` exists and contains title + prev/next for each page
- [ ] No `.md` file is empty or under 50 characters

## Phase 3: README + Mermaid (`scripts/build_readme.py`)
- [ ] `README.md` exists at project root
- [ ] Contains `graph TD` mermaid block (sitemap)
- [ ] Contains `flowchart LR` mermaid block (nav flow)
- [ ] Both blocks render without syntax error (test at mermaid.live)

## Phase 4: Enhanced HTML (`scripts/to_html.py`)
- [ ] `output/html/` mirrors same structure as `output/raw/`
- [ ] Opening `output/html/index.html` in browser shows sidebar nav
- [ ] Sidebar nav links work (clicking navigates to correct page)
- [ ] Prev/Next buttons present and functional
- [ ] Search input visible (even if index incomplete)
- [ ] Original content styling preserved (not plain unstyled text)
- [ ] `assets/custom.css` exists
- [ ] `output/html/search-index.json` exists

## Overall
- [ ] No files outside `output/`, `assets/`, `scripts/`, `docs/` were modified
- [ ] `.venv/` not committed to git
- [ ] No hardcoded absolute paths (use `pathlib.Path(__file__).parent`)
