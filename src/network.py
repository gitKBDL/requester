import logging
import requests
from typing import Dict, Optional
import config
from .models import ParsedRequest
from .proxies import ProxyPool, ProxyExhausted

def send_request(
    parsed: ParsedRequest,
    session: requests.Session,
    proxies: Optional[Dict[str, str]] = None,
    verify_override: Optional[bool] = None,
) -> requests.Response:
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
    )
    return response

def send_with_proxy_failover(
    parsed: ParsedRequest, session: requests.Session, pool: ProxyPool
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
                )
                if proxy_url and not response.ok:
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
                    len(response.content),
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
