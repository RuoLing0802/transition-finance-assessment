from __future__ import annotations

import re
import unicodedata
from typing import Any
from urllib.parse import urlparse


ALLOWLIST_VERSION = "M5-ALLOWLIST-v1"
RANKING_CONFIG_VERSION = "ranking-config-v2"
TOKENIZER_VERSION = "zh-ngram-v1"
INDUSTRY_MAPPING_VERSION = "industry-map-v2"
DECISION_DATE = "2026-08-22"

# knowledge_fts has three UNINDEXED columns before the five indexed columns:
# title, standard_no, section_title, body and normalized_search_text. Keep the
# leading zeroes explicit so a later query cannot silently shift weights onto
# entry metadata.
BM25_WEIGHTS = (0.0, 0.0, 0.0, 10.0, 12.0, 6.0, 1.0, 0.0)

INDUSTRY_MAP = {
    "农业行业": "农业",
    "农业": "农业",
    "冶金行业 铜": "冶金行业铜",
    "冶金行业铜": "冶金行业铜",
    "铜": "冶金行业铜",
    "冶金行业 铝": "冶金行业铝",
    "冶金行业铝": "冶金行业铝",
    "铝": "冶金行业铝",
    "化工业": "化工",
    "化工": "化工",
    "建材行业": "建材",
    "建材": "建材",
    "水上运输行业": "水上运输",
    "水上运输": "水上运输",
    "煤电行业": "煤电",
    "煤电": "煤电",
    "石化行业": "石化",
    "石化": "石化",
    "纺织行业": "纺织",
    "纺织": "纺织",
    "钢铁行业": "钢铁",
    "钢铁": "钢铁",
    "陶瓷行业": "陶瓷",
    "陶瓷": "陶瓷",
}
INDUSTRIES = (
    "农业",
    "冶金行业铜",
    "冶金行业铝",
    "化工",
    "建材",
    "水上运输",
    "煤电",
    "石化",
    "纺织",
    "钢铁",
    "陶瓷",
)

SEARCHABLE_SOURCE_IDS = {
    "CETS-VG-001",
    "POL-001",
    "STD-001",
    "STD-002",
    "STD-003",
    "STD-004",
    "STD-005",
    "STD-007",
    "STD-008",
    "STD-009",
    "STD-010",
    "MEE-GHG-QA-2025",
}
METADATA_ONLY_SOURCE_IDS = {
    "CETS-004",
    "CETS-POWER-UP-2026",
    "CETS-VG-002",
    "CETS-VG-003",
    "FAC-DB2",
}
BLOCKED_SOURCE_IDS = {
    "F-SRC-001",
    "F-SRC-002",
    "F-SRC-003",
    "F-SRC-004",
    "F-SRC-005",
    "F-SRC-006",
    "F-SRC-007",
    "F-SRC-008",
    "F-SRC-009",
    "F-SRC-010",
    "F-SRC-011",
    "F-SRC-012",
    "F-SRC-013",
    "F-SRC-014",
    "F-SRC-015",
    "F-SRC-016",
    "F-SRC-017",
    "F-SRC-018",
    "F-SRC-019",
    "F-SRC-020",
    "F-SRC-021",
}

SOURCE_ROLE_ORDER = {
    "official_standard": 0,
    "official_policy": 1,
    "regulatory_guidance": 2,
    "official_methodology": 3,
    "research_literature": 4,
    "other": 5,
}

