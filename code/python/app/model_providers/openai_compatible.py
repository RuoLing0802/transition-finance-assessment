from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .model_catalog import DEFAULT_SESSION_MODEL, available_model_capabilities, get_model_catalog_entry


SESSION_PROMPT_VERSION = "session-orchestration-v1"
Transport = Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]


class SessionModelError(RuntimeError):
    """Safe error at the external session-model boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SessionModelConfig:
    base_url: str
    api_key: str
    model_id: str
    provider_id: str = "openai-compatible"
    timeout: float = 45.0
    max_retries: int = 1


def _extract_content(raw: dict[str, Any]) -> str:
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        raise SessionModelError("invalid_provider_response", "外部会话模型未返回choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise SessionModelError("invalid_provider_response", "外部会话模型响应缺少message")
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("type") in {"text", "output_text"}
        )
    raise SessionModelError("invalid_provider_response", "外部会话模型响应缺少文本内容")


def _extract_json(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.IGNORECASE | re.DOTALL).strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            raise SessionModelError("invalid_model_json", "外部会话模型未返回可解析的JSON")
        try:
            value = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            raise SessionModelError("invalid_model_json", "外部会话模型返回的JSON无法解析") from exc
    if not isinstance(value, dict):
        raise SessionModelError("invalid_model_schema", "外部会话模型结果不是JSON对象")
    return value


class OpenAICompatibleSessionProvider:
    """Provider-neutral session model adapter using a Chat Completions shape.

    It only returns a structured orchestration proposal. Rules, scoring, source
    facts and report generation remain outside this adapter. Tests inject a
    transport and never send project data to a real provider.
    """

    def __init__(self, config: SessionModelConfig | None, transport: Transport | None = None) -> None:
        self.config = config
        self.transport = transport

    @classmethod
    def from_environment(
        cls,
        model_id: str | None = None,
        transport: Transport | None = None,
    ) -> "OpenAICompatibleSessionProvider":
        base_url = os.environ.get("TRANSITION_FINANCE_SESSION_API_BASE_URL", "").strip()
        api_key = os.environ.get("TRANSITION_FINANCE_SESSION_API_KEY", "").strip()
        configured_model_id = os.environ.get("TRANSITION_FINANCE_SESSION_MODEL", "").strip()
        selected_model_id = (model_id or configured_model_id or DEFAULT_SESSION_MODEL).strip()
        provider_id = os.environ.get("TRANSITION_FINANCE_SESSION_PROVIDER", "openai-compatible").strip()
        try:
            timeout = float(os.environ.get("TRANSITION_FINANCE_SESSION_TIMEOUT", "45"))
        except ValueError:
            timeout = 45.0
        try:
            max_retries = int(os.environ.get("TRANSITION_FINANCE_SESSION_MAX_RETRIES", "1"))
        except ValueError:
            max_retries = 1
        config = None
        if base_url and api_key and selected_model_id:
            config = SessionModelConfig(
                base_url=base_url,
                api_key=api_key,
                model_id=selected_model_id,
                provider_id=provider_id or "openai-compatible",
                timeout=max(1.0, min(timeout, 180.0)),
                max_retries=max(0, min(max_retries, 2)),
            )
        return cls(config, transport=transport)

    @classmethod
    def available_models_from_environment(cls) -> list[dict[str, Any]]:
        base_url = os.environ.get("TRANSITION_FINANCE_SESSION_API_BASE_URL", "").strip()
        api_key = os.environ.get("TRANSITION_FINANCE_SESSION_API_KEY", "").strip()
        provider_id = os.environ.get("TRANSITION_FINANCE_SESSION_PROVIDER", "openai-compatible").strip() or "openai-compatible"
        return available_model_capabilities(configured=bool(base_url and api_key), provider_id=provider_id)

    def capability(self) -> dict[str, Any]:
        if self.config is None:
            return {
                "available": False,
                "provider_id": None,
                "model_id": None,
                "display_name": None,
                "context_window": None,
                "multimodal": False,
                "reason": "未配置会话模型的后端API地址、密钥和模型标识",
                "mode": "external",
            }
        catalog_entry = get_model_catalog_entry(self.config.model_id)
        if catalog_entry is None:
            return {
                "available": False,
                "provider_id": self.config.provider_id,
                "model_id": self.config.model_id,
                "display_name": None,
                "context_window": None,
                "multimodal": False,
                "supports_vision": False,
                "capabilities": [],
                "reason": "请求的模型不在当前受控模型能力目录中",
                "mode": "external",
            }
        return {
            "available": True,
            "provider_id": self.config.provider_id,
            "model_id": self.config.model_id,
            "display_name": f"{self.config.provider_id}/{self.config.model_id}",
            "context_window": None,
            "multimodal": bool(catalog_entry and "vision" in catalog_entry["capabilities"]),
            "supports_vision": bool(catalog_entry and "vision" in catalog_entry["capabilities"]),
            "capabilities": catalog_entry["capabilities"] if catalog_entry else ["text"],
            "reason": None,
            "mode": "external",
        }

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        purpose: str = "assessment_session",
    ) -> dict[str, Any]:
        if self.config is None:
            raise SessionModelError("provider_unavailable", "未配置外部会话模型，已进入离线模式")
        payload = {
            "model": self.config.model_id,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "metadata": {"purpose": purpose, "prompt_version": SESSION_PROMPT_VERSION},
            "tools": tools,
        }
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "X-Transition-Finance-Prompt-Version": SESSION_PROMPT_VERSION,
        }
        raw = self._request(payload, headers)
        return _extract_json(_extract_content(raw))

    def _request(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        url = self._completion_url()
        max_retries = self.config.max_retries if self.config else 0
        timeout = self.config.timeout if self.config else 45.0
        for attempt in range(max_retries + 1):
            try:
                if self.transport is not None:
                    response = self.transport(url, headers, payload, timeout)
                else:
                    request = Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers=headers, method="POST")
                    with urlopen(request, timeout=timeout) as response_stream:
                        response = json.loads(response_stream.read().decode("utf-8"))
                if not isinstance(response, dict):
                    raise SessionModelError("invalid_provider_response", "外部会话模型响应不是JSON对象")
                return response
            except SessionModelError as exc:
                retryable = exc.code in {"api_network_error", "rate_limited", "timeout"}
                if retryable and attempt < max_retries:
                    continue
                raise
            except HTTPError as exc:
                code = "rate_limited" if exc.code == 429 else "api_http_error"
                error = SessionModelError(code, f"外部会话模型返回HTTP {exc.code}")
                retryable = exc.code == 429 or exc.code == 408 or exc.code >= 500
                if retryable and attempt < max_retries:
                    continue
                raise error from exc
            except (URLError, TimeoutError, OSError) as exc:
                error = SessionModelError("api_network_error", f"外部会话模型调用失败：{type(exc).__name__}")
                if attempt < max_retries:
                    continue
                raise error from exc
            except json.JSONDecodeError as exc:
                raise SessionModelError("invalid_provider_response", "外部会话模型返回内容不是有效JSON") from exc
        raise SessionModelError("api_network_error", "外部会话模型调用失败")

    def _completion_url(self) -> str:
        if self.config is None:
            return ""
        base_url = self.config.base_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        if base_url.endswith("/v1"):
            return f"{base_url}/chat/completions"
        return f"{base_url}/v1/chat/completions"
