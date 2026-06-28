from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT_RAW = ROOT / "output" / "raw"
OUTPUT_MD = ROOT / "output" / "markdown"
OUTPUT_HTML = ROOT / "output" / "html"
ASSETS = ROOT / "assets"
METADATA_FILE = ROOT / "output" / "metadata.json"
ERRORS_LOG = ROOT / "output" / "errors.log"

def url_to_path(url: str, base_url: str = "https://www.markdown.engineering") -> Path:
    """Convert a URL to a relative filesystem path."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    return Path(path) if path else Path("index")

def ensure_dirs():
    for d in [OUTPUT_RAW, OUTPUT_MD, OUTPUT_HTML, ASSETS]:
        d.mkdir(parents=True, exist_ok=True)
    METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
