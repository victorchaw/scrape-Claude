# ADR — Architecture Decision Records

## ADR-001: Python + Playwright over Node/Playwright
**Status:** Accepted  
**Reason:** Owner familiar with Python. Same headless browser capability. Venv isolation preferred over npx.

## ADR-002: Playwright over Requests/BeautifulSoup-only
**Status:** Accepted  
**Reason:** Site has JS "press any key" gate. Static HTTP requests return gated landing, not content.

## ADR-003: Mirror URL path as folder structure
**Status:** Accepted  
**Reason:** Preserves site hierarchy. HTML relative links work without rewriting. Easy to diff against live site.

## ADR-004: Two-phase scrape (raw HTML first, convert second)
**Status:** Accepted  
**Reason:** Decouples network failures from conversion failures. Resume-on-interrupt becomes trivial (skip existing raw files). Easier to re-run conversion without re-scraping.

## ADR-005: CSS hybrid (original + custom layer)
**Status:** Accepted  
**Reason:** Original CSS preserves content styling. Custom CSS layer adds sidebar/nav/search without forking the original. Custom CSS loaded after original, overrides only layout shell.

## ADR-006: Mermaid in README (not separate tool)
**Status:** Accepted  
**Reason:** README.md renders Mermaid natively in GitHub and most Markdown viewers. No external diagramming tool dependency.

## ADR-007: Four-script build pipeline (strict order)
**Status:** Accepted  
**Reason:** Each script is independently runnable and testable. Failure in step 3 doesn't invalidate step 1-2 outputs. Easier for AI agents to resume partial work.
