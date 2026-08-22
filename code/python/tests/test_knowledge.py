from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from app.domain_store import DomainStore
from app.knowledge.policy import BM25_WEIGHTS, INDUSTRIES, public_url
from app.knowledge.service import KnowledgeAssetPaths, KnowledgeIndexNotReady, KnowledgeService
from app.orchestration.tools import ToolBoundaryError, execute_tool


def _service(tmp_path: Path, *codes: str) -> tuple[DomainStore, KnowledgeService, dict[str, dict]]:
    store = DomainStore(tmp_path / "application-data")
    batch = store.register_source_batch(
        m1_batch_id="m1-knowledge-test",
        source_filename="配套数据.xlsx",
        sha256="a" * 64,
        validation_status="passed",
        available_company_codes=list(codes),
    )
    workspace = store.create_workspace("M5知识检索测试")
    runs: dict[str, dict] = {}
    for code, industry in zip(codes, ("冶金行业 铜", "钢铁"), strict=False):
        runs[code] = store.create_assessment_run(
            workspace_id=workspace["workspace_id"],
            enterprise_code=code,
            source_batch_id=batch["source_batch_id"],
            run_name=f"{code}知识检索",
            rule_version="m5-test",
            model_config={"mode": "offline"},
            basic_info_index={"企业代号": code, "行业": industry},
        )

    def analysis_loader(run_id: str):
        run = store.get_assessment_run(run_id)
        industry = {"TF0001": "冶金行业 铜", "TF0002": "钢铁", "TF0003": "冶金行业 铝"}.get(run["enterprise_code"], "钢铁")
        return run, {"input_data": {"basic_info": {"企业代号": run["enterprise_code"], "行业": industry}}}

    return store, KnowledgeService(store, analysis_loader=analysis_loader), runs


def _service_for_specs(tmp_path: Path, specs: list[tuple[str, str]]) -> tuple[DomainStore, KnowledgeService, dict[str, dict]]:
    store = DomainStore(tmp_path / "application-data")
    codes = [code for code, _industry in specs]
    batch = store.register_source_batch(
        m1_batch_id="m1-knowledge-isolation-test",
        source_filename="配套数据.xlsx",
        sha256="b" * 64,
        validation_status="passed",
        available_company_codes=codes,
    )
    workspace = store.create_workspace("M5 Gold隔离探针测试")
    industry_by_code = {code: industry for code, industry in specs}
    runs: dict[str, dict] = {}
    for code, industry in specs:
        runs[code] = store.create_assessment_run(
            workspace_id=workspace["workspace_id"],
            enterprise_code=code,
            source_batch_id=batch["source_batch_id"],
            run_name=f"{code} Gold隔离测试",
            rule_version="m5-test",
            model_config={"mode": "offline"},
            basic_info_index={"企业代号": code, "行业": industry},
        )

    def analysis_loader(run_id: str):
        run = store.get_assessment_run(run_id)
        industry = industry_by_code[run["enterprise_code"]]
        return run, {"input_data": {"basic_info": {"企业代号": run["enterprise_code"], "行业": industry}}}

    return store, KnowledgeService(store, analysis_loader=analysis_loader), runs


def test_m5_dry_run_reports_admission_stats_and_no_reference_layer(tmp_path: Path) -> None:
    _store, service, _runs = _service(tmp_path, "TF0001")
    report = service.dry_run()
    stats = report["stats"]
    assert report["status"] == "ready"
    assert stats["industry_count"] == 11
    assert stats["governance_records"] == 731
    assert stats["diagnostic_only"] == 710
    assert stats["factor_candidate_blocked"] == 21
    manifest = service._manifest()
    research_sources = [item for item in manifest["source_entries"] if item["source_role"] == "research_literature"]
    research_chunks = [item for item in manifest["chunks"] if item["chunk_type"] == "research_fragment"]
    searchable_research_ids = {item["source_id"] for item in research_sources if item["visibility"] == "searchable_candidate"}
    assert len(research_sources) == 19
    assert stats["research_fragment_chunks"] == len(research_chunks)
    assert {item["source_id"] for item in research_chunks} <= searchable_research_ids
    assert stats["reference_conclusion_hits"] == 0
    assert report["reference_conclusion_hits"] == []
    assert "转型规划结论" not in json.dumps(report, ensure_ascii=False)


