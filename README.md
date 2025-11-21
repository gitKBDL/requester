# Raw Request Sender

Python utility that replays raw HTTP requests from text files on a timer. Built for automation and flexibility: placeholder substitution, proxy pinning/removal, TLS retry, response dumping, and a parallel proxy checker. Everything is plain text so it’s easy to edit and version.

---

## What it does (high level)
1) Reads all `requests/*.txt` (excluding files that start with `example`).
2) Applies placeholder substitutions (`{name}`) from `placeholders/name(.txt)`.
3) Builds the URL (full URL is respected; otherwise `SCHEME + Host + path`).
4) Sends each request once per loop with a pinned proxy (or direct).
5) Drops failing proxies (network or HTTP status >= 400), writes the updated list back to `proxies.txt`, and moves to the next. If all provided proxies die, stops instead of silently going direct.
6) On SSL errors, retries once without verification; still drops bad proxies if retry fails.
7) Optionally dumps responses to console or file.
8) Repeats after `INTERVAL_SECONDS`.

There’s also a proxy checker (`--check`) that tests all proxies in parallel, keeps only the working ones, and rewrites the proxy file.

---

## Installation
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

---

## Request files (`requests/*.txt`)
- Format: request line + headers + blank line + body. Example:
  ```
  POST /path HTTP/1.1
  Host: example.com
  Content-Type: application/x-www-form-urlencoded

  foo=bar&msg={greeting}
  ```
- If the request line contains a full URL, it is used as-is; otherwise the URL is built from `SCHEME` + Host header + path.
- `Content-Length` is stripped automatically.
- Files whose name starts with `example` are ignored until you rename them.

---

## Placeholders (`{name}`)
- Values live in `placeholders/name` or `placeholders/name.txt`, one per line. Blank lines and `#` comments are skipped.
- All occurrences of `{name}` inside one request share the same chosen value.
- Rotation mode is set in `config.py`: sequential round-robin or random.
- Example:
  - `placeholders/greeting.txt`:
    ```
    hello
    welcome
    hi there
    ```
  - In request body: `msg={greeting}` → gets replaced per send.

---

## Proxies (`proxies.txt`)
- Accepts `ip:port`, `user:pass@ip:port`, `http://...`, `socks5://...`, space- or colon-delimited. `#` and blank lines are ignored.
- Startup:
  - If proxies list is empty and not `--direct`, a 10s warning delay then direct mode.
  - `--direct` skips proxies entirely (no delay).
- Runtime behavior:
  - First working proxy is pinned and reused until it fails.
  - HTTP status >= 400 or any network error → proxy is removed from memory and from `proxies.txt`, then the next proxy is tried.
  - SSL errors retry once with `verify=False`; if still bad, the proxy is removed.
  - If you started with proxies and they all die, the program stops (no silent fallback). If you started with zero or `--direct`, it stays direct.
- Proxy checker:
  - `python -m requester --check` tests all proxies in parallel (up to `PROXY_CHECK_WORKERS`) against `PROXY_CHECK_URL`, keeps only the working ones, and rewrites the file.

---

## Running modes
- Main loop: `python -m requester`
- Direct mode: `python -m requester --direct`
- Response dump:
  - `--response` → print each response (status, headers, body) to console.
  - `--response out.txt` → append responses to `responses/out.txt` (folder auto-created).
- Proxy file override: `--proxy-file /path/to/list.txt`
- Dry proxy check: `python -m requester --check`

---

## Configuration (`config.py`)
- Paths: `REQUESTS_DIR`, `PROXIES_FILE`, `PLACEHOLDERS_DIR`, `RESPONSES_DIR`
- Schedule: `INTERVAL_SECONDS` (default 30s)
- URL building: `SCHEME`, `DEFAULT_HOST`
- Network: `VERIFY_TLS`, `TIMEOUT_SECONDS`
- Placeholders: `PLACEHOLDER_ROTATION`
- Proxy check: `PROXY_CHECK_URL`, `PROXY_CHECK_WORKERS`
- Headers skipped: `SKIP_HEADERS` (e.g., `Content-Length` auto-set)

---

## Response dumping
- Format: status line + headers + body, wrapped with separators.
- Console when `--response` is used without filename; otherwise append to file under `responses/` (or absolute path).

---

## Troubleshooting
- “Proxy list exhausted” → all provided proxies failed; refresh `proxies.txt` or run `--check` to prune.
- `InsecureRequestWarning` → TLS verification was skipped after an SSL error. Replace the proxy if you need strict TLS.
- No requests sent → ensure your files aren’t named `example*.txt`, and Host header exists if you’re not using full URLs.
- Installer complains about “externally managed environment” → use the venv’s pip: `source .venv/bin/activate` then `python -m pip install -r requirements.txt`.

---

## Project structure
```
config.py           # Settings (paths, network, rotation, proxy check)
requester.py        # Main logic and CLI
requirements.txt    # Python deps (requests[socks], PySocks, colorama)
requests/           # Your raw HTTP requests (*.txt)
proxies.txt         # Proxy list (auto-updated when bad proxies are removed)
placeholders/       # Placeholder value lists
responses/          # Optional response dumps (created on demand)
```
