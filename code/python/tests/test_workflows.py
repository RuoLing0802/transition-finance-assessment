from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app import main
from app.domain_store import DomainConflictError
from app.workflows import workflow_analysis_view
from tests.test_domain import create_run, domain_client, register_batch


def test_m4_workflows_checkpoint_pause_resume_and_review(domain_client) -> None:
    workspace = domain_client.post("/api/v1/workspaces", json={"name": "M4流程验收"}).json()
    source = register_batch(domain_client)
    run = create_run(domain_client, workspace["workspace_id"], source["source_batch_id"], "TFTEST01")
    run_id = run["assessment_run_id"]

    definitions = domain_client.get(f"/api/v1/assessment-runs/{run_id}/workflows")
    assert definitions.status_code == 200, definitions.text
    assert {item["workflow_name"] for item in definitions.json()["definitions"]} == {
        "baseline_review",
        "evidence_followup",
    }

    started = domain_client.post(
        f"/api/v1/assessment-runs/{run_id}/workflows/start",
        json={"workflow_name": "baseline_review"},
    )
    assert started.status_code == 200, started.text
    checkpoint = started.json()
    assert checkpoint["status"] == "waiting_for_input"
    assert checkpoint["current_node"] == "human_review"
    assert run_id in checkpoint["thread_id"]
    assert "转型规划结论" not in json.dumps(checkpoint, ensure_ascii=False)
    assert "参考用能" not in json.dumps(checkpoint, ensure_ascii=False)

    paused = domain_client.post(f"/api/v1/assessment-runs/{run_id}/workflows/baseline_review/pause")
    assert paused.status_code == 200, paused.text
    assert paused.json()["status"] == "paused"

    resumed = domain_client.post(
        f"/api/v1/assessment-runs/{run_id}/workflows/baseline_review/resume",
        json={"answers": ["已确认，后续由人工复核"]},
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == "waiting_human_review"
    assert resumed.json()["state"]["answer_count"] == 1

    reviewed = domain_client.post(
        f"/api/v1/assessment-runs/{run_id}/workflows/baseline_review/review",
        json={"decision": "approve"},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "completed"
    assert reviewed.json()["current_node"] is None

    evidence = domain_client.post(
        f"/api/v1/assessment-runs/{run_id}/workflows/start",
        json={"workflow_name": "evidence_followup"},
    )
    assert evidence.status_code == 200, evidence.text
    assert evidence.json()["status"] == "waiting_for_input"

    restored = domain_client.get(f"/api/v1/assessment-runs/{run_id}/workflows")
    assert restored.status_code == 200, restored.text
    workflow_states = {item["workflow_name"]: item for item in restored.json()["workflows"]}
    assert workflow_states["baseline_review"]["status"] == "completed"
    assert workflow_states["evidence_followup"]["status"] == "waiting_for_input"


def test_m4_rejects_illegal_review_and_empty_answer_but_accepts_explicit_no_additional(
    domain_client,
) -> None:
    workspace = domain_client.post("/api/v1/workspaces", json={"name": "M4状态迁移"}).json()
    source = register_batch(domain_client)
    run = create_run(domain_client, workspace["workspace_id"], source["source_batch_id"], "TFTEST01")
    run_id = run["assessment_run_id"]

    started = domain_client.post(
        f"/api/v1/assessment-runs/{run_id}/workflows/start",
        json={"workflow_name": "baseline_review"},
    )
    assert started.json()["status"] == "waiting_for_input"

    illegal_review = domain_client.post(
        f"/api/v1/assessment-runs/{run_id}/workflows/baseline_review/review",
        json={"decision": "approve"},
    )
    assert illegal_review.status_code == 409

    empty_resume = domain_client.post(
        f"/api/v1/assessment-runs/{run_id}/workflows/baseline_review/resume",
        json={"answers": []},
    )
    assert empty_resume.status_code == 409

    paused = domain_client.post(f"/api/v1/assessment-runs/{run_id}/workflows/baseline_review/pause")
    assert paused.status_code == 200, paused.text
    assert paused.json()["status"] == "paused"
    assert paused.json()["state"]["paused_from_status"] == "waiting_for_input"

    empty_after_pause = domain_client.post(
        f"/api/v1/assessment-runs/{run_id}/workflows/baseline_review/resume",
        json={"answers": []},
    )
    assert empty_after_pause.status_code == 409

    explicit_confirmation = domain_client.post(
        f"/api/v1/assessment-runs/{run_id}/workflows/baseline_review/resume",
        json={"confirm_no_additional": True},
    )
    assert explicit_confirmation.status_code == 200, explicit_confirmation.text
    assert explicit_confirmation.json()["status"] == "waiting_human_review"
    assert explicit_confirmation.json()["state"]["no_additional_confirmed"] is True

    reviewed = domain_client.post(
        f"/api/v1/assessment-runs/{run_id}/workflows/baseline_review/review",
        json={"decision": "approve"},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "completed"


def test_m4_checkpoint_optimistic_lock_rejects_stale_write(domain_client) -> None:
    workspace = domain_client.post("/api/v1/workspaces", json={"name": "M4乐观锁"}).json()
    source = register_batch(domain_client)
    run = create_run(domain_client, workspace["workspace_id"], source["source_batch_id"], "TFTEST01")
    run_id = run["assessment_run_id"]
    started = domain_client.post(
        f"/api/v1/assessment-runs/{run_id}/workflows/start",
        json={"workflow_name": "baseline_review"},
    ).json()
    next_version = started["version"] + 1
    store = main.domain_store

    store.upsert_workflow_checkpoint(
        run_id,
        workflow_name="baseline_review",
        thread_id=started["thread_id"],
        status="paused",
        current_node=started["current_node"],
        version=next_version,
        state=started["state"],
        checkpoint=started["checkpoint"],
    )
    with pytest.raises(DomainConflictError):
        store.upsert_workflow_checkpoint(
            run_id,
            workflow_name="baseline_review",
            thread_id=started["thread_id"],
            status="waiting_for_input",
            current_node=started["current_node"],
            version=next_version,
            state=started["state"],
            checkpoint=started["checkpoint"],
        )


def test_m4_workflow_analysis_view_is_allow_listed() -> None:
    view = workflow_analysis_view(
        {
            "input_data": {"basic_info": {"企业代号": "TFTEST01"}, "secret": "drop"},
            "quality_issues": [],
            "energy_trend": {},
            "catalog_matches": {},
            "reference_comparison": {"结论": "不得进入工作流"},
            "boundaries": {"reference_sheet_excluded_from_input": True},
        }
    )
    assert set(view) == {"input_data", "quality_issues", "energy_trend", "catalog_matches"}
    encoded = json.dumps(view, ensure_ascii=False)
    assert "reference_comparison" not in encoded
    assert "不得进入工作流" not in encoded
    assert "secret" not in encoded


def test_m4_workflows_are_isolated_and_resume_in_a_new_process(domain_client) -> None:
    workspace = domain_client.post("/api/v1/workspaces", json={"name": "M4隔离恢复"}).json()
    source = register_batch(domain_client)
    first = create_run(domain_client, workspace["workspace_id"], source["source_batch_id"], "TFTEST01")
    second = create_run(domain_client, workspace["workspace_id"], source["source_batch_id"], "TFTEST02")

    first_checkpoint = domain_client.post(
        f"/api/v1/assessment-runs/{first['assessment_run_id']}/workflows/start",
        json={"workflow_name": "baseline_review"},
    ).json()
    second_checkpoint = domain_client.post(
        f"/api/v1/assessment-runs/{second['assessment_run_id']}/workflows/start",
        json={"workflow_name": "baseline_review"},
    ).json()
    assert first_checkpoint["thread_id"] != second_checkpoint["thread_id"]
    first_states = domain_client.get(f"/api/v1/assessment-runs/{first['assessment_run_id']}/workflows").json()["workflows"]
    second_states = domain_client.get(f"/api/v1/assessment-runs/{second['assessment_run_id']}/workflows").json()["workflows"]
    assert {item["assessment_run_id"] for item in first_states} == {first["assessment_run_id"]}
    assert {item["assessment_run_id"] for item in second_states} == {second["assessment_run_id"]}

    child_code = """
import json
import os
from fastapi.testclient import TestClient
from app.main import app

run_id = os.environ["M4_RUN_ID"]
client = TestClient(app)
listed = client.get(f"/api/v1/assessment-runs/{run_id}/workflows")
assert listed.status_code == 200, listed.text
resumed = client.post(
    f"/api/v1/assessment-runs/{run_id}/workflows/baseline_review/resume",
    json={"confirm_no_additional": True},
)
assert resumed.status_code == 200, resumed.text
assert resumed.json()["status"] == "waiting_human_review"
reviewed = client.post(
    f"/api/v1/assessment-runs/{run_id}/workflows/baseline_review/review",
    json={"decision": "approve"},
)
assert reviewed.status_code == 200, reviewed.text
print(json.dumps({"status": reviewed.json()["status"], "thread_id": reviewed.json()["thread_id"]}))
"""
    environment = os.environ.copy()
    environment["TRANSITION_FINANCE_APP_DATA_ROOT"] = str(main.domain_store.root)
    environment["M1_RUNTIME_ROOT"] = str(main.store.root)
    environment["M4_RUN_ID"] = first["assessment_run_id"]
    subprocess_result = subprocess.run(
        [sys.executable, "-c", child_code],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert '"status": "completed"' in subprocess_result.stdout


def test_m4_deterministic_fallback_reaches_waiting_state(domain_client, monkeypatch) -> None:
    import app.workflows.runtime as workflow_runtime

    monkeypatch.setattr(workflow_runtime, "LANGGRAPH_AVAILABLE", False)
    monkeypatch.setattr(workflow_runtime, "InMemorySaver", None)
    main.workflow_runtime = None
    workspace = domain_client.post("/api/v1/workspaces", json={"name": "M4离线回退"}).json()
    source = register_batch(domain_client)
    run = create_run(domain_client, workspace["workspace_id"], source["source_batch_id"], "TFTEST01")
    run_id = run["assessment_run_id"]

    listing = domain_client.get(f"/api/v1/assessment-runs/{run_id}/workflows")
    assert listing.status_code == 200
    assert listing.json()["engine"] == "deterministic_fallback"
    started = domain_client.post(
        f"/api/v1/assessment-runs/{run_id}/workflows/start",
        json={"workflow_name": "baseline_review"},
    )
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "waiting_for_input"
