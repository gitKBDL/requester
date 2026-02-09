import logging
import threading
import codecs
from typing import Iterable, Mapping, Protocol, Optional
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional
import requests
from rich.logging import RichHandler
import config

def setup_logging():
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    handlers = []
    
    # Console Handler (Rich)
    # rich.traceback.install() can be added in app.py if desired
    console_handler = RichHandler(
        rich_tracebacks=True,
        markup=True,
        show_path=False
    )
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    handlers.append(console_handler)
    
    # File Handler (Rotating)
    file_handler = RotatingFileHandler(
        log_dir / "app.log", 
        maxBytes=5*1024*1024, # 5 MB
        backupCount=3,
        encoding="utf-8"
    )
    file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(file_formatter)
    handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=handlers
    )

class ResponseLike(Protocol):
    @property
    def status_code(self) -> int:
        ...

    @property
    def reason(self) -> str:
        ...

    @property
    def url(self) -> str:
        ...

    @property
    def headers(self) -> Mapping[str, str]:
        ...

    @property
    def encoding(self) -> Optional[str]:
        ...

    def iter_content(self, chunk_size: int) -> Iterable[bytes]:
        ...

    def close(self) -> None:
        ...


def format_response_block(response: ResponseLike) -> str:
    status_line = f"{response.status_code} {response.reason} {response.url}"
    headers = "\n".join(f"{k}: {v}" for k, v in response.headers.items())
    return "\n".join(
        [
            "=" * 70,
            status_line,
            headers,
            "",
        ]
    )

def _iter_response_text(
    response: ResponseLike,
    max_bytes: int,
    chunk_size: int,
) -> tuple[bool, list[str]]:
    encoding = response.encoding or "utf-8"
    decoder = codecs.getincrementaldecoder(encoding)(errors="replace")
    limit_enabled = max_bytes > 0
    remaining = max_bytes
    chunks: list[str] = []
    truncated = False
    for chunk in response.iter_content(chunk_size=chunk_size):
        if not chunk:
            continue
        if limit_enabled and len(chunk) > remaining:
            chunk = chunk[:remaining]
            truncated = True
        if limit_enabled:
            remaining -= len(chunk)
        chunks.append(decoder.decode(chunk))
        if limit_enabled and remaining <= 0:
            break
    tail = decoder.decode(b"", final=True)
    if tail:
        chunks.append(tail)
    if not truncated and limit_enabled:
        try:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                truncated = True
        except (ValueError, TypeError):
            pass
    return truncated, chunks

class ResponseSink:
    def __init__(self, target: Optional[str]) -> None:
        """
        target:
            None       -> disabled
            True/""    -> console dump
            "file"     -> append to responses/<file> (or absolute path)
        """
        self._lock = threading.Lock()
        if target is None:
            self.mode = "off"
            self.path = None
        elif target is True:
            self.mode = "console"
            self.path = None
        else:
            dest = Path(target)
            if not dest.is_absolute():
                dest = Path(config.RESPONSES_DIR) / dest
            dest.parent.mkdir(parents=True, exist_ok=True)
            self.mode = "file"
            self.path = dest

    def enabled(self) -> bool:
        return self.mode != "off"

    def write(self, response: ResponseLike) -> None:
        with self._lock:
            block = format_response_block(response)
            truncated, body_chunks = _iter_response_text(
                response,
                config.RESPONSE_MAX_BYTES,
                config.RESPONSE_DUMP_CHUNK_SIZE,
            )
            trailer = ""
            if truncated:
                trailer = f"\n[truncated after {config.RESPONSE_MAX_BYTES} bytes]"
            if self.mode == "console":
                print(block, end="")
                for chunk in body_chunks:
                    print(chunk, end="")
                if trailer:
                    print(trailer, end="")
                print("")
                print("=" * 70)
                print("")
            elif self.mode == "file" and self.path:
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(block)
                    for chunk in body_chunks:
                        fh.write(chunk)
                    if trailer:
                        fh.write(trailer)
                    fh.write("\n")
                    fh.write("=" * 70)
                    fh.write("\n\n")
        response.close()
