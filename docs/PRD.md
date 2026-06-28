# PRD — Claude Code Learn Scraper

## Problem
`markdown.engineering/learn-claude-code/` has no offline access, no Markdown export, no portable HTML.

## Goal
Produce offline-ready, organized, interactive copy of the full course.

## Users
- Developer (owner): wants Markdown for note-taking, reference, and AI ingestion.
- Future readers: want navigable HTML offline.

## Requirements

### Must Have
- [ ] Full crawl of all pages under `/learn-claude-code/`
- [ ] Handle JS keypress gate on landing page
- [ ] Markdown file per page at mirrored URL path
- [ ] Root `README.md` with two Mermaid diagrams (sitemap + nav flow)
- [ ] Enhanced HTML per page: original CSS + sidebar nav + prev/next + search
- [ ] Original site CSS downloaded and referenced locally
- [ ] All assets (images, fonts) downloaded locally

### Must Not
- No global pip installs — venv only
- No credentials, API keys, or auth headers stored in code
- No modifying scraped content (preserve original text exactly)

### Nice to Have
- Progress bar during crawl
- Resume-on-interrupt (skip already-scraped pages)
- Single CLI entry point: `python scripts/scraper.py --all`

## Success Metric
All pages accessible offline via `output/html/index.html` with working sidebar nav and prev/next.
