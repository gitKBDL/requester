import logging
import concurrent.futures
from pathlib import Path
from typing import List, Optional
import requests
import config

class ProxyExhausted(Exception):
    """Raised when all proxies are dead and direct fallback is not allowed."""

class ProxyPool:
    def __init__(
        self,
        proxies: List[str],
        ignore_proxies: bool = False,
        file_path: Optional[Path] = None,
    ) -> None:
        self._proxies = proxies
        self._index = 0
        self.ignore_proxies = ignore_proxies
        self._warned_empty = not proxies
        self._initial_count = len(proxies)
        self._exhausted = False
        self._current: Optional[str] = None
        self._file_path = file_path

    def has_proxies(self) -> bool:
        return (not self.ignore_proxies) and bool(self._proxies)

    def allow_direct_fallback(self) -> bool:
        return self.ignore_proxies or self._initial_count == 0

    def exhausted(self) -> bool:
        return self._exhausted

    def next_proxy(self) -> Optional[str]:
        if self._current and self._current in self._proxies:
            return self._current
        if not self.has_proxies():
            return None
        proxy = self._proxies[self._index % len(self._proxies)]
        self._index = (self._index + 1) % len(self._proxies)
        self._current = proxy
        return proxy

    def _persist(self) -> None:
        if not self._file_path:
            return
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            data = "\n".join(self._proxies)
            if self._proxies:
                data += "\n"
            self._file_path.write_text(data, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logging.error("Failed to update proxy file %s: %s", self._file_path, exc)

    def mark_bad(self, proxy: Optional[str]) -> None:
        if proxy is None:
            return
        try:
            idx = self._proxies.index(proxy)
        except ValueError:
            return
        self._proxies.pop(idx)
        if self._index > idx:
            self._index -= 1
        if proxy == self._current:
            self._current = None
        if not self._proxies:
            if not self.allow_direct_fallback():
                self._exhausted = True
                logging.error("Proxy list exhausted; stopping (no direct fallback).")
            elif not self._warned_empty:
                logging.warning("Proxy list is empty, running direct.")
                self._warned_empty = True
        self._persist()

def normalize_proxy_line(line: str) -> Optional[str]:
    raw = line.strip()
    if not raw or raw.startswith("#"):
        return None

    token = raw.split()[0]

    if "://" in token:
        return token
    if "@" in token:
        return f"http://{token}"

    parts = token.split(":")
    if len(parts) >= 4:
        host, port, user, password = parts[0], parts[1], parts[2], parts[3]
        return f"http://{user}:{password}@{host}:{port}"
    if len(parts) >= 2:
        host, port = parts[0], parts[1]
        return f"http://{host}:{port}"

    return f"http://{token}"

def load_proxies(path: Path) -> List[str]:
    if not path.exists():
        logging.warning("Proxy file not found: %s", path)
        return []

    proxies: List[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        normalized = normalize_proxy_line(raw_line)
        if normalized:
            proxies.append(normalized)
    return proxies

def test_proxy(proxy_url: str) -> tuple[bool, str]:
    proxies = {"http": proxy_url, "https": proxy_url}
    attempts = [config.VERIFY_TLS]
    if config.VERIFY_TLS:
        attempts.append(False)

    last_error = "unknown error"
    for verify_flag in attempts:
        try:
            resp = requests.get(
                config.PROXY_CHECK_URL,
                proxies=proxies,
                timeout=config.TIMEOUT_SECONDS,
                verify=verify_flag,
            )
            if resp.ok:
                mode = "verify" if verify_flag else "no-verify"
                return True, f"HTTP {resp.status_code} ({mode})"
            return False, f"HTTP {resp.status_code}"
        except requests.exceptions.SSLError as exc:
            last_error = f"SSL error: {exc}"
            if verify_flag and config.VERIFY_TLS:
                continue  # retry without verification
        except requests.RequestException as exc:
            last_error = str(exc)
        break
    return False, last_error

def check_proxies(proxies: List[str], dest_file: Optional[Path] = None) -> None:
    if not proxies:
        logging.warning("No proxies to check.")
        return
    logging.info(
        "Checking %s proxies against %s (timeout=%ss)...",
        len(proxies),
        config.PROXY_CHECK_URL,
        config.TIMEOUT_SECONDS,
    )
    good: List[str] = []
    max_workers = min(len(proxies), config.PROXY_CHECK_WORKERS)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(test_proxy, proxy): proxy for proxy in proxies}
        for future in concurrent.futures.as_completed(future_map):
            proxy = future_map[future]
            try:
                ok, detail = future.result()
            except Exception as exc:  # noqa: BLE001
                logging.error("Proxy %s check raised: %s", proxy, exc)
                continue
            if ok:
                good.append(proxy)
                logging.info("OK   %s (%s)", proxy, detail)
            else:
                logging.error("BAD  %s (%s)", proxy, detail)
    logging.info("Proxy check finished: %s good / %s total.", len(good), len(proxies))
    if dest_file is not None:
        try:
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            data = "\n".join(good)
            if good:
                data += "\n"
            dest_file.write_text(data, encoding="utf-8")
            logging.info(
                "Updated proxy file %s with %s working proxies (removed %s).",
                dest_file,
                len(good),
                len(proxies) - len(good),
            )
        except Exception as exc:  # noqa: BLE001
            logging.error("Failed to write proxy check results to %s: %s", dest_file, exc)
    if good:
        logging.info("Working proxies:\n%s", "\n".join(good))