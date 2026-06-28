"""
to_markdown.py — Convert raw scraped HTML to Markdown.

Pipeline position: step 2 (run scraper.py first).

For each output/raw/**/index.html:
  - Parse with BeautifulSoup (html.parser)
  - Extract page title from <title> or <h1>
  - Extract prev/next nav links from <a> tags
  - Locate content via main → article → body fallback chain
  - Convert content to ATX Markdown via markdownify
  - Write to output/markdown/<mirrored-path>/index.md
  - Collect per-page metadata

After all pages: write output/metadata.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import markdownify
from bs4 import BeautifulSoup
from tqdm import tqdm

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "output" / "raw"
MD_DIR = ROOT / "output" / "markdown"
METADATA_FILE = ROOT / "output" / "metadata.json"


def _extract_title(soup: BeautifulSoup) -> str:
    """Return page title from <title> tag, falling back to the first <h1>."""
    title_tag = soup.find("title")
    if title_tag and title_tag.get_text(strip=True):
        return title_tag.get_text(strip=True)
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    return ""


def _extract_nav_links(soup: BeautifulSoup) -> tuple[str, str]:
    """Return (prev_url, next_url) extracted from anchor tags.

    Strategy:
    1. Look for <a rel="prev"> / <a rel="next"> attributes.
    2. Fall back to anchors whose visible text contains "prev"/"previous"/"next"
       (case-insensitive).
    """
    prev_url = ""
    next_url = ""

    for a in soup.find_all("a", href=True):
        rel = a.get("rel", [])
        # rel attribute may be a list (BeautifulSoup parses it that way)
        if isinstance(rel, str):
            rel = [rel]
        rel_lower = [r.lower() for r in rel]

        href = a["href"].strip()
        text = a.get_text(strip=True).lower()

        if not prev_url and ("prev" in rel_lower or "prev" in text or "previous" in text):
            prev_url = href
        if not next_url and ("next" in rel_lower or "next" in text):
            next_url = href

    return prev_url, next_url


def _extract_content(soup: BeautifulSoup) -> BeautifulSoup:
    """Return the best content element using main → article → body fallback."""
    for tag in ("main", "article", "body"):
        element = soup.find(tag)
        if element:
            return element
    # Absolute fallback: return the whole soup
    return soup


def convert_file(html_path: Path) -> dict | None:
    """Convert a single HTML file to Markdown.

    Returns metadata dict for this page, or None if skipped.
    """
    # Compute paths
    relative = html_path.relative_to(RAW_DIR)          # e.g. foo/bar/index.html
    md_path = MD_DIR / relative.parent / "index.md"    # e.g. output/markdown/foo/bar/index.md

    if md_path.exists():
        return None  # already converted — skip

    html = html_path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")

    title = _extract_title(soup)
    prev_url, next_url = _extract_nav_links(soup)
    content = _extract_content(soup)

    markdown = markdownify.markdownify(str(content), heading_style="ATX")

    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(markdown, encoding="utf-8")

    rel_key = str(relative.parent)  # e.g. "foo/bar" or "." for root

    return {
        "title": title,
        "prev_url": prev_url,
        "next_url": next_url,
        "md_path": str(md_path.relative_to(ROOT)),
    }, rel_key


def main() -> None:
    if not RAW_DIR.exists():
        print(
            "Error: output/raw/ not found. "
            "Run scraper.py first — output/raw/ not found",
            file=sys.stderr,
        )
        sys.exit(1)

    html_files = sorted(RAW_DIR.rglob("index.html"))

    if not html_files:
        print("No index.html files found in output/raw/. Nothing to convert.")
        sys.exit(0)

    # Load existing metadata so incremental runs don't wipe previous entries
    metadata: dict[str, dict] = {}
    if METADATA_FILE.exists():
        try:
            metadata = json.loads(METADATA_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            metadata = {}

    converted = 0
    skipped = 0

    for html_path in tqdm(html_files, desc="Converting", unit="page"):
        result = convert_file(html_path)
        if result is None:
            skipped += 1
        else:
            page_meta, rel_key = result
            metadata[rel_key] = page_meta
            converted += 1

    # Always rewrite metadata (even on zero conversions, to keep it consistent)
    METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    METADATA_FILE.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"\nDone. {converted} page(s) converted, {skipped} skipped.")
    print(f"Metadata written to {METADATA_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
