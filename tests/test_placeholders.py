import pytest
from pathlib import Path
from src.placeholders import PlaceholderResolver

@pytest.fixture
def placeholder_dir(tmp_path):
    d = tmp_path / "placeholders"
    d.mkdir()
    (d / "name.txt").write_text("alice\nbob\ncharlie", encoding="utf-8")
    (d / "id").write_text("101\n102", encoding="utf-8")
    return d

def test_resolver_sequential(placeholder_dir):
    resolver = PlaceholderResolver(placeholder_dir, rotation="sequential")
    
    # First pass
    assert resolver.replace("Hello {name}") == "Hello alice"
    assert resolver.replace("ID: {id}") == "ID: 101"
    
    # Second pass
    assert resolver.replace("Hello {name}") == "Hello bob"
    assert resolver.replace("ID: {id}") == "ID: 102"
    
    # Third pass (wrap around for id)
    assert resolver.replace("Hello {name}") == "Hello charlie"
    assert resolver.replace("ID: {id}") == "ID: 101"
    
    # Wrap around for name
    assert resolver.replace("Hello {name}") == "Hello alice"

def test_resolver_random(placeholder_dir):
    resolver = PlaceholderResolver(placeholder_dir, rotation="random")
    # Just check that it returns one of the valid values
    res = resolver.replace("Hello {name}")
    assert res in ["Hello alice", "Hello bob", "Hello charlie"]

def test_missing_placeholder_file(tmp_path):
    resolver = PlaceholderResolver(tmp_path / "empty")
    with pytest.raises(ValueError, match="Placeholder 'missing' not found"):
        resolver.replace("Values {missing}")

def test_no_placeholders_in_text(placeholder_dir):
    resolver = PlaceholderResolver(placeholder_dir)
    text = "No variables here"
    assert resolver.replace(text) == text
