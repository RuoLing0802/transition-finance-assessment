from __future__ import annotations

import hashlib
from copy import deepcopy
from collections import Counter
from typing import Any, Callable, TypedDict

from ..domain_store import DomainConflictError, DomainNotFoundError, DomainStore

try:  # Optional at import time so the offline baseline remains runnable.
    from langchain_core.runnables import RunnableLambda
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only in minimal environments.
    RunnableLambda = None  # type: ignore[assignment,misc]
    InMemorySaver = None  # type: ignore[assignment,misc]
    END = "__end__"
    START = "__start__"
    StateGraph = None  # type: ignore[assignment,misc]
    LANGGRAPH_AVAILABLE = False


AnalysisLoader = Callable[[str], tuple[dict[str, Any], dict[str, Any]]]

WORKFLOW_DEFINITIONS: dict[str, dict[str, Any]] = {
    "baseline_review": {
        "label": "基础评估审查",
        "description": "按企业加载、画像、质量、证据、补问和人工确认顺序运行。",
        "nodes": ["load_enterprise", "build_profile", "quality_check", "evidence_review", "follow_up", "human_review"],
        "pause_points": ["follow_up", "human_review"],
    },
    "evidence_followup": {
        "label": "证据补充复核",
        "description": "围绕当前企业的补充材料、解析状态和人工复核运行。",
        "nodes": ["load_enterprise", "evidence_review", "follow_up", "human_review"],
        "pause_points": ["follow_up", "human_review"],
    },
}

_NODE_LABELS = {
    "load_enterprise": "载入当前企业",
    "build_profile": "整理企业画像",
    "quality_check": "检查数据质量",
    "evidence_review": "复核补充证据",
    "follow_up": "生成待补问题",
    "human_review": "等待人工确认",
}
_PAUSED_STATUSES = {"paused", "waiting_for_input", "waiting_human_review"}
_SAFE_STATE_KEYS = {
    "run_id",
    "workflow_name",
    "thread_id",
    "status",
    "current_node",
    "completed_nodes",
    "node_status",
    "enterprise_code",
    "source_batch_id",
    "profile_field_count",
    "quality_issue_count",
    "quality_severity_counts",
    "quality_gate",
    "attachment_count",
    "attachment_status_counts",
    "evidence_gate",
    "follow_up_questions",
    "answer_count",
    "answer_hashes",
    "review_decision",
    "pause_reason",
    "paused_from_status",
    "force_follow_up",
    "no_additional_confirmed",
    "engine",
    "graph_version",
}


def workflow_analysis_view(analysis: dict[str, Any]) -> dict[str, Any]:
    """Return the allow-listed M4 analysis view without the reference layer."""
    input_data = analysis.get("input_data")
    if not isinstance(input_data, dict):
        raise DomainConflictError("工作流分析视图缺少输入数据")
    return {
        "input_data": {
            key: deepcopy(input_data.get(key, {}))
            for key in ("basic_info", "energy_info", "supplement_info")
        },
        "quality_issues": deepcopy(analysis.get("quality_issues") or []),
        "energy_trend": deepcopy(analysis.get("energy_trend") or {}),
        "catalog_matches": deepcopy(analysis.get("catalog_matches") or {}),
    }


class WorkflowState(TypedDict, total=False):
    run_id: str
    workflow_name: str
    thread_id: str
    status: str
    current_node: str | None
    completed_nodes: list[str]
    node_status: dict[str, str]
    enterprise_code: str
    source_batch_id: str
    profile_field_count: int
    quality_issue_count: int
    quality_severity_counts: dict[str, int]
    quality_gate: str
    attachment_count: int
    attachment_status_counts: dict[str, int]
    evidence_gate: str
    follow_up_questions: list[str]
    answer_count: int
    answer_hashes: list[str]
    review_decision: str | None
    pause_reason: str | None
    paused_from_status: str | None
    force_follow_up: bool
    no_additional_confirmed: bool
    engine: str
    graph_version: str
    checkpoint_version: int


