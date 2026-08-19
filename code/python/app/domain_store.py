from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

from .config import APPLICATION_DATA_ROOT, REQUIRED_HEADERS, SIMULATED_DATA_NOTICE
from .parsers.multimodal import safe_filename


SCHEMA_VERSION = 5
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,24}-[A-Za-z0-9_-]{2,80}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMPARABLE_RUN_STATUSES = {"completed", "archived"}
REFERENCE_ONLY_FIELDS = set(REQUIRED_HEADERS["转型规划结论"]) - {"企业代号"}


class DomainNotFoundError(LookupError):
    pass


class DomainConflictError(ValueError):
    pass


class DomainValidationError(ValueError):
    pass


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _loads(value: str | None, default: Any) -> Any:
    if value in (None, ""):
        return default
    return json.loads(value)


def validate_domain_id(value: str) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise DomainValidationError("非法领域对象标识")
    return value


def validate_relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise DomainValidationError("报告路径必须是非空的相对路径")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise DomainValidationError("报告路径不能越出应用数据目录")
    normalized = path.as_posix()
    if not normalized.startswith("reports/"):
        raise DomainValidationError("报告路径必须位于应用数据目录的reports子目录")
    return normalized


def validate_attachment_relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise DomainValidationError("附件路径必须是非空的相对路径")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise DomainValidationError("附件路径不能越出应用数据目录")
    normalized = path.as_posix()
    if not normalized.startswith("attachments/"):
        raise DomainValidationError("附件路径必须位于应用数据目录的attachments子目录")
    return normalized