def test_m5_rebuild_search_returns_traceable_chunk_and_freezes_context(tmp_path: Path) -> None:
    store, service, runs = _service(tmp_path, "TF0001")
    status = service.rebuild()
    result = service.search(runs["TF0001"]["assessment_run_id"], "铜行业 节能 技术", top_k=3)
    assert result["index_version_id"] == status["index_version_id"]
    assert result["allowlist_version"] == "M5-ALLOWLIST-v1"
    assert result["results"]
    first = result["results"][0]
    assert first["chunk_id"] and first["document_id"] and first["locator"]
    assert first["visibility"] == "searchable_candidate"
    assert first["use_boundary"]
    assert "转型规划结论" not in json.dumps(result, ensure_ascii=False)
    context = store._connection()
    with context as connection:
        frozen = connection.execute(
            "SELECT * FROM assessment_run_knowledge_context WHERE assessment_run_id = ?",
            (runs["TF0001"]["assessment_run_id"],),
        ).fetchone()
    assert frozen is not None
    assert frozen["index_version_id"] == status["index_version_id"]
    assert service.get_chunk(runs["TF0001"]["assessment_run_id"], first["chunk_id"])["document_id"] == first["document_id"]


def test_m5_normal_search_never_builds_an_index(tmp_path: Path) -> None:
    _store, service, runs = _service(tmp_path, "TF0001")
    with pytest.raises(KnowledgeIndexNotReady):
        service.search(runs["TF0001"]["assessment_run_id"], "铜行业 节能")
    assert service.index_status()["available"] is False


def test_m5_run_scoped_logs_and_industry_filter_do_not_cross_runs(tmp_path: Path) -> None:
    _store, service, runs = _service(tmp_path, "TF0001", "TF0002")
    service.rebuild()
    first = service.search(runs["TF0001"]["assessment_run_id"], "铜行业 节能", top_k=2)
    second = service.search(runs["TF0002"]["assessment_run_id"], "钢铁 工序", top_k=2)
    assert first["enterprise_id"] != second["enterprise_id"]
    assert first["retrieval_id"] != second["retrieval_id"]
    assert service.list_retrievals(runs["TF0001"]["assessment_run_id"])[0]["assessment_run_id"] == runs["TF0001"]["assessment_run_id"]
    assert service.list_retrievals(runs["TF0002"]["assessment_run_id"])[0]["assessment_run_id"] == runs["TF0002"]["assessment_run_id"]
    assert all(item["source_id"] not in {"STD-007", "CETS-VG-001"} for item in first["results"])
    if first["results"] and first["results"][0]["chunk_id"]:
        with pytest.raises(LookupError):
            service.get_chunk(runs["TF0002"]["assessment_run_id"], first["results"][0]["chunk_id"])


def test_m5_gold_tests_are_real_44_record_execution(tmp_path: Path) -> None:
    _store, service, _runs = _service(tmp_path, "TF0001", "TF0002")
    service.rebuild()
    results = service.run_gold_tests()
    assert len(results) == 44
    assert all(item["status"] in {"passed", "correct_degrade"} for item in results)
    target_misses = [item for item in results if item["target_expected"] and not item["target_hit"]]
    assert len(target_misses) == 11
    assert all(item["status"] == "correct_degrade" and item["passed"] is False for item in target_misses)
    assert not any(item["target_expected"] and not item["target_hit"] and item["status"] == "passed" for item in results)
    assert {item["mode"] for item in results} >= {"real_service_negative_search", "real_run_isolation_probe", "deterministic_ordinary_and_governance_check"}
    assert all("actual_top_k" in item and "expected_behavior" in item for item in results)
    copper = next(item for item in results if item["test_id"] == "T-S2-02-01")
    assert "PATH-001" in copper["diagnostic_matches"]
    assert not any(item.startswith("PATH-") for item in copper["actual_source_ids"])


def test_m5_isolation_probes_use_source_only_non_global_chunks_and_distinguish_boundaries(tmp_path: Path) -> None:
    _store, service, _runs = _service(tmp_path, "TF0001", "TF0002")
    service.rebuild()
    results = {item["test_id"]: item for item in service.run_gold_tests()}
    for test_id, boundary_type in (("N-S2-05", "cross_enterprise"), ("N-S2-06", "cross_run")):
        item = results[test_id]
        probe = item["isolation_probe"]
        assert item["status"] == "passed"
        assert probe["status"] == "passed"
        assert probe["boundary_type"] == boundary_type
        assert probe["probe_chunk_id"] in probe["source_returned_chunk_ids"]
        assert probe["probe_chunk_id"] not in probe["target_returned_chunk_ids"]
        assert "global" not in probe["probe_industry_scope"]
        assert probe["source_assessment_run_id"] != probe["target_assessment_run_id"]
        assert probe["source_thread_id"] != probe["target_thread_id"]
        assert probe["checks"]["target_rejected"] is True
        assert probe["target_rejection_reason"]
        assert probe["source_retrieval_id"] != probe["target_retrieval_id"]
        if boundary_type == "cross_enterprise":
            assert probe["source_enterprise_id"] != probe["target_enterprise_id"]
        else:
            assert probe["source_assessment_run_id"] != probe["target_assessment_run_id"]


