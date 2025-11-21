"""Basic settings for sending raw HTTP requests from text files.

These defaults can be adjusted to fit your environment.
"""
from pathlib import Path

# Folder that holds *.txt files with raw HTTP requests.
REQUESTS_DIR = Path(__file__).parent / "requests"

# File with proxy list (one per line). Lines may be in nearly any common format.
PROXIES_FILE = Path(__file__).parent / "proxies.txt"

# Folder with placeholder value lists (one file per placeholder).
PLACEHOLDERS_DIR = Path(__file__).parent / "placeholders"

# Folder where response dumps can be stored when --response <file> is used.
RESPONSES_DIR = Path(__file__).parent / "responses"

# URL used by --check to validate proxies.
PROXY_CHECK_URL = "https://httpbin.org/get"

# Max parallel workers when checking proxies.
PROXY_CHECK_WORKERS = 32

# Placeholder rotation strategy: "sequential" (round-robin) or "random".
PLACEHOLDER_ROTATION = "sequential"

# Delay between sending batches of requests (in seconds).
INTERVAL_SECONDS = 30

# Scheme used to build the final URL. Change to "http" if needed.
SCHEME = "https"

# If provided, overrides the Host header from files (e.g. "www.example.com").
DEFAULT_HOST = None

# Network controls.
VERIFY_TLS = True
TIMEOUT_SECONDS = 20

# Headers that will be stripped before sending (requests sets these automatically).
SKIP_HEADERS = {"content-length"}
