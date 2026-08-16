from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class SourceBatchRegister(BaseModel):
    batch_id: str = Field(min_length=3, max_length=80)
    source: str = Field(default="local_upload", max_length=80)


class AssessmentRunCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    enterprise_code: str = Field(min_length=1, max_length=120)
    source_batch_id: str = Field(min_length=3, max_length=80)
    run_name: str = Field(default="企业评估", min_length=1, max_length=120)
    rule_version: str = Field(default="m1-local-v0.1", min_length=1, max_length=80)
    model_config_data: dict[str, Any] = Field(default_factory=dict, alias="model_config")
    basic_info_index: dict[str, Any] = Field(default_factory=dict)


class AssessmentRunUpdate(BaseModel):
    status: Literal[
        "draft",
        "uploading",
        "parsing",
        "needs_subject",
        "collecting",
        "needs_input",
        "validating",
        "ready_to_assess",
        "assessing",
        "needs_review",
        "report_ready",
        "completed",
        "failed",
        "archived",
    ]
    quality_gate_status: str = Field(default="not_run", min_length=1, max_length=80)


class ConversationMessageCreate(BaseModel):
    role: Literal["user", "assistant", "system", "tool", "human_review"]
    message_type: Literal["text", "tool_call", "tool_result", "status", "review"] = "text"
    content: str = Field(min_length=1, max_length=20000)
    tool_name: str | None = Field(default=None, max_length=120)
    payload: dict[str, Any] = Field(default_factory=dict)


class ConversationTurnCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    model_id: str | None = Field(default=None, min_length=1, max_length=160)
    mode: Literal["auto", "offline"] = "auto"


class ReportArtifactCreate(BaseModel):
    report_type: str = Field(min_length=1, max_length=80)
    file_format: Literal["md", "pdf", "docx"]
    relative_path: str = Field(min_length=1, max_length=300)
    version: str = Field(default="v1", min_length=1, max_length=80)
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    generation_config: dict[str, Any] = Field(default_factory=dict)
    export_records: list[dict[str, Any]] = Field(default_factory=list)


class ReportExportRequest(BaseModel):
    target_directory: str = Field(min_length=1, max_length=2000)


class ComparisonViewCreate(BaseModel):
    workspace_id: str = Field(min_length=3, max_length=80)
    assessment_run_ids: list[str] = Field(min_length=2, max_length=20)
    dimensions: list[str] = Field(default_factory=lambda: ["企业基本信息", "数据质量", "能耗变化", "目录候选", "参考结论对照"])