def test_m5_gold_isolation_is_order_independent_with_eleven_runs_and_shared_global_hits(tmp_path: Path) -> None:
    specs = list(zip((f"TF{index:04d}" for index in range(1, 12)), INDUSTRIES, strict=True))
    distributions: list[Counter[str]] = []
    probes: list[dict[str, dict]] = []
    for label, ordered_specs in (("forward", specs), ("reverse", list(reversed(specs)))):
        _store, service, runs = _service_for_specs(tmp_path / label, ordered_specs)
        service.rebuild()
        # Both selected runs legitimately receive the same global research
        # result. The isolation probe must not mistake that shared evidence
        # for a cross-run violation.
        first_code, second_code = ordered_specs[0][0], ordered_specs[1][0]
        service.search(runs[first_code]["assessment_run_id"], "转型金融 碳减排", top_k=3)
        service.search(runs[second_code]["assessment_run_id"], "转型金融 碳减排", top_k=3)
        results = service.run_gold_tests()
        distributions.append(Counter(item["status"] for item in results))
        probes.append({item["test_id"]: item["isolation_probe"] for item in results if item["test_id"] in {"N-S2-05", "N-S2-06"}})

    assert distributions == [Counter({"passed": 33, "correct_degrade": 11})] * 2
    for probe_set in probes:
        for probe in probe_set.values():
            assert probe["status"] == "passed"
            assert "global" not in probe["probe_industry_scope"]
            assert probe["probe_chunk_id"] not in probe["target_returned_chunk_ids"]
            assert probe["checks"]["target_rejected"] is True


def test_m5_research_fragments_have_governed_global_scope_or_safely_degrade_without_local_pdfs(tmp_path: Path) -> None:
    store, service, _runs = _service(tmp_path, "TF0001")
    service.rebuild()
    with store._connection() as connection:
        research = connection.execute(
            "SELECT source_id, industry_scope_json, mapping_method, visibility FROM knowledge_sources WHERE source_role = 'research_literature' ORDER BY source_id"
        ).fetchall()
        index = service.index_status()
        assert len(research) == 19
        chinese = [row for row in research if row["source_id"].startswith("CN-LIT-")]
        english = [row for row in research if row["source_id"].startswith("EN-LIT-")]
        assert len(chinese) == 12
        assert len(english) == 7
        assert all(json.loads(row["industry_scope_json"]) == ["global"] for row in chinese)
        assert all(row["mapping_method"] == "literature_id_exact+governance_global_scope" for row in chinese)
        assert all(row["visibility"] == "blocked" for row in english)
        searchable = [row for row in chinese if row["visibility"] == "searchable_candidate"]
        for industry in INDUSTRIES:
            rows = service._search_rows(connection, index, "转型金融 碳减排", industry, [], "2026-08-22")
            has_chinese_research = any(str(row[0]["source_id"]).startswith("CN-LIT-") for row in rows)
            assert has_chinese_research is bool(searchable), industry


def test_m5_missing_controlled_pdf_originals_degrade_without_creating_research_chunks(tmp_path: Path) -> None:
    store = DomainStore(tmp_path / "application-data")
    service = KnowledgeService(
        store,
        assets=KnowledgeAssetPaths.from_project_root(),
        project_root=tmp_path / "clean-public-clone",
    )
    report = service.dry_run()
    assert report["status"] == "ready"
    assert report["stats"]["research_fragment_chunks"] == 0
    assert report["stats"]["reference_conclusion_hits"] == 0
    service.rebuild()
    with store._connection() as connection:
        research = connection.execute(
            "SELECT visibility FROM knowledge_sources WHERE source_role = 'research_literature'"
        ).fetchall()
        chunks = connection.execute(
            "SELECT chunk_id FROM knowledge_chunks WHERE chunk_type = 'research_fragment'"
        ).fetchall()
    assert len(research) == 19
    assert all(row["visibility"] == "blocked" for row in research)
    assert chunks == []


