"""Modeled warehouse over the lake: ledgers, masters and facts.

Organized by data kind. Today: :mod:`pulsar.model.movements` (the OINM ledger).
Future masters/facts live as sibling packages, each one its own table in the
same lake (table naming convention: ``ledger_*`` / ``master_*`` / ``fact_*``).
"""

from __future__ import annotations
