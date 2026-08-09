# 第五届中国研究生金融科技创新大赛：企业转型金融评估

## 项目简介

本项目参加第五届中国研究生金融科技创新大赛“揭榜挂帅”赛道第27题：

**碳迹可循，绿贷智评：基于多维度数据与行业标准的企业转型金融评估系统。**

项目拟面向金融机构和企业，构建以标准规则、行业模板、多模态材料解析、数据质量控制、能耗与碳排放核算、动态补充提问、评分与风险提示、证据链和报告生成为核心的转型金融评估系统。系统输出用于授信审查和企业转型管理辅助，不自动批准或拒绝授信。

## 当前状态

- 阶段：材料审阅与总体规划阶段，项目开发入口尚未开启。
- 正式总体计划：[`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) v1.0，是本项目唯一正式总体计划。
- 总体方案：已确认保留“8行业框架＋2行业深验”；铜产业为第一深验行业，第二深验行业待正式数据和标准到达后确定。
- 正式数据：当前尚未取得正式参赛数据、数据字典、标签定义和训练/测试划分。
- 重要边界：赛题材料中的数据规模和字段是赛题描述，不代表本仓库已有正式数据；当前未使用模拟数据产出模型效果或真实企业结果。
- 开发授权：只有收到完全一致的口令“开始开发MVP”后，才进入程序开发阶段。

## 先读什么

其他团队成员或Codex接入本项目时，按以下顺序阅读：

1. `AGENTS.md`
2. `docs/PROJECT_CONTEXT.md`
3. `docs/PROJECT_STATUS.md`
4. `docs/PROJECT_PLAN.md`
5. `docs/DECISIONS.md`、`docs/DATA_STATUS.md`、`docs/TEAM_ROLES.md`
6. `docs/SYNC_WORKFLOW.md`、`docs/CODEX_ONBOARDING.md`
7. `docs/TASK_BOARD.md`、`handoffs/README.md`（工具可选，但接入时阅读说明）
8. `企业转型金融智能评估系统-项目统领提示词-计划模式.md`（历史规划输入，仅作追溯）

统一接入提示词见 [`docs/CODEX_ONBOARDING.md`](docs/CODEX_ONBOARDING.md)。

## 当前目录

### 已有材料

- `27-多模态技术与数据治理赛道-江西普惠征信-碳迹可循，绿贷智评：基于多维度数据与行业标准的企业转型金融评估系统.docx`：目标赛题书。
- `附件1：第五届中国研究生金融科技创新大赛参赛指南.pdf`：赛事流程、提交要求和统一可运行性测试要求。
- `附件3：第五届中国研究生金融科技创新大赛精益画布模板.pptx`：精益画布模板。
- `赛题文件/`：其他揭榜赛题材料，用于横向理解赛道和技术要求。
- `图片信息/`：往届作品经验分享图，仅作评审偏好和表达方式参考，不得照搬成果、指标或技术选型。
- `企业转型金融智能评估系统-项目统领提示词-计划模式.md`：本项目此前的一次性规划输入，仅作历史追溯，不再作为当前任务指令。

### 项目治理文档

- [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md)：跨成员、跨Codex任务的主上下文。
- [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md)：唯一正式总体计划、实施阶段和MVP范围。
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)：当前进度、阻塞和下一步。
- [`docs/DECISIONS.md`](docs/DECISIONS.md)：重大决策登记。
- [`docs/DATA_STATUS.md`](docs/DATA_STATUS.md)：正式数据状态、需求和审计流程。
- [`docs/TEAM_ROLES.md`](docs/TEAM_ROLES.md)：固定Codex对话、5人动态分工和成果审查机制。
- [`docs/TASK_BOARD.md`](docs/TASK_BOARD.md)：可选的简要待办清单，不是任务启动前置条件。
- [`docs/SYNC_WORKFLOW.md`](docs/SYNC_WORKFLOW.md)：单向GitHub、成员直接交付和项目总控接收流程。
- [`docs/SKILLS_MANIFEST.md`](docs/SKILLS_MANIFEST.md)：项目继承和全局Skills说明。
- [`docs/CODEX_ONBOARDING.md`](docs/CODEX_ONBOARDING.md)：供其他成员使用的统一Codex接入提示词。
- [`handoffs/README.md`](handoffs/README.md)：可选的成员成果存档入口。

### 计划中的目录

`data/raw/`、`data/interim/`、`data/processed/`、`code/python/`、`code/stata/`、`output/`、`references/`、`logs/`等目录属于后续项目规范或开发阶段预留，目前不应被解读为已经存在正式数据、代码或可运行成果。

## 团队同步方式

本项目采用“若翎单点维护正式仓库、其他成员只读获取、任务成果直接交付”的方式。正式仓库为公开个人GitHub仓库：<https://github.com/RuoLing0802/transition-finance-assessment>。吴、钟、刘、夏无需加入Collaborator，只需使用公开地址 `clone`、`pull` 和读取；不得向远端推送、创建分支或发起拉取请求。

成员第一次使用时clone仓库；每次开始新工作前，在没有未保存本地改动的情况下执行 `git pull --ff-only origin main`，再读取最新版项目文档。完成后把建议、反馈、文档、代码片段、数据结果或ZIP直接发送给若翎。任务编号、任务卡、固定目录、`HANDOFF.md`、`SYNC_PROMPT.md`、固定ZIP结构和同步口令均不再是必要条件。

若翎长期使用少量固定对话：`01_项目总控与决策`负责总体计划、决策、状态、成果审查和正式Git操作；`02_软件开发`负责获得授权后的工程工作；`03_数据、政策与评分体系`负责数据审计、政策标准、行业规则与评分校准。`00_项目上下文整理与Codex交接包`已完成、可归档，`04_报告、PPT与答辩`待后期再创建。完整规则见 [`docs/TEAM_ROLES.md`](docs/TEAM_ROLES.md)。

## 开发入口尚未开启

当前只允许材料分析、总体规划、规则需求、数据需求、测试设计、报告大纲和只读评审，不编写程序、不安装依赖、不修改开发环境、不使用模拟数据产出项目结论。收到精确口令“开始开发MVP”后，可以在正式数据尚未取得的情况下按完整MVP实施；如需构造最小测试样例，仍须先说明生成规则并取得若翎确认，且显式标注“模拟数据，不代表比赛正式数据”。正式数据、隐私或保密不是工程开发的前置条件。

## Python环境约定

获得开发授权后，日常 Python 默认使用：

```text
/opt/anaconda3/bin/python
```

依赖安装使用同一解释器的 `-m pip`；不使用裸 `python3` 或 `pip3` 作为默认环境。本次任务不安装任何依赖。
