from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .config import SIMULATED_DATA_NOTICE


def _value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def build_basic_report(analysis: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    generated_at = datetime.now(timezone.utc).isoformat()
    code = analysis["company_code"]
    issues = analysis.get("quality_issues", [])
    trend = analysis.get("energy_trend", {})
    catalog = analysis.get("catalog_matches", {})
    reference = analysis.get("reference_comparison", {})
    lines = [
        f"# 企业转型金融评估 M1 基础流程报告：{code}",
        "",
        f"> 数据声明：{SIMULATED_DATA_NOTICE}。",
        "> 本报告是流程联调和人工审阅材料，不代表真实企业结论、正式碳核算、评分结果或授信决定。",
        "",
        "## 1. 输入与边界",
        "",
        f"- 企业代号：`{code}`",
        f"- 批次：`{analysis['batch_id']}`",
        f"- 规则版本：`{analysis['rule_version']}`",
        "- 输入表：`基本信息`、`能耗信息`、`补充信息`",
        "- 规则/知识层：`转型目录`",
        "- 参考输出层：`转型规划结论`，独立加载，不进入输入特征或标签链路",
        "",
        "## 2. 数据质量与待补材料",
        "",
        f"- 质量问题数量：{len(issues)}",
        f"- 错误：{sum(item.get('severity') == 'error' for item in issues)}；警告：{sum(item.get('severity') == 'warning' for item in issues)}；提示：{sum(item.get('severity') == 'info' for item in issues)}",
        "",
    ]
    if issues:
        lines.extend(["| 严重度 | 表 | 字段 | 问题 | 原值 | 状态 |", "|---|---|---|---|---|---|"])
        for issue in issues[:100]:
            lines.append(
                "| {severity} | {sheet} | {field} | {message} | {value} | {status} |".format(
                    severity=_value(issue.get("severity")),
                    sheet=_value(issue.get("sheet_name")),
                    field=_value(issue.get("field")),
                    message=_value(issue.get("message")).replace("|", "\\|"),
                    value=_value(issue.get("original_value")).replace("|", "\\|"),
                    status=_value(issue.get("status")),
                )
            )
    else:
        lines.append("当前批次未发现结构或字段质量问题；仍需结合正式数据字典和人工复核确认口径。")
    lines.extend(["", "## 3. 2024—2025 年度变化", ""])
    lines.append("| 指标 | 单位 | 2024 | 2025 | 变化 | 变化率 | 状态 |")
    lines.append("|---|---|---:|---:|---:|---:|---|")
    for item in [*trend.get("resources", []), *trend.get("operating_metrics", [])]:
        rate = item.get("change_rate")
        rate_display = "—" if rate is None else f"{rate:.2%}"
        lines.append(
            f"| {_value(item.get('name'))} | {_value(item.get('unit'))} | {_value(item.get('2024'))} | {_value(item.get('2025'))} | {_value(item.get('change'))} | {rate_display} | {_value(item.get('status'))} |"
        )
    lines.extend(["", f"> {trend.get('calculation_note', '')}", "", "## 4. 转型目录候选", ""])
    lines.append(f"- 匹配状态：{_value(catalog.get('status'))}")
    lines.append(f"- 候选数量：{_value(len(catalog.get('candidates', [])))}")
    lines.append(f"- 人工复核：{'需要' if catalog.get('manual_review_required') else '暂未触发'}")
    lines.append("")
    if catalog.get("candidates"):
        lines.extend(["| 临时行级ID | 类别/领域 | 转型路径 | 暂定排序值（非评分） | 匹配依据 |", "|---|---|---|---:|---|"])
        for candidate in catalog["candidates"][:10]:
            lines.append(
                f"| `{_value(candidate.get('catalog_row_id'))}` | {_value(candidate.get('category'))} | {_value(candidate.get('transition_path'))} | {_value(candidate.get('provisional_sort_key'))} | {'；'.join(candidate.get('match_reasons', []))} |"
            )
        lines.append("\n> 目录排序值仅用于本轮候选展示，不是评分、排名或授信依据。")
    else:
        lines.append("未生成行业目录候选，需补充目录覆盖或人工确认，不自行编造路径。")
    lines.extend(["", "## 5. 参考结论对照", ""])
    lines.append(f"- 参考结论状态：{_value(reference.get('status'))}")
    lines.append(f"- 参考字段已加载数量：{_value(reference.get('reference_fields_present'))}")
    lines.append(f"- 泄漏隔离检查：{_value(reference.get('leakage_guard', {}).get('status'))}")
    lines.append(f"- 对照说明：{_value(reference.get('comparison_notice'))}")
    lines.append("")
    lines.append("| 参考字段 | 是否有参考值 | 对照状态 |")
    lines.append("|---|---|---|")
    for item in reference.get("field_presence_comparison", []):
        lines.append(
            f"| {_value(item.get('field'))} | {'是' if item.get('reference_value_present') else '否'} | {_value(item.get('comparison_status'))} |"
        )
    lines.extend(["", "### 5.1 明确语义映射", "", "| 映射 | 流程来源 | 状态 | 说明 |", "|---|---|---|---|"])
    for item in reference.get("comparison_items", []):
        reason = _value(item.get("reason")).replace("|", "\\|")
        lines.append(
            f"| {_value(item.get('mapping'))} | {_value(item.get('flow_source'))} | {_value(item.get('status'))} | {reason} |"
        )
    lines.extend(
        [
            "",
            "## 6. 当前未输出内容",
            "",
            "本 M1 报告不输出最终评分、权重、阈值、行业基准、正式碳排放量、授信通过/拒绝结论或模型效果指标。",
            "",
            f"报告生成时间：`{generated_at}`",
        ]
    )
    payload = {
        "report_type": "basic_m1",
        "generated_at": generated_at,
        "report_period": "2024—2025",
        "company_code": code,
        "batch_id": analysis["batch_id"],
        "simulated_data": True,
        "data_notice": SIMULATED_DATA_NOTICE,
        "analysis": analysis,
        "markdown": "\n".join(lines),
    }
    return "\n".join(lines), payload
