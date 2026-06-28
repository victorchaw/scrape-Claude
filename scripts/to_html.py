#!/usr/bin/env python3
"""
to_html.py — Generate enhanced static HTML from raw scraped pages.

For each page in output/raw/**/index.html:
  - Extracts main content via BeautifulSoup
  - Rewrites asset URLs to local assets/ paths
  - Injects sidebar nav, prev/next buttons, client-side search
  - Saves enhanced HTML to output/html/<mirrored-path>/index.html

Also generates:
  - assets/custom.css   — sidebar layout + search UI styles
  - output/html/search-index.json — [{title, url, text}] for client-side search
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "output" / "raw"
HTML_DIR = ROOT / "output" / "html"
ASSETS_DIR = ROOT / "assets"
METADATA_FILE = ROOT / "output" / "metadata.json"
CUSTOM_CSS_FILE = ASSETS_DIR / "custom.css"
SEARCH_INDEX_FILE = HTML_DIR / "search-index.json"

# ---------------------------------------------------------------------------
# HTML shell template
# ---------------------------------------------------------------------------

HTML_SHELL = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{page_title}</title>
  {original_css_links}
  <link rel="stylesheet" href="{depth_prefix}assets/custom.css">
</head>
<body class="scrape-layout">
  <button id="scrape-toggle" onclick="document.querySelector('.scrape-sidebar').classList.toggle('open')">☰ LESSONS</button>
  <nav class="scrape-sidebar">
    <div class="scrape-sidebar-header">
      <span>COURSE INDEX</span>
      <button id="scrape-close" onclick="document.querySelector('.scrape-sidebar').classList.remove('open')">✕</button>
    </div>
    {sidebar_nav_links}
    <div class="scrape-search">
      <input type="text" id="scrape-search-input" placeholder="Search lessons..." />
      <ul id="scrape-search-results"></ul>
    </div>
  </nav>
  <main class="scrape-content">
    {page_content}
    <div class="scrape-nav-buttons">
      {prev_button}
      {next_button}
    </div>
  </main>
  <script>
    // Close sidebar when clicking backdrop
    document.querySelector('.scrape-sidebar').addEventListener('click', function(e) {{
      if (e.target === this) this.classList.remove('open');
    }});
    // Client-side search
    fetch('{depth_prefix}search-index.json').then(r=>r.json()).then(idx=>{{
      document.getElementById('scrape-search-input').addEventListener('input',function(){{
        const q=this.value.toLowerCase();
        const results=idx.filter(p=>p.title.toLowerCase().includes(q)||p.text.toLowerCase().includes(q));
        document.getElementById('scrape-search-results').innerHTML=
          results.slice(0,10).map(p=>`<li><a href="${{p.url}}">${{p.title}}</a></li>`).join('');
      }});
    }});
  </script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

CUSTOM_CSS = None  # written only if assets/custom.css does not exist

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_metadata() -> list[dict]:
    """Load and return metadata.json. Exits with error if missing/invalid."""
    if not METADATA_FILE.exists():
        print(
            f"ERROR: metadata.json not found at {METADATA_FILE}\n"
            "Run scripts/to_markdown.py first to generate it.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        data = json.loads(METADATA_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: metadata.json is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    if isinstance(data, dict):
        # Keys are relative paths like "learn-claude-code/01-boot-sequence"
        # Inject as url field so downstream functions can build links
        pages = []
        for path_key, meta in data.items():
            entry = dict(meta)
            entry["url"] = "/" + path_key.strip("/") + "/"
            pages.append(entry)
    elif isinstance(data, list):
        pages = data
    else:
        pages = []

    return pages


def collect_raw_files() -> list[Path]:
    """Return sorted list of raw index.html files."""
    if not RAW_DIR.exists():
        print(
            f"ERROR: raw output directory not found at {RAW_DIR}\n"
            "Run scripts/scraper.py first.",
            file=sys.stderr,
        )
        sys.exit(1)
    files = sorted(RAW_DIR.rglob("index.html"))
    if not files:
        print(f"WARNING: No index.html files found under {RAW_DIR}", file=sys.stderr)
    return files


def depth_prefix_for(html_out_path: Path) -> str:
    """
    Calculate the relative prefix from an output HTML file back to output/html/.

    E.g. output/html/learn-claude-code/basics/index.html → '../../'
         output/html/index.html → ''
    """
    relative = html_out_path.relative_to(HTML_DIR)
    # Number of directory levels above the file itself (excluding 'index.html')
    depth = len(relative.parts) - 1  # subtract filename
    if depth <= 0:
        return "./"
    return "../" * depth


def extract_content(soup: BeautifulSoup) -> Tag:
    """Extract the primary content element from parsed HTML."""
    for selector in ("main", "article"):
        tag = soup.find(selector)
        if tag:
            return tag
    # Fall back to body
    body = soup.find("body")
    if body:
        return body
    return soup  # last resort: whole document


def extract_title(soup: BeautifulSoup, fallback: str = "Untitled") -> str:
    """Extract page title."""
    title_tag = soup.find("title")
    if title_tag and title_tag.get_text(strip=True):
        return title_tag.get_text(strip=True)
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return fallback


def rewrite_asset_urls(content: Tag, depth_prefix: str) -> None:
    """
    Rewrite src/href attributes that point to remote assets so they resolve
    locally under assets/.

    CSS <link> tags and <img> src attributes are rewritten.
    Relative paths that already look local are left alone.
    """
    # Images
    for img in content.find_all("img", src=True):
        src: str = img["src"]
        if src.startswith("http://") or src.startswith("https://"):
            filename = Path(urlparse(src).path).name
            if filename:
                img["src"] = f"{depth_prefix}assets/{filename}"

    # Anchor hrefs that point to assets (e.g. .svg, .png in links) — skip nav links
    for a in content.find_all("a", href=True):
        href: str = a["href"]
        if href.startswith("http://") or href.startswith("https://"):
            path = urlparse(href).path
            if Path(path).suffix in {".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp"}:
                filename = Path(path).name
                if filename:
                    a["href"] = f"{depth_prefix}assets/{filename}"


def extract_css_links(soup: BeautifulSoup, depth_prefix: str) -> str:
    """
    Find <link rel=stylesheet> tags pointing to the original domain.
    Rewrite them to local assets/ paths and return as HTML string.
    """
    lines: list[str] = []
    for link in soup.find_all("link", rel=lambda r: r and "stylesheet" in r):
        href: str = link.get("href", "")
        if href.startswith("http://") or href.startswith("https://"):
            filename = Path(urlparse(href).path).name
            if filename:
                lines.append(f'  <link rel="stylesheet" href="{depth_prefix}assets/{filename}">')
            else:
                # Keep original if we can't determine filename
                lines.append(f'  <link rel="stylesheet" href="{href}">')
        elif href.startswith("/"):
            # Server-relative path — extract filename and rewrite to local assets/
            filename = Path(href).name
            if filename and filename.endswith(".css"):
                lines.append(f'  <link rel="stylesheet" href="{depth_prefix}assets/{filename}">')
            # Skip non-CSS server-relative links (favicons, etc.)
        elif href:
            lines.append(f'  <link rel="stylesheet" href="{href}">')
    return "\n".join(lines)


def build_sidebar_nav(pages: list[dict], current_url: str, depth_prefix: str) -> str:
    """Build <nav> HTML listing all pages, highlighting current page."""
    items: list[str] = []
    for page in pages:
        url = page.get("url", "")
        title = page.get("title", url) or url
        # Convert absolute URL → relative path from output/html/
        # e.g. https://site.com/learn-claude-code/foo/ → learn-claude-code/foo/index.html
        parsed = urlparse(url)
        path_parts = parsed.path.strip("/").split("/")
        rel_url = depth_prefix + "/".join(path_parts) + "/index.html" if path_parts and path_parts[0] else "#"

        active = " active" if url == current_url else ""
        items.append(f'    <li><a href="{rel_url}" class="{active.strip()}">{title}</a></li>')

    nav_items = "\n".join(items)
    return f"<nav>\n  <ul>\n{nav_items}\n  </ul>\n</nav>"


def build_prev_next(page_meta: dict | None, depth_prefix: str) -> tuple[str, str]:
    """Return (prev_button_html, next_button_html) strings."""
    prev_btn = ""
    next_btn = ""

    if not page_meta:
        return prev_btn, next_btn

    prev_url = page_meta.get("prev_url", "")
    next_url = page_meta.get("next_url", "")
    prev_title = page_meta.get("prev_title", "Previous")
    next_title = page_meta.get("next_title", "Next")

    if prev_url:
        parsed = urlparse(prev_url)
        path_parts = parsed.path.strip("/").split("/")
        rel = depth_prefix + "/".join(path_parts) + "/index.html" if path_parts and path_parts[0] else "#"
        prev_btn = f'<a href="{rel}" class="prev">{prev_title or "Previous"}</a>'

    if next_url:
        parsed = urlparse(next_url)
        path_parts = parsed.path.strip("/").split("/")
        rel = depth_prefix + "/".join(path_parts) + "/index.html" if path_parts and path_parts[0] else "#"
        next_btn = f'<a href="{rel}" class="next">{next_title or "Next"}</a>'

    return prev_btn, next_btn


def find_page_meta(pages: list[dict], raw_file: Path) -> dict | None:
    """
    Match a raw HTML file to its metadata entry by comparing URL paths.

    raw file: output/raw/learn-claude-code/foo/bar/index.html
    expected URL path:   /learn-claude-code/foo/bar/
    """
    # Derive URL path from file location relative to RAW_DIR
    rel = raw_file.relative_to(RAW_DIR)
    # Drop trailing 'index.html' to get directory path
    dir_parts = rel.parts[:-1]  # e.g. ('learn-claude-code', 'foo', 'bar')
    url_path = "/" + "/".join(dir_parts) + "/"

    for page in pages:
        page_url = page.get("url", "")
        parsed_path = urlparse(page_url).path
        # Normalise trailing slash
        if parsed_path.rstrip("/") == url_path.rstrip("/"):
            return page
    return None


# ---------------------------------------------------------------------------
# Search index
# ---------------------------------------------------------------------------


def build_search_index(pages: list[dict], raw_files: list[Path]) -> list[dict]:
    """
    Build search index entries from raw HTML files.
    Returns [{title, url, text}] where text = first 200 chars of plain text.
    """
    # Build lookup: url_path → raw file
    path_to_file: dict[str, Path] = {}
    for f in raw_files:
        rel = f.relative_to(RAW_DIR)
        dir_parts = rel.parts[:-1]
        path_to_file["/" + "/".join(dir_parts) + "/"] = f

    index: list[dict] = []
    for page in pages:
        url = page.get("url", "")
        title = page.get("title", "")
        parsed_path = urlparse(url).path
        raw_file = path_to_file.get(parsed_path) or path_to_file.get(parsed_path.rstrip("/") + "/")
        text = ""
        if raw_file and raw_file.exists():
            try:
                raw_soup = BeautifulSoup(raw_file.read_text(encoding="utf-8", errors="replace"), "html.parser")
                content = extract_content(raw_soup)
                text = content.get_text(separator=" ", strip=True)[:200]
            except Exception:
                pass
        index.append({"title": title, "url": url, "text": text})
    return index


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------


def process_file(raw_file: Path, pages: list[dict]) -> dict | None:
    """
    Process one raw HTML file → write enhanced HTML to output/html/.
    Returns search-index entry or None on failure.
    """
    # Determine output path
    rel = raw_file.relative_to(RAW_DIR)
    html_out = HTML_DIR / rel
    html_out.parent.mkdir(parents=True, exist_ok=True)

    # Parse raw HTML
    try:
        raw_html = raw_file.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"  WARNING: Cannot read {raw_file}: {exc}", file=sys.stderr)
        return None

    soup = BeautifulSoup(raw_html, "html.parser")

    # Metadata for this page
    page_meta = find_page_meta(pages, raw_file)

    # Title
    page_title = extract_title(soup)
    if page_meta and page_meta.get("title"):
        page_title = page_meta["title"]

    # Depth prefix (relative path back to output/html/ root)
    prefix = depth_prefix_for(html_out)

    # Extract and clean content
    content = extract_content(soup)
    rewrite_asset_urls(content, prefix)
    page_content = str(content)

    # Original CSS links rewritten to local
    original_css = extract_css_links(soup, prefix)

    # Sidebar
    current_url = page_meta.get("url", "") if page_meta else ""
    sidebar = build_sidebar_nav(pages, current_url, prefix)

    # Prev / next
    prev_btn, next_btn = build_prev_next(page_meta, prefix)

    # Render shell
    final_html = HTML_SHELL.format(
        page_title=page_title,
        original_css_links=original_css,
        depth_prefix=prefix,
        sidebar_nav_links=sidebar,
        page_content=page_content,
        prev_button=prev_btn,
        next_button=next_btn,
    )

    html_out.write_text(final_html, encoding="utf-8")
    return html_out


def main() -> None:
    print(f"scrape-Claude — to_html.py")
    print(f"  ROOT: {ROOT}")

    # Validate inputs
    pages = load_metadata()
    print(f"  Loaded {len(pages)} pages from metadata.json")

    raw_files = collect_raw_files()
    print(f"  Found {len(raw_files)} raw HTML files")

    if not raw_files:
        print("Nothing to process. Exiting.")
        sys.exit(0)

    # Ensure output directories exist
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    # Write custom.css only if it doesn't already exist (don't overwrite edits)
    if not CUSTOM_CSS_FILE.exists():
        CUSTOM_CSS_FILE.write_text("/* add CSS here */\n", encoding="utf-8")
        print(f"  Wrote {CUSTOM_CSS_FILE}")
    else:
        print(f"  Using existing {CUSTOM_CSS_FILE}")

    # Process each raw file
    processed = 0
    errors = 0
    for raw_file in raw_files:
        rel = raw_file.relative_to(RAW_DIR)
        print(f"  Processing {rel} ...", end=" ")
        result = process_file(raw_file, pages)
        if result:
            print("OK")
            processed += 1
        else:
            print("SKIP")
            errors += 1

    # Build and write search index
    print("  Building search index ...")
    search_index = build_search_index(pages, raw_files)
    SEARCH_INDEX_FILE.write_text(
        json.dumps(search_index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  Wrote {SEARCH_INDEX_FILE} ({len(search_index)} entries)")

    print(f"\nDone. {processed} pages generated, {errors} skipped.")
    if errors:
        print(f"Check stderr for warnings.")


if __name__ == "__main__":
    main()
