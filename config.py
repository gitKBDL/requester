"""Basic settings for sending raw HTTP requests from text files.

These defaults can be adjusted to fit your environment.
You can also override them using environment variables (e.g. for Docker).
"""
import os
from pathlib import Path

def get_env(key, default, cast=None):
    val = os.getenv(key, default)
    if cast and val is not None:
        try:
            return cast(val)
        except (ValueError, TypeError):
            return default
    return val

def get_bool(key, default):
    val = os.getenv(key)
    if val is None:
        return default
    return val.lower() in ("true", "1", "yes", "on")

# Folder that holds *.txt files with raw HTTP requests.
REQUESTS_DIR = Path(get_env("REQUESTS_DIR", Path(__file__).parent / "requests"))

# File with proxy list (one per line). Lines may be in nearly any common format.
PROXIES_FILE = Path(get_env("PROXIES_FILE", Path(__file__).parent / "proxies.txt"))

# Folder with placeholder value lists (one file per placeholder).
PLACEHOLDERS_DIR = Path(get_env("PLACEHOLDERS_DIR", Path(__file__).parent / "placeholders"))

# Folder where response dumps can be stored when --response <file> is used.
RESPONSES_DIR = Path(get_env("RESPONSES_DIR", Path(__file__).parent / "responses"))

# URL used by --check to validate proxies.
PROXY_CHECK_URL = get_env("PROXY_CHECK_URL", "https://httpbin.org/get")

# Max parallel workers when checking proxies.
PROXY_CHECK_WORKERS = get_env("PROXY_CHECK_WORKERS", 32, int)

# Placeholder rotation strategy: "sequential" (round-robin) or "random".
PLACEHOLDER_ROTATION = get_env("PLACEHOLDER_ROTATION", "sequential")

# Delay between sending batches of requests (in seconds).
INTERVAL_SECONDS = get_env("INTERVAL_SECONDS", 30, int)

# Scheme used to build the final URL. Change to "http" if needed.
SCHEME = get_env("SCHEME", "https")

# If provided, overrides the Host header from files (e.g. "www.example.com").
DEFAULT_HOST = get_env("DEFAULT_HOST", None)

# Network controls.
VERIFY_TLS = get_bool("VERIFY_TLS", True)
TIMEOUT_SECONDS = get_env("TIMEOUT_SECONDS", 20, int)

# Headers that will be stripped before sending (requests sets these automatically).
SKIP_HEADERS = {"content-length"}
