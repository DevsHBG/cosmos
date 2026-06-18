"""Smoke test: the package imports and exposes its version."""

import pulsar


def test_version() -> None:
    assert pulsar.__version__ == "0.1.0"
