from __future__ import annotations

import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import FIELD_CONTRACT_VERSION, MAX_UPLOAD_BYTES, PROJECT_ROOT, RULE_VERSION, SIMULATED_DATA_NOTICE
from .domain_schemas import (
    AssessmentRunCreate,
    AssessmentRunUpdate,
    ComparisonViewCreate,
    ConversationMessageCreate,
    ConversationTurnCreate,
    ModelConfigCreate,
    ReportArtifactCreate,
    ReportExportRequest,
    SourceBatchRegister,
    WorkspaceCreate,
    WorkflowResumeRequest,
    WorkflowReviewRequest,
    WorkflowStartRequest,
)
from .domain_store import (
    DomainConflictError,
    DomainNotFoundError,
    DomainStore,
    DomainValidationError,
)
from .knowledge import KnowledgeBuildBlocked, KnowledgeService
from .knowledge.schemas import KnowledgeSearchRequest
from .m1_core import WorkbookAnalyzer
from .model_providers import OpenAICompatibleSessionProvider, vision_route_with_capability
from .orchestration import OrchestrationService
from .parsers import classify_file, parse_file, sha256_bytes
from .reporting import build_basic_report
from .store import BatchStore, validate_artifact_name
from .workflows import AssessmentWorkflowRuntime, workflow_analysis_view


class ReportRequest(BaseModel):
    batch_id: str = Field(min_length=3)
    company_code: str = Field(min_length=1)


class AdminSessionRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


app = FastAPI(
    title="企业转型金融评估系统 M1",
    version=RULE_VERSION,
    description="配套Excel数据评估流程闭环；仅用于模拟数据开发测试。",
)
store = BatchStore()
domain_store: DomainStore | None = None
orchestration_service: OrchestrationService | None = None
workflow_runtime: AssessmentWorkflowRuntime | None = None
knowledge_service: KnowledgeService | None = None
STATIC_DIR = Path(__file__).resolve().parent / "static"
FRONTEND_DIST = STATIC_DIR / "frontend-dist"
_admin_sessions: dict[str, float] = {}

if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")


def _metadata(batch_id: str) -> dict[str, Any]:
    return store.load_json(batch_id, "metadata.json")


def _summary(batch_id: str) -> dict[str, Any]:
    return store.load_json(batch_id, "result.json")


def _analyzer(batch_id: str) -> WorkbookAnalyzer:
    analyzer = WorkbookAnalyzer(store.source_path(batch_id), batch_id)
    analyzer.load()
    return analyzer


def _require_batch(batch_id: str) -> dict[str, Any]:
    try:
        return _summary(batch_id)
    except (FileNotFoundError, json.JSONDecodeError):
        raise HTTPException(status_code=404, detail=f"批次不存在：{batch_id}")


def _require_usable_batch(batch_id: str) -> dict[str, Any]:
    summary = _require_batch(batch_id)
    validation = summary.get("validation", {})
    if summary.get("status") == "failed" or validation.get("status") == "failed":
        first_issue = (validation.get("validation_issues") or [{}])[0]
        message = first_issue.get("message") or "请修复工作簿后重新上传"
        raise HTTPException(status_code=409, detail=f"批次不可进入企业详情或报告流程：{message}")
    return summary


def _get_domain_store() -> DomainStore:
    global domain_store
    if domain_store is None:
        domain_store = DomainStore()
    return domain_store


def _get_knowledge_service() -> KnowledgeService:
    global knowledge_service
    current_store = _get_domain_store()
    if knowledge_service is None or knowledge_service.domain_store is not current_store:
        knowledge_service = KnowledgeService(current_store, analysis_loader=_run_analysis)
    return knowledge_service


DEFAULT_WORKBOOK_RELATIVE_PATH = Path(
    "27-多模态技术与数据治理赛道-碳迹可循，绿贷智评：基于多维度数据与行业标准的企业转型金融评估系统"
) / "配套数据.xlsx"


