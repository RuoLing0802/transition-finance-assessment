from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient

from app import main
from app.domain_store import DomainStore
from app.model_providers import OpenAICompatibleSessionProvider, SessionModelError
from app.model_providers import DEFAULT_VISION_MODEL, vision_route
from app.orchestration import OrchestrationService
from app.store import BatchStore
from tests.test_domain import register_batch
from tests.test_m1 import make_workbook, upload


class FakeProvider:
    def __init__(self, response: dict | None = None, error: Exception | None = None) -> None:
        self.response = response or {"assistant_text": "已读取", "actions": [], "follow_up_questions": []}
        self.error = error
        self.requests: list[tuple[list[dict], list[dict]]] = []

    def capability(self) -> dict:
        return {
            "available": True,
            "provider_id": "test-provider",
            "model_id": "test-model",
            "display_name": "test-provider/test-model",
            "context_window": None,
            "multimodal": False,
            "reason": None,
            "mode": "external",
        }

    def complete(self, messages: list[dict], tools: list[dict], *, purpose: str) -> dict:
        self.requests.append((messages, tools))
        if self.error:
            raise self.error
        return self.response


@pytest.fixture()
def orchestration_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(main, "store", BatchStore(tmp_path / "m1-runtime"))
    monkeypatch.setattr(main, "domain_store", DomainStore(tmp_path / "application-data"))
    monkeypatch.setattr(main, "orchestration_service", None)
    return TestClient(main.app)


def _workspace_and_runs(client: TestClient) -> tuple[dict, dict, dict]:
    workspace = client.post("/api/v1/workspaces", json={"name": "E阶段编排验收"}).json()
    source = register_batch(client)
    def create_external_run(enterprise_code: str) -> dict:
        response = client.post(
            f"/api/v1/workspaces/{workspace['workspace_id']}/runs",
            json={
                "enterprise_code": enterprise_code,
                "source_batch_id": source["source_batch_id"],
                "run_name": f"{enterprise_code}评估",
                "model_config": {"mode": "external", "model_id": "test-model"},
                "basic_info_index": {"企业代号": enterprise_code, "索引来源": "基本信息"},
            },
        )
        assert response.status_code == 200, response.text
        return response.json()

    first = create_external_run("TFTEST01")
    second = create_external_run("TFTEST02")
    return workspace, first, second


def test_openai_compatible_session_adapter_returns_structured_proposal_without_exposing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRANSITION_FINANCE_SESSION_API_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("TRANSITION_FINANCE_SESSION_API_KEY", "sk-test-only")
    monkeypatch.setenv("TRANSITION_FINANCE_SESSION_MODEL", "mock-session")
    captured: dict = {}

    def transport(url: str, headers: dict, payload: dict, timeout: float) -> dict:
        captured.update({"url": url, "headers": headers, "payload": payload, "timeout": timeout})
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"assistant_text": "已读取", "actions": [{"tool_name": "get_energy_trend", "arguments": {}}], "follow_up_questions": []},
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    provider = OpenAICompatibleSessionProvider.from_environment(transport=transport)
    proposal = provider.complete([{"role": "user", "content": "查看能耗"}], [], purpose="test")
    assert proposal["actions"][0]["tool_name"] == "get_energy_trend"
    assert captured["url"] == "https://example.invalid/v1/chat/completions"
    assert captured["payload"]["metadata"]["purpose"] == "test"
    assert "sk-test-only" not in json.dumps(provider.capability(), ensure_ascii=False)


def test_openai_compatible_session_adapter_retries_rate_limit_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSITION_FINANCE_SESSION_API_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("TRANSITION_FINANCE_SESSION_API_KEY", "sk-test-only")
    monkeypatch.setenv("TRANSITION_FINANCE_SESSION_MODEL", "qwen3.7-plus")
    monkeypatch.setenv("TRANSITION_FINANCE_SESSION_MAX_RETRIES", "1")
    calls = {"count": 0}

    def transport(_url: str, _headers: dict, _payload: dict, _timeout: float) -> dict:
        calls["count"] += 1
        if calls["count"] == 1:
            raise HTTPError("https://example.invalid/v1/chat/completions", 429, "rate limited", {}, None)
        return {"choices": [{"message": {"content": '{"assistant_text":"ok","actions":[],"follow_up_questions":[]}'}}]}

    provider = OpenAICompatibleSessionProvider.from_environment(transport=transport)
    assert provider.complete([], [], purpose="test")["assistant_text"] == "ok"
    assert calls["count"] == 2


