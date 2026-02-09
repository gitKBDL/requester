import logging
import requests
from typing import Dict, Optional, Protocol, Mapping, Any
import config
from .models import ParsedRequest
from .proxies import ProxyPool, ProxyExhausted

class SessionLike(Protocol):
    def request(
        self,
        method: str | bytes,
        url: str | bytes,
        *args: Any,
        **kwargs: Any,
    ) -> requests.Response:
        ...

def send_request(
    parsed: ParsedRequest,
    session: SessionLike,
    proxies: Optional[Dict[str, str]] = None,
    verify_override: Optional[bool] = None,
    stream: bool = False,
) -> requests.Response:
    headers: Dict[str, str] = {}
    if parsed.headers_list:
        for name, value in parsed.headers_list:
            key_lower = name.lower()
            if key_lower in config.SKIP_HEADERS:
                continue
            if key_lower in headers:
                sep = "; " if key_lower == "cookie" else ", "
                headers[key_lower] = f"{headers[key_lower]}{sep}{value}"
            else:
                headers[key_lower] = value
        # Restore original casing where possible by looking at the first occurrence.
        restored: Dict[str, str] = {}
        for name, value in parsed.headers_list:
            key_lower = name.lower()
            if key_lower in headers and key_lower not in restored:
                restored[name] = headers[key_lower]
        headers = restored
    else:
        headers = {
            key: value
            for key, value in parsed.headers.items()
            if key.lower() not in config.SKIP_HEADERS
        }

    if parsed.path.lower().startswith(("http://", "https://")):
        url = parsed.path
    else:
        host = config.DEFAULT_HOST or parsed.headers.get("Host")
        if not host:
            raise ValueError("Host header is missing and DEFAULT_HOST is not set")
        url = f"{config.SCHEME}://{host}{parsed.path}"
    response = session.request(
        parsed.method,
        url,
        headers=headers,
        data=parsed.body,
        verify=config.VERIFY_TLS if verify_override is None else verify_override,
        timeout=config.TIMEOUT_SECONDS,
        proxies=proxies,
        stream=stream,
    )
    return response

def _response_size_label(response: requests.Response) -> str:
    content_length = response.headers.get("Content-Length")
    if content_length:
        return content_length
    if getattr(response, "_content", None) is not None:
        try:
            return str(len(response.content))
        except Exception:
            return "unknown"
    return "unknown"

def send_with_proxy_failover(
    parsed: ParsedRequest,
    session: SessionLike,
    pool: ProxyPool,
    stream: bool = False,
) -> requests.Response:
    while True:
        proxy_url = pool.next_proxy()
        if proxy_url is None and pool.exhausted():
            raise ProxyExhausted("Proxy list exhausted")
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        tried_insecure = False
        while True:
            try:
                response = send_request(
                    parsed,
                    session,
                    proxies=proxies,
                    verify_override=False if tried_insecure else None,
                    stream=stream,
                )
                if proxy_url and response.status_code in config.PROXY_DROP_STATUSES:
                    logging.warning(
                        "Proxy %s returned HTTP %s; dropping and trying next.",
                        proxy_url,
                        response.status_code,
                    )
                    pool.mark_bad(proxy_url)
                    if pool.exhausted():
                        raise ProxyExhausted("Proxy list exhausted")
                    break  # go to next proxy
                mode = f"proxy={proxy_url}" if proxy_url else (
                    "direct-insecure" if tried_insecure else "direct"
                )
                if tried_insecure and not proxy_url:
                    logging.warning("SSL verification disabled for this request (direct).")
                logging.info(
                    "%s %s -> %s (%s bytes) via %s",
                    parsed.method,
                    parsed.path,
                    response.status_code,
                    _response_size_label(response),
                    mode,
                )
                return response
            except requests.exceptions.SSLError as exc:
                if not tried_insecure:
                    logging.warning(
                        "SSL error via %s; retrying without verification.",
                        proxy_url or "direct",
                    )
                    tried_insecure = True
                    continue
                if proxy_url:
                    logging.error(
                        "Proxy failed (%s) after SSL retry, removing. Error: %s",
                        proxy_url,
                        exc,
                    )
                    pool.mark_bad(proxy_url)
                    if pool.exhausted():
                        raise ProxyExhausted("Proxy list exhausted")
                    break
                raise
            except requests.RequestException as exc:
                if proxy_url:
                    logging.error("Proxy failed (%s), removing. Error: %s", proxy_url, exc)
                    pool.mark_bad(proxy_url)
                    if pool.exhausted():
                        raise ProxyExhausted("Proxy list exhausted")
                    break
                raise
