"""Test minimal — garantit que le module se charge."""
import src


def test_import():
    assert src is not None
