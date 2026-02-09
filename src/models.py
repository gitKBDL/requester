from dataclasses import dataclass, field
from typing import Any, List, Tuple, MutableMapping, Dict
import re
from requests.structures import CaseInsensitiveDict

@dataclass
class ParsedRequest:
    method: str
    path: str
    headers: MutableMapping[str, str]
    headers_list: List[Tuple[str, str]]
    body: str
    meta: Dict[str, Any] = field(default_factory=dict)

def _split_head_and_body(raw_text: str) -> tuple[str, str]:
    parts = re.split(r"\r?\n\r?\n", raw_text, maxsplit=1)
    head = parts[0].replace("\r", "")
    body = parts[1] if len(parts) > 1 else ""
    return head, body

def parse_raw_request(raw_text: str) -> ParsedRequest:
    """Convert raw HTTP text into a ParsedRequest object."""
    if not raw_text.strip():
        raise ValueError("request text is empty")

    # Extract meta options (# @key: value) from the top
    lines = raw_text.splitlines()
    meta = {}
    start_idx = 0
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("# @"):
            try:
                # format: # @key: value
                part = stripped[3:] # remove "# @"
                key, val = part.split(":", 1)
                meta[key.strip()] = val.strip()
            except ValueError:
                pass # ignore malformed meta lines
        elif not stripped or stripped.startswith("#"):
            # skip blank lines or normal comments
            continue
        else:
            # First non-comment, non-empty line is the start of the request
            start_idx = i
            break
            
    # Reassemble the actual request text
    request_text = "\n".join(lines[start_idx:])
    
    head, body = _split_head_and_body(request_text)
    head_lines = [line for line in head.splitlines() if line.strip()]
    if not head_lines:
        raise ValueError("missing request line")

    def looks_like_request_line(line: str) -> bool:
        parts = line.strip().split()
        if len(parts) != 3:
            return False
        return parts[2].upper().startswith("HTTP/")

    method = None
    path = None
    headers_list: List[Tuple[str, str]] = []
    headers: MutableMapping[str, str] = CaseInsensitiveDict()
    pseudo: Dict[str, str] = {}

    start_idx = 0
    if looks_like_request_line(head_lines[0]):
        try:
            method, path, _ = head_lines[0].strip().split()
        except ValueError as exc:  # not enough values to unpack
            raise ValueError(f"cannot parse request line: {head_lines[0]}") from exc
        start_idx = 1
    elif ":" not in head_lines[0]:
        raise ValueError(f"cannot parse request line: {head_lines[0]}")

    for line in head_lines[start_idx:]:
        if ":" not in line:
            raise ValueError(f"invalid header format: {line}")
        if line.startswith(":"):
            # Pseudo-headers (HTTP/2 style), e.g. :method: POST
            rest = line[1:]
            if ":" not in rest:
                raise ValueError(f"invalid pseudo-header format: {line}")
            name, value = rest.split(":", 1)
            pseudo[name.strip().lower()] = value.strip()
            continue
        name, value = line.split(":", 1)
        name = name.strip()
        value = value.strip()
        headers_list.append((name, value))
        headers[name] = value

    if method is None or path is None:
        method = method or pseudo.get("method")
        path = path or pseudo.get("path")
        if not method or not path:
            raise ValueError("missing request line or pseudo-headers (:method/:path)")

    authority = pseudo.get("authority")
    if authority and "Host" not in headers:
        headers["Host"] = authority
        headers_list.append(("Host", authority))

    scheme = pseudo.get("scheme")
    if scheme and authority and not str(path).lower().startswith(("http://", "https://")):
        path = f"{scheme}://{authority}{path}"

    return ParsedRequest(
        method=method,
        path=path,
        headers=headers,
        headers_list=headers_list,
        body=body,
        meta=meta,
    )
