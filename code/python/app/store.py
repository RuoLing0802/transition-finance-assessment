from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import RUNTIME_ROOT


SAFE_ARTIFACT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,160}$")


def validate_artifact_name(name: str) -> str:
    """Keep JSON artifacts inside their intended batch directory."""
    if not isinstance(name, str) or Path(name).name != name or not SAFE_ARTIFACT_NAME.fullmatch(name):
        raise ValueError("非法文件名")
    return name


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_default(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


class BatchStore:
    """Filesystem store for local M1 runs; originals are never placed in Git."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or RUNTIME_ROOT).resolve()
        self.batches_root = self.root / "batches"
        self.reports_root = self.root / "reports"
        self.batches_root.mkdir(parents=True, exist_ok=True)
        self.reports_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def safe_filename(filename: str) -> str:
        base = Path(filename or "upload.xlsx").name
        base = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", base, flags=re.UNICODE).strip("._")
        return base or "upload.xlsx"

    def create_batch(self, filename: str, content: bytes) -> dict[str, Any]:
        batch_id = f"m1-{uuid.uuid4().hex[:12]}"
        batch_dir = self.batches_root / batch_id
        batch_dir.mkdir(parents=True, exist_ok=False)
        safe_name = self.safe_filename(filename)
        source_path = batch_dir / safe_name
        source_path.write_bytes(content)
        os.chmod(source_path, 0o444)
        metadata = {
            "batch_id": batch_id,
            "source_filename": safe_name,
            "source_path": str(source_path),
            "file_size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "is_simulated_data": True,
            "received_at": utc_now(),
            "status": "received",
        }
        self.save_json(batch_id, "metadata.json", metadata)
        return metadata

    def batch_dir(self, batch_id: str) -> Path:
        path = (self.batches_root / batch_id).resolve()
        if path.parent != self.batches_root.resolve() or not path.is_dir():
            raise FileNotFoundError(f"批次不存在: {batch_id}")
        return path

    def source_path(self, batch_id: str) -> Path:
        metadata = self.load_json(batch_id, "metadata.json")
        path = Path(metadata["source_path"]).resolve()
        if path.parent != self.batch_dir(batch_id):
            raise ValueError("批次原件路径不在批次目录内")
        return path

    def save_json(self, batch_id: str, name: str, payload: dict[str, Any]) -> Path:
        path = self.batch_dir(batch_id) / validate_artifact_name(name)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")
        return path

    def load_json(self, batch_id: str, name: str) -> dict[str, Any]:
        path = self.batch_dir(batch_id) / validate_artifact_name(name)
        return json.loads(path.read_text(encoding="utf-8"))

    def save_report(self, batch_id: str, report_id: str, markdown: str, payload: dict[str, Any]) -> Path:
        validate_artifact_name(report_id)
        report_dir = self.reports_root / batch_id
        report_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = report_dir / f"{report_id}.md"
        markdown_path.write_text(markdown, encoding="utf-8")
        self.save_json(batch_id, f"report-{report_id}.json", payload)
        return markdown_path
