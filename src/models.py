from dataclasses import dataclass
from typing import Dict
import re

@dataclass
class ParsedRequest:
    method: str
    path: str
    headers: Dict[str, str]
    body: str

def _split_head_and_body(raw_text: str) -> tuple[str, str]:
    parts = re.split(r"\r?\n\r?\n", raw_text, maxsplit=1)
    head = parts[0].replace("\r", "")
    body = parts[1] if len(parts) > 1 else ""
    return head, body

def parse_raw_request(raw_text: str) -> ParsedRequest:
    """Convert raw HTTP text into a ParsedRequest object."""
    if not raw_text.strip():
        raise ValueError("request text is empty")

    head, body = _split_head_and_body(raw_text)
    head_lines = head.splitlines()
    if not head_lines:
        raise ValueError("missing request line")

    try:
        method, path, _ = head_lines[0].strip().split()
    except ValueError as exc:  # not enough values to unpack
        raise ValueError(f"cannot parse request line: {head_lines[0]}") from exc

    headers: Dict[str, str] = {}
    for line in head_lines[1:]:
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"invalid header format: {line}")
        name, value = line.split(":", 1)
        headers[name.strip()] = value.strip()

    return ParsedRequest(method=method, path=path, headers=headers, body=body)