def test_m5_admission_decision_change_appends_supersedes_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, service, _runs = _service(tmp_path, "TF0001")
    service.rebuild()
    with store._connection() as connection:
        previous = connection.execute(
            "SELECT decision_id FROM knowledge_admission_decisions WHERE source_id = 'STD-003'"
        ).fetchone()
    assert previous is not None

    original = service._decision_for_source

    def changed_decision(source, asset, *, mapping_method):
        decision = original(source, asset, mapping_method=mapping_method)
        if source.get("source_id") == "STD-003":
            decision.update({
                "visibility": "blocked",
                "hash_status": "mismatch",
                "actual_sha256": "b" * 64,
                "decision_basis": "测试：受控原件SHA-256不一致，正文阻断",
            })
            decision["allowlist_entry_id"] = service._admission_decision_id(decision)
        return decision

    monkeypatch.setattr(service, "_decision_for_source", changed_decision)
    service.rebuild()
    with store._connection() as connection:
        history = connection.execute(
            "SELECT decision_id, visibility, supersedes_decision_id FROM knowledge_admission_decisions WHERE source_id = 'STD-003' ORDER BY decision_id"
        ).fetchall()
    assert len(history) == 2
    new_decision = next(row for row in history if row["decision_id"] != previous["decision_id"])
    assert new_decision["visibility"] == "blocked"
    assert new_decision["supersedes_decision_id"] == previous["decision_id"]


def test_m5_fts_weights_cover_unindexed_and_indexed_columns() -> None:
    assert len(BM25_WEIGHTS) == 8
    assert BM25_WEIGHTS[:3] == (0.0, 0.0, 0.0)
    assert BM25_WEIGHTS[3:] == (10.0, 12.0, 6.0, 1.0, 0.0)


def test_m5_rebuild_reuses_identical_manifest_without_rewriting_members(tmp_path: Path) -> None:
    store, service, _runs = _service(tmp_path, "TF0001")
    first = service.rebuild()
    with store._connection() as connection:
        before = connection.execute("SELECT COUNT(*) AS count FROM knowledge_index_members WHERE index_version_id = ?", (first["index_version_id"],)).fetchone()["count"]
    second = service.rebuild()
    with store._connection() as connection:
        after = connection.execute("SELECT COUNT(*) AS count FROM knowledge_index_members WHERE index_version_id = ?", (first["index_version_id"],)).fetchone()["count"]
    assert second["index_version_id"] == first["index_version_id"]
    assert before == after


def test_m5_metadata_only_requires_exact_source_lookup_and_marks_year_uncertain(tmp_path: Path) -> None:
    _store, service, runs = _service(tmp_path, "TF0003")
    service.rebuild()
    result = service.search(runs["TF0003"]["assessment_run_id"], "CETS-VG-002", top_k=3)
    assert result["results"]
    metadata = next(item for item in result["results"] if item["source_id"] == "CETS-VG-002")
    assert metadata["result_type"] == "source_metadata"
    assert metadata["chunk_id"] is None
    assert metadata["excerpt"] is None
    assert metadata["locator"] is None
    assert metadata["date_uncertain"] is True
    assert any("date_uncertain" in warning for warning in result["warnings"])


def test_m5_public_url_only_returns_http_or_https() -> None:
    assert public_url("https://example.com/source") == "https://example.com/source"
    assert public_url("javascript:alert(1)") is None
    assert public_url("file:///tmp/private.pdf") is None


def test_m5_negative_query_guards_block_reference_candidate_and_factor_requests(tmp_path: Path) -> None:
    _store, service, runs = _service(tmp_path, "TF0001")
    service.rebuild()
    run_id = runs["TF0001"]["assessment_run_id"]
    for query, marker in (
        ("要求直接执行候选规则阈值", "候选规则"),
        ("要求直接调用未经核准排放因子", "排放因子"),
        ("检索隔离参考结论类字段作为输入标签", "参考对照"),
    ):
        response = service.search(run_id, query)
        assert response["results"] == []
        assert any(marker in warning for warning in response["warnings"])


def test_m5_search_knowledge_tool_is_read_only_and_run_bound(tmp_path: Path) -> None:
    _store, service, runs = _service(tmp_path, "TF0001", "TF0002")
    service.rebuild()
    current = runs["TF0001"]
    result = execute_tool(
        "search_knowledge",
        {"query": "铜行业 节能", "top_k": 2},
        run=current,
        analysis={},
        attachments_loader=lambda _run_id: [],
        knowledge_searcher=lambda run_id, query, top_k, roles: service.search(run_id, query, top_k=top_k, source_roles=roles),
    )
    assert result["assessment_run_id"] == current["assessment_run_id"]
    assert result["results"]
    with pytest.raises(ToolBoundaryError):
        execute_tool(
            "search_knowledge",
            {"assessment_run_id": runs["TF0002"]["assessment_run_id"], "query": "钢铁 工序"},
            run=current,
            analysis={},
            attachments_loader=lambda _run_id: [],
            knowledge_searcher=lambda *_args: {},
        )
    with pytest.raises(ToolBoundaryError):
        execute_tool(
            "search_knowledge",
            {"query": "参考结论类字段"},
            run=current,
            analysis={},
            attachments_loader=lambda _run_id: [],
            knowledge_searcher=lambda *_args: {},
        )