# 03's accepted literature governance records classify the 12 Chinese papers
# as cross-industry research evidence for module 07/08. They are deliberately
# explicit here: "global" is a governance decision for research evidence, not
# a default for unknown sources and not an authorization to treat the papers
# as policy, standards, factors, scores or labels.
RESEARCH_INDUSTRY_SCOPE = {
    "CN-LIT-001": ["global"],
    "CN-LIT-002": ["global"],
    "CN-LIT-003": ["global"],
    "CN-LIT-004": ["global"],
    "CN-LIT-005": ["global"],
    "CN-LIT-006": ["global"],
    "CN-LIT-007": ["global"],
    "CN-LIT-008": ["global"],
    "CN-LIT-009": ["global"],
    "CN-LIT-010": ["global"],
    "CN-LIT-011": ["global"],
    "CN-LIT-012": ["global"],
}
RESEARCH_SCOPE_BASIS = (
    "03治理成果：14号中文文献证据表与19号接收审查将中文文献限定为模块07/08的跨行业研究证据；"
    "仅作机制解释、风险提示和补问依据，不替代政策、标准、因子、评分或授信规则。"
)

REFERENCE_MARKERS = (
    "转型规划结论",
    "主要用能特征",
    "能耗数据关联要点",
    "建议改进方向",
    "匹配的转型路径名称",
    "近阶段转型行动建议",
    "中期转型行动建议",
    "长期转型行动建议",
    "规划书要点",
    "reference_comparison",
    "reference_conclusion",
)


def normalize_industry(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return INDUSTRY_MAP.get(text)


def industry_scope_for_source(source_id: str, role: str | None = None) -> list[str]:
    if source_id in RESEARCH_INDUSTRY_SCOPE and role in {None, "research_literature"}:
        return list(RESEARCH_INDUSTRY_SCOPE[source_id])
    exact = {
        "CETS-VG-001": ["钢铁"],
        "CETS-VG-002": ["冶金行业铝"],
        "CETS-VG-003": ["建材"],
        "POL-001": ["冶金行业铜"],
        "STD-003": ["冶金行业铜"],
        "STD-004": ["冶金行业铜"],
        "STD-005": ["冶金行业铝"],
        "STD-007": ["钢铁"],
        "STD-008": ["建材"],
        "STD-009": ["陶瓷"],
        "STD-010": ["水上运输"],
    }
    if source_id in exact:
        return exact[source_id]
    # Only sources explicitly approved by the governance layer may be global.
    # Unknown IDs intentionally return an empty scope; they must never inherit
    # global visibility merely because an industry mapping is missing.
    if source_id in {"STD-001", "STD-002", "MEE-GHG-QA-2025"}:
        return ["global"]
    return []


def visibility_rank(value: str) -> int:
    return {
        "searchable_candidate": 0,
        "diagnostic_only": 1,
        "metadata_only": 2,
        "blocked": 3,
    }.get(value, 3)


def most_restrictive(*values: str) -> str:
    return max(values, key=visibility_rank) if values else "blocked"


def has_reference_marker(value: Any) -> bool:
    if isinstance(value, dict):
        return any(has_reference_marker(key) or has_reference_marker(item) for key, item in value.items())
    if isinstance(value, list):
        return any(has_reference_marker(item) for item in value)
    if value is None:
        return False
    text = str(value)
    return any(marker.casefold() in text.casefold() for marker in REFERENCE_MARKERS)


def normalize_search_text(*values: Any) -> str:
    """Stable CJK 2/3-gram tokens plus alphanumeric/standard-number tokens."""
    raw = " ".join(str(value) for value in values if value not in (None, ""))
    raw = unicodedata.normalize("NFKC", raw).casefold()
    raw = re.sub(r"\s+", "", raw)
    tokens: set[str] = set()
    for token in re.findall(r"[a-z0-9][a-z0-9./_-]*|[\u4e00-\u9fff]+", raw):
        tokens.add(token)
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            for size in (2, 3):
                tokens.update(token[index : index + size] for index in range(max(0, len(token) - size + 1)))
    return " ".join(sorted(token for token in tokens if token))


def normalize_query_tokens(query: str) -> list[str]:
    normalized = normalize_search_text(query)
    return normalized.split() if normalized else []


def source_role_priority(role: str | None) -> int:
    return SOURCE_ROLE_ORDER.get(role or "other", SOURCE_ROLE_ORDER["other"])


def public_url(value: Any) -> str | None:
    if value in (None, ""):
        return None
    candidate = str(value).splitlines()[0].strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return candidate
