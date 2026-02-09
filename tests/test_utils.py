import sys
import types
from typing import Any, cast

import config

rich_module = types.ModuleType("rich")
rich_logging_module = types.ModuleType("rich.logging")

class DummyRichHandler:  # noqa: D401 - simple stub
    def __init__(self, *args, **kwargs):
        pass

cast(Any, rich_logging_module).RichHandler = DummyRichHandler
sys.modules.setdefault("rich", rich_module)
sys.modules.setdefault("rich.logging", rich_logging_module)

from src.utils import ResponseSink


class FakeResponse:
    def __init__(self, body: bytes, headers=None, encoding: str | None = "utf-8"):
        self.status_code = 200
        self.reason = "OK"
        self.url = "http://example.com"
        self.headers = dict(headers or {})
        self.encoding = encoding
        self._body = body
        self.closed = False

    def iter_content(self, chunk_size=1):
        for idx in range(0, len(self._body), chunk_size):
            yield self._body[idx : idx + chunk_size]

    def close(self):
        self.closed = True


def test_response_sink_truncates(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESPONSE_MAX_BYTES", 5)
    monkeypatch.setattr(config, "RESPONSE_DUMP_CHUNK_SIZE", 2)

    out_file = tmp_path / "out.txt"
    sink = ResponseSink(str(out_file))
    resp = FakeResponse(b"hello world", headers={"Content-Length": "11"})

    sink.write(resp)

    data = out_file.read_text(encoding="utf-8")
    assert "hello" in data
    assert "world" not in data
    assert "[truncated after 5 bytes]" in data
    assert resp.closed is True