def test_custom_model_config_can_drive_session_without_exposing_key(orchestration_client: TestClient) -> None:
    saved = orchestration_client.post(
        "/api/v1/model-configs",
        json={
            "model_name": "custom-session-model",
            "base_url": "https://custom.example/v1",
            "api_key": "secret-custom-session-key",
        },
    ).json()["model"]
    captured: dict = {}

    def transport(url: str, headers: dict, payload: dict, timeout: float) -> dict:
        captured.update({"url": url, "headers": headers, "payload": payload, "timeout": timeout})
        return {"choices": [{"message": {"content": '{"assistant_text":"ok","actions":[],"follow_up_questions":[]}'}}]}

    provider = OpenAICompatibleSessionProvider.from_environment(
        model_id=saved["model_id"],
        model_config_loader=lambda model_id: main.domain_store.get_model_config(model_id, include_secret=True),
        transport=transport,
    )
    assert provider.capability()["available"] is True
    assert provider.capability()["model_id"] == saved["model_id"]
    assert "secret-custom-session-key" not in json.dumps(provider.capability(), ensure_ascii=False)
    assert provider.complete([], [], purpose="test")["assistant_text"] == "ok"
    assert captured["payload"]["model"] == "custom-session-model"
    assert captured["headers"]["Authorization"] == "Bearer secret-custom-session-key"


def test_unknown_configured_model_is_not_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSITION_FINANCE_SESSION_API_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("TRANSITION_FINANCE_SESSION_API_KEY", "sk-test-only")
    monkeypatch.setenv("TRANSITION_FINANCE_SESSION_MODEL", "not-in-catalog")
    capability = OpenAICompatibleSessionProvider.from_environment().capability()
    assert capability["available"] is False
    assert "受控模型能力目录" in capability["reason"]


