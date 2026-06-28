# TDD — Technical Design Document

## Stack
| Component | Library | Version |
|---|---|---|
| Browser automation | `playwright` | latest |
| HTML parsing | `beautifulsoup4` | latest |
| HTML→Markdown | `markdownify` | latest |
| Progress display | `tqdm` | latest |
| HTTP fallback | `requests` | latest |

## Script Contracts

### `scripts/scraper.py`
**Input:** CLI flag `--url` (default: `https://www.markdown.engineering/learn-claude-code/`)  
**Process:**
1. Launch Playwright Chromium (headless)
2. Navigate to root URL
3. Detect "press any key" gate → dispatch `KeyboardEvent` (key: `Space`)
4. Wait for content to render (`networkidle`)
5. Extract all internal links under `/learn-claude-code/`
6. For each link: navigate, wait, save raw HTML to `output/raw/<mirrored-path>/index.html`
7. Download all CSS/images referenced in pages → `assets/`
8. Skip pages where raw file already exists (resume support)

**Output:** `output/raw/` tree of raw HTML files + `assets/`

---

### `scripts/to_markdown.py`
**Input:** `output/raw/` tree  
**Process:**
1. For each raw HTML file: parse with BeautifulSoup
2. Extract `<main>` or largest content block
3. Convert to Markdown via `markdownify`
4. Save to `output/markdown/<mirrored-path>/index.md`
5. Extract page title + prev/next links → store in page metadata JSON sidecar

**Output:** `output/markdown/` tree of `.md` files + `output/metadata.json`

---

### `scripts/build_readme.py`
**Input:** `output/metadata.json`  
**Process:**
1. Build sitemap tree from all page paths
2. Render as Mermaid `graph TD` block
3. Build nav flow from prev/next metadata
4. Render as Mermaid `flowchart LR` block
5. Write `README.md` at project root

**Output:** `README.md`

---

### `scripts/to_html.py`
**Input:** `output/raw/` tree + `assets/` + `output/metadata.json`  
**Process:**
1. For each raw HTML file:
   a. Inject sidebar HTML (generated from sitemap)
   b. Inject prev/next nav buttons
   c. Inject search index script (client-side, no server needed)
   d. Rewrite asset URLs to local `../../assets/` paths
   e. Append custom CSS link (`assets/custom.css`)
2. Save to `output/html/<mirrored-path>/index.html`
3. Generate `assets/custom.css` (sidebar layout, nav buttons, search UI)
4. Generate `output/html/search-index.json` (title + text per page)

**Output:** `output/html/` tree of enhanced `.html` files

## Error Handling
- Playwright timeout on page load → log to `output/errors.log`, skip page, continue
- Missing `<main>` tag → fall back to `<body>` content
- Asset download failure → log, use original remote URL as fallback

## File Naming
All output paths derived from URL path: `https://site.com/learn-claude-code/foo/bar/` → `foo/bar/index.{html,md}`
