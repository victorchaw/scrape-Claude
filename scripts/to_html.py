"""
to_html.py — Clone mode: rewrite asset URLs in Playwright-rendered HTML for offline use.

For each page in output/raw/:
  - Keep full rendered HTML exactly as captured (pixel-perfect clone)
  - Rewrite asset URLs (/_astro/*, https://site/*) to local relative paths
  - Download any JS/CSS/image assets not yet saved locally
  - For lesson pages only: strip boot-screen element, make content visible
  - Index page (/learn-claude-code/index.html): kept exactly as-is

Output mirrors the same path structure in output/html/.
"""

from __future__ import annotations

import json
import sys
import re
from pathlib import Path
from urllib.parse import urlparse, urljoin, urlunparse
from bs4 import BeautifulSoup, Tag

import requests
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Paths / constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "output" / "raw"
HTML_DIR = ROOT / "output" / "html"
ASSETS_DIR = ROOT / "assets"

TARGET_HOST = "www.markdown.engineering"
BASE_URL = f"https://{TARGET_HOST}"
ASSET_EXTENSIONS = {".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".gif",
                    ".webp", ".ico", ".woff", ".woff2", ".ttf", ".eot", ".map"}

SESSION = requests.Session()
SESSION.headers["User-Agent"] = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def collect_raw_files() -> list[Path]:
    if not RAW_DIR.exists():
        print("ERROR: output/raw/ not found. Run scripts/scraper.py first.", file=sys.stderr)
        sys.exit(1)
    return sorted(RAW_DIR.rglob("index.html"))


def depth_prefix_for(html_out: Path) -> str:
    """Return relative prefix (e.g. '../../') to reach output/html/ root."""
    depth = len(html_out.relative_to(HTML_DIR).parts) - 1  # subtract filename
    return ("../" * depth) if depth > 0 else "./"


def is_index_page(raw_file: Path) -> bool:
    """True if this is the root index page (not a lesson)."""
    rel = raw_file.relative_to(RAW_DIR)
    # e.g. learn-claude-code/index.html  (only 2 parts)
    return len(rel.parts) == 2 and rel.parts[-1] == "index.html"


def server_path_to_local_asset(path: str) -> tuple[str, str]:
    """
    Map a server-side path like /_astro/foo.css or /favicon.svg to:
      - a local asset sub-path  (e.g. _astro/foo.css)
      - a full local destination (ASSETS_DIR / subpath)
    Returns (subpath, dest_str).
    """
    clean = path.lstrip("/")           # _astro/foo.css  or  favicon.svg
    return clean, str(ASSETS_DIR / clean)


def download_asset(url: str, dest: Path) -> bool:
    """Download url → dest. Returns True on success."""
    if dest.exists():
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = SESSION.get(url, timeout=30)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True
    except Exception as exc:
        print(f"  WARN: failed to download {url}: {exc}", file=sys.stderr)
        return False


def is_asset_url(path: str) -> bool:
    ext = Path(urlparse(path).path).suffix.lower()
    return ext in ASSET_EXTENSIONS


def internal_url_to_local(url: str, prefix: str) -> str:
    """
    Convert an internal link (https://www.markdown.engineering/learn-claude-code/foo/)
    to a local relative HTML path (../../learn-claude-code/foo/index.html).
    Returns None if not an internal link.
    """
    parsed = urlparse(url)
    if parsed.netloc not in ("", TARGET_HOST, f"www.{TARGET_HOST}"):
        return None
    path = parsed.path.rstrip("/")
    if not path:
        path = "index"
    # Build relative link: prefix + path_without_leading_slash + /index.html
    local = prefix + path.lstrip("/") + "/index.html"
    return local


# ---------------------------------------------------------------------------
# Per-page processing
# ---------------------------------------------------------------------------

def remove_boot_animation(soup: BeautifulSoup) -> None:
    """
    On lesson pages: remove #boot-screen and make #course-hub visible.
    Safe to call even if elements don't exist.
    """
    boot = soup.find(id="boot-screen")
    if boot:
        boot.decompose()

    hub = soup.find(id="course-hub")
    if hub and isinstance(hub, Tag):
        style = hub.get("style", "")
        # Remove display:none
        style = re.sub(r"display\s*:\s*none\s*;?", "", style, flags=re.I).strip()
        style += "; display: block;"
        hub["style"] = style

    # Also remove the inline <script> that drives the boot animation
    # (it references boot-screen and would error if element is missing)
    source_root = soup.find(id="source-root")
    if source_root and isinstance(source_root, Tag):
        for script in source_root.find_all("script"):
            text = script.string or ""
            if "boot-screen" in text or "bootOutput" in text or "chapters" in text:
                script.decompose()


