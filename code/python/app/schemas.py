from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Issue:
    issue_id: str
    batch_id: str
    company_code: str | None
    sheet_name: str | None
    row_number: int | None
    field: str | None
    rule: str
    severity: str
    message: str
    original_value: Any = None
    status: str = "待处理"
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "batch_id": self.batch_id,
            "company_code": self.company_code,
            "sheet_name": self.sheet_name,
            "row_number": self.row_number,
            "field": self.field,
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "original_value": self.original_value,
            "status": self.status,
            "evidence": self.evidence,
        }
