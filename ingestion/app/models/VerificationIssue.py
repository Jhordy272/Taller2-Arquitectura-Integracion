"""Domain entity: one difference found while verifying an extraction."""
from dataclasses import dataclass


@dataclass(frozen=True)
class VerificationIssue:
    source: str
    field: str
    expected: str
    actual: str