def rewrite_assets(soup: BeautifulSoup, prefix: str, base_url: str) -> None:
    """
    Rewrite all asset references in soup to local relative paths.
    Downloads missing assets.
    """
    # --- <link rel="stylesheet" href="..."> ---
    for tag in soup.find_all("link", href=True):
        href: str = tag["href"]
        parsed = urlparse(href)

        if parsed.scheme in ("http", "https") and parsed.netloc == TARGET_HOST:
            # Absolute URL to own domain — treat as server-relative
            href = parsed.path + (f"?{parsed.query}" if parsed.query else "")

        if href.startswith("/") and not href.startswith("//"):
            # Server-relative path
            if is_asset_url(href):
                subpath, dest = server_path_to_local_asset(href)
                download_asset(urljoin(base_url, href), Path(dest))
                tag["href"] = prefix + "assets/" + subpath
        elif href.startswith("//"):
            pass  # Protocol-relative external (Google Fonts etc) — leave alone
        # External (https://fonts.googleapis.com etc) — leave alone

    # --- <script src="..."> ---
    for tag in soup.find_all("script", src=True):
        src: str = tag["src"]
        parsed = urlparse(src)

        if parsed.scheme in ("http", "https") and parsed.netloc == TARGET_HOST:
            src = parsed.path

        if src.startswith("/") and not src.startswith("//"):
            if is_asset_url(src):
                subpath, dest = server_path_to_local_asset(src)
                download_asset(urljoin(base_url, src), Path(dest))
                tag["src"] = prefix + "assets/" + subpath

    # --- <img src="..."> ---
    for tag in soup.find_all("img", src=True):
        src: str = tag["src"]
        parsed = urlparse(src)

        if parsed.scheme in ("http", "https") and parsed.netloc == TARGET_HOST:
            src = parsed.path

        if src.startswith("/") and not src.startswith("//"):
            subpath, dest = server_path_to_local_asset(src)
            download_asset(urljoin(base_url, src), Path(dest))
            tag["src"] = prefix + "assets/" + subpath
        elif parsed.scheme in ("http", "https") and is_asset_url(src):
            # External image — download to assets
            filename = Path(parsed.path).name
            if filename:
                dest = ASSETS_DIR / filename
                download_asset(src, dest)
                tag["src"] = prefix + "assets/" + filename

    # --- <a href="..."> internal links → local HTML ---
    for tag in soup.find_all("a", href=True):
        href: str = tag["href"]
        if href.startswith("#") or href.startswith("mailto:"):
            continue
        parsed = urlparse(href)
        if parsed.netloc in ("", TARGET_HOST):
            local = internal_url_to_local(urljoin(base_url, href), prefix)
            if local:
                tag["href"] = local

    # --- inline style: url('/...') patterns ---
    for tag in soup.find_all(style=True):
        style = tag["style"]
        def replace_url(m):
            url_val = m.group(1).strip("'\"")
            if url_val.startswith("/") and not url_val.startswith("//"):
                subpath, dest = server_path_to_local_asset(url_val)
                download_asset(urljoin(base_url, url_val), Path(dest))
                return f"url('{prefix}assets/{subpath}')"
            return m.group(0)
        tag["style"] = re.sub(r"url\(([^)]+)\)", replace_url, style)


def process_file(raw_file: Path) -> bool:
    rel = raw_file.relative_to(RAW_DIR)
    html_out = HTML_DIR / rel
    html_out.parent.mkdir(parents=True, exist_ok=True)

    try:
        raw_html = raw_file.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"  ERROR reading {raw_file}: {exc}", file=sys.stderr)
        return False

    soup = BeautifulSoup(raw_html, "html.parser")
    prefix = depth_prefix_for(html_out)
    base_url = BASE_URL + "/" + str(rel.parent).replace("\\", "/") + "/"

    # Lesson pages only: strip boot animation
    if not is_index_page(raw_file):
        remove_boot_animation(soup)

    # Rewrite all asset + internal link URLs
    rewrite_assets(soup, prefix, BASE_URL)

    html_out.write_text(str(soup), encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("scrape-Claude — to_html.py (clone mode)")
    print(f"  RAW:    {RAW_DIR}")
    print(f"  OUTPUT: {HTML_DIR}")

    raw_files = collect_raw_files()
    print(f"  Found {len(raw_files)} raw pages")

    HTML_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    ok = fail = 0
    for raw_file in tqdm(raw_files, desc="Cloning pages", unit="page"):
        if process_file(raw_file):
            ok += 1
        else:
            fail += 1

    print(f"\nDone. {ok} cloned, {fail} failed.")
    if fail:
        print("Check stderr above for details.")


if __name__ == "__main__":
    main()
