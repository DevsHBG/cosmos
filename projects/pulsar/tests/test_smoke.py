"""Smoke test: el paquete importa y expone su versión."""

import pulsar


def test_version() -> None:
    assert pulsar.__version__ == "0.1.0"