class DomainStore:
    """SQLite metadata store for M2 domain objects; business facts stay run-scoped."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or APPLICATION_DATA_ROOT).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.reports_root = self.root / "reports"
        self.reports_root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "transition_finance.sqlite3"
        self.migrate()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        with self._connection() as connection:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version > SCHEMA_VERSION:
                raise DomainConflictError("数据库版本高于当前程序，不能降级打开")
            if version < 1:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS workspaces (
                        workspace_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        archived INTEGER NOT NULL DEFAULT 0,
                        last_active_run_id TEXT
                    );
                    CREATE TABLE IF NOT EXISTS source_batches (
                        source_batch_id TEXT PRIMARY KEY,
                        m1_batch_id TEXT NOT NULL UNIQUE,
                        source_filename TEXT NOT NULL,
                        sha256 TEXT NOT NULL UNIQUE,
                        source TEXT NOT NULL,
                        simulated_data INTEGER NOT NULL,
                        validation_status TEXT NOT NULL,
                        available_company_codes_json TEXT NOT NULL,
                        metadata_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS enterprise_profiles (
                        enterprise_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id),
                        enterprise_code TEXT NOT NULL,
                        basic_info_index_json TEXT NOT NULL,
                        source_batch_ids_json TEXT NOT NULL,
                        fact_version INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(workspace_id, enterprise_code)
                    );
                    CREATE TABLE IF NOT EXISTS assessment_runs (
                        assessment_run_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id),
                        enterprise_id TEXT NOT NULL REFERENCES enterprise_profiles(enterprise_id),
                        source_batch_id TEXT NOT NULL REFERENCES source_batches(source_batch_id),
                        run_name TEXT NOT NULL,
                        batch_snapshot_json TEXT NOT NULL,
                        rule_version TEXT NOT NULL,
                        model_config_json TEXT NOT NULL,
                        status TEXT NOT NULL,
                        quality_gate_status TEXT NOT NULL,
                        report_ids_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_runs_workspace ON assessment_runs(workspace_id, updated_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_runs_enterprise ON assessment_runs(enterprise_id, updated_at DESC);
                    CREATE TABLE IF NOT EXISTS conversation_messages (
                        message_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id),
                        assessment_run_id TEXT NOT NULL REFERENCES assessment_runs(assessment_run_id),
                        enterprise_id TEXT NOT NULL REFERENCES enterprise_profiles(enterprise_id),
                        role TEXT NOT NULL,
                        message_type TEXT NOT NULL,
                        content TEXT NOT NULL,
                        tool_name TEXT,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_messages_run ON conversation_messages(assessment_run_id, created_at);
                    CREATE TABLE IF NOT EXISTS comparison_views (
                        comparison_view_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id),
                        dimensions_json TEXT NOT NULL,
                        version_differences_json TEXT NOT NULL,
                        incomparability_reasons_json TEXT NOT NULL,
                        output_snapshot_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS comparison_view_runs (
                        comparison_view_id TEXT NOT NULL REFERENCES comparison_views(comparison_view_id),
                        assessment_run_id TEXT NOT NULL REFERENCES assessment_runs(assessment_run_id),
                        position INTEGER NOT NULL,
                        PRIMARY KEY(comparison_view_id, assessment_run_id)
                    );
                    CREATE TABLE IF NOT EXISTS report_artifacts (
                        report_artifact_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id),
                        assessment_run_id TEXT NOT NULL REFERENCES assessment_runs(assessment_run_id),
                        enterprise_id TEXT NOT NULL REFERENCES enterprise_profiles(enterprise_id),
                        report_type TEXT NOT NULL,
                        file_format TEXT NOT NULL,
                        relative_path TEXT NOT NULL,
                        version TEXT NOT NULL,
                        sha256 TEXT,
                        generation_config_json TEXT NOT NULL,
                        export_records_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_reports_run ON report_artifacts(assessment_run_id, created_at DESC);
                    PRAGMA user_version = 1;
                    """
                )
            if version < 2:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS multimodal_attachments (
                        attachment_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id),
                        assessment_run_id TEXT NOT NULL REFERENCES assessment_runs(assessment_run_id),
                        enterprise_id TEXT NOT NULL REFERENCES enterprise_profiles(enterprise_id),
                        source_batch_id TEXT NOT NULL REFERENCES source_batches(source_batch_id),
                        source_filename TEXT NOT NULL,
                        file_type TEXT NOT NULL,
                        mime_type TEXT,
                        file_size INTEGER NOT NULL,
                        sha256 TEXT NOT NULL,
                        relative_path TEXT NOT NULL,
                        parse_status TEXT NOT NULL,
                        merge_allowed INTEGER NOT NULL DEFAULT 0,
                        parse_result_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        UNIQUE(assessment_run_id, sha256)
                    );
                    CREATE INDEX IF NOT EXISTS idx_attachments_run ON multimodal_attachments(assessment_run_id, created_at DESC);
                    PRAGMA user_version = 2;
                    """
                )
            if version < 3:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS orchestration_events (
                        event_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id),
                        assessment_run_id TEXT NOT NULL REFERENCES assessment_runs(assessment_run_id),
                        enterprise_id TEXT NOT NULL REFERENCES enterprise_profiles(enterprise_id),
                        event_type TEXT NOT NULL,
                        provider_id TEXT,
                        model_id TEXT,
                        purpose TEXT NOT NULL,
                        tool_name TEXT,
                        input_evidence_refs_json TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        status TEXT NOT NULL,
                        error_code TEXT,
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_orchestration_events_run
                        ON orchestration_events(assessment_run_id, created_at, event_id);
                    PRAGMA user_version = 3;
                    """
                )
            if version < 4:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS model_configs (
                        model_config_id TEXT PRIMARY KEY,
                        model_name TEXT NOT NULL,
                        display_name TEXT NOT NULL,
                        provider_id TEXT NOT NULL,
                        base_url TEXT NOT NULL,
                        api_key TEXT NOT NULL,
                        supports_vision INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_model_configs_updated
                        ON model_configs(updated_at DESC);
                    PRAGMA user_version = 4;
                    """
                )
            if version < 5:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS workflow_checkpoints (
                        checkpoint_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id),
                        assessment_run_id TEXT NOT NULL REFERENCES assessment_runs(assessment_run_id),
                        enterprise_id TEXT NOT NULL REFERENCES enterprise_profiles(enterprise_id),
                        workflow_name TEXT NOT NULL,
                        thread_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        current_node TEXT,
                        version INTEGER NOT NULL DEFAULT 1,
                        state_json TEXT NOT NULL,
                        checkpoint_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(assessment_run_id, workflow_name),
                        UNIQUE(thread_id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_run
                        ON workflow_checkpoints(assessment_run_id, updated_at DESC);
                    PRAGMA user_version = 5;
                    """
                )

    @staticmethod
    def _workspace(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "workspace_id": row["workspace_id"],
            "name": row["name"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "archived": bool(row["archived"]),
            "last_active_run_id": row["last_active_run_id"],
        }

    @staticmethod
    def _source_batch(row: sqlite3.Row, *, reused: bool = False) -> dict[str, Any]:
        return {
            "source_batch_id": row["source_batch_id"],
            "m1_batch_id": row["m1_batch_id"],
            "source_filename": row["source_filename"],
            "sha256": row["sha256"],
            "source": row["source"],
            "simulated_data": bool(row["simulated_data"]),
            "validation_status": row["validation_status"],
            "available_company_codes": _loads(row["available_company_codes_json"], []),
            "created_at": row["created_at"],
            "reused": reused,
            "data_notice": SIMULATED_DATA_NOTICE if bool(row["simulated_data"]) else None,
        }

    @staticmethod
    def _enterprise(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "enterprise_id": row["enterprise_id"],
            "workspace_id": row["workspace_id"],
            "enterprise_code": row["enterprise_code"],
            "basic_info_index": _loads(row["basic_info_index_json"], {}),
            "source_batch_ids": _loads(row["source_batch_ids_json"], []),
            "fact_version": row["fact_version"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _run(self, connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        enterprise = connection.execute(
            "SELECT * FROM enterprise_profiles WHERE enterprise_id = ?", (row["enterprise_id"],)
        ).fetchone()
        source = self._find_source_batch_row(connection, row["source_batch_id"])
        if source is None:
            snapshot = _loads(row["batch_snapshot_json"], {})
            source = self._find_source_batch_row(connection, snapshot.get("m1_batch_id"))
        return {
            "assessment_run_id": row["assessment_run_id"],
            "workspace_id": row["workspace_id"],
            "enterprise_id": row["enterprise_id"],
            "enterprise_code": enterprise["enterprise_code"] if enterprise else None,
            "source_batch_id": row["source_batch_id"],
            "m1_batch_id": source["m1_batch_id"] if source else None,
            "simulated_data": bool(source["simulated_data"]) if source else True,
            "data_notice": SIMULATED_DATA_NOTICE if source and bool(source["simulated_data"]) else None,
            "run_name": row["run_name"],
            "batch_snapshot": _loads(row["batch_snapshot_json"], {}),
            "rule_version": row["rule_version"],
            "model_config": _loads(row["model_config_json"], {}),
            "status": row["status"],
            "quality_gate_status": row["quality_gate_status"],
            "report_ids": _loads(row["report_ids_json"], []),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _find_source_batch_row(connection: sqlite3.Connection, batch_reference: str | None) -> sqlite3.Row | None:
        """Resolve both the durable source_batch_id and legacy M1 batch_id.

        Older local runs could retain the M1 filesystem batch ID in the UI-facing
        source_batch_id slot. Keeping this read-side compatibility avoids forcing
        users to re-upload the workbook just to switch back to an existing run.
        """
        if not batch_reference:
            return None
        return connection.execute(
            "SELECT * FROM source_batches WHERE source_batch_id = ? OR m1_batch_id = ? LIMIT 1",
            (batch_reference, batch_reference),
        ).fetchone()

    def _get_workspace_row(self, connection: sqlite3.Connection, workspace_id: str) -> sqlite3.Row:
        validate_domain_id(workspace_id)
        row = connection.execute("SELECT * FROM workspaces WHERE workspace_id = ?", (workspace_id,)).fetchone()
        if row is None:
            raise DomainNotFoundError(f"工作空间不存在：{workspace_id}")
        return row

    def create_workspace(self, name: str) -> dict[str, Any]:
        if not name.strip():
            raise DomainValidationError("工作空间名称不能为空")
        now = _now()
        workspace_id = _new_id("ws")
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO workspaces(workspace_id,name,created_at,updated_at) VALUES(?,?,?,?)",
                (workspace_id, name.strip(), now, now),
            )
            return self._workspace(connection.execute("SELECT * FROM workspaces WHERE workspace_id = ?", (workspace_id,)).fetchone())

    def list_workspaces(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM workspaces ORDER BY updated_at DESC").fetchall()
            return [self._workspace(row) for row in rows]

    @staticmethod
    def _model_config(row: sqlite3.Row, *, include_secret: bool = False) -> dict[str, Any]:
        payload = {
            "model_config_id": row["model_config_id"],
            "model_id": row["model_config_id"],
            "model_name": row["model_name"],
            "display_name": row["display_name"],
            "provider_id": row["provider_id"],
            "base_url": row["base_url"],
            "supports_vision": bool(row["supports_vision"]),
            "api_key_configured": bool(row["api_key"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        if include_secret:
            payload["api_key"] = row["api_key"]
        return payload

    @staticmethod
    def _validate_model_config(*, model_name: str, display_name: str, provider_id: str, base_url: str, api_key: str) -> tuple[str, str, str, str, str]:
        values = {
            "model_name": model_name.strip(),
            "display_name": display_name.strip() or model_name.strip(),
            "provider_id": provider_id.strip() or "openai-compatible",
            "base_url": base_url.strip().rstrip("/"),
            "api_key": api_key.strip(),
        }
        if not values["model_name"]:
            raise DomainValidationError("模型名称不能为空")
        if not values["base_url"]:
            raise DomainValidationError("接口地址不能为空")
        parsed = urlparse(values["base_url"])
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            raise DomainValidationError("接口地址必须是不含账号密码的HTTP或HTTPS地址")
        if any(char.isspace() for char in values["base_url"]):
            raise DomainValidationError("接口地址不能包含空白字符")
        if not values["api_key"]:
            raise DomainValidationError("API key不能为空")
        if any(marker in values["provider_id"].lower() for marker in ("key", "secret", "token", "password")):
            raise DomainValidationError("服务商标识不能包含密钥字段")
        return values["model_name"], values["display_name"], values["provider_id"], values["base_url"], values["api_key"]

    def create_model_config(
        self,
        *,
        model_name: str,
        display_name: str,
        provider_id: str,
        base_url: str,
        api_key: str,
        supports_vision: bool = False,
    ) -> dict[str, Any]:
        model_name, display_name, provider_id, base_url, api_key = self._validate_model_config(
            model_name=model_name,
            display_name=display_name,
            provider_id=provider_id,
            base_url=base_url,
            api_key=api_key,
        )
        now = _now()
        model_config_id = _new_id("mdl")
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO model_configs(
                    model_config_id,model_name,display_name,provider_id,base_url,api_key,
                    supports_vision,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (model_config_id, model_name, display_name, provider_id, base_url, api_key, int(supports_vision), now, now),
            )
            return self._model_config(
                connection.execute("SELECT * FROM model_configs WHERE model_config_id = ?", (model_config_id,)).fetchone()
            )

    def list_model_configs(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM model_configs ORDER BY updated_at DESC, model_config_id").fetchall()
            return [self._model_config(row) for row in rows]

    def get_model_config(self, model_config_id: str, *, include_secret: bool = False) -> dict[str, Any]:
        validate_domain_id(model_config_id)
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM model_configs WHERE model_config_id = ?", (model_config_id,)).fetchone()
            if row is None:
                raise DomainNotFoundError(f"模型配置不存在：{model_config_id}")
            return self._model_config(row, include_secret=include_secret)

    def delete_model_config(self, model_config_id: str) -> dict[str, Any]:
        validate_domain_id(model_config_id)
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM model_configs WHERE model_config_id = ?", (model_config_id,)).fetchone()
            if row is None:
                raise DomainNotFoundError(f"模型配置不存在：{model_config_id}")
            deleted = self._model_config(row)
            connection.execute("DELETE FROM model_configs WHERE model_config_id = ?", (model_config_id,))
            deleted["deleted"] = True
            return deleted

    def get_workspace(self, workspace_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            return self._workspace(self._get_workspace_row(connection, workspace_id))

    def register_source_batch(
        self,
        *,
        m1_batch_id: str,
        source_filename: str,
        sha256: str,
        validation_status: str,
        available_company_codes: list[str],
        source: str = "local_upload",
        simulated_data: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not SHA256_PATTERN.fullmatch(sha256):
            raise DomainValidationError("source_batch必须提供64位SHA-256")
        with self._connection() as connection:
            existing = connection.execute("SELECT * FROM source_batches WHERE sha256 = ?", (sha256,)).fetchone()
            if existing is not None:
                return self._source_batch(existing, reused=True)
            source_batch_id = _new_id("src")
            now = _now()
            connection.execute(
                """INSERT INTO source_batches(
                    source_batch_id,m1_batch_id,source_filename,sha256,source,simulated_data,
                    validation_status,available_company_codes_json,metadata_json,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    source_batch_id,
                    m1_batch_id,
                    source_filename,
                    sha256,
                    source,
                    int(simulated_data),
                    validation_status,
                    _json(sorted(set(available_company_codes))),
                    _json(metadata or {}),
                    now,
                ),
            )
            row = connection.execute("SELECT * FROM source_batches WHERE source_batch_id = ?", (source_batch_id,)).fetchone()
            return self._source_batch(row)

    def ensure_source_batch_runtime(
        self,
        *,
        m1_batch_id: str,
        source_filename: str,
        sha256: str,
        validation_status: str,
        available_company_codes: list[str],
        source: str = "bundled_simulated_data",
        simulated_data: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Register the bundled workbook and repair its local M1 runtime link.

        The SQLite domain record is durable, while parsed M1 artifacts live in a
        runtime directory that can change between source checkouts and packaged
        app launches. Matching by SHA-256 lets startup restore the same source
        batch without asking the user to upload the workbook again.
        """
        if not SHA256_PATTERN.fullmatch(sha256):
            raise DomainValidationError("source_batch必须提供64位SHA-256")
        with self._connection() as connection:
            existing = connection.execute("SELECT * FROM source_batches WHERE sha256 = ?", (sha256,)).fetchone()
            if existing is None:
                source_batch_id = _new_id("src")
                now = _now()
                connection.execute(
                    """INSERT INTO source_batches(
                        source_batch_id,m1_batch_id,source_filename,sha256,source,simulated_data,
                        validation_status,available_company_codes_json,metadata_json,created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (
                        source_batch_id,
                        m1_batch_id,
                        source_filename,
                        sha256,
                        source,
                        int(simulated_data),
                        validation_status,
                        _json(sorted(set(available_company_codes))),
                        _json(metadata or {}),
                        now,
                    ),
                )
                existing = connection.execute(
                    "SELECT * FROM source_batches WHERE source_batch_id = ?", (source_batch_id,)
                ).fetchone()
                return self._source_batch(existing)

            conflicting = connection.execute(
                "SELECT source_batch_id FROM source_batches WHERE m1_batch_id = ? AND source_batch_id != ?",
                (m1_batch_id, existing["source_batch_id"]),
            ).fetchone()
            if conflicting is not None:
                raise DomainConflictError("M1批次标识已绑定到另一份数据，无法自动恢复")
            connection.execute(
                """UPDATE source_batches SET m1_batch_id = ?, source_filename = ?, source = ?,
                    simulated_data = ?, validation_status = ?, available_company_codes_json = ?, metadata_json = ?
                    WHERE source_batch_id = ?""",
                (
                    m1_batch_id,
                    source_filename,
                    source,
                    int(simulated_data),
                    validation_status,
                    _json(sorted(set(available_company_codes))),
                    _json(metadata or {}),
                    existing["source_batch_id"],
                ),
            )
            row = connection.execute(
                "SELECT * FROM source_batches WHERE source_batch_id = ?", (existing["source_batch_id"],)
            ).fetchone()
            return self._source_batch(row, reused=True)

    def get_source_batch(self, source_batch_id: str) -> dict[str, Any]:
        validate_domain_id(source_batch_id)
        with self._connection() as connection:
            row = self._find_source_batch_row(connection, source_batch_id)
            if row is None:
                raise DomainNotFoundError(f"数据批次不存在：{source_batch_id}")
            return self._source_batch(row)

    def get_source_batch_by_sha256(self, sha256: str) -> dict[str, Any] | None:
        if not SHA256_PATTERN.fullmatch(sha256):
            raise DomainValidationError("source_batch必须提供64位SHA-256")
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM source_batches WHERE sha256 = ?", (sha256,)).fetchone()
            return self._source_batch(row) if row is not None else None

    def create_assessment_run(
        self,
        *,
        workspace_id: str,
        enterprise_code: str,
        source_batch_id: str,
        run_name: str,
        rule_version: str,
        model_config: dict[str, Any],
        basic_info_index: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not enterprise_code.strip():
            raise DomainValidationError("企业代号不能为空")
        if REFERENCE_ONLY_FIELDS.intersection(basic_info_index or {}):
            raise DomainValidationError("企业档案索引不能包含转型规划结论字段")
        for key in (model_config or {}):
            normalized_key = str(key).lower()
            if any(marker in normalized_key for marker in ("api_key", "apikey", "secret", "token", "password")):
                raise DomainValidationError("评估运行配置不能保存API密钥、令牌或密码；密钥必须留在后端受控环境")
        with self._connection() as connection:
            self._get_workspace_row(connection, workspace_id)
            validate_domain_id(source_batch_id)
            source = self._find_source_batch_row(connection, source_batch_id)
            if source is None:
                raise DomainNotFoundError(f"数据批次不存在：{source_batch_id}")
            if source["validation_status"] == "failed":
                raise DomainConflictError("校验失败的数据批次不能创建评估运行")
            available = set(_loads(source["available_company_codes_json"], []))
            if enterprise_code not in available:
                raise DomainValidationError(f"企业代号不属于所选数据批次：{enterprise_code}")
            enterprise = connection.execute(
                "SELECT * FROM enterprise_profiles WHERE workspace_id = ? AND enterprise_code = ?",
                (workspace_id, enterprise_code),
            ).fetchone()
            now = _now()
            if enterprise is None:
                enterprise_id = _new_id("ent")
                connection.execute(
                    """INSERT INTO enterprise_profiles(
                        enterprise_id,workspace_id,enterprise_code,basic_info_index_json,
                        source_batch_ids_json,fact_version,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        enterprise_id,
                        workspace_id,
                        enterprise_code,
                        _json(basic_info_index or {"企业代号": enterprise_code}),
                        _json([source_batch_id]),
                        1,
                        now,
                        now,
                    ),
                )
            else:
                enterprise_id = enterprise["enterprise_id"]
                source_batch_ids = _loads(enterprise["source_batch_ids_json"], [])
                if source_batch_id not in source_batch_ids:
                    source_batch_ids.append(source_batch_id)
                connection.execute(
                    """UPDATE enterprise_profiles SET basic_info_index_json = ?, source_batch_ids_json = ?,
                        fact_version = fact_version + 1, updated_at = ? WHERE enterprise_id = ?""",
                    (_json(basic_info_index or _loads(enterprise["basic_info_index_json"], {})), _json(source_batch_ids), now, enterprise_id),
                )
            run_id = _new_id("run")
            snapshot = {
                "source_batch_id": source_batch_id,
                "m1_batch_id": source["m1_batch_id"],
                "sha256": source["sha256"],
                "validation_status": source["validation_status"],
                "available_company_count": len(available),
                "report_period": "2024—2025",
            }
            connection.execute(
                """INSERT INTO assessment_runs(
                    assessment_run_id,workspace_id,enterprise_id,source_batch_id,run_name,
                    batch_snapshot_json,rule_version,model_config_json,status,quality_gate_status,
                    report_ids_json,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run_id,
                    workspace_id,
                    enterprise_id,
                    source_batch_id,
                    run_name.strip(),
                    _json(snapshot),
                    rule_version,
                    _json(model_config),
                    "draft",
                    "not_run",
                    _json([]),
                    now,
                    now,
                ),
            )
            connection.execute("UPDATE workspaces SET updated_at = ?, last_active_run_id = ? WHERE workspace_id = ?", (now, run_id, workspace_id))
            return self._run(connection, connection.execute("SELECT * FROM assessment_runs WHERE assessment_run_id = ?", (run_id,)).fetchone())

    def get_assessment_run(self, assessment_run_id: str) -> dict[str, Any]:
        validate_domain_id(assessment_run_id)
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM assessment_runs WHERE assessment_run_id = ?", (assessment_run_id,)).fetchone()
            if row is None:
                raise DomainNotFoundError(f"评估运行不存在：{assessment_run_id}")
            return self._run(connection, row)

    def list_assessment_runs(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            self._get_workspace_row(connection, workspace_id)
            rows = connection.execute("SELECT * FROM assessment_runs WHERE workspace_id = ? ORDER BY updated_at DESC", (workspace_id,)).fetchall()
            return [self._run(connection, row) for row in rows]

    def update_assessment_run(self, assessment_run_id: str, *, status: str, quality_gate_status: str) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM assessment_runs WHERE assessment_run_id = ?", (assessment_run_id,)).fetchone()
            if row is None:
                raise DomainNotFoundError(f"评估运行不存在：{assessment_run_id}")
            if row["status"] == "archived" and status != "archived":
                raise DomainConflictError("已归档评估运行不可覆盖，请创建新的重评运行")
            if row["status"] == "completed" and status not in {"completed", "archived"}:
                raise DomainConflictError("已完成评估运行不可回写，请创建新的重评运行")
            now = _now()
            connection.execute(
                "UPDATE assessment_runs SET status = ?, quality_gate_status = ?, updated_at = ? WHERE assessment_run_id = ?",
                (status, quality_gate_status, now, assessment_run_id),
            )
            connection.execute("UPDATE workspaces SET updated_at = ?, last_active_run_id = ? WHERE workspace_id = ?", (now, assessment_run_id, row["workspace_id"]))
            return self._run(connection, connection.execute("SELECT * FROM assessment_runs WHERE assessment_run_id = ?", (assessment_run_id,)).fetchone())

    def create_message(
        self,
        assessment_run_id: str,
        *,
        role: str,
        message_type: str,
        content: str,
        tool_name: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        with self._connection() as connection:
            run_row = connection.execute("SELECT * FROM assessment_runs WHERE assessment_run_id = ?", (assessment_run_id,)).fetchone()
            if run_row is None:
                raise DomainNotFoundError(f"评估运行不存在：{assessment_run_id}")
            message_id = _new_id("msg")
            now = _now()
            connection.execute(
                """INSERT INTO conversation_messages(
                    message_id,workspace_id,assessment_run_id,enterprise_id,role,message_type,
                    content,tool_name,payload_json,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (message_id, run_row["workspace_id"], assessment_run_id, run_row["enterprise_id"], role, message_type, content, tool_name, _json(payload), now),
            )
            run = self._run(connection, run_row)
            return {
                "message_id": message_id,
                "workspace_id": run_row["workspace_id"],
                "assessment_run_id": assessment_run_id,
                "enterprise_id": run_row["enterprise_id"],
                "role": role,
                "message_type": message_type,
                "content": content,
                "tool_name": tool_name,
                "payload": payload,
                "created_at": now,
                "source_batch_id": run["source_batch_id"],
                "m1_batch_id": run["m1_batch_id"],
                "simulated_data": run["simulated_data"],
                "data_notice": run["data_notice"],
                "rule_version": run["rule_version"],
                "model_config": run["model_config"],
            }

    def list_messages(self, assessment_run_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            if connection.execute("SELECT 1 FROM assessment_runs WHERE assessment_run_id = ?", (assessment_run_id,)).fetchone() is None:
                raise DomainNotFoundError(f"评估运行不存在：{assessment_run_id}")
            run = self._run(
                connection,
                connection.execute("SELECT * FROM assessment_runs WHERE assessment_run_id = ?", (assessment_run_id,)).fetchone(),
            )
            rows = connection.execute("SELECT * FROM conversation_messages WHERE assessment_run_id = ? ORDER BY created_at, message_id", (assessment_run_id,)).fetchall()
            return [
                {
                    "message_id": row["message_id"],
                    "workspace_id": row["workspace_id"],
                    "assessment_run_id": row["assessment_run_id"],
                    "enterprise_id": row["enterprise_id"],
                    "role": row["role"],
                    "message_type": row["message_type"],
                    "content": row["content"],
                    "tool_name": row["tool_name"],
                    "payload": _loads(row["payload_json"], {}),
                    "created_at": row["created_at"],
                    "source_batch_id": run["source_batch_id"],
                    "m1_batch_id": run["m1_batch_id"],
                    "simulated_data": run["simulated_data"],
                    "data_notice": run["data_notice"],
                    "rule_version": run["rule_version"],
                    "model_config": run["model_config"],
                }
                for row in rows
            ]

    def create_report_artifact(
        self,
        assessment_run_id: str,
        *,
        report_type: str,
        file_format: str,
        relative_path: str,
        version: str,
        sha256: str | None,
        generation_config: dict[str, Any],
        export_records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        relative_path = validate_relative_path(relative_path)
        if sha256 is not None and not SHA256_PATTERN.fullmatch(sha256):
            raise DomainValidationError("报告哈希必须是64位SHA-256")
        with self._connection() as connection:
            run = connection.execute("SELECT * FROM assessment_runs WHERE assessment_run_id = ?", (assessment_run_id,)).fetchone()
            if run is None:
                raise DomainNotFoundError(f"评估运行不存在：{assessment_run_id}")
            artifact_id = _new_id("rpt")
            now = _now()
            connection.execute(
                """INSERT INTO report_artifacts(
                    report_artifact_id,workspace_id,assessment_run_id,enterprise_id,report_type,
                    file_format,relative_path,version,sha256,generation_config_json,export_records_json,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (artifact_id, run["workspace_id"], assessment_run_id, run["enterprise_id"], report_type, file_format, relative_path, version, sha256, _json(generation_config), _json(export_records), now),
            )
            report_ids = _loads(run["report_ids_json"], [])
            report_ids.append(artifact_id)
            connection.execute("UPDATE assessment_runs SET report_ids_json = ?, updated_at = ? WHERE assessment_run_id = ?", (_json(report_ids), now, assessment_run_id))
            run_context = self._run(connection, connection.execute("SELECT * FROM assessment_runs WHERE assessment_run_id = ?", (assessment_run_id,)).fetchone())
            return {
                "report_artifact_id": artifact_id,
                "workspace_id": run["workspace_id"],
                "assessment_run_id": assessment_run_id,
                "enterprise_id": run["enterprise_id"],
                "report_type": report_type,
                "file_format": file_format,
                "relative_path": relative_path,
                "version": version,
                "sha256": sha256,
                "generation_config": generation_config,
                "export_records": export_records,
                "created_at": now,
                "report_period": run_context["batch_snapshot"].get("report_period", "未记录"),
                "source_batch_id": run_context["source_batch_id"],
                "m1_batch_id": run_context["m1_batch_id"],
                "simulated_data": run_context["simulated_data"],
                "data_notice": run_context["data_notice"],
                "rule_version": run_context["rule_version"],
                "model_config": run_context["model_config"],
            }

    def save_report_file(self, relative_path: str, content: str) -> str:
        relative_path = validate_relative_path(relative_path)
        path = (self.root / relative_path).resolve()
        if self.root not in path.parents:
            raise DomainValidationError("报告路径不能越出应用数据目录")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def save_attachment_file(self, sha256: str, source_filename: str, content: bytes) -> str:
        if not SHA256_PATTERN.fullmatch(sha256):
            raise DomainValidationError("附件必须提供64位SHA-256")
        safe_name = safe_filename(source_filename)
        relative_path = validate_attachment_relative_path(f"attachments/{sha256}/{safe_name}")
        path = (self.root / relative_path).resolve()
        if self.root not in path.parents:
            raise DomainValidationError("附件路径不能越出应用数据目录")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if existing_hash != sha256:
                raise DomainConflictError("附件哈希与已保存原件不一致")
            return relative_path
        path.write_bytes(content)
        path.chmod(0o444)
        return relative_path

    @staticmethod
    def _attachment(row: sqlite3.Row, *, reused: bool = False) -> dict[str, Any]:
        parsed = _loads(row["parse_result_json"], {})
        return {
            "attachment_id": row["attachment_id"],
            "workspace_id": row["workspace_id"],
            "assessment_run_id": row["assessment_run_id"],
            "enterprise_id": row["enterprise_id"],
            "source_batch_id": row["source_batch_id"],
            "source_filename": row["source_filename"],
            "file_type": row["file_type"],
            "mime_type": row["mime_type"],
            "file_size": row["file_size"],
            "sha256": row["sha256"],
            "relative_path": row["relative_path"],
            "parse_status": row["parse_status"],
            "merge_allowed": bool(row["merge_allowed"]),
            "parse_result": parsed,
            "created_at": row["created_at"],
            "reused": reused,
            "simulated_data": True,
            "data_notice": SIMULATED_DATA_NOTICE,
        }

    def create_attachment(
        self,
        assessment_run_id: str,
        *,
        source_filename: str,
        file_type: str,
        mime_type: str | None,
        file_size: int,
        sha256: str,
        relative_path: str,
        parse_result: dict[str, Any],
    ) -> dict[str, Any]:
        validate_domain_id(assessment_run_id)
        validate_attachment_relative_path(relative_path)
        if not SHA256_PATTERN.fullmatch(sha256):
            raise DomainValidationError("附件必须提供64位SHA-256")
        with self._connection() as connection:
            run = connection.execute("SELECT * FROM assessment_runs WHERE assessment_run_id = ?", (assessment_run_id,)).fetchone()
            if run is None:
                raise DomainNotFoundError(f"评估运行不存在：{assessment_run_id}")
            existing = connection.execute(
                "SELECT * FROM multimodal_attachments WHERE assessment_run_id = ? AND sha256 = ?",
                (assessment_run_id, sha256),
            ).fetchone()
            if existing is not None:
                return self._attachment(existing, reused=True)
            attachment_id = _new_id("att")
            now = _now()
            connection.execute(
                """INSERT INTO multimodal_attachments(
                    attachment_id,workspace_id,assessment_run_id,enterprise_id,source_batch_id,
                    source_filename,file_type,mime_type,file_size,sha256,relative_path,parse_status,
                    merge_allowed,parse_result_json,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    attachment_id,
                    run["workspace_id"],
                    assessment_run_id,
                    run["enterprise_id"],
                    run["source_batch_id"],
                    safe_filename(source_filename),
                    file_type,
                    mime_type,
                    file_size,
                    sha256,
                    relative_path,
                    str(parse_result.get("status", "failed")),
                    int(bool(parse_result.get("merge_allowed"))),
                    _json(parse_result),
                    now,
                ),
            )
            row = connection.execute("SELECT * FROM multimodal_attachments WHERE attachment_id = ?", (attachment_id,)).fetchone()
            return self._attachment(row)

    def list_attachments(self, assessment_run_id: str) -> list[dict[str, Any]]:
        validate_domain_id(assessment_run_id)
        with self._connection() as connection:
            if connection.execute("SELECT 1 FROM assessment_runs WHERE assessment_run_id = ?", (assessment_run_id,)).fetchone() is None:
                raise DomainNotFoundError(f"评估运行不存在：{assessment_run_id}")
            rows = connection.execute(
                "SELECT * FROM multimodal_attachments WHERE assessment_run_id = ? ORDER BY created_at DESC",
                (assessment_run_id,),
            ).fetchall()
            return [self._attachment(row) for row in rows]

    def get_attachment(self, assessment_run_id: str, attachment_id: str) -> dict[str, Any]:
        validate_domain_id(assessment_run_id)
        validate_domain_id(attachment_id)
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM multimodal_attachments WHERE assessment_run_id = ? AND attachment_id = ?",
                (assessment_run_id, attachment_id),
            ).fetchone()
            if row is None:
                raise DomainNotFoundError(f"运行附件不存在：{attachment_id}")
            return self._attachment(row)

    @staticmethod
    def _orchestration_event(row: sqlite3.Row, *, run: dict[str, Any]) -> dict[str, Any]:
        return {
            "event_id": row["event_id"],
            "workspace_id": row["workspace_id"],
            "assessment_run_id": row["assessment_run_id"],
            "enterprise_id": row["enterprise_id"],
            "event_type": row["event_type"],
            "provider_id": row["provider_id"],
            "model_id": row["model_id"],
            "purpose": row["purpose"],
            "tool_name": row["tool_name"],
            "input_evidence_refs": _loads(row["input_evidence_refs_json"], []),
            "payload": _loads(row["payload_json"], {}),
            "status": row["status"],
            "error_code": row["error_code"],
            "created_at": row["created_at"],
            "source_batch_id": run["source_batch_id"],
            "simulated_data": run["simulated_data"],
            "data_notice": run["data_notice"],
            "rule_version": run["rule_version"],
        }

    def create_orchestration_event(
        self,
        assessment_run_id: str,
        *,
        event_type: str,
        provider_id: str | None,
        model_id: str | None,
        purpose: str,
        tool_name: str | None,
        input_evidence_refs: list[str],
        payload: dict[str, Any],
        status: str,
        error_code: str | None = None,
    ) -> dict[str, Any]:
        validate_domain_id(assessment_run_id)
        if not event_type.strip() or not purpose.strip() or not status.strip():
            raise DomainValidationError("编排审计事件必须包含事件类型、用途和状态")
        if any(not isinstance(item, str) for item in input_evidence_refs):
            raise DomainValidationError("编排审计证据引用必须是字符串数组")
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM assessment_runs WHERE assessment_run_id = ?", (assessment_run_id,)).fetchone()
            if row is None:
                raise DomainNotFoundError(f"评估运行不存在：{assessment_run_id}")
            run = self._run(connection, row)
            event_id = _new_id("evt")
            now = _now()
            connection.execute(
                """INSERT INTO orchestration_events(
                    event_id,workspace_id,assessment_run_id,enterprise_id,event_type,
                    provider_id,model_id,purpose,tool_name,input_evidence_refs_json,
                    payload_json,status,error_code,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event_id,
                    row["workspace_id"],
                    assessment_run_id,
                    row["enterprise_id"],
                    event_type.strip(),
                    provider_id,
                    model_id,
                    purpose.strip(),
                    tool_name,
                    _json(sorted(set(input_evidence_refs))),
                    _json(payload),
                    status.strip(),
                    error_code,
                    now,
                ),
            )
            event_row = connection.execute("SELECT * FROM orchestration_events WHERE event_id = ?", (event_id,)).fetchone()
            return self._orchestration_event(event_row, run=run)

    def list_orchestration_events(self, assessment_run_id: str) -> list[dict[str, Any]]:
        validate_domain_id(assessment_run_id)
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM assessment_runs WHERE assessment_run_id = ?", (assessment_run_id,)).fetchone()
            if row is None:
                raise DomainNotFoundError(f"评估运行不存在：{assessment_run_id}")
            run = self._run(connection, row)
            rows = connection.execute(
                "SELECT * FROM orchestration_events WHERE assessment_run_id = ? ORDER BY created_at, event_id",
                (assessment_run_id,),
            ).fetchall()
            return [self._orchestration_event(item, run=run) for item in rows]

    @staticmethod
    def _workflow_checkpoint(row: sqlite3.Row, *, run: dict[str, Any]) -> dict[str, Any]:
        return {
            "checkpoint_id": row["checkpoint_id"],
            "workspace_id": row["workspace_id"],
            "assessment_run_id": row["assessment_run_id"],
            "enterprise_id": row["enterprise_id"],
            "enterprise_code": run["enterprise_code"],
            "workflow_name": row["workflow_name"],
            "thread_id": row["thread_id"],
            "status": row["status"],
            "current_node": row["current_node"],
            "version": row["version"],
            "state": _loads(row["state_json"], {}),
            "checkpoint": _loads(row["checkpoint_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "source_batch_id": run["source_batch_id"],
            "simulated_data": run["simulated_data"],
            "data_notice": run["data_notice"],
            "rule_version": run["rule_version"],
        }

    def upsert_workflow_checkpoint(
        self,
        assessment_run_id: str,
        *,
        workflow_name: str,
        thread_id: str,
        status: str,
        current_node: str | None,
        version: int,
        state: dict[str, Any],
        checkpoint: dict[str, Any],
    ) -> dict[str, Any]:
        validate_domain_id(assessment_run_id)
        if not workflow_name.strip() or not thread_id.strip() or not status.strip():
            raise DomainValidationError("工作流检查点必须包含流程名、线程标识和状态")
        if not isinstance(state, dict) or not isinstance(checkpoint, dict):
            raise DomainValidationError("工作流检查点状态必须是对象")
        with self._connection() as connection:
            run_row = connection.execute(
                "SELECT * FROM assessment_runs WHERE assessment_run_id = ?", (assessment_run_id,)
            ).fetchone()
            if run_row is None:
                raise DomainNotFoundError(f"评估运行不存在：{assessment_run_id}")
            now = _now()
            existing = connection.execute(
                "SELECT * FROM workflow_checkpoints WHERE assessment_run_id = ? AND workflow_name = ?",
                (assessment_run_id, workflow_name),
            ).fetchone()
            if existing is None:
                if int(version) != 1:
                    raise DomainConflictError("新工作流检查点版本必须从1开始")
                checkpoint_id = _new_id("ckpt")
                connection.execute(
                    """INSERT INTO workflow_checkpoints(
                        checkpoint_id,workspace_id,assessment_run_id,enterprise_id,workflow_name,
                        thread_id,status,current_node,version,state_json,checkpoint_json,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        checkpoint_id,
                        run_row["workspace_id"],
                        assessment_run_id,
                        run_row["enterprise_id"],
                        workflow_name.strip(),
                        thread_id.strip(),
                        status.strip(),
                        current_node,
                        max(1, int(version)),
                        _json(state),
                        _json(checkpoint),
                        now,
                        now,
                    ),
                )
            else:
                if existing["thread_id"] != thread_id:
                    raise DomainConflictError("工作流线程标识与已有评估运行不一致")
                expected_version = int(existing["version"]) + 1
                if int(version) != expected_version:
                    raise DomainConflictError(
                        f"工作流检查点版本冲突：期望{expected_version}，收到{version}"
                    )
                checkpoint_id = existing["checkpoint_id"]
                cursor = connection.execute(
                    """UPDATE workflow_checkpoints SET status = ?, current_node = ?, version = ?,
                        state_json = ?, checkpoint_json = ?, updated_at = ?
                        WHERE checkpoint_id = ? AND version = ?""",
                    (
                        status.strip(),
                        current_node,
                        int(version),
                        _json(state),
                        _json(checkpoint),
                        now,
                        checkpoint_id,
                        int(version) - 1,
                    ),
                )
                if cursor.rowcount != 1:
                    raise DomainConflictError("工作流检查点已被其他操作更新，请刷新后重试")
            row = connection.execute(
                "SELECT * FROM workflow_checkpoints WHERE checkpoint_id = ?", (checkpoint_id,)
            ).fetchone()
            return self._workflow_checkpoint(row, run=self._run(connection, run_row))

    def get_workflow_checkpoint(self, assessment_run_id: str, workflow_name: str) -> dict[str, Any]:
        validate_domain_id(assessment_run_id)
        with self._connection() as connection:
            run_row = connection.execute(
                "SELECT * FROM assessment_runs WHERE assessment_run_id = ?", (assessment_run_id,)
            ).fetchone()
            if run_row is None:
                raise DomainNotFoundError(f"评估运行不存在：{assessment_run_id}")
            row = connection.execute(
                "SELECT * FROM workflow_checkpoints WHERE assessment_run_id = ? AND workflow_name = ?",
                (assessment_run_id, workflow_name),
            ).fetchone()
            if row is None:
                raise DomainNotFoundError(f"当前运行尚未启动流程：{workflow_name}")
            return self._workflow_checkpoint(row, run=self._run(connection, run_row))

    def list_workflow_checkpoints(self, assessment_run_id: str) -> list[dict[str, Any]]:
        validate_domain_id(assessment_run_id)
        with self._connection() as connection:
            run_row = connection.execute(
                "SELECT * FROM assessment_runs WHERE assessment_run_id = ?", (assessment_run_id,)
            ).fetchone()
            if run_row is None:
                raise DomainNotFoundError(f"评估运行不存在：{assessment_run_id}")
            rows = connection.execute(
                "SELECT * FROM workflow_checkpoints WHERE assessment_run_id = ? ORDER BY updated_at DESC",
                (assessment_run_id,),
            ).fetchall()
            run = self._run(connection, run_row)
            return [self._workflow_checkpoint(row, run=run) for row in rows]

    @staticmethod
    def _report_artifact(row: sqlite3.Row, *, run: dict[str, Any]) -> dict[str, Any]:
        return {
            "report_artifact_id": row["report_artifact_id"],
            "workspace_id": row["workspace_id"],
            "assessment_run_id": row["assessment_run_id"],
            "enterprise_id": row["enterprise_id"],
            "report_type": row["report_type"],
            "file_format": row["file_format"],
            "relative_path": row["relative_path"],
            "version": row["version"],
            "sha256": row["sha256"],
            "generation_config": _loads(row["generation_config_json"], {}),
            "export_records": _loads(row["export_records_json"], []),
            "created_at": row["created_at"],
            "report_period": run["batch_snapshot"].get("report_period", "未记录"),
            "source_batch_id": run["source_batch_id"],
            "m1_batch_id": run["m1_batch_id"],
            "simulated_data": run["simulated_data"],
            "data_notice": run["data_notice"],
            "rule_version": run["rule_version"],
            "model_config": run["model_config"],
        }

    def get_report_artifact(self, assessment_run_id: str, report_artifact_id: str) -> dict[str, Any]:
        validate_domain_id(assessment_run_id)
        validate_domain_id(report_artifact_id)
        with self._connection() as connection:
            run_row = connection.execute("SELECT * FROM assessment_runs WHERE assessment_run_id = ?", (assessment_run_id,)).fetchone()
            if run_row is None:
                raise DomainNotFoundError(f"评估运行不存在：{assessment_run_id}")
            row = connection.execute(
                "SELECT * FROM report_artifacts WHERE assessment_run_id = ? AND report_artifact_id = ?",
                (assessment_run_id, report_artifact_id),
            ).fetchone()
            if row is None:
                raise DomainNotFoundError(f"报告工件不存在：{report_artifact_id}")
            return self._report_artifact(row, run=self._run(connection, run_row))

    def record_report_export(self, assessment_run_id: str, report_artifact_id: str, export_record: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(export_record, dict) or not export_record.get("format") or not export_record.get("status"):
            raise DomainValidationError("报告导出记录必须包含格式和状态")
        with self._connection() as connection:
            run_row = connection.execute("SELECT * FROM assessment_runs WHERE assessment_run_id = ?", (assessment_run_id,)).fetchone()
            if run_row is None:
                raise DomainNotFoundError(f"评估运行不存在：{assessment_run_id}")
            row = connection.execute(
                "SELECT * FROM report_artifacts WHERE assessment_run_id = ? AND report_artifact_id = ?",
                (assessment_run_id, report_artifact_id),
            ).fetchone()
            if row is None:
                raise DomainNotFoundError(f"报告工件不存在：{report_artifact_id}")
            records = _loads(row["export_records_json"], [])
            records.append(export_record)
            connection.execute(
                "UPDATE report_artifacts SET export_records_json = ? WHERE report_artifact_id = ?",
                (_json(records), report_artifact_id),
            )
            return self._report_artifact(
                connection.execute("SELECT * FROM report_artifacts WHERE report_artifact_id = ?", (report_artifact_id,)).fetchone(),
                run=self._run(connection, run_row),
            )

    def list_report_artifacts(self, assessment_run_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            if connection.execute("SELECT 1 FROM assessment_runs WHERE assessment_run_id = ?", (assessment_run_id,)).fetchone() is None:
                raise DomainNotFoundError(f"评估运行不存在：{assessment_run_id}")
            run = self._run(
                connection,
                connection.execute("SELECT * FROM assessment_runs WHERE assessment_run_id = ?", (assessment_run_id,)).fetchone(),
            )
            rows = connection.execute("SELECT * FROM report_artifacts WHERE assessment_run_id = ? ORDER BY created_at DESC", (assessment_run_id,)).fetchall()
            return [self._report_artifact(row, run=run) for row in rows]

    def create_comparison_view(
        self,
        *,
        workspace_id: str,
        assessment_run_ids: list[str],
        dimensions: list[str],
        detail_snapshots: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        unique_run_ids = list(dict.fromkeys(assessment_run_ids))
        if len(unique_run_ids) < 2:
            raise DomainValidationError("对比视图至少需要两个不同的评估运行")
        with self._connection() as connection:
            self._get_workspace_row(connection, workspace_id)
            runs = []
            for run_id in unique_run_ids:
                row = connection.execute("SELECT * FROM assessment_runs WHERE assessment_run_id = ?", (run_id,)).fetchone()
                if row is None or row["workspace_id"] != workspace_id:
                    raise DomainConflictError("只能比较同一工作空间内的评估运行")
                if row["status"] not in COMPARABLE_RUN_STATUSES:
                    raise DomainConflictError("对比视图只能读取已完成或已归档运行")
                runs.append(self._run(connection, row))
            rule_versions = sorted({run["rule_version"] for run in runs})
            batch_ids = sorted({run["source_batch_id"] for run in runs})
            report_periods = sorted({run["batch_snapshot"].get("report_period", "未记录") for run in runs})
            reasons: list[str] = []
            if len(rule_versions) > 1:
                reasons.append("规则版本不同，不能直接比较")
            if len(batch_ids) > 1:
                reasons.append("数据批次不同，需核对报告期和口径后比较")
            if len(report_periods) > 1:
                reasons.append("报告期不同，不能直接比较")
            comparison_id = _new_id("cmp")
            now = _now()
            output_snapshot = {
                "enterprise_ids": [run["enterprise_id"] for run in runs],
                "enterprise_codes": [run["enterprise_code"] for run in runs],
                "run_statuses": {run["assessment_run_id"]: run["status"] for run in runs},
                "run_summaries": [
                    {
                        "assessment_run_id": run["assessment_run_id"],
                        "enterprise_code": run["enterprise_code"],
                        "source_batch_id": run["source_batch_id"],
                        "report_period": run["batch_snapshot"].get("report_period", "未记录"),
                        "rule_version": run["rule_version"],
                        "quality_gate_status": run["quality_gate_status"],
                        "status": run["status"],
                    }
                    for run in runs
                ],
                "run_details": detail_snapshots or [],
                "notice": "对比视图仅读取运行快照，不生成企业排名或未经验证的优劣结论。",
            }
            connection.execute(
                """INSERT INTO comparison_views(
                    comparison_view_id,workspace_id,dimensions_json,version_differences_json,
                    incomparability_reasons_json,output_snapshot_json,created_at
                ) VALUES(?,?,?,?,?,?,?)""",
                (
                    comparison_id,
                    workspace_id,
                    _json(dimensions),
                    _json({"rule_versions": rule_versions, "source_batch_ids": batch_ids, "report_periods": report_periods}),
                    _json(reasons),
                    _json(output_snapshot),
                    now,
                ),
            )
            connection.executemany(
                "INSERT INTO comparison_view_runs(comparison_view_id,assessment_run_id,position) VALUES(?,?,?)",
                [(comparison_id, run_id, position) for position, run_id in enumerate(unique_run_ids)],
            )
            return self._comparison(connection, comparison_id)

    @staticmethod
    def _comparison(connection: sqlite3.Connection, comparison_view_id: str) -> dict[str, Any]:
        row = connection.execute("SELECT * FROM comparison_views WHERE comparison_view_id = ?", (comparison_view_id,)).fetchone()
        if row is None:
            raise DomainNotFoundError(f"对比视图不存在：{comparison_view_id}")
        run_ids = [
            item["assessment_run_id"]
            for item in connection.execute(
                "SELECT assessment_run_id FROM comparison_view_runs WHERE comparison_view_id = ? ORDER BY position",
                (comparison_view_id,),
            ).fetchall()
        ]
        return {
            "comparison_view_id": comparison_view_id,
            "workspace_id": row["workspace_id"],
            "assessment_run_ids": run_ids,
            "enterprise_ids": _loads(row["output_snapshot_json"], {}).get("enterprise_ids", []),
            "enterprise_codes": _loads(row["output_snapshot_json"], {}).get("enterprise_codes", []),
            "simulated_data": True,
            "data_notice": SIMULATED_DATA_NOTICE,
            "dimensions": _loads(row["dimensions_json"], []),
            "version_differences": _loads(row["version_differences_json"], {}),
            "incomparability_reasons": _loads(row["incomparability_reasons_json"], []),
            "output_snapshot": _loads(row["output_snapshot_json"], {}),
            "created_at": row["created_at"],
        }

    def get_comparison_view(self, comparison_view_id: str) -> dict[str, Any]:
        validate_domain_id(comparison_view_id)
        with self._connection() as connection:
            return self._comparison(connection, comparison_view_id)

    def list_comparison_views(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            self._get_workspace_row(connection, workspace_id)
            rows = connection.execute(
                "SELECT comparison_view_id FROM comparison_views WHERE workspace_id = ? ORDER BY created_at DESC",
                (workspace_id,),
            ).fetchall()
            return [self._comparison(connection, row["comparison_view_id"]) for row in rows]
