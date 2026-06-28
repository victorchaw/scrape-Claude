"""
scraper.py — Playwright-based crawler for markdown.engineering/learn-claude-code/

Usage:
    python scripts/scraper.py [--url URL]

Handles the JS "press any key" gate, mirrors URL structure to output/raw/,
downloads CSS and image assets, and supports resume on interrupt.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent
OUTPUT_RAW = ROOT / "output" / "raw"
ASSETS_DIR = ROOT / "assets"
ERRORS_LOG = ROOT / "output" / "errors.log"

DEFAULT_URL = "https://www.markdown.engineering/learn-claude-code/"
TARGET_HOST = "www.markdown.engineering"
TARGET_PREFIX = "/learn-claude-code/"


# ---------------------------------------------------------------------------
# Inline helpers (scripts/utils.py not yet available on this branch)
# ---------------------------------------------------------------------------

def ensure_dirs(*paths: Path) -> None:
    """Create directories if they do not already exist."""
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)


def url_to_rel_path(url: str) -> str:
    """
    Strip scheme + host from a URL and return the path component
    without leading/trailing slashes.

    Example:
        https://www.markdown.engineering/learn-claude-code/basics/
        → learn-claude-code/basics
    """
    parsed = urllib.parse.urlparse(url)
    return parsed.path.strip("/")


def output_path_for(url: str) -> Path:
    """Return the output/raw/<path>/index.html destination for a URL."""
    rel = url_to_rel_path(url)
    return OUTPUT_RAW / rel / "index.html"


# ---------------------------------------------------------------------------
# Asset downloading
# ---------------------------------------------------------------------------

def download_asset(url: str, dest_dir: Path) -> Path | None:
    """Download a remote asset to dest_dir/<filename> and return the local path."""
    filename = Path(urllib.parse.urlparse(url).path).name
    if not filename:
        return None
    dest = dest_dir / filename
    if dest.exists():
        return dest
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return dest
    except Exception as exc:  # noqa: BLE001
        logging.warning("Asset download failed %s: %s", url, exc)
        return None


def download_page_assets(soup: BeautifulSoup, base_url: str) -> None:
    """Download CSS and image assets referenced in *soup* to assets/."""
    ensure_dirs(ASSETS_DIR)

    # CSS stylesheets
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href", "")
        if href:
            abs_url = urllib.parse.urljoin(base_url, href)
            download_asset(abs_url, ASSETS_DIR)

    # Images
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src:
            abs_url = urllib.parse.urljoin(base_url, src)
            download_asset(abs_url, ASSETS_DIR)


# ---------------------------------------------------------------------------
# Link extraction
# ---------------------------------------------------------------------------

def extract_slugs_from_script(soup: BeautifulSoup, base_url: str) -> list[str]:
    """
    Parse lesson URLs from the inline chapters JS array.
    The root page embeds all lesson slugs as:
        const chapters = [{..., "lessons": [{"slug": "01-boot-sequence", ...}]}]
    Returns list of absolute lesson URLs.
    """
    for script in soup.find_all("script"):
        text = script.string or ""
        match = re.search(r"const chapters\s*=\s*(\[.*?\]);", text, re.DOTALL)
        if match:
            try:
                chapters = json.loads(match.group(1))
                urls = []
                for chapter in chapters:
                    for lesson in chapter.get("lessons", []):
                        slug = lesson.get("slug", "")
                        if slug:
                            urls.append(f"https://www.markdown.engineering/learn-claude-code/{slug}/")
                logging.info("Extracted %d lesson URLs from chapters script", len(urls))
                return urls
            except json.JSONDecodeError as exc:
                logging.warning("Failed to parse chapters JSON: %s", exc)
    return []


def extract_internal_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    """
    Return deduplicated absolute URLs that are under TARGET_PREFIX
    on TARGET_HOST, excluding the base URL itself.
    """
    seen: set[str] = set()
    links: list[str] = []

    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        abs_url = urllib.parse.urljoin(base_url, href)
        parsed = urllib.parse.urlparse(abs_url)

        if (
            parsed.netloc == TARGET_HOST
            and parsed.path.startswith(TARGET_PREFIX)
            and abs_url not in seen
        ):
            # Normalise: drop fragment and query, ensure trailing slash
            clean = urllib.parse.urlunparse(
                (parsed.scheme, parsed.netloc, parsed.path, "", "", "")
            )
            if not clean.endswith("/"):
                clean += "/"
            if clean not in seen:
                seen.add(clean)
                links.append(clean)

    return links


# ---------------------------------------------------------------------------
# Core async crawler
# ---------------------------------------------------------------------------

async def handle_js_gate(page) -> None:
    """Dismiss the 'press any key' boot screen and wait for course hub to render."""
    try:
        # Simulate keypress to dismiss boot animation
        await page.keyboard.press("Space")
        # Wait for the course hub to become visible (boot animation completes)
        await page.wait_for_selector("#course-hub", state="visible", timeout=20_000)
        await page.wait_for_load_state("networkidle", timeout=15_000)
        logging.info("Boot animation dismissed, course hub visible")
    except Exception as exc:  # noqa: BLE001
        logging.debug("JS gate handling (non-fatal): %s", exc)


async def navigate_and_save(page, url: str) -> str | None:
    """
    Navigate to *url*, wait for networkidle, and return the page HTML.
    Returns None on failure.
    """
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_load_state("networkidle", timeout=30_000)
        return await page.content()
    except Exception as exc:  # noqa: BLE001
        logging.error("Failed to load %s: %s", url, exc)
        return None


async def crawl(root_url: str) -> None:
    ensure_dirs(OUTPUT_RAW, ASSETS_DIR, ERRORS_LOG.parent)

    # Set up error log handler
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    file_handler = logging.FileHandler(ERRORS_LOG, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(file_handler)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        # --- Step 1: Load root page ---
        logging.info("Loading root URL: %s", root_url)
        html = await navigate_and_save(page, root_url)
        if html is None:
            logging.error("Could not load root URL — aborting.")
            await browser.close()
            return

        # --- Step 2: Handle JS gate ---
        await handle_js_gate(page)

        # Re-fetch content after gate dismissal
        html = await page.content()

        # --- Step 3: Save root page ---
        root_dest = output_path_for(root_url)
        if not root_dest.exists():
            ensure_dirs(root_dest.parent)
            root_dest.write_text(html, encoding="utf-8")
            logging.info("Saved root → %s", root_dest)

        soup = BeautifulSoup(html, "html.parser")
        download_page_assets(soup, root_url)

        # --- Step 4: Collect links ---
        # Primary: extract lesson slugs from inline chapters JS array
        links = extract_slugs_from_script(soup, root_url)
        if not links:
            # Fallback: scan <a href> DOM links (for fully rendered pages)
            links = extract_internal_links(soup, root_url)
        logging.info("Found %d internal links to crawl", len(links))

        # --- Step 5: Crawl each link ---
        for url in tqdm(links, desc="Crawling pages", unit="page"):
            dest = output_path_for(url)

            if dest.exists():
                logging.debug("Skip (already saved): %s", url)
                continue

            page_html = await navigate_and_save(page, url)
            if page_html is None:
                # Error already logged inside navigate_and_save
                continue

            ensure_dirs(dest.parent)
            try:
                dest.write_text(page_html, encoding="utf-8")
            except OSError as exc:
                logging.error("Write failed %s: %s", dest, exc)
                continue

            page_soup = BeautifulSoup(page_html, "html.parser")
            download_page_assets(page_soup, url)

        await browser.close()

    logging.info("Crawl complete. Raw HTML in %s", OUTPUT_RAW)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl markdown.engineering/learn-claude-code/ and mirror raw HTML."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"Root URL to start crawl from (default: {DEFAULT_URL})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(crawl(args.url))


if __name__ == "__main__":
    main()
