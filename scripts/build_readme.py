"""build_readme.py — Generate root README.md with two Mermaid diagrams.

Input:  output/metadata.json  (produced by to_markdown.py)
Output: README.md at project root

Diagrams produced:
  1. graph TD  — sitemap tree built from URL path segments
  2. flowchart LR — navigation flow built from prev_url / next_url metadata

Usage:
    python scripts/build_readme.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
METADATA_PATH = ROOT / "output" / "metadata.json"
README_PATH = ROOT / "README.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_id(text: str) -> str:
    """Convert arbitrary text to a Mermaid-safe node identifier."""
    node_id = re.sub(r"[^a-zA-Z0-9_]", "_", text)
    node_id = re.sub(r"_+", "_", node_id).strip("_")
    return node_id or "node"


def _label(text: str, max_len: int = 40) -> str:
    """Truncate label and escape Mermaid special chars."""
    text = text.strip()
    if len(text) > max_len:
        text = text[:max_len - 1] + "…"
    # Escape double quotes inside labels
    text = text.replace('"', "'")
    return text


# ---------------------------------------------------------------------------
# Diagram 1: Sitemap tree (graph TD)
# ---------------------------------------------------------------------------

def build_sitemap_diagram(metadata: dict) -> str:
    """Build a Mermaid graph TD from the path hierarchy in metadata keys."""

    # Each key is a relative path like "learn-claude-code/basics/"
    # We parse it into segments and build a parent→child tree.

    # node registry: segment_path_tuple -> (node_id, display_label)
    nodes: dict[tuple, tuple[str, str]] = {}
    edges: list[tuple[str, str]] = []  # (parent_id, child_id)

    # Root node
    root_tuple: tuple = ()
    root_id = "ROOT"
    nodes[root_tuple] = (root_id, "markdown.engineering")

    def register_path(segments: list[str], page_title: str) -> None:
        parent_tuple: tuple = ()
        for i, seg in enumerate(segments):
            current_tuple = tuple(segments[: i + 1])
            if current_tuple not in nodes:
                # Use the page title only for the leaf (last segment)
                is_leaf = i == len(segments) - 1
                label = _label(page_title) if is_leaf else _label(seg.replace("-", " ").title())
                node_id = _safe_id("_".join(current_tuple))
                nodes[current_tuple] = (node_id, label)
                edges.append((nodes[parent_tuple][0], node_id))
            parent_tuple = current_tuple

    for path_key, page_meta in metadata.items():
        # Strip leading/trailing slashes, split on "/"
        segments = [s for s in path_key.strip("/").split("/") if s]
        if not segments:
            continue
        title = page_meta.get("title") or segments[-1].replace("-", " ").title()
        register_path(segments, title)

    lines: list[str] = ["graph TD"]

    # Emit root node definition
    root_node_id, root_label = nodes[root_tuple]
    lines.append(f'  {root_node_id}["{root_label}"]')

    # Emit all other node definitions
    for tup, (node_id, label) in nodes.items():
        if tup == root_tuple:
            continue
        lines.append(f'  {node_id}["{label}"]')

    # Emit edges
    for parent_id, child_id in edges:
        lines.append(f"  {parent_id} --> {child_id}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Diagram 2: Navigation flow (flowchart LR)
# ---------------------------------------------------------------------------

def _url_to_id(url: str) -> str:
    """Convert a URL or path string to a Mermaid node ID."""
    # Strip scheme + domain if present
    path = re.sub(r"^https?://[^/]+", "", url)
    return _safe_id(path)


def build_nav_diagram(metadata: dict) -> str:
    """Build a Mermaid flowchart LR from prev_url / next_url fields."""

    # Collect all nodes (by node_id -> label) and directed edges
    node_labels: dict[str, str] = {}
    directed_edges: set[tuple[str, str]] = set()

    def get_label(path_key: str) -> str:
        page = metadata.get(path_key, {})
        title = page.get("title") or path_key.strip("/").split("/")[-1].replace("-", " ").title()
        return _label(title)

    def url_to_key(url: str) -> str:
        """Normalise a URL/path to the metadata key format (trailing slash)."""
        path = re.sub(r"^https?://[^/]+", "", url).strip("/")
        return path + "/" if path else ""

    for path_key, page_meta in metadata.items():
        current_id = _safe_id(path_key)
        node_labels.setdefault(current_id, get_label(path_key))

        prev_url = page_meta.get("prev_url") or ""
        next_url = page_meta.get("next_url") or ""

        if prev_url:
            prev_key = url_to_key(prev_url)
            prev_id = _safe_id(prev_key)
            node_labels.setdefault(prev_id, get_label(prev_key))
            directed_edges.add((prev_id, current_id))

        if next_url:
            next_key = url_to_key(next_url)
            next_id = _safe_id(next_key)
            node_labels.setdefault(next_id, get_label(next_key))
            directed_edges.add((current_id, next_id))

    lines: list[str] = ["flowchart LR"]

    for node_id, label in node_labels.items():
        lines.append(f'  {node_id}["{label}"]')

    for src_id, dst_id in sorted(directed_edges):
        lines.append(f"  {src_id} --> {dst_id}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pages table
# ---------------------------------------------------------------------------

def build_pages_table(metadata: dict) -> str:
    rows: list[str] = [
        "| Page | Path |",
        "|---|---|",
    ]
    for path_key, page_meta in sorted(metadata.items()):
        title = page_meta.get("title") or path_key
        md_path = f"output/markdown/{path_key.strip('/')}/index.md"
        rows.append(f"| {title} | {md_path} |")
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not METADATA_PATH.exists():
        print("Run to_markdown.py first — metadata.json not found")
        sys.exit(1)

    with METADATA_PATH.open(encoding="utf-8") as fh:
        metadata: dict = json.load(fh)

    n_pages = len(metadata)

    sitemap_mermaid = build_sitemap_diagram(metadata)
    nav_mermaid = build_nav_diagram(metadata)
    pages_table = build_pages_table(metadata)

    readme_content = f"""\
# Learn Claude Code — Scraped Reference

> Offline mirror of [markdown.engineering/learn-claude-code](https://www.markdown.engineering/learn-claude-code/)
> Generated by scrape-Claude.

## Site Map

```mermaid
{sitemap_mermaid}
```

## Navigation Flow

```mermaid
{nav_mermaid}
```

## Pages ({n_pages} total)

{pages_table}
"""

    README_PATH.write_text(readme_content, encoding="utf-8")
    print(f"README.md written with {n_pages} pages, 2 Mermaid diagrams")


if __name__ == "__main__":
    main()
