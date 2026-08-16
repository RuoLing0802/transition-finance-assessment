from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUNTIME_ROOT = Path(__file__).resolve().parents[1] / ".m1_runtime"
RUNTIME_ROOT = Path(os.environ.get("M1_RUNTIME_ROOT", DEFAULT_RUNTIME_ROOT)).resolve()


def _default_application_data_root() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / "Library" / "Application Support"
    return base / "TransitionFinanceAssessment"


APPLICATION_DATA_ROOT = Path(
    os.environ.get("TRANSITION_FINANCE_APP_DATA_ROOT", _default_application_data_root())
).resolve()

RULE_VERSION = "m1-local-v0.1"
CATALOG_RULE_VERSION = "m1-catalog-v0.1"
FIELD_CONTRACT_VERSION = "workbook-contract-v0.1"
SIMULATED_DATA_NOTICE = "命题方脱敏模拟数据，仅用于比赛开发测试，不代表真实企业业务数据"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

EXPECTED_SHEETS = ["基本信息", "能耗信息", "补充信息", "转型规划结论", "转型目录"]
INPUT_SHEETS = ["基本信息", "能耗信息", "补充信息"]
REFERENCE_SHEET = "转型规划结论"
CATALOG_SHEET = "转型目录"

REQUIRED_HEADERS: dict[str, list[str]] = {
    "基本信息": ["企业代号", "行业", "细分行业/领域", "所属地区", "企业规模", "成立年份"],
    "能耗信息": [
        "企业代号",
        "主要用能来源",
        "主用能项数量",
        "2024年电力消费量（万千瓦时）",
        "2025年电力消费量（万千瓦时）",
        "2024年煤炭消费量（吨）",
        "2025年煤炭消费量（吨）",
        "2024年天然气消费量（万立方米）",
        "2025年天然气消费量（万立方米）",
        "2024年热力消费量（吉焦）",
        "2025年热力消费量（吉焦）",
        "2024年柴油消费量（吨）",
        "2025年柴油消费量（吨）",
        "2024年汽油消费量（吨）",
        "2025年汽油消费量（吨）",
        "2024年水消费量（万吨）",
        "2025年水消费量（万吨）",
        "2024年主要产品产量",
        "2025年主要产品产量",
        "产量单位",
        "2024年营业收入（万元）",
        "2025年营业收入（万元）",
    ],
    "补充信息": [
        "企业代号",
        "主要产品/服务",
        "主要生产设备或设施",
        "核心设备平均投运年限",
        "是否已建设能耗/碳排在线管理系统",
        "是否已开展余热/余压回收",
        "是否已建设分布式光伏",
        "2025年绿电比例",
        "当前主要痛点",
        "企业自述转型诉求",
    ],
    "转型规划结论": [
        "企业代号",
        "主要用能特征",
        "能耗数据关联要点",
        "建议改进方向",
        "匹配的转型路径名称",
        "近阶段转型行动建议",
        "中期转型行动建议",
        "长期转型行动建议",
        "规划书要点",
    ],
    "转型目录": ["行业", "类别/领域", "转型路径", "说明"],
}

ENERGY_SPECS = [
    ("电力", "2024年电力消费量（万千瓦时）", "2025年电力消费量（万千瓦时）", "万千瓦时"),
    ("煤炭", "2024年煤炭消费量（吨）", "2025年煤炭消费量（吨）", "吨"),
    ("天然气", "2024年天然气消费量（万立方米）", "2025年天然气消费量（万立方米）", "万立方米"),
    ("热力", "2024年热力消费量（吉焦）", "2025年热力消费量（吉焦）", "吉焦"),
    ("柴油", "2024年柴油消费量（吨）", "2025年柴油消费量（吨）", "吨"),
    ("汽油", "2024年汽油消费量（吨）", "2025年汽油消费量（吨）", "吨"),
    ("水", "2024年水消费量（万吨）", "2025年水消费量（万吨）", "万吨"),
]

OPERATING_SPECS = [
    ("主要产品产量", "2024年主要产品产量", "2025年主要产品产量", None),
    ("营业收入", "2024年营业收入（万元）", "2025年营业收入（万元）", "万元"),
]