class AssessmentWorkflowRuntime:
    """Run-scoped M4 workflows with durable SQLite checkpoints.

    LangGraph provides the node graph and conditional routing when installed.
    The SQLite checkpoint is the durable source of truth so restart/recovery
    does not depend on LangGraph's in-memory saver. LangChain's RunnableLambda
    wraps each deterministic node; no business fact or reference conclusion is
    stored in framework-private state.
    """

    def __init__(self, domain_store: DomainStore, analysis_loader: AnalysisLoader) -> None:
        self.domain_store = domain_store
        self.analysis_loader = analysis_loader
        self._graphs: dict[str, Any] = {}
        self._runnables: dict[str, Any] = {}
        self._checkpointer = InMemorySaver() if LANGGRAPH_AVAILABLE and InMemorySaver else None

    def list(self, assessment_run_id: str) -> dict[str, Any]:
        self.domain_store.get_assessment_run(assessment_run_id)
        return {
            "assessment_run_id": assessment_run_id,
            "engine": "langgraph" if LANGGRAPH_AVAILABLE else "deterministic_fallback",
            "thread_binding": "assessment_run_id",
            "definitions": self._definitions(),
            "workflows": self.domain_store.list_workflow_checkpoints(assessment_run_id),
            "notice": "流程状态按评估运行保存；不包含模型私有思维链，也不把转型规划结论写入工作流状态。",
        }

    def start(self, assessment_run_id: str, workflow_name: str) -> dict[str, Any]:
        definition = self._definition(workflow_name)
        try:
            existing = self.domain_store.get_workflow_checkpoint(assessment_run_id, workflow_name)
        except DomainNotFoundError:
            existing = None
        if existing is not None:
            return existing
        run = self.domain_store.get_assessment_run(assessment_run_id)
        thread_id = f"{assessment_run_id}:{workflow_name}"
        state: WorkflowState = {
            "run_id": assessment_run_id,
            "workflow_name": workflow_name,
            "thread_id": thread_id,
            "status": "running",
            "current_node": definition["nodes"][0],
            "completed_nodes": [],
            "node_status": {},
            "enterprise_code": run["enterprise_code"],
            "source_batch_id": run["source_batch_id"],
            "follow_up_questions": [],
            "answer_count": 0,
            "answer_hashes": [],
            "review_decision": None,
            "pause_reason": None,
            "paused_from_status": None,
            "force_follow_up": False,
            "no_additional_confirmed": False,
            "engine": "langgraph" if LANGGRAPH_AVAILABLE else "deterministic_fallback",
            "graph_version": "m4-v1",
        }
        return self._execute(state)

    def pause(self, assessment_run_id: str, workflow_name: str) -> dict[str, Any]:
        checkpoint = self.domain_store.get_workflow_checkpoint(assessment_run_id, workflow_name)
        if checkpoint["status"] == "completed":
            raise DomainConflictError("已完成流程不能暂停")
        if checkpoint["status"] == "paused":
            raise DomainConflictError("当前流程已经暂停")
        state = self._state_from_checkpoint(checkpoint)
        state["paused_from_status"] = checkpoint["status"]
        state["status"] = "paused"
        state["pause_reason"] = "用户请求暂停，当前检查点已保存"
        return self._persist(state, event_status="paused")

    def resume(
        self,
        assessment_run_id: str,
        workflow_name: str,
        answers: list[str] | None = None,
        *,
        confirm_no_additional: bool = False,
    ) -> dict[str, Any]:
        checkpoint = self.domain_store.get_workflow_checkpoint(assessment_run_id, workflow_name)
        if checkpoint["status"] == "completed":
            return checkpoint
        if checkpoint["status"] == "waiting_human_review":
            raise DomainConflictError("当前流程等待人工确认，请使用人工确认接口")
        if checkpoint["status"] not in {"paused", "waiting_for_input"}:
            raise DomainConflictError(f"当前流程状态不可恢复：{checkpoint['status']}")
        state = self._state_from_checkpoint(checkpoint)
        clean_answers = [str(item).strip() for item in (answers or []) if str(item).strip()]
        paused_from_status = state.get("paused_from_status")
        resume_source_status = checkpoint["status"]
        if checkpoint["status"] == "paused":
            resume_source_status = paused_from_status or (
                "waiting_for_input" if state.get("follow_up_questions") else "paused"
            )
        if clean_answers and confirm_no_additional:
            raise DomainConflictError("不能同时提交补充回答和确认暂不补充")
        if resume_source_status == "waiting_for_input" and not clean_answers and not confirm_no_additional:
            raise DomainConflictError("当前流程需要补充回答，或明确确认暂不补充")
        if clean_answers:
            state["answer_count"] = int(state.get("answer_count", 0)) + len(clean_answers)
            state["answer_hashes"] = list(state.get("answer_hashes", [])) + [
                hashlib.sha256(item.encode("utf-8")).hexdigest() for item in clean_answers
            ]
        state["no_additional_confirmed"] = bool(confirm_no_additional)
        state["paused_from_status"] = None
        state["status"] = "running"
        state["pause_reason"] = None
        return self._execute(state)

    def review(self, assessment_run_id: str, workflow_name: str, decision: str) -> dict[str, Any]:
        if decision not in {"approve", "request_changes"}:
            raise DomainConflictError("人工确认结果只能是approve或request_changes")
        checkpoint = self.domain_store.get_workflow_checkpoint(assessment_run_id, workflow_name)
        if checkpoint["status"] == "completed":
            return checkpoint
        if checkpoint["status"] != "waiting_human_review":
            raise DomainConflictError("当前流程尚未进入人工确认阶段")
        state = self._state_from_checkpoint(checkpoint)
        state["review_decision"] = decision
        state["status"] = "running"
        state["current_node"] = "human_review"
        state["pause_reason"] = None
        return self._execute(state)

    def _definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "workflow_name": name,
                "label": definition["label"],
                "description": definition["description"],
                "nodes": definition["nodes"],
                "pause_points": definition["pause_points"],
            }
            for name, definition in WORKFLOW_DEFINITIONS.items()
        ]

    @staticmethod
    def _definition(workflow_name: str) -> dict[str, Any]:
        definition = WORKFLOW_DEFINITIONS.get(workflow_name)
        if definition is None:
            raise DomainConflictError(f"不支持的M4流程：{workflow_name}")
        return definition

    def _state_from_checkpoint(self, checkpoint: dict[str, Any]) -> WorkflowState:
        state = dict(checkpoint.get("state") or {})
        state.setdefault("run_id", checkpoint["assessment_run_id"])
        state.setdefault("workflow_name", checkpoint["workflow_name"])
        state.setdefault("thread_id", checkpoint["thread_id"])
        state.setdefault("completed_nodes", [])
        state.setdefault("node_status", {})
        state.setdefault("answer_count", 0)
        state.setdefault("answer_hashes", [])
        state.setdefault("follow_up_questions", [])
        state.setdefault("paused_from_status", None)
        state.setdefault("force_follow_up", False)
        state.setdefault("no_additional_confirmed", False)
        state["checkpoint_version"] = int(checkpoint.get("version", 0))
        return state  # type: ignore[return-value]

    def _execute(self, state: WorkflowState) -> dict[str, Any]:
        if LANGGRAPH_AVAILABLE:
            graph = self._graph(str(state["workflow_name"]))
            result = graph.invoke(state, config={"configurable": {"thread_id": state["thread_id"]}})
        else:
            result = self._execute_fallback(state)
        return self._persist(result, event_status=str(result.get("status", "running")))

    def _graph(self, workflow_name: str) -> Any:
        if workflow_name in self._graphs:
            return self._graphs[workflow_name]
        definition = self._definition(workflow_name)
        builder = StateGraph(WorkflowState)
        for node_name in definition["nodes"]:
            builder.add_node(node_name, lambda state, node_name=node_name: self._run_node(node_name, state))
        builder.add_conditional_edges(START, lambda state: str(state.get("current_node") or definition["nodes"][0]))
        for node_name in definition["nodes"]:
            builder.add_conditional_edges(node_name, self._route_after_node)
        self._graphs[workflow_name] = builder.compile(checkpointer=self._checkpointer)
        return self._graphs[workflow_name]

    def _run_node(self, node_name: str, state: WorkflowState) -> WorkflowState:
        if RunnableLambda is not None:
            runnable = self._runnables.setdefault(
                node_name,
                RunnableLambda(lambda value, node_name=node_name: self._run_node_logic(node_name, value)),
            )
            return runnable.invoke(state)
        return self._run_node_logic(node_name, state)

    def _route_after_node(self, state: WorkflowState) -> str:
        if state.get("status") in _PAUSED_STATUSES or not state.get("current_node"):
            return END
        return str(state["current_node"])

    def _execute_fallback(self, state: WorkflowState) -> WorkflowState:
        current = str(state.get("current_node") or "")
        while current and state.get("status") == "running":
            state = self._run_node_logic(current, state)
            current = str(state.get("current_node") or "")
        return state

    def _run_node_logic(self, node_name: str, state: WorkflowState) -> WorkflowState:
        handlers = {
            "load_enterprise": self._load_enterprise,
            "build_profile": self._build_profile,
            "quality_check": self._quality_check,
            "evidence_review": self._evidence_review,
            "follow_up": self._follow_up,
            "human_review": self._human_review,
        }
        try:
            return handlers[node_name](state)
        except KeyError as exc:
            raise DomainConflictError(f"M4流程节点不存在：{node_name}") from exc

    def _load_enterprise(self, state: WorkflowState) -> WorkflowState:
        run, _analysis = self.analysis_loader(str(state["run_id"]))
        return self._advance(
            state,
            "load_enterprise",
            {"enterprise_code": run["enterprise_code"], "source_batch_id": run["source_batch_id"]},
        )

    def _build_profile(self, state: WorkflowState) -> WorkflowState:
        _run, analysis = self.analysis_loader(str(state["run_id"]))
        input_data = analysis.get("input_data") or {}
        field_count = sum(
            len(section)
            for key, section in input_data.items()
            if key in {"basic_info", "supplement_info"} and isinstance(section, dict)
        )
        return self._advance(state, "build_profile", {"profile_field_count": field_count})

    def _quality_check(self, state: WorkflowState) -> WorkflowState:
        _run, analysis = self.analysis_loader(str(state["run_id"]))
        issues = [item for item in (analysis.get("quality_issues") or []) if isinstance(item, dict)]
        severity_counts = dict(Counter(str(item.get("severity") or "warning") for item in issues))
        return self._advance(
            state,
            "quality_check",
            {
                "quality_issue_count": len(issues),
                "quality_severity_counts": severity_counts,
                "quality_gate": "warning" if issues else "passed",
            },
        )

    def _evidence_review(self, state: WorkflowState) -> WorkflowState:
        attachments = self.domain_store.list_attachments(str(state["run_id"]))
        statuses = dict(Counter(str(item.get("parse_status") or "unknown") for item in attachments))
        evidence_gate = "ready" if attachments and all(item.get("parse_status") in {"parsed", "review_required"} for item in attachments) else "warning"
        return self._advance(
            state,
            "evidence_review",
            {
                "attachment_count": len(attachments),
                "attachment_status_counts": statuses,
                "evidence_gate": evidence_gate,
            },
        )

    def _follow_up(self, state: WorkflowState) -> WorkflowState:
        questions: list[str] = []
        if state.get("force_follow_up"):
            questions.append("请根据人工复核要求补充说明或材料，完成后再提交确认。")
        if int(state.get("quality_issue_count", 0)) > 0:
            questions.append("请补充说明当前数据质量提示，并确认是否需要人工修正。")
        if int(state.get("attachment_count", 0)) == 0:
            questions.append("请上传与当前企业和本次评估相关的补充材料，或确认暂不补充。")
        elif state.get("evidence_gate") != "ready":
            questions.append("请确认已登记补充材料的解析状态，必要时重新上传或申请人工复核。")
        if int(state.get("answer_count", 0)) > 0 or state.get("no_additional_confirmed"):
            questions = []
            state["force_follow_up"] = False
        if questions:
            return self._advance(
                state,
                "follow_up",
                {"follow_up_questions": questions},
                status="waiting_for_input",
                next_node="human_review",
                pause_reason="等待用户补充信息或确认当前资料状态",
            )
        return self._advance(
            state,
            "follow_up",
            {"follow_up_questions": []},
            status="waiting_human_review",
            next_node="human_review",
            pause_reason="等待人工确认是否完成本轮流程",
        )

    def _human_review(self, state: WorkflowState) -> WorkflowState:
        decision = state.get("review_decision")
        if decision == "approve":
            return self._advance(
                state,
                "human_review",
                {"review_decision": "approve"},
                status="completed",
                next_node=None,
            )
        if decision == "request_changes":
            return self._advance(
                state,
                "human_review",
                {
                    "review_decision": "request_changes",
                    "force_follow_up": True,
                    "no_additional_confirmed": False,
                    "paused_from_status": None,
                    "answer_count": 0,
                    "answer_hashes": [],
                },
                status="waiting_for_input",
                next_node="follow_up",
                pause_reason="人工复核要求补充或修正材料",
            )
        return self._advance(
            state,
            "human_review",
            {},
            status="waiting_human_review",
            next_node="human_review",
            pause_reason="等待人工确认，不自动生成评分、碳排放或授信结论",
        )

    def _advance(
        self,
        state: WorkflowState,
        node_name: str,
        updates: dict[str, Any],
        *,
        status: str = "running",
        next_node: str | None = None,
        pause_reason: str | None = None,
    ) -> WorkflowState:
        definition = self._definition(str(state["workflow_name"]))
        if next_node is None and status == "running":
            nodes = definition["nodes"]
            index = nodes.index(node_name)
            next_node = nodes[index + 1] if index + 1 < len(nodes) else None
        completed = list(dict.fromkeys([*state.get("completed_nodes", []), node_name]))
        node_status = {**state.get("node_status", {}), node_name: "done" if status != "error" else "error"}
        result: WorkflowState = {
            **state,
            **updates,
            "status": status,
            "current_node": next_node,
            "completed_nodes": completed,
            "node_status": node_status,
            "pause_reason": pause_reason,
        }
        self._persist(result, event_status=status, node_name=node_name)
        return result

    def _persist(
        self,
        state: WorkflowState,
        *,
        event_status: str,
        node_name: str | None = None,
    ) -> dict[str, Any]:
        safe_state = {key: state[key] for key in _SAFE_STATE_KEYS if key in state}
        current_version = int(state.get("checkpoint_version", 0) or 0)
        checkpoint = self.domain_store.upsert_workflow_checkpoint(
            str(state["run_id"]),
            workflow_name=str(state["workflow_name"]),
            thread_id=str(state["thread_id"]),
            status=str(state.get("status", event_status)),
            current_node=state.get("current_node"),
            version=current_version + 1,
            state=safe_state,
            checkpoint={
                "engine": state.get("engine"),
                "graph_version": state.get("graph_version", "m4-v1"),
                "node": node_name or state.get("current_node"),
                "status": state.get("status", event_status),
                "thread_id": state.get("thread_id"),
            },
        )
        state["checkpoint_version"] = checkpoint["version"]
        self.domain_store.create_orchestration_event(
            str(state["run_id"]),
            event_type="workflow_checkpoint",
            provider_id=None,
            model_id=None,
            purpose="m4_workflow",
            tool_name=None,
            input_evidence_refs=[],
            payload={
                "workflow_name": state["workflow_name"],
                "thread_id": state["thread_id"],
                "node": node_name or state.get("current_node"),
                "label": _NODE_LABELS.get(node_name or str(state.get("current_node")), "评估流程状态已保存"),
                "status": checkpoint["status"],
                "checkpoint_version": checkpoint["version"],
                "completed_nodes": checkpoint["state"].get("completed_nodes", []),
            },
            status=event_status,
        )
        return checkpoint
