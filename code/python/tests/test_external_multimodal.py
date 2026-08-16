from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.parsers.external_multimodal import ExternalMultimodalClient, ExternalMultimodalError
from app.parsers.multimodal import parse_file


def _image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (160, 80), color="white").save(output, format="PNG")
    return output.getvalue()


def _scanned_pdf_bytes() -> bytes:
    image = _image_bytes()
    output = BytesIO()
    document = canvas.Canvas(output)
    document.drawImage(ImageReader(BytesIO(image)), 72, 680, width=160, height=80)
    document.save()
    return output.getvalue()


def _client(response: dict, calls: list[tuple[str, dict, dict]]) -> ExternalMultimodalClient:
    def transport(url: str, headers: dict[str, str], payload: dict, timeout: float) -> dict:
        calls.append((url, headers, payload))
        return response

    return ExternalMultimodalClient(
        base_url="https://provider.example/v1",
        api_key="secret-not-for-logs",
        model="vision-test-model",
        provider="mock-provider",
        transport=transport,
    )


def _response(text: str, confidence: float = 0.95) -> dict:
    return {
        "id": "mock-response",
        "choices": [{
            "message": {
                "content": (
                    '{"items":[{"text":"%s","location":{"page":1,"bbox":[1,2,30,40]},"confidence":%s}],'
                    '"enterprise_codes":["TFTEST01"],"notes":[]}'
                ) % (text, confidence),
            }
        }],
    }


def test_external_image_adapter_returns_evidence_and_keeps_secret_out_of_payload(tmp_path: Path) -> None:
    calls: list[tuple[str, dict, dict]] = []
    client = _client(_response("企业代号：TFTEST01"), calls)
    path = tmp_path / "evidence.png"
    path.write_bytes(_image_bytes())
    result = parse_file(path, path.name, "TFTEST01", external_client=client)
    assert result["status"] == "passed"
    assert result["parser"] == "external_multimodal"
    assert result["detected_enterprise_codes"] == ["TFTEST01"]
    assert result["metadata"]["external_multimodal"]["model"] == "vision-test-model"
    assert result["metadata"]["external_multimodal"]["response_id"] == "mock-response"
    assert calls[0][0] == "https://provider.example/v1/chat/completions"
    assert calls[0][1]["Authorization"] == "Bearer secret-not-for-logs"
    serialized_payload = str(calls[0][2])
    assert "secret-not-for-logs" not in serialized_payload
    assert "转型规划结论" in serialized_payload


def test_external_scanned_pdf_is_rendered_and_page_location_is_preserved(tmp_path: Path) -> None:
    calls: list[tuple[str, dict, dict]] = []
    client = _client(_response("企业代号：TFTEST01"), calls)
    path = tmp_path / "scanned.pdf"
    path.write_bytes(_scanned_pdf_bytes())
    result = parse_file(path, path.name, "TFTEST01", external_client=client)
    assert result["status"] == "passed"
    assert "external_multimodal" in result["parser"]
    assert result["metadata"]["native_text_pages"] == 0
    assert any(item["location"].get("page") == 1 for item in result["evidence"])
    assert calls


def test_external_low_confidence_and_conflict_are_still_blocked(tmp_path: Path) -> None:
    calls: list[tuple[str, dict, dict]] = []
    client = _client(_response("企业代号：TFTEST02", confidence=0.42), calls)
    path = tmp_path / "conflict.png"
    path.write_bytes(_image_bytes())
    result = parse_file(path, path.name, "TFTEST01", external_client=client)
    assert result["status"] == "blocked_conflict"
    assert result["merge_allowed"] is False
    codes = {issue["code"] for issue in result["issues"]}
    assert {"enterprise_conflict", "low_confidence"}.issubset(codes)


def test_external_failure_degrades_to_manual_review_without_raising(tmp_path: Path) -> None:
    def failing_transport(url: str, headers: dict[str, str], payload: dict, timeout: float) -> dict:
        raise ExternalMultimodalError("api_http_error", "模拟API失败")

    client = ExternalMultimodalClient(
        base_url="https://provider.example/v1",
        api_key="secret",
        model="vision-test-model",
        transport=failing_transport,
    )
    path = tmp_path / "failed.png"
    path.write_bytes(_image_bytes())
    result = parse_file(path, path.name, "TFTEST01", external_client=client)
    assert result["status"] == "needs_review"
    assert result["merge_allowed"] is False
    assert any(issue["code"] == "external_api_failed" for issue in result["issues"])


def test_session_endpoint_can_route_selected_text_model_to_vision_model(monkeypatch) -> None:
    monkeypatch.delenv("TRANSITION_FINANCE_MULTIMODAL_API_BASE_URL", raising=False)
    monkeypatch.delenv("TRANSITION_FINANCE_MULTIMODAL_API_KEY", raising=False)
    monkeypatch.delenv("TRANSITION_FINANCE_MULTIMODAL_MODEL", raising=False)
    monkeypatch.setenv("TRANSITION_FINANCE_SESSION_API_BASE_URL", "https://example.invalid/compatible-mode/v1")
    monkeypatch.setenv("TRANSITION_FINANCE_SESSION_API_KEY", "sk-test-only")
    client = ExternalMultimodalClient.from_environment(model_override="qwen3.6-flash")
    assert client.base_url.endswith("compatible-mode/v1")
    assert client.model == "qwen3.6-flash"
    assert client.configured is True
