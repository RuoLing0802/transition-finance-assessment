from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.domain_store import DomainStore
from app.store import BatchStore
from tests.test_m1 import make_workbook, upload


@pytest.fixture()
def domain_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(main, "store", BatchStore(tmp_path / "m1-runtime"))
    monkeypatch.setattr(main, "domain_store", DomainStore(tmp_path / "application-data"))
    return TestClient(main.app)


def register_batch(client: TestClient) -> dict:
    batch = upload(client, make_workbook())
    response = client.post("/api/v1/source-batches", json={"batch_id": batch["batch_id"]})
    assert response.status_code == 200, response.text
    return response.json()


def create_run(client: TestClient, workspace_id: str, source_batch_id: str, enterprise_code: str) -> dict:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/runs",
        json={
            "enterprise_code": enterprise_code,
            "source_batch_id": source_batch_id,
            "run_name": f"{enterprise_code}评估",
            "rule_version": "m1-local-v0.1",
            "model_config_data": {"mode": "offline", "provider": "none"},
            "basic_info_index": {"企业代号": enterprise_code, "索引来源": "基本信息"},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_workspace_two_runs_reuse_batch_and_refresh_recovery(domain_client: TestClient) -> None:
    workspace = domain_client.post("/api/v1/workspaces", json={"name": "M2最小模拟工作空间"})
    assert workspace.status_code == 200, workspace.text
    workspace_id = workspace.json()["workspace_id"]
    source = register_batch(domain_client)
    reused = domain_client.post(
        "/api/v1/source-batches",
        json={"batch_id": source["m1_batch_id"], "source": "local_upload_repeat"},
    )
    assert reused.status_code == 200, reused.text
    assert reused.json()["source_batch_id"] == source["source_batch_id"]
    assert reused.json()["reused"] is True
    legacy_lookup = domain_client.get(f"/api/v1/source-batches/{source['m1_batch_id']}")
    assert legacy_lookup.status_code == 200, legacy_lookup.text
    assert legacy_lookup.json()["source_batch_id"] == source["source_batch_id"]

    first = create_run(domain_client, workspace_id, source["source_batch_id"], "TFTEST01")
    second = create_run(domain_client, workspace_id, source["source_batch_id"], "TFTEST02")
    assert first["assessment_run_id"] != second["assessment_run_id"]
    assert first["enterprise_id"] != second["enterprise_id"]
    assert first["source_batch_id"] == second["source_batch_id"]
    assert first["status"] == second["status"] == "draft"
    assert first["batch_snapshot"]["m1_batch_id"] == source["m1_batch_id"]

    persisted_root = main.domain_store.root
    main.domain_store = DomainStore(persisted_root)
    refreshed_client = TestClient(main.app)
    recovered_workspace = refreshed_client.get(f"/api/v1/workspaces/{workspace_id}").json()
    recovered_runs = refreshed_client.get(f"/api/v1/workspaces/{workspace_id}/runs").json()["runs"]
    assert recovered_workspace["last_active_run_id"] == second["assessment_run_id"]
    assert {run["enterprise_code"] for run in recovered_runs} == {"TFTEST01", "TFTEST02"}


def test_default_source_rehydrates_runtime_and_repairs_existing_run(
    domain_client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workbook_path = tmp_path / "配套数据.xlsx"
    workbook_path.write_bytes(make_workbook())
    monkeypatch.setattr(main, "_find_default_workbook", lambda: workbook_path)

    source = domain_client.get("/api/v1/source-batches/default")
    assert source.status_code == 200, source.text
    source_body = source.json()
    workspace = domain_client.post("/api/v1/workspaces", json={"name": "默认数据恢复"}).json()
    run = create_run(domain_client, workspace["workspace_id"], source_body["source_batch_id"], "TFTEST01")

    # A new runtime directory simulates relaunching from a packaged app or
    # after the old local M1 cache was removed. The same source is re-parsed by
    # SHA-256 and the durable run remains usable without another upload.
    monkeypatch.setattr(main, "store", BatchStore(tmp_path / "recreated-runtime"))
    repaired = domain_client.get("/api/v1/source-batches/default")
    assert repaired.status_code == 200, repaired.text
    assert repaired.json()["source_batch_id"] == source_body["source_batch_id"]
    assert repaired.json()["m1_batch_id"] != source_body["m1_batch_id"]

    detail = domain_client.get(f"/api/v1/assessment-runs/{run['assessment_run_id']}/company-detail")
    assert detail.status_code == 200, detail.text
    assert detail.json()["enterprise_code"] == "TFTEST01"


def test_messages_and_report_index_are_run_scoped(domain_client: TestClient) -> None:
    workspace = domain_client.post("/api/v1/workspaces", json={"name": "隔离验收"}).json()
    source = register_batch(domain_client)
    first = create_run(domain_client, workspace["workspace_id"], source["source_batch_id"], "TFTEST01")
    second = create_run(domain_client, workspace["workspace_id"], source["source_batch_id"], "TFTEST02")

    message = domain_client.post(
        f"/api/v1/assessment-runs/{first['assessment_run_id']}/messages",
        json={"role": "user", "message_type": "text", "content": "请查看企业详情"},
    )
    assert message.status_code == 200, message.text
    assert message.json()["enterprise_id"] == first["enterprise_id"]
    assert domain_client.get(f"/api/v1/assessment-runs/{second['assessment_run_id']}/messages").json()["messages"] == []

    artifact = domain_client.post(
        f"/api/v1/assessment-runs/{first['assessment_run_id']}/reports",
        json={
            "report_type": "basic_m2",
            "file_format": "md",
            "relative_path": f"reports/{first['assessment_run_id']}/TFTEST01-basic-v1.md",
            "version": "v1",
            "generation_config": {"mode": "offline"},
            "export_records": [{"format": "md", "status": "indexed"}],
        },
    )
    assert artifact.status_code == 200, artifact.text
    assert not Path(artifact.json()["relative_path"]).is_absolute()
    reports = domain_client.get(f"/api/v1/assessment-runs/{first['assessment_run_id']}/reports")
    assert reports.status_code == 200
    assert reports.json()["reports"][0]["assessment_run_id"] == first["assessment_run_id"]
    assert domain_client.post(
        f"/api/v1/assessment-runs/{first['assessment_run_id']}/reports",
        json={"report_type": "bad", "file_format": "md", "relative_path": "../outside.md"},
    ).status_code == 400


def test_run_scoped_detail_and_report_prevent_cross_enterprise_access(domain_client: TestClient) -> None:
    workspace = domain_client.post("/api/v1/workspaces", json={"name": "运行边界"}).json()
    source = register_batch(domain_client)
    first = create_run(domain_client, workspace["workspace_id"], source["source_batch_id"], "TFTEST01")
    detail = domain_client.get(f"/api/v1/assessment-runs/{first['assessment_run_id']}/company-detail")
    assert detail.status_code == 200, detail.text
    assert detail.json()["enterprise_code"] == "TFTEST01"
    assert detail.json()["analysis"]["company_code"] == "TFTEST01"
    mismatch = domain_client.get(f"/api/v1/assessment-runs/{first['assessment_run_id']}/companies/TFTEST02")
    assert mismatch.status_code == 409

    report = domain_client.post(f"/api/v1/assessment-runs/{first['assessment_run_id']}/reports/basic")
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["artifact"]["relative_path"].startswith("reports/")
    assert body["assessment_run"]["status"] == "report_ready"
    recovered = domain_client.get(
        f"/api/v1/assessment-runs/{first['assessment_run_id']}/reports/{body['artifact']['report_artifact_id']}"
    )
    assert recovered.status_code == 200
    assert "模拟数据" in recovered.json()["markdown"]


def test_report_download_export_and_local_directory_action(
    domain_client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = domain_client.post("/api/v1/workspaces", json={"name": "报告交付验收"}).json()
    source = register_batch(domain_client)
    run = create_run(domain_client, workspace["workspace_id"], source["source_batch_id"], "TFTEST01")
    response = domain_client.post(f"/api/v1/assessment-runs/{run['assessment_run_id']}/reports/basic")
    assert response.status_code == 200, response.text
    body = response.json()
    artifact = body["artifact"]
    assert run["assessment_run_id"] in artifact["relative_path"]
    assert artifact["relative_path"].endswith(".md")
    assert artifact["report_period"] == "2024—2025"

    download = domain_client.get(
        f"/api/v1/assessment-runs/{run['assessment_run_id']}/reports/{artifact['report_artifact_id']}/download"
    )
    assert download.status_code == 200
    assert "text/markdown" in download.headers["content-type"]
    assert download.content.decode("utf-8") == body["markdown"].encode("utf-8").decode("utf-8")

    export_directory = tmp_path / "user-selected-export"
    export_directory.mkdir()
    exported = domain_client.post(
        f"/api/v1/assessment-runs/{run['assessment_run_id']}/reports/{artifact['report_artifact_id']}/export",
        json={"target_directory": str(export_directory)},
    )
    assert exported.status_code == 200, exported.text
    exported_path = export_directory / artifact["relative_path"].split("/")[-1]
    assert exported_path.is_file()
    assert exported.json()["artifact"]["export_records"][-1]["status"] == "exported"

    monkeypatch.setattr(main, "_open_local_directory", lambda _directory: True)
    opened = domain_client.post(
        f"/api/v1/assessment-runs/{run['assessment_run_id']}/reports/{artifact['report_artifact_id']}/open-directory"
    )
    assert opened.status_code == 200, opened.text
    assert opened.json()["opened"] is True


def test_completed_runs_can_create_non_ranking_comparison(domain_client: TestClient) -> None:
    workspace = domain_client.post("/api/v1/workspaces", json={"name": "对比验收"}).json()
    source = register_batch(domain_client)
    first = create_run(domain_client, workspace["workspace_id"], source["source_batch_id"], "TFTEST01")
    second = create_run(domain_client, workspace["workspace_id"], source["source_batch_id"], "TFTEST02")
    for run in (first, second):
        updated = domain_client.patch(
            f"/api/v1/assessment-runs/{run['assessment_run_id']}",
            json={"status": "completed", "quality_gate_status": "passed_with_warnings"},
        )
        assert updated.status_code == 200, updated.text
    assert domain_client.patch(
        f"/api/v1/assessment-runs/{first['assessment_run_id']}",
        json={"status": "draft", "quality_gate_status": "not_run"},
    ).status_code == 409

    comparison = domain_client.post(
        "/api/v1/comparison-views",
        json={
            "workspace_id": workspace["workspace_id"],
            "assessment_run_ids": [first["assessment_run_id"], second["assessment_run_id"]],
        },
    )
    assert comparison.status_code == 200, comparison.text
    body = comparison.json()
    assert len(body["assessment_run_ids"]) == 2
    assert body["incomparability_reasons"] == []
    assert "企业排名" in body["output_snapshot"]["notice"]
    assert body["version_differences"]["report_periods"] == ["2024—2025"]
    assert body["output_snapshot"]["run_summaries"][0]["report_period"] == "2024—2025"
    details = body["output_snapshot"]["run_details"]
    assert {item["enterprise_code"] for item in details} == {"TFTEST01", "TFTEST02"}
    assert all("energy_trend" in item and "catalog_matches" in item and "reference_comparison" in item for item in details)
    assert all("score" not in json.dumps(item, ensure_ascii=False) for item in details)
    recovered = domain_client.get(f"/api/v1/comparison-views/{body['comparison_view_id']}")
    assert recovered.status_code == 200
    assert recovered.json()["assessment_run_ids"] == body["assessment_run_ids"]
    restored = domain_client.get(f"/api/v1/workspaces/{workspace['workspace_id']}/comparison-views")
    assert restored.status_code == 200
    assert restored.json()["comparisons"][0]["comparison_view_id"] == body["comparison_view_id"]


def test_failed_source_batch_cannot_create_run(domain_client: TestClient) -> None:
    workspace = domain_client.post("/api/v1/workspaces", json={"name": "失败批次隔离"}).json()
    damaged = domain_client.post(
        "/api/v1/documents",
        files={"file": ("damaged.xlsx", b"not-xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    ).json()
    source = domain_client.post("/api/v1/source-batches", json={"batch_id": damaged["batch_id"]})
    assert source.status_code == 200
    run = domain_client.post(
        f"/api/v1/workspaces/{workspace['workspace_id']}/runs",
        json={"enterprise_code": "TFTEST01", "source_batch_id": source.json()["source_batch_id"]},
    )
    assert run.status_code == 409


def test_enterprise_index_rejects_reference_conclusion_fields(domain_client: TestClient) -> None:
    workspace = domain_client.post("/api/v1/workspaces", json={"name": "泄漏隔离"}).json()
    source = register_batch(domain_client)
    run = domain_client.post(
        f"/api/v1/workspaces/{workspace['workspace_id']}/runs",
        json={
            "enterprise_code": "TFTEST01",
            "source_batch_id": source["source_batch_id"],
            "basic_info_index": {"企业代号": "TFTEST01", "建议改进方向": "不应进入企业档案"},
        },
    )
    assert run.status_code == 400


def test_custom_model_config_is_persisted_but_key_is_never_returned(domain_client: TestClient) -> None:
    created = domain_client.post(
        "/api/v1/model-configs",
        json={
            "model_name": "custom-chat-model",
            "base_url": "https://provider.example/compatible-mode/v1",
            "api_key": "secret-custom-key",
            "supports_vision": True,
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    model = body["model"]
    assert model["model_name"] == "custom-chat-model"
    assert model["supports_vision"] is True
    assert "secret-custom-key" not in json.dumps(body, ensure_ascii=False)

    listed = domain_client.get("/api/v1/model-configs")
    assert listed.status_code == 200
    assert listed.json()["models"][0]["model_id"] == model["model_id"]
    assert "secret-custom-key" not in json.dumps(listed.json(), ensure_ascii=False)

    capabilities = domain_client.get("/api/v1/models")
    assert capabilities.status_code == 200
    custom = next(item for item in capabilities.json()["models"] if item["model_id"] == model["model_id"])
    assert custom["custom"] is True
    assert custom["supports_vision"] is True
    assert "secret-custom-key" not in json.dumps(capabilities.json(), ensure_ascii=False)

    deleted = domain_client.delete(f"/api/v1/model-configs/{model['model_id']}")
    assert deleted.status_code == 200
    assert domain_client.get("/api/v1/model-configs").json()["models"] == []
