import requests

from src.models import ParsedRequest
from src.network import send_request


class DummySession:
    def __init__(self):
        self.last_headers: dict[str, str] = {}
        self.last_url: str | None = None
        self.last_method: str | None = None

    def request(self, method, url, headers=None, **kwargs):
        self.last_method = method
        self.last_url = url
        self.last_headers = dict(headers or {})
        resp = requests.Response()
        resp.status_code = 200
        return resp


def test_send_request_combines_duplicate_headers():
    parsed = ParsedRequest(
        method="GET",
        path="http://example.com",
        headers={"Host": "example.com"},
        headers_list=[
            ("Host", "example.com"),
            ("Cookie", "a=1"),
            ("Cookie", "b=2"),
            ("X-Test", "1"),
            ("X-Test", "2"),
            ("Content-Length", "10"),
        ],
        body="",
    )
    session = DummySession()
    send_request(parsed, session)

    assert session.last_headers["Host"] == "example.com"
    assert session.last_headers["Cookie"] == "a=1; b=2"
    assert session.last_headers["X-Test"] == "1, 2"
    assert "Content-Length" not in session.last_headers
