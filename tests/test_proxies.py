import pytest
from src.proxies import normalize_proxy_line, ProxyPool

@pytest.mark.parametrize("input_line,expected", [
    ("1.2.3.4:8080", "http://1.2.3.4:8080"),
    ("user:pass@1.2.3.4:8080", "http://user:pass@1.2.3.4:8080"),
    ("http://1.2.3.4:8080", "http://1.2.3.4:8080"),
    ("socks5://1.2.3.4:9050", "socks5://1.2.3.4:9050"),
    ("  1.2.3.4:80 ", "http://1.2.3.4:80"),
    ("# comment", None),
    ("", None),
    ("   ", None),
])
def test_normalize_proxy_line(input_line, expected):
    assert normalize_proxy_line(input_line) == expected

def test_proxy_pool_pinning_and_failover():
    proxies = ["p1", "p2", "p3"]
    pool = ProxyPool(list(proxies)) # copy list
    
    # Should pin the first proxy
    assert pool.next_proxy() == "p1"
    assert pool.next_proxy() == "p1"
    
    # Mark p1 bad, should move to p2
    pool.mark_bad("p1")
    assert pool.next_proxy() == "p2"
    assert pool.next_proxy() == "p2" # Pins p2

    # Mark p2 bad, move to p3
    pool.mark_bad("p2")
    assert pool.next_proxy() == "p3"

def test_proxy_pool_mark_bad():
    proxies = ["p1", "p2", "p3"]
    pool = ProxyPool(list(proxies))
    
    # Pin p1
    assert pool.next_proxy() == "p1"
    assert pool.next_proxy() == "p1" # Still p1 because it works (simulated)
    
    # Mark p1 bad
    pool.mark_bad("p1")
    
    # Should verify it's gone
    assert pool.next_proxy() == "p2" # moves to p2
    pool.mark_bad("p2")
    assert pool.next_proxy() == "p3"

def test_proxy_pool_exhausted():
    pool = ProxyPool(["p1"])
    pool.mark_bad("p1")
    assert pool.exhausted()
    assert pool.next_proxy() is None

def test_proxy_pool_direct_fallback():
    # If started with empty list, allows direct fallback
    pool = ProxyPool([], ignore_proxies=False)
    assert pool.allow_direct_fallback()
    
    # If started with list but all died, normally no fallback unless configured?
    # The code says: allow_direct_fallback() is True ONLY IF ignore_proxies OR initial_count == 0.
    pool2 = ProxyPool(["p1"], ignore_proxies=False)
    pool2.mark_bad("p1")
    assert not pool2.allow_direct_fallback()
    assert pool2.exhausted()
