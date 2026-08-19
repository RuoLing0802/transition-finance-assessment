from __future__ import annotations

from typing import Any


DEFAULT_SESSION_MODEL = "qwen3.7-plus"
DEFAULT_VISION_MODEL = "qwen3.6-flash"

# This is a product capability catalog, not a claim that the current machine
# is configured or that any provider call has succeeded.
SESSION_MODEL_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "model_id": "qwen3.8-max",
        "display_name": "千问 qwen3.8-max",
        "provider_family": "qwen",
        "capabilities": ["text", "reasoning", "vision"],
        "recommended_for": ["复杂会话编排", "视觉理解", "高质量解释"],
    },
    {
        "model_id": "qwen3.7-plus",
        "display_name": "千问 qwen3.7-plus",
        "provider_family": "qwen",
        "capabilities": ["text", "reasoning", "vision"],
        "recommended_for": ["默认会话", "视觉理解", "通用评估解释"],
    },
    {
        "model_id": "qwen3.7-max",
        "display_name": "千问 qwen3.7-max",
        "provider_family": "qwen",
        "capabilities": ["text", "reasoning"],
        "recommended_for": ["复杂文本推理", "结构化结果解释"],
    },
    {
        "model_id": "qwen3.6-flash",
        "display_name": "千问 qwen3.6-flash",
        "provider_family": "qwen",
        "capabilities": ["text", "reasoning", "vision"],
        "recommended_for": ["图片/扫描PDF解析", "快速会话", "视觉降级回退"],
    },
    {
        "model_id": "deepseek-v4-pro-0813",
        "display_name": "DeepSeek deepseek-v4-pro-0813",
        "provider_family": "deepseek",
        "capabilities": ["text", "reasoning"],
        "recommended_for": ["复杂文本推理", "评估解释"],
    },
    {
        "model_id": "deepseek-v4-pro",
        "display_name": "DeepSeek deepseek-v4-pro",
        "provider_family": "deepseek",
        "capabilities": ["text", "reasoning"],
        "recommended_for": ["复杂文本推理", "评估解释"],
    },
    {
        "model_id": "deepseek-v4-flash-0731",
        "display_name": "DeepSeek deepseek-v4-flash-0731",
        "provider_family": "deepseek",
        "capabilities": ["text", "reasoning"],
        "recommended_for": ["快速文本推理", "低延迟会话"],
    },
    {
        "model_id": "glm-5.2",
        "display_name": "智谱 GLM-5.2",
        "provider_family": "zhipu",
        "capabilities": ["text", "reasoning"],
        "recommended_for": ["文本推理", "结构化结果解释"],
    },
)

_CATALOG_BY_ID = {item["model_id"]: item for item in SESSION_MODEL_CATALOG}


def get_model_catalog_entry(model_id: str) -> dict[str, Any] | None:
    entry = _CATALOG_BY_ID.get(model_id)
    return dict(entry) if entry else None


def model_supports_vision(model_id: str | None) -> bool:
    entry = _CATALOG_BY_ID.get(model_id or "")
    return bool(entry and "vision" in entry["capabilities"])


def vision_route(selected_model_id: str | None) -> dict[str, Any]:
    return vision_route_with_capability(selected_model_id)


def vision_route_with_capability(selected_model_id: str | None, *, supports_vision: bool | None = None) -> dict[str, Any]:
    selected = selected_model_id or DEFAULT_SESSION_MODEL
    selected_supports_vision = model_supports_vision(selected) if supports_vision is None else supports_vision
    if selected_supports_vision:
        return {
            "requested_model_id": selected,
            "vision_model_id": selected,
            "return_to_model_id": selected,
            "switched": False,
            "reason": "所选模型支持视觉理解，直接使用所选模型解析。",
        }
    return {
        "requested_model_id": selected,
        "vision_model_id": DEFAULT_VISION_MODEL,
        "return_to_model_id": selected,
        "switched": True,
        "reason": f"所选模型 {selected} 不支持视觉理解，先由 {DEFAULT_VISION_MODEL} 提取证据，再回到 {selected} 继续会话。",
    }


def custom_model_capability(config: dict[str, Any]) -> dict[str, Any]:
    model_config_id = str(config.get("model_config_id") or config.get("model_id") or "")
    model_name = str(config.get("model_name") or "")
    display_name = str(config.get("display_name") or model_name or model_config_id)
    supports_vision = bool(config.get("supports_vision"))
    return {
        "available": bool(model_config_id and model_name and config.get("api_key_configured", True)),
        "provider_id": config.get("provider_id") or "openai-compatible",
        "model_id": model_config_id,
        "provider_model": model_name,
        "display_name": display_name,
        "context_window": None,
        "multimodal": supports_vision,
        "supports_vision": supports_vision,
        "capabilities": ["text", "reasoning", "vision"] if supports_vision else ["text", "reasoning"],
        "recommended_for": ["用户自定义会话"],
        "reason": None,
        "mode": "external",
        "custom": True,
    }


def available_model_capabilities(*, configured: bool, provider_id: str = "openai-compatible") -> list[dict[str, Any]]:
    if not configured:
        return []
    return [
        {
            "available": True,
            "provider_id": provider_id,
            "model_id": item["model_id"],
            "display_name": item["display_name"],
            "context_window": None,
            "multimodal": "vision" in item["capabilities"],
            "supports_vision": "vision" in item["capabilities"],
            "capabilities": item["capabilities"],
            "recommended_for": item["recommended_for"],
            "reason": None,
            "mode": "external",
        }
        for item in SESSION_MODEL_CATALOG
    ]