def _find_default_workbook() -> Path | None:
    """Locate the competition workbook shipped with the local project package."""
    candidates = [
        PROJECT_ROOT / DEFAULT_WORKBOOK_RELATIVE_PATH,
        PROJECT_ROOT / "配套数据.xlsx",
        Path(__file__).resolve().parent / "bundled_data" / "配套数据.xlsx",
        Path(__file__).resolve().parent / "bundled_data" / "default_workbook.xlsx",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _ensure_default_source_batch() -> dict[str, Any] | None:
    """Make the known competition workbook available without a user upload."""
    workbook_path = _find_default_workbook()
    if workbook_path is None:
        return None
    content = workbook_path.read_bytes()
    fingerprint = sha256_bytes(content)
    domain = _get_domain_store()
    existing = domain.get_source_batch_by_sha256(fingerprint)
    if existing is not None:
        try:
            _require_batch(existing["m1_batch_id"])
            return existing
        except HTTPException:
            # The durable domain record survived, but its parsed M1 runtime did not.
            # Re-ingest the same bytes and rebind the existing source_batch_id below.
            pass

    summary = _ingest_workbook(workbook_path.name, content)
    validation = summary.get("validation", {})
    return domain.ensure_source_batch_runtime(
        m1_batch_id=summary["batch_id"],
        source_filename=summary.get("source_filename", workbook_path.name),
        sha256=summary["sha256"],
        source="bundled_simulated_data",
        validation_status=summary.get("status", validation.get("status", "failed")),
        available_company_codes=validation.get("company_codes", []),
        simulated_data=True,
        metadata={
            "field_contract_version": summary.get("field_contract_version"),
            "quality_overview": summary.get("quality_overview"),
            "default_source": True,
            "source_path": workbook_path.name,
        },
    )


def _get_orchestration_service() -> OrchestrationService:
    global orchestration_service
    current_store = _get_domain_store()
    if orchestration_service is None or orchestration_service.domain_store is not current_store:
        orchestration_service = OrchestrationService(
            current_store,
            _run_analysis,
            provider_factory=lambda model_id: OpenAICompatibleSessionProvider.from_environment(
                model_id=model_id,
                model_config_loader=lambda selected_id: current_store.get_model_config(selected_id, include_secret=True),
            ),
            knowledge_searcher=lambda run_id, query, top_k, source_roles: _get_knowledge_service().search(
                run_id, query, top_k=top_k, source_roles=source_roles
            ),
        )
    return orchestration_service


def _get_workflow_runtime() -> AssessmentWorkflowRuntime:
    global workflow_runtime
    current_store = _get_domain_store()
    if workflow_runtime is None or workflow_runtime.domain_store is not current_store:
        workflow_runtime = AssessmentWorkflowRuntime(current_store, _run_workflow_analysis)
    return workflow_runtime


def _domain_error(exc: Exception) -> HTTPException:
    if isinstance(exc, DomainNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, DomainConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


async def _read_uploaded_content(file: UploadFile) -> tuple[str, str, bytes]:
    filename = file.filename or "attachment"
    file_type = classify_file(filename)
    if file_type is None:
        raise HTTPException(status_code=400, detail="仅支持XLSX、PDF、DOCX、PNG/JPG/WEBP/TIFF/BMP文件")
    chunks: list[bytes] = []
    total = 0
    while total <= MAX_UPLOAD_BYTES:
        chunk = await file.read(min(1024 * 1024, MAX_UPLOAD_BYTES + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"上传文件超过限制（{MAX_UPLOAD_BYTES // (1024 * 1024)} MiB）")
    content = b"".join(chunks)
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    return filename, file_type, content


def _mime_matches(file_type: str, mime_type: str | None) -> bool:
    if not mime_type or mime_type == "application/octet-stream":
        return True
    normalized = mime_type.split(";", 1)[0].strip().lower()
    expected = {
        "pdf": {"application/pdf"},
        "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        "image": set(),
    }
    if file_type == "image":
        return normalized.startswith("image/")
    return normalized in expected.get(file_type, set())


def _safe_report_id(batch_id: str, company_code: str) -> str:
    safe_code = re.sub(r"[^A-Za-z0-9_-]+", "_", company_code).strip("_") or "company"
    report_id = f"m1-{batch_id}-{safe_code}"
    try:
        return validate_artifact_name(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="企业代号无法生成安全报告标识") from exc


def _resolve_report_file(assessment_run_id: str, report_artifact_id: str) -> tuple[dict[str, Any], Path]:
    report_store = _get_domain_store()
    artifact = report_store.get_report_artifact(assessment_run_id, report_artifact_id)
    path = (report_store.root / artifact["relative_path"]).resolve()
    if report_store.root not in path.parents or not path.is_file():
        raise DomainNotFoundError("报告文件不存在或已移出应用数据目录")
    return artifact, path


def _open_local_directory(directory: Path) -> bool:
    """Open a resolved local directory without invoking a shell."""
    try:
        system = platform.system()
        if system == "Darwin":
            command = ["open", str(directory)]
        elif system == "Windows":
            os.startfile(str(directory))  # type: ignore[attr-defined]
            return True
        else:
            command = ["xdg-open", str(directory)]
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


@app.get("/", response_class=FileResponse)
def index() -> FileResponse:
    frontend_index = FRONTEND_DIST / "index.html"
    return FileResponse(frontend_index if frontend_index.is_file() else STATIC_DIR / "index.html")


@app.get("/favicon.svg", response_class=FileResponse)
def favicon() -> FileResponse:
    frontend_favicon = FRONTEND_DIST / "favicon.svg"
    if frontend_favicon.is_file():
        return FileResponse(frontend_favicon, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="favicon不可用")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "rule_version": RULE_VERSION, "simulated_data": True}


@app.get("/api/v1/knowledge/indexes/current")
def current_knowledge_index() -> dict[str, Any]:
    return _get_knowledge_service().index_status()


@app.post("/api/v1/knowledge/indexes/dry-run")
def dry_run_knowledge_index(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_admin_session(authorization)
    return _get_knowledge_service().dry_run()


@app.post("/api/v1/knowledge/indexes/rebuild")
def rebuild_knowledge_index(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_admin_session(authorization)
    try:
        return _get_knowledge_service().rebuild()
    except KnowledgeBuildBlocked as exc:
        raise _domain_error(exc) from exc


@app.get("/api/v1/knowledge/sources")
def list_knowledge_sources(
    visibility: str | None = Query(default=None),
    source_role: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_admin_session(authorization)
    return {"sources": _get_knowledge_service().list_sources(visibility=visibility, source_role=source_role)}


@app.get("/api/v1/knowledge/tests/gold")
def run_knowledge_gold_tests(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_admin_session(authorization)
    results = _get_knowledge_service().run_gold_tests()
    status_counts = {}
    for item in results:
        status = str(item.get("status") or ("passed" if item.get("passed") else "failed"))
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "test_count": len(results),
        "passed_count": status_counts.get("passed", 0),
        "correct_degrade_count": status_counts.get("correct_degrade", 0),
        "failed_count": status_counts.get("failed", 0),
        "not_executed_count": status_counts.get("not_executed", 0),
        "env_blocked_count": status_counts.get("env_blocked", 0),
        "status_counts": status_counts,
        "results": results,
        "notice": "13号44条仅验证M5准入、行业过滤、治理隔离和负向门禁，不代表检索准确率、企业效果或正式规则覆盖。",
    }


@app.post("/api/v1/assessment-runs/{assessment_run_id}/knowledge/search")
def search_run_knowledge(assessment_run_id: str, request: KnowledgeSearchRequest) -> dict[str, Any]:
    try:
        return _get_knowledge_service().search(
            assessment_run_id,
            request.query,
            top_k=request.top_k,
            source_roles=request.source_roles,
        )
    except (DomainConflictError, DomainValidationError, DomainNotFoundError, KnowledgeBuildBlocked) as exc:
        raise _domain_error(exc) from exc


@app.get("/api/v1/assessment-runs/{assessment_run_id}/knowledge/retrievals")
def list_run_knowledge_retrievals(assessment_run_id: str) -> dict[str, Any]:
    try:
        return {"assessment_run_id": assessment_run_id, "retrievals": _get_knowledge_service().list_retrievals(assessment_run_id)}
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.get("/api/v1/assessment-runs/{assessment_run_id}/knowledge/chunks/{chunk_id}")
def get_run_knowledge_chunk(assessment_run_id: str, chunk_id: str) -> dict[str, Any]:
    try:
        return _get_knowledge_service().get_chunk(assessment_run_id, chunk_id)
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.post("/api/v1/workspaces")
def create_workspace(request: WorkspaceCreate) -> dict[str, Any]:
    try:
        return _get_domain_store().create_workspace(request.name)
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.get("/api/v1/workspaces")
def list_workspaces() -> dict[str, Any]:
    return {"workspaces": _get_domain_store().list_workspaces()}


@app.get("/api/v1/workspaces/{workspace_id}")
def get_workspace(workspace_id: str) -> dict[str, Any]:
    try:
        return _get_domain_store().get_workspace(workspace_id)
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.post("/api/v1/source-batches")
def register_source_batch(request: SourceBatchRegister) -> dict[str, Any]:
    summary = _require_batch(request.batch_id)
    validation = summary.get("validation", {})
    try:
        return _get_domain_store().register_source_batch(
            m1_batch_id=request.batch_id,
            source_filename=summary.get("source_filename", "upload.xlsx"),
            sha256=summary["sha256"],
            source=request.source,
            validation_status=summary.get("status", validation.get("status", "failed")),
            available_company_codes=validation.get("company_codes", []),
            simulated_data=True,
            metadata={
                "field_contract_version": summary.get("field_contract_version"),
                "quality_overview": summary.get("quality_overview"),
            },
        )
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.get("/api/v1/source-batches/default")
def get_default_source_batch() -> dict[str, Any]:
    try:
        source = _ensure_default_source_batch()
    except (DomainConflictError, DomainValidationError, DomainNotFoundError, OSError, ValueError) as exc:
        raise _domain_error(exc) from exc
    if source is None:
        raise HTTPException(status_code=404, detail="项目目录中未找到配套数据.xlsx")
    return source


@app.get("/api/v1/source-batches/{source_batch_id}")
def get_source_batch(source_batch_id: str) -> dict[str, Any]:
    try:
        return _get_domain_store().get_source_batch(source_batch_id)
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.post("/api/v1/workspaces/{workspace_id}/runs")
def create_assessment_run(workspace_id: str, request: AssessmentRunCreate) -> dict[str, Any]:
    try:
        return _get_domain_store().create_assessment_run(
            workspace_id=workspace_id,
            enterprise_code=request.enterprise_code,
            source_batch_id=request.source_batch_id,
            run_name=request.run_name,
            rule_version=request.rule_version,
            model_config=request.model_config_data,
            basic_info_index=request.basic_info_index,
        )
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.get("/api/v1/workspaces/{workspace_id}/runs")
def list_assessment_runs(workspace_id: str) -> dict[str, Any]:
    try:
        return {"workspace_id": workspace_id, "runs": _get_domain_store().list_assessment_runs(workspace_id)}
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.get("/api/v1/assessment-runs/{assessment_run_id}")
def get_assessment_run(assessment_run_id: str) -> dict[str, Any]:
    try:
        return _get_domain_store().get_assessment_run(assessment_run_id)
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


def _run_analysis(assessment_run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    run = _get_domain_store().get_assessment_run(assessment_run_id)
    if not run.get("m1_batch_id"):
        raise DomainConflictError("评估运行没有可回放的M1数据批次")
    _require_usable_batch(run["m1_batch_id"])
    try:
        analysis = _analyzer(run["m1_batch_id"]).analyze_company(run["enterprise_code"])
    except KeyError as exc:
        raise DomainConflictError(f"运行绑定企业无法在数据批次中回放：{run['enterprise_code']}") from exc
    except (FileNotFoundError, ValueError, OSError) as exc:
        raise DomainConflictError(f"运行数据批次原件不可用：{type(exc).__name__}") from exc
    return run, analysis


def _run_workflow_analysis(assessment_run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    run, analysis = _run_analysis(assessment_run_id)
    return run, workflow_analysis_view(analysis)


@app.get("/api/v1/assessment-runs/{assessment_run_id}/company-detail")
def get_run_company_detail(assessment_run_id: str) -> dict[str, Any]:
    try:
        run, analysis = _run_analysis(assessment_run_id)
        return {
            "workspace_id": run["workspace_id"],
            "assessment_run_id": run["assessment_run_id"],
            "enterprise_id": run["enterprise_id"],
            "enterprise_code": run["enterprise_code"],
            "source_batch_id": run["source_batch_id"],
            "m1_batch_id": run["m1_batch_id"],
            "simulated_data": run["simulated_data"],
            "data_notice": run["data_notice"],
            "rule_version": run["rule_version"],
            "model_config": run["model_config"],
            "run_status": run["status"],
            "analysis": analysis,
        }
    except (DomainConflictError, DomainValidationError, DomainNotFoundError, HTTPException) as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise _domain_error(exc) from exc


@app.get("/api/v1/assessment-runs/{assessment_run_id}/companies/{company_code}")
def get_run_scoped_company_detail(assessment_run_id: str, company_code: str) -> dict[str, Any]:
    try:
        run = _get_domain_store().get_assessment_run(assessment_run_id)
        if company_code != run["enterprise_code"]:
            raise DomainConflictError("跨运行企业访问被阻断：请求企业与当前评估运行绑定企业不一致")
        return get_run_company_detail(assessment_run_id)
    except (DomainConflictError, DomainValidationError, DomainNotFoundError, HTTPException) as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise _domain_error(exc) from exc


@app.post("/api/v1/assessment-runs/{assessment_run_id}/reports/basic")
def create_run_basic_report(assessment_run_id: str) -> dict[str, Any]:
    try:
        run, analysis = _run_analysis(assessment_run_id)
        safe_code = re.sub(r"[^A-Za-z0-9_-]+", "_", run["enterprise_code"]).strip("_") or "enterprise"
        markdown, payload = build_basic_report(analysis)
        generated_at = datetime.fromisoformat(payload["generated_at"])
        timestamp = generated_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        relative_path = f"reports/{assessment_run_id}/{safe_code}-{assessment_run_id}-basic-v1-{timestamp}.md"
        artifacts = _get_domain_store()
        sha256 = artifacts.save_report_file(relative_path, markdown)
        artifact = artifacts.create_report_artifact(
            assessment_run_id,
            report_type="basic_m2",
            file_format="md",
            relative_path=relative_path,
            version="v1",
            sha256=sha256,
            generation_config={"mode": "offline", "source": "m1_basic_report"},
            export_records=[{"format": "md", "status": "saved"}],
        )
        if run["status"] == "draft":
            run = artifacts.update_assessment_run(assessment_run_id, status="report_ready", quality_gate_status=run["quality_gate_status"])
        return {"artifact": artifact, "markdown": markdown, "report": payload, "assessment_run": run}
    except (DomainConflictError, DomainValidationError, DomainNotFoundError, HTTPException) as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise _domain_error(exc) from exc


@app.get("/api/v1/assessment-runs/{assessment_run_id}/reports/{report_artifact_id}")
def get_run_report_content(assessment_run_id: str, report_artifact_id: str) -> dict[str, Any]:
    try:
        artifact, path = _resolve_report_file(assessment_run_id, report_artifact_id)
        return {
            "artifact": artifact,
            "assessment_run": _get_domain_store().get_assessment_run(assessment_run_id),
            "markdown": path.read_text(encoding="utf-8"),
        }
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.get("/api/v1/assessment-runs/{assessment_run_id}/reports/{report_artifact_id}/download")
def download_run_report(assessment_run_id: str, report_artifact_id: str) -> FileResponse:
    try:
        artifact, path = _resolve_report_file(assessment_run_id, report_artifact_id)
        media_type = "text/markdown; charset=utf-8" if artifact["file_format"] == "md" else "application/octet-stream"
        return FileResponse(path, media_type=media_type, filename=path.name)
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.post("/api/v1/assessment-runs/{assessment_run_id}/reports/{report_artifact_id}/open-directory")
def open_run_report_directory(assessment_run_id: str, report_artifact_id: str) -> dict[str, Any]:
    try:
        _artifact, path = _resolve_report_file(assessment_run_id, report_artifact_id)
        opened = _open_local_directory(path.parent)
        relative_directory = path.parent.relative_to(_get_domain_store().root).as_posix()
        return {
            "assessment_run_id": assessment_run_id,
            "report_artifact_id": report_artifact_id,
            "opened": opened,
            "directory_relative_path": relative_directory,
            "notice": "目录打开请求仅作用于运行后端所在的本机；报告和共享文档不暴露本机绝对路径。",
        }
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.post("/api/v1/assessment-runs/{assessment_run_id}/reports/{report_artifact_id}/export")
def export_run_report(
    assessment_run_id: str,
    report_artifact_id: str,
    request: ReportExportRequest,
) -> dict[str, Any]:
    try:
        artifact, path = _resolve_report_file(assessment_run_id, report_artifact_id)
        target_directory = Path(request.target_directory).expanduser().resolve()
        if not target_directory.is_dir():
            raise DomainValidationError("导出目录不存在或不是目录")
        destination = target_directory / path.name
        if destination.resolve() == path:
            raise DomainConflictError("导出目录不能与报告原目录相同")
        shutil.copy2(path, destination)
        updated_artifact = _get_domain_store().record_report_export(
            assessment_run_id,
            report_artifact_id,
            {
                "format": artifact["file_format"],
                "status": "exported",
                "file_name": destination.name,
                "exported_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {
            "assessment_run_id": assessment_run_id,
            "report_artifact_id": report_artifact_id,
            "artifact": updated_artifact,
            "exported_file": destination.name,
            "exported_path": str(destination),
            "data_notice": SIMULATED_DATA_NOTICE,
        }
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.patch("/api/v1/assessment-runs/{assessment_run_id}")
def update_assessment_run(assessment_run_id: str, request: AssessmentRunUpdate) -> dict[str, Any]:
    try:
        return _get_domain_store().update_assessment_run(
            assessment_run_id,
            status=request.status,
            quality_gate_status=request.quality_gate_status,
        )
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.post("/api/v1/assessment-runs/{assessment_run_id}/messages")
def create_message(assessment_run_id: str, request: ConversationMessageCreate) -> dict[str, Any]:
    try:
        return _get_domain_store().create_message(
            assessment_run_id,
            role=request.role,
            message_type=request.message_type,
            content=request.content,
            tool_name=request.tool_name,
            payload=request.payload,
        )
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.get("/api/v1/assessment-runs/{assessment_run_id}/messages")
def list_messages(assessment_run_id: str) -> dict[str, Any]:
    try:
        return {"assessment_run_id": assessment_run_id, "messages": _get_domain_store().list_messages(assessment_run_id)}
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.post("/api/v1/assessment-runs/{assessment_run_id}/conversation/turn")
def orchestration_turn(assessment_run_id: str, request: ConversationTurnCreate) -> dict[str, Any]:
    try:
        return _get_orchestration_service().run_turn(
            assessment_run_id,
            request.content,
            model_id=request.model_id,
            force_offline=request.mode == "offline",
        )
    except (DomainConflictError, DomainValidationError, DomainNotFoundError, HTTPException) as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise _domain_error(exc) from exc


@app.post("/api/v1/assessment-runs/{assessment_run_id}/conversation/stop")
def stop_orchestration(assessment_run_id: str) -> dict[str, Any]:
    try:
        return _get_orchestration_service().request_stop(assessment_run_id)
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.post("/api/v1/assessment-runs/{assessment_run_id}/conversation/retry")
def retry_orchestration(assessment_run_id: str, request: ConversationTurnCreate | None = None) -> dict[str, Any]:
    try:
        return _get_orchestration_service().retry_last_turn(
            assessment_run_id,
            model_id=request.model_id if request else None,
        )
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.get("/api/v1/assessment-runs/{assessment_run_id}/conversation/summary")
def list_process_summary(assessment_run_id: str) -> dict[str, Any]:
    try:
        return _get_orchestration_service().list_process_summary(assessment_run_id)
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.get("/api/v1/assessment-runs/{assessment_run_id}/workflows")
def list_assessment_workflows(assessment_run_id: str) -> dict[str, Any]:
    try:
        return _get_workflow_runtime().list(assessment_run_id)
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.post("/api/v1/assessment-runs/{assessment_run_id}/workflows/start")
def start_assessment_workflow(assessment_run_id: str, request: WorkflowStartRequest) -> dict[str, Any]:
    try:
        return _get_workflow_runtime().start(assessment_run_id, request.workflow_name)
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.post("/api/v1/assessment-runs/{assessment_run_id}/workflows/{workflow_name}/pause")
def pause_assessment_workflow(assessment_run_id: str, workflow_name: str) -> dict[str, Any]:
    try:
        return _get_workflow_runtime().pause(assessment_run_id, workflow_name)
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.post("/api/v1/assessment-runs/{assessment_run_id}/workflows/{workflow_name}/resume")
def resume_assessment_workflow(
    assessment_run_id: str,
    workflow_name: str,
    request: WorkflowResumeRequest,
) -> dict[str, Any]:
    try:
        return _get_workflow_runtime().resume(
            assessment_run_id,
            workflow_name,
            request.answers,
            confirm_no_additional=request.confirm_no_additional,
        )
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.post("/api/v1/assessment-runs/{assessment_run_id}/workflows/{workflow_name}/review")
def review_assessment_workflow(
    assessment_run_id: str,
    workflow_name: str,
    request: WorkflowReviewRequest,
) -> dict[str, Any]:
    try:
        return _get_workflow_runtime().review(assessment_run_id, workflow_name, request.decision)
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


def _require_admin_session(authorization: str | None) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="需要管理员诊断会话")
    token = authorization[7:].strip()
    expires_at = _admin_sessions.get(token)
    if not expires_at or expires_at <= time.time():
        _admin_sessions.pop(token, None)
        raise HTTPException(status_code=401, detail="管理员诊断会话已失效")


@app.get("/api/v1/assessment-runs/{assessment_run_id}/conversation/events")
def list_orchestration_events(assessment_run_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    try:
        _require_admin_session(authorization)
        return {
            "assessment_run_id": assessment_run_id,
            "events": _get_orchestration_service().list_events(assessment_run_id),
        }
    except (DomainConflictError, DomainValidationError, DomainNotFoundError, HTTPException) as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise _domain_error(exc) from exc


@app.post("/api/v1/assessment-runs/{assessment_run_id}/reports")
def create_report_artifact(assessment_run_id: str, request: ReportArtifactCreate) -> dict[str, Any]:
    try:
        return _get_domain_store().create_report_artifact(
            assessment_run_id,
            report_type=request.report_type,
            file_format=request.file_format,
            relative_path=request.relative_path,
            version=request.version,
            sha256=request.sha256,
            generation_config=request.generation_config,
            export_records=request.export_records,
        )
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.get("/api/v1/assessment-runs/{assessment_run_id}/reports")
def list_report_artifacts(assessment_run_id: str) -> dict[str, Any]:
    try:
        return {"assessment_run_id": assessment_run_id, "reports": _get_domain_store().list_report_artifacts(assessment_run_id)}
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.get("/api/v1/parsers/capabilities")
def parser_capabilities() -> dict[str, Any]:
    from .parsers.multimodal import _ocr_capability
    from .parsers.external_multimodal import ExternalMultimodalClient

    ocr = _ocr_capability()
    external = ExternalMultimodalClient.from_environment().capability()
    return {
        "offline": True,
        "file_types": {
            "xlsx": {"available": True, "mode": "m1_five_table_contract"},
            "pdf": {"available": True, "mode": "native_text_and_table; scanned_pdf_external_multimodal"},
            "docx": {"available": True, "mode": "paragraph_table_and_image_reference"},
            "image": {
                "available": external["available"] or ocr["available"],
                "mode": "external_multimodal_api" if external["available"] else "ocr" if ocr["available"] else "validation_only",
            },
        },
        "ocr": ocr,
        "external_multimodal": external,
        "notice": "图片和扫描PDF优先使用后端受控的外部多模态API；未配置或调用失败时降级为待复核，不影响离线XLSX/PDF原生文本/DOCX流程。",
    }


@app.get("/api/v1/model-providers")
@app.get("/api/v1/models")
def session_model_capabilities() -> dict[str, Any]:
    capability = OpenAICompatibleSessionProvider.from_environment().capability()
    models = OpenAICompatibleSessionProvider.available_models_from_environment(_get_domain_store().list_model_configs())
    return {
        "models": models,
        "offline": {
            "available": True,
            "mode": "offline",
            "display_name": "离线基础流程",
            "reason": "离线模式不作为外部模型选项；文件登记、五张表校验、企业查询、目录匹配和基础报告仍可用。",
        },
        "external_configured": bool(models),
        "default_model_id": capability.get("model_id") if capability.get("available") else None,
        "notice": "模型列表只显示已在后端受控环境中配置的外部模型；规则、权重、阈值和评分配置不属于模型选项。",
    }


@app.post("/api/v1/model-configs")
def create_model_config(request: ModelConfigCreate) -> dict[str, Any]:
    try:
        return {
            "model": _get_domain_store().create_model_config(
                model_name=request.model_name,
                display_name=request.display_name or request.model_name,
                provider_id=request.provider_id,
                base_url=request.base_url,
                api_key=request.api_key,
                supports_vision=request.supports_vision,
            ),
            "notice": "API key仅保存在本机后端应用数据中，不会返回到模型列表、前端日志或报告。",
        }
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.get("/api/v1/model-configs")
def list_model_configs() -> dict[str, Any]:
    return {
        "models": _get_domain_store().list_model_configs(),
        "notice": "列表只返回脱敏配置；API key不会返回。",
    }


@app.delete("/api/v1/model-configs/{model_config_id}")
def delete_model_config(model_config_id: str) -> dict[str, Any]:
    try:
        return _get_domain_store().delete_model_config(model_config_id)
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.post("/api/v1/admin/session")
def create_admin_session(request: AdminSessionRequest) -> dict[str, Any]:
    """Gate the optional diagnostics surface without shipping a default password."""
    configured_password = os.environ.get("TRANSITION_FINANCE_ADMIN_PASSWORD", "")
    if not configured_password:
        raise HTTPException(status_code=503, detail="管理员口令尚未配置，请在受控环境设置TRANSITION_FINANCE_ADMIN_PASSWORD")
    if not secrets.compare_digest(request.password, configured_password):
        raise HTTPException(status_code=401, detail="管理员口令不正确")
    access_token = secrets.token_urlsafe(32)
    _admin_sessions[access_token] = time.time() + 1800
    return {"authenticated": True, "scope": "diagnostics", "access_token": access_token, "expires_in_seconds": 1800}


@app.post("/api/v1/assessment-runs/{assessment_run_id}/attachments")
async def upload_run_attachment(
    assessment_run_id: str,
    file: UploadFile = File(...),
    session_model_id: str | None = Form(default=None),
) -> dict[str, Any]:
    try:
        run = _get_domain_store().get_assessment_run(assessment_run_id)
        filename, file_type, content = await _read_uploaded_content(file)
        sha256 = sha256_bytes(content)
        domain = _get_domain_store()
        relative_path = domain.save_attachment_file(sha256, filename, content)
        if file_type == "xlsx":
            source_batch = domain.get_source_batch(run["source_batch_id"])
            if sha256 != source_batch["sha256"]:
                parse_result = {
                    "status": "blocked_conflict",
                    "file_type": "xlsx",
                    "parser": "m1-batch-boundary",
                    "expected_enterprise_code": run["enterprise_code"],
                    "detected_enterprise_codes": [],
                    "merge_allowed": False,
                    "fact_eligible": False,
                    "confidence": 0.0,
                    "confidence_threshold": 0.8,
                    "evidence": [],
                    "issues": [{
                        "code": "source_batch_mismatch",
                        "severity": "error",
                        "message": "XLSX与当前运行绑定批次哈希不同；不能覆盖当前运行，请新建运行并登记新批次。",
                        "location": None,
                    }],
                    "metadata": {"sha256": sha256, "bound_source_batch_sha256": source_batch["sha256"]},
                    "reference_only": {"detected": False, "model_context_excluded": True},
                }
            else:
                parse_result = {
                    "status": "passed",
                    "file_type": "xlsx",
                    "parser": "m1-workbook-link",
                    "expected_enterprise_code": run["enterprise_code"],
                    "detected_enterprise_codes": [run["enterprise_code"]],
                    "merge_allowed": True,
                    "fact_eligible": True,
                    "confidence": 1.0,
                    "confidence_threshold": 0.8,
                    "evidence": [{
                        "evidence_id": "m1-company-binding",
                        "kind": "m1_company_binding",
                        "location": {"sheet": "基本信息", "field": "企业代号"},
                        "text_excerpt": run["enterprise_code"],
                        "confidence": 1.0,
                        "source_field": "企业代号",
                    }],
                    "issues": [],
                    "metadata": {"sha256": sha256, "source_batch_id": run["source_batch_id"]},
                    "reference_only": {"detected": False, "model_context_excluded": True},
                }
        else:
            selected_model_id = session_model_id or (run.get("model_config") or {}).get("model_id")
            custom_model_config = None
            if selected_model_id:
                try:
                    custom_model_config = domain.get_model_config(selected_model_id, include_secret=True)
                except (DomainValidationError, DomainNotFoundError):
                    custom_model_config = None
            model_routing = (
                vision_route_with_capability(
                    selected_model_id,
                    supports_vision=custom_model_config["supports_vision"] if custom_model_config else None,
                )
                if file_type in {"image", "pdf"}
                else None
            )
            external_client = None
            if model_routing is not None:
                from .parsers.external_multimodal import ExternalMultimodalClient

                if custom_model_config and model_routing["vision_model_id"] == selected_model_id:
                    candidate_client = ExternalMultimodalClient.from_model_config(custom_model_config)
                else:
                    candidate_client = ExternalMultimodalClient.from_environment(model_override=model_routing["vision_model_id"])
                if candidate_client.configured:
                    external_client = candidate_client
            parse_path = domain.root / relative_path
            if external_client is None:
                parse_result = parse_file(parse_path, filename, run["enterprise_code"])
            else:
                parse_result = parse_file(
                    parse_path,
                    filename,
                    run["enterprise_code"],
                    external_client=external_client,
                )
            if model_routing is not None:
                parse_result.setdefault("metadata", {})["model_routing"] = model_routing
        if file.content_type and file.content_type != "application/octet-stream":
            parse_result.setdefault("metadata", {})["reported_mime_type"] = file.content_type
            if not _mime_matches(file_type, file.content_type):
                parse_result.setdefault("issues", []).append({
                    "code": "mime_mismatch",
                    "severity": "warning",
                    "message": f"扩展名识别为{file_type}，但上传MIME为{file.content_type}；已保留原件并要求复核。",
                    "location": None,
                })
                if parse_result.get("status") == "passed":
                    parse_result["status"] = "needs_review"
                    parse_result["merge_allowed"] = False
                    parse_result["fact_eligible"] = False
        attachment = domain.create_attachment(
            assessment_run_id,
            source_filename=filename,
            file_type=file_type,
            mime_type=file.content_type,
            file_size=len(content),
            sha256=sha256,
            relative_path=relative_path,
            parse_result=parse_result,
        )
        return {
            "assessment_run_id": assessment_run_id,
            "enterprise_code": run["enterprise_code"],
            "attachment": attachment,
            "parse": attachment["parse_result"],
            "model_routing": (attachment["parse_result"].get("metadata") or {}).get("model_routing"),
            "merge_blocked": not attachment["merge_allowed"],
            "data_notice": SIMULATED_DATA_NOTICE,
        }
    except (DomainConflictError, DomainValidationError, DomainNotFoundError, HTTPException) as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise _domain_error(exc) from exc


@app.get("/api/v1/assessment-runs/{assessment_run_id}/attachments")
def list_run_attachments(assessment_run_id: str) -> dict[str, Any]:
    try:
        return {
            "assessment_run_id": assessment_run_id,
            "attachments": _get_domain_store().list_attachments(assessment_run_id),
            "data_notice": SIMULATED_DATA_NOTICE,
        }
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.get("/api/v1/assessment-runs/{assessment_run_id}/attachments/{attachment_id}")
def get_run_attachment(assessment_run_id: str, attachment_id: str) -> dict[str, Any]:
    try:
        return _get_domain_store().get_attachment(assessment_run_id, attachment_id)
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.post("/api/v1/comparison-views")
def create_comparison_view(request: ComparisonViewCreate) -> dict[str, Any]:
    try:
        domain = _get_domain_store()
        detail_snapshots: list[dict[str, Any]] = []
        for assessment_run_id in dict.fromkeys(request.assessment_run_ids):
            run = domain.get_assessment_run(assessment_run_id)
            if run["workspace_id"] != request.workspace_id:
                raise DomainConflictError("只能比较同一工作空间内的评估运行")
            if run["status"] not in {"completed", "archived"}:
                raise DomainConflictError("对比视图只能读取已完成或已归档运行")
            _run, analysis = _run_analysis(assessment_run_id)
            issues = analysis.get("quality_issues", [])
            severity_counts = {
                severity: sum(item.get("severity") == severity for item in issues)
                for severity in ("error", "warning", "info")
            }
            catalog = analysis.get("catalog_matches", {})
            detail_snapshots.append(
                {
                    "assessment_run_id": run["assessment_run_id"],
                    "enterprise_code": run["enterprise_code"],
                    "enterprise_basic_info": analysis.get("input_data", {}).get("basic_info", {}),
                    "data_quality": {
                        "issue_count": len(issues),
                        "severity_counts": severity_counts,
                        "issues": issues[:20],
                    },
                    "energy_trend": analysis.get("energy_trend", {}),
                    "catalog_matches": {
                        "status": catalog.get("status"),
                        "manual_review_required": catalog.get("manual_review_required"),
                        "candidates": catalog.get("candidates", [])[:12],
                    },
                    "reference_comparison": analysis.get("reference_comparison", {}),
                    "notice": "以上为当前运行已生成的结构化事实快照；参考结论仅作独立对照，不进入模型输入或事实特征。",
                }
            )
        return domain.create_comparison_view(
            workspace_id=request.workspace_id,
            assessment_run_ids=request.assessment_run_ids,
            dimensions=request.dimensions,
            detail_snapshots=detail_snapshots,
        )
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.get("/api/v1/comparison-views/{comparison_view_id}")
def get_comparison_view(comparison_view_id: str) -> dict[str, Any]:
    try:
        return _get_domain_store().get_comparison_view(comparison_view_id)
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


@app.get("/api/v1/workspaces/{workspace_id}/comparison-views")
def list_workspace_comparison_views(workspace_id: str) -> dict[str, Any]:
    try:
        return {
            "workspace_id": workspace_id,
            "comparisons": _get_domain_store().list_comparison_views(workspace_id),
        }
    except (DomainConflictError, DomainValidationError, DomainNotFoundError) as exc:
        raise _domain_error(exc) from exc


def _ingest_workbook(filename: str, content: bytes) -> dict[str, Any]:
    """Save, parse, and persist one workbook using the same path for upload/default data."""
    metadata = store.create_batch(filename, content)
    try:
        analyzer = WorkbookAnalyzer(store.source_path(metadata["batch_id"]), metadata["batch_id"])
        summary = analyzer.batch_summary(metadata)
    except Exception as exc:  # malformed ZIP/encrypted workbook is a readable batch error
        summary = {
            "batch_id": metadata["batch_id"],
            "source_filename": metadata["source_filename"],
            "file_size": metadata["file_size"],
            "sha256": metadata["sha256"],
            "received_at": metadata["received_at"],
            "simulated_data": True,
            "data_notice": SIMULATED_DATA_NOTICE,
            "status": "failed",
            "processing_stage": "failed",
            "rule_version": RULE_VERSION,
            "field_contract_version": FIELD_CONTRACT_VERSION,
            "quality_overview": {
                "structural": {"issue_count": 1, "error_count": 1, "warning_count": 0},
                "enterprise_derived": {
                    "status": "blocked",
                    "issue_count": 0,
                    "affected_company_count": 0,
                    "notice": "工作簿无法读取，未执行企业级派生质量聚合。",
                },
            },
            "validation": {
                "status": "failed",
                "field_contract_version": FIELD_CONTRACT_VERSION,
                "error_count": 1,
                "warning_count": 0,
                "issue_count": 1,
                "validation_issues": [
                    {
                        "issue_id": "workbook-read-error",
                        "batch_id": metadata["batch_id"],
                        "company_code": None,
                        "sheet_name": None,
                        "row_number": None,
                        "field": None,
                        "rule": "workbook_readable",
                        "severity": "error",
                        "message": f"工作簿无法读取：{type(exc).__name__}: {exc}",
                        "original_value": None,
                        "status": "待处理",
                        "evidence": {"rule_version": RULE_VERSION},
                    }
                ],
            },
        }
    store.save_json(metadata["batch_id"], "result.json", summary)
    return summary


@app.post("/api/v1/documents")
async def upload_document(file: UploadFile = File(...)) -> dict[str, Any]:
    filename = file.filename or "upload.xlsx"
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="M1当前只接收.xlsx文件")
    chunks: list[bytes] = []
    total = 0
    while total <= MAX_UPLOAD_BYTES:
        chunk = await file.read(min(1024 * 1024, MAX_UPLOAD_BYTES + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"上传文件超过M1限制（{MAX_UPLOAD_BYTES // (1024 * 1024)} MiB）")
    content = b"".join(chunks)
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    return _ingest_workbook(filename, content)


@app.get("/api/v1/jobs/{batch_id}")
def get_job(batch_id: str) -> dict[str, Any]:
    return _require_batch(batch_id)


@app.get("/api/v1/batches/{batch_id}/companies")
def list_companies(batch_id: str) -> dict[str, Any]:
    summary = _require_batch(batch_id)
    validation = summary.get("validation", {})
    return {
        "batch_id": batch_id,
        "status": summary.get("status"),
        "simulated_data": True,
        "data_notice": SIMULATED_DATA_NOTICE,
        "companies": [] if summary.get("status") == "failed" else validation.get("company_codes", []),
        "follow_up_allowed": summary.get("status") != "failed",
        "diagnostic": None if summary.get("status") != "failed" else "该批次校验失败，不能继续进入企业详情或报告流程。",
    }


def _resolve_batch(batch_id: str | None) -> str:
    if batch_id:
        _require_batch(batch_id)
        return batch_id
    candidates = sorted(store.batches_root.glob("m1-*/result.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise HTTPException(status_code=404, detail="尚未上传工作簿")
    return candidates[0].parent.name


@app.get("/api/v1/companies/{company_code}")
def company_detail(company_code: str, batch_id: str | None = Query(default=None)) -> dict[str, Any]:
    resolved = _resolve_batch(batch_id)
    _require_usable_batch(resolved)
    try:
        analyzer = _analyzer(resolved)
        return analyzer.analyze_company(company_code)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (FileNotFoundError, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=f"批次原件不可用，无法继续分析：{type(exc).__name__}") from exc


@app.get("/api/v1/companies/{company_code}/energy-trend")
def company_energy_trend(company_code: str, batch_id: str | None = Query(default=None)) -> dict[str, Any]:
    detail = company_detail(company_code, batch_id)
    return {
        "batch_id": detail["batch_id"],
        "company_code": company_code,
        "simulated_data": True,
        "data_notice": SIMULATED_DATA_NOTICE,
        "energy_trend": detail["energy_trend"],
        "quality_issues": detail["quality_issues"],
    }


@app.get("/api/v1/companies/{company_code}/catalog-matches")
def company_catalog_matches(company_code: str, batch_id: str | None = Query(default=None)) -> dict[str, Any]:
    detail = company_detail(company_code, batch_id)
    return {
        "batch_id": detail["batch_id"],
        "company_code": company_code,
        "simulated_data": True,
        "data_notice": SIMULATED_DATA_NOTICE,
        "catalog_matches": detail["catalog_matches"],
    }


@app.post("/api/v1/reports/basic")
def create_basic_report(request: ReportRequest) -> dict[str, Any]:
    _require_usable_batch(request.batch_id)
    try:
        analyzer = _analyzer(request.batch_id)
        analysis = analyzer.analyze_company(request.company_code)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (FileNotFoundError, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=f"批次原件不可用，无法生成报告：{type(exc).__name__}") from exc
    markdown, payload = build_basic_report(analysis)
    report_id = _safe_report_id(request.batch_id, request.company_code)
    store.save_report(request.batch_id, report_id, markdown, payload)
    return {
        "report_id": report_id,
        "batch_id": request.batch_id,
        "company_code": request.company_code,
        "simulated_data": True,
        "data_notice": SIMULATED_DATA_NOTICE,
        "report_relative_path": f"reports/{request.batch_id}/{report_id}.md",
        "markdown": markdown,
        "report": payload,
    }


@app.get("/api/v1/reports/{batch_id}/{report_id}")
def get_basic_report(batch_id: str, report_id: str) -> dict[str, Any]:
    _require_batch(batch_id)
    try:
        validate_artifact_name(report_id)
        return store.load_json(batch_id, f"report-{report_id}.json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="非法报告标识") from exc
    except (FileNotFoundError, json.JSONDecodeError):
        raise HTTPException(status_code=404, detail="报告不存在")