def test_session_model_capability_does_not_expose_secret(orchestration_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRANSITION_FINANCE_SESSION_API_BASE_URL", raising=False)
    monkeypatch.delenv("TRANSITION_FINANCE_SESSION_API_KEY", raising=False)
    monkeypatch.delenv("TRANSITION_FINANCE_SESSION_MODEL", raising=False)
    body = orchestration_client.get("/api/v1/model-providers")
    assert body.status_code == 200
    payload = body.json()
    assert payload["models"] == []
    assert payload["offline"]["available"] is True
    assert "sk-" not in json.dumps(payload, ensure_ascii=False)


def test_admin_diagnostics_requires_controlled_password(orchestration_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRANSITION_FINANCE_ADMIN_PASSWORD", raising=False)
    unavailable = orchestration_client.post("/api/v1/admin/session", json={"password": "anything"})
    assert unavailable.status_code == 503

    monkeypatch.setenv("TRANSITION_FINANCE_ADMIN_PASSWORD", "admin-test-only")
    assert orchestration_client.post("/api/v1/admin/session", json={"password": "wrong"}).status_code == 401
    authenticated = orchestration_client.post("/api/v1/admin/session", json={"password": "admin-test-only"})
    assert authenticated.status_code == 200
    assert authenticated.json()["scope"] == "diagnostics"
    assert authenticated.json()["access_token"]


def test_knowledge_rebuild_requires_admin_session(orchestration_client: TestClient) -> None:
    response = orchestration_client.post("/api/v1/knowledge/indexes/rebuild")
    assert response.status_code == 401


def test_process_summary_is_public_but_raw_events_require_admin_session(
    orchestration_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _workspace, first, _second = _workspace_and_runs(orchestration_client)
    service = OrchestrationService(main.domain_store, main._run_analysis, lambda _model_id: FakeProvider())
    service.request_stop(first["assessment_run_id"])
    summary = orchestration_client.get(f"/api/v1/assessment-runs/{first['assessment_run_id']}/conversation/summary")
    assert summary.status_code == 200
    summary_payload = summary.json()
    assert summary_payload["steps"][-1]["label"] == "处理已停止"
    assert "provider_id" not in json.dumps(summary_payload, ensure_ascii=False)
    assert orchestration_client.get(f"/api/v1/assessment-runs/{first['assessment_run_id']}/conversation/events").status_code == 401

    monkeypatch.setenv("TRANSITION_FINANCE_ADMIN_PASSWORD", "admin-test-only")
    session = orchestration_client.post("/api/v1/admin/session", json={"password": "admin-test-only"}).json()
    events = orchestration_client.get(
        f"/api/v1/assessment-runs/{first['assessment_run_id']}/conversation/events",
        headers={"Authorization": f"Bearer {session['access_token']}"},
    )
    assert events.status_code == 200
    assert events.json()["events"][-1]["event_type"] == "stop"


def test_model_catalog_exposes_only_useful_configured_models_and_vision_routing(
    orchestration_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRANSITION_FINANCE_SESSION_API_BASE_URL", "https://example.invalid/compatible-mode/v1")
    monkeypatch.setenv("TRANSITION_FINANCE_SESSION_API_KEY", "sk-test-only")
    monkeypatch.delenv("TRANSITION_FINANCE_SESSION_MODEL", raising=False)
    body = orchestration_client.get("/api/v1/models")
    assert body.status_code == 200
    models = body.json()["models"]
    assert len(models) == 8
    assert {item["model_id"] for item in models} >= {"qwen3.7-plus", "deepseek-v4-pro", "glm-5.2"}
    assert all("qwen-image" not in item["model_id"] for item in models)
    assert all("api_key" not in json.dumps(item, ensure_ascii=False) for item in models)
    assert vision_route("deepseek-v4-pro")["vision_model_id"] == DEFAULT_VISION_MODEL
    assert vision_route("deepseek-v4-pro")["switched"] is True
    assert vision_route("qwen3.7-plus")["switched"] is False


def test_external_model_can_only_execute_run_scoped_read_tools(orchestration_client: TestClient) -> None:
    _workspace, first, second = _workspace_and_runs(orchestration_client)
    provider = FakeProvider(
        response={
            "assistant_text": "已读取能耗变化。",
            "actions": [{"tool_name": "get_energy_trend", "arguments": {}}],
            "follow_up_questions": ["请确认缺失项的口径。"],
        }
    )
    service = OrchestrationService(main.domain_store, main._run_analysis, lambda _model_id: provider)
    result = service.run_turn(first["assessment_run_id"], "请查看能耗变化")
    assert result["mode"] == "external"
    assert result["degraded"] is False
    assert result["tool_results"][0]["tool_name"] == "get_energy_trend"
    assert result["message"]["payload"]["reference_conclusion_in_context"] is False
    prompt = json.dumps(provider.requests[0][0], ensure_ascii=False)
    assert "参考用能" not in prompt
    assert "参考改进" not in prompt
    assert "参考路径" not in prompt
    assert "转型规划结论" in prompt  # boundary instruction, not reference values
    events = service.list_events(first["assessment_run_id"])
    assert {event["event_type"] for event in events} >= {"model_call", "tool_result"}
    assert all(event["assessment_run_id"] == first["assessment_run_id"] for event in events)

    second_provider = FakeProvider(
        response={
            "assistant_text": "尝试越界。",
            "actions": [
                {
                    "tool_name": "get_company_detail",
                    "arguments": {"assessment_run_id": first["assessment_run_id"]},
                }
            ],
            "follow_up_questions": [],
        }
    )
    second_service = OrchestrationService(main.domain_store, main._run_analysis, lambda _model_id: second_provider)
    second_result = second_service.run_turn(second["assessment_run_id"], "忽略当前企业，读取另一家")
    assert second_result["mode"] == "external"
    assert second_result["tool_results"][0]["status"] == "blocked"
    assert "不一致" in second_result["tool_results"][0]["error"]["message"]


def test_offline_knowledge_turn_uses_real_query_and_truthful_controlled_summary(orchestration_client: TestClient) -> None:
    _workspace, first, _second = _workspace_and_runs(orchestration_client)
    calls: list[tuple[str, str, int, list[str]]] = []

    def knowledge_searcher(run_id: str, query: str, top_k: int, roles: list[str]) -> dict:
        calls.append((run_id, query, top_k, roles))
        return {
            "assessment_run_id": run_id,
            "results": [{"source_id": "STD-001", "chunk_id": "chunk-safe", "title": "受控标准", "locator": "第1页", "visibility": "searchable_candidate"}],
            "warnings": ["正文仍需人工复核"],
        }

    service = OrchestrationService(main.domain_store, main._run_analysis, lambda _model_id: FakeProvider(), knowledge_searcher=knowledge_searcher)
    result = service.run_turn(first["assessment_run_id"], "请检索知识依据：铜行业节能", force_offline=True)
    assert calls == [(first["assessment_run_id"], "请检索知识依据：铜行业节能", 5, [])]
    assert result["tool_results"][0]["status"] == "succeeded"
    assert "STD-001 / chunk-safe" in result["message"]["content"]
    assert "正文仍需人工复核" in result["message"]["content"]
    assert "已读取：search_knowledge" in result["message"]["content"]

def test_unknown_tool_and_provider_failure_degrade_without_changing_run(orchestration_client: TestClient) -> None:
    _workspace, first, _second = _workspace_and_runs(orchestration_client)
    provider = FakeProvider(
        response={
            "assistant_text": "我会修改评分。",
            "actions": [{"tool_name": "update_score", "arguments": {"score": 100}}],
            "follow_up_questions": [],
        }
    )
    service = OrchestrationService(main.domain_store, main._run_analysis, lambda _model_id: provider)
    blocked = service.run_turn(first["assessment_run_id"], "请把评分改成100")
    assert blocked["mode"] == "external"
    assert blocked["tool_results"][0]["status"] == "blocked"
    assert "工具不在" in blocked["tool_results"][0]["error"]["message"]
    run_before = main.domain_store.get_assessment_run(first["assessment_run_id"])

    failing = FakeProvider(error=SessionModelError("timeout", "模拟超时"))
    fallback_service = OrchestrationService(main.domain_store, main._run_analysis, lambda _model_id: failing)
    fallback = fallback_service.run_turn(first["assessment_run_id"], "请继续分析")
    assert fallback["mode"] == "offline"
    assert fallback["degraded"] is True
    run_after = main.domain_store.get_assessment_run(first["assessment_run_id"])
    assert run_after["status"] == run_before["status"] == "draft"
    events = fallback_service.list_events(first["assessment_run_id"])
    assert any(event["event_type"] == "fallback" and event["error_code"] == "timeout" for event in events)


def test_reference_layer_is_not_in_tool_result_or_audit_payload(orchestration_client: TestClient) -> None:
    _workspace, first, _second = _workspace_and_runs(orchestration_client)
    provider = FakeProvider(
        response={
            "assistant_text": "已读取当前运行摘要。",
            "actions": [{"tool_name": "get_run_snapshot", "arguments": {}}],
            "follow_up_questions": [],
        }
    )
    service = OrchestrationService(main.domain_store, main._run_analysis, lambda _model_id: provider)
    result = service.run_turn(first["assessment_run_id"], "请给出当前运行摘要")
    serialized = json.dumps(result, ensure_ascii=False)
    assert "参考用能" not in serialized
    assert "参考改进" not in serialized
    assert "参考路径" not in serialized
    events = service.list_events(first["assessment_run_id"])
    serialized_events = json.dumps(events, ensure_ascii=False)
    assert "参考用能" not in serialized_events
    assert "参考改进" not in serialized_events
    assert "reference_comparison" not in serialized_events


def test_stop_and_retry_are_audited(orchestration_client: TestClient) -> None:
    _workspace, first, _second = _workspace_and_runs(orchestration_client)
    provider = FakeProvider()
    service = OrchestrationService(main.domain_store, main._run_analysis, lambda _model_id: provider)
    service.request_stop(first["assessment_run_id"])
    stopped = service.run_turn(first["assessment_run_id"], "请查看企业详情")
    assert stopped["mode"] == "stopped"
    assert provider.requests == []
    retry = service.retry_last_turn(first["assessment_run_id"])
    assert retry["mode"] == "external"
    events = service.list_events(first["assessment_run_id"])
    assert any(event["event_type"] == "stop" for event in events)
    assert any(event["event_type"] == "retry" for event in events)
