import pytest
from src.models import parse_raw_request, ParsedRequest

def test_parse_simple_get():
    raw = "GET / HTTP/1.1\nHost: example.com\n\n"
    req = parse_raw_request(raw)
    assert req.method == "GET"
    assert req.path == "/"
    assert req.headers["Host"] == "example.com"
    assert req.body == ""

def test_parse_post_with_body():
    raw = """POST /api/v1/login HTTP/1.1
Host: api.example.com
Content-Type: application/json

{"user": "admin"}"""
    req = parse_raw_request(raw)
    assert req.method == "POST"
    assert req.path == "/api/v1/login"
    assert req.headers["Host"] == "api.example.com"
    assert req.headers["Content-Type"] == "application/json"
    assert req.body == '{"user": "admin"}'

def test_parse_full_url():
    raw = "GET https://example.com/foo HTTP/1.1\nHost: example.com\n\n"
    req = parse_raw_request(raw)
    assert req.path == "https://example.com/foo"

def test_parse_empty_raises_error():
    with pytest.raises(ValueError, match="request text is empty"):
        parse_raw_request("   ")

def test_parse_malformed_line():
    with pytest.raises(ValueError, match="cannot parse request line"):
        parse_raw_request("NOT_HTTP_REQUEST\nHost: foo")

