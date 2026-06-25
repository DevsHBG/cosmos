"""Settings for pulsar.

Connection credentials come exclusively from the environment (no hardcoded
secrets — an initial architecture decision, to be formalised in an ADR). Schema
names are not secret and have sensible defaults
that match the three SAP Business One company databases.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Company(StrEnum):
    """The three SAP Business One company databases pulsar reads from."""

    COMERCIAL = "COMERCIAL"  # CEDIS / supply source
    HR = "HR"  # stores, HR brand
    CAP = "CAP"  # stores, Caprichos and Elilu brands


_DEFAULT_SCHEMAS: dict[Company, str] = {
    Company.COMERCIAL: "HBG_COMERCIAL",
    Company.HR: "HBG_THR",
    Company.CAP: "HBG_CAPRICHOS_2",
}


class HanaSettings(BaseSettings):
    """SAP HANA connection settings, loaded from environment variables.

    Reads from `HANA_*` env vars (and an optional local `.env`). Credentials
    (`HANA_USER`, `HANA_PASSWORD`, `HANA_HOST`) are required and have no default.
    """

    model_config = SettingsConfigDict(env_prefix="HANA_", env_file=".env", extra="ignore")

    host: str
    port: int = 30015
    user: str
    password: str

    schema_comercial: str = Field(default=_DEFAULT_SCHEMAS[Company.COMERCIAL])
    schema_hr: str = Field(default=_DEFAULT_SCHEMAS[Company.HR])
    schema_cap: str = Field(default=_DEFAULT_SCHEMAS[Company.CAP])

    def schema_for(self, company: Company) -> str:
        """Return the HANA schema (database) name for a company.

        Args:
            company: The company whose schema is requested.

        Returns:
            The HANA schema name (e.g. ``"HBG_THR"``).
        """
        return {
            Company.COMERCIAL: self.schema_comercial,
            Company.HR: self.schema_hr,
            Company.CAP: self.schema_cap,
        }[company]


@lru_cache
def get_hana_settings() -> HanaSettings:
    """Return cached HANA settings loaded from the environment.

    Returns:
        The process-wide :class:`HanaSettings` instance.
    """
    return HanaSettings()  # type: ignore[call-arg]  # required fields come from env
