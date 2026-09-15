"""Public response contract for `GET /readiness` -- see
docs/product/production-reliability-deployment-v1.md (#26B) §15/§17/§19,
implemented by Increment #26C.

Deliberately minimal and public-safe (#26B §19): `expected_schema_revision`/
`actual_schema_revision` are short, non-secret Alembic revision hex
identifiers, and `version` is this application's own build/git
identifier -- none of these are connection strings, hostnames, or
credentials. Never a stack trace, never any other environment value.
"""

from typing import Literal

from pydantic import BaseModel

ReadinessReason = Literal["schema_mismatch", "database_unreachable", "configuration_missing"]


class ReadinessResponse(BaseModel):
    ready: bool
    reason: ReadinessReason | None
    expected_schema_revision: str | None
    actual_schema_revision: str | None
    version: str
