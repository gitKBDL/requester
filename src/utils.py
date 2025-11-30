import logging
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

def format_response_block(response: requests.Response) -> str:
    status_line = f"{response.status_code} {response.reason} {response.url}"
    headers = "\n".join(f"{k}: {v}" for k, v in response.headers.items())
    body = response.text
    return "\n".join(
        [
            "=" * 70,
            status_line,
            headers,
            "",
            body,
            "=" * 70,
            "",
        ]
    )

class ResponseSink:
    def __init__(self, target: Optional[str]) -> None:
        """
        target:
            None       -> disabled
            True/""    -> console dump
            "file"     -> append to responses/<file> (or absolute path)
        """
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

    def write(self, response: requests.Response) -> None:
        block = format_response_block(response)
        if self.mode == "console":
            print(block)
        elif self.mode == "file" and self.path:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(block)
