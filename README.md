# 第五届中国研究生金融科技创新大赛：企业转型金融评估

## 项目简介

本项目参加第五届中国研究生金融科技创新大赛“揭榜挂帅”赛道第27题：

**碳迹可循，绿贷智评：基于多维度数据与行业标准的企业转型金融评估系统。**

项目拟面向金融机构和企业，构建以标准规则、行业模板、多模态材料解析、数据质量控制、能耗与碳排放核算、动态补充提问、评分与风险提示、证据链和报告生成为核心的转型金融评估系统。系统输出用于授信审查和企业转型管理辅助，不自动批准或拒绝授信。

## 当前状态

- 阶段：M1成果审查与下一阶段开发规划阶段；M1已由02在本地交付，尚未正式合并。
- 正式总体计划：[`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) v1.6，是本项目唯一正式总体计划。
- 总体方案：已确认保留“8行业框架＋2行业深验”；铜产业为第一深验行业，第二深验行业待配套模拟数据审计、正式标准和评审需要进一步确认。
- 配套数据：命题方配套模拟数据已经取得，文件保存在本地未跟踪目录；该数据脱敏、模拟生成，仅用于比赛开发测试，不是真实企业业务数据。
- 数据缺口：当前仍未取得独立数据字典、训练/测试划分和正式评分标签；不得据此宣称模型效果、评分结果或真实企业结论。
- 工作簿分工：`基本信息`、`能耗信息`、`补充信息`为主要输入；`转型目录`为规则与知识来源；`转型规划结论`为参考结论和验证对照，不得作为同一模型输入特征。
- 03初步审计：已归档企业表主键闭合、缺失/重复、单位观察、语义一致性、目录覆盖缺口和泄漏风险；详见 [`docs/DATA_PROFILE.md`](docs/DATA_PROFILE.md)。候选数据契约详见 [`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md)，其中宽转长、缺失等级、目录ID和质量阻断规则仍待若翎确认。
- M1审查：配套Excel主流程可运行，但失败批次后续查询、批次级警告聚合、参考结论对照、完整报告重复性和负向测试仍需整改；当前结论为“有条件通过、待整改”。
- 02开发指导：[`docs/DEVELOPMENT_BRIEF.md`](docs/DEVELOPMENT_BRIEF.md) v0.5已形成。M2采用一个工作空间管理多个企业、一次评估运行绑定一家企业，并支持独立报告和已完成运行对比；开发顺序为M1整改、领域模型与持久化、多企业Web交互、多模态解析、模型编排、报告/对比和桌面封装；外部模型调度当前评估会话和受控工具，同期支持XLSX/PDF/DOCX/图片，并交付Web、macOS DMG和Windows MSI；规则、核算、评分和证据链仍由独立可回放模块负责。
- 公开边界：原始配套数据、ZIP和解压目录由`.gitignore`排除，不上传公开GitHub。
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
- `27-多模态技术与数据治理赛道-碳迹可循，绿贷智评：基于多维度数据与行业标准的企业转型金融评估系统/配套数据.xlsx`：命题方配套脱敏模拟数据，已到达但不纳入公开仓库。
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
- [`docs/DATA_PROFILE.md`](docs/DATA_PROFILE.md)：03配套数据初步画像、事实性审计结果和缺口。
- [`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md)：初步审计后的候选数据契约，待确认，不是程序实现规范。
- [`docs/DATA_AUDIT_REVIEW_AND_FLOW_READINESS.md`](docs/DATA_AUDIT_REVIEW_AND_FLOW_READINESS.md)：审计复核、问题完善顺序和流程软件准备清单。
- [`docs/DEVELOPMENT_BRIEF.md`](docs/DEVELOPMENT_BRIEF.md)：02软件开发的当前执行版、M1整改门、领域模型、接口、赛题映射和M2端到端开发方案。
- [`docs/TEAM_ROLES.md`](docs/TEAM_ROLES.md)：固定Codex对话、5人动态分工和成果审查机制。
- [`docs/TASK_BOARD.md`](docs/TASK_BOARD.md)：可选的简要待办清单，不是任务启动前置条件。
- [`docs/SYNC_WORKFLOW.md`](docs/SYNC_WORKFLOW.md)：单向GitHub、成员直接交付和项目总控接收流程。
- [`docs/SKILLS_MANIFEST.md`](docs/SKILLS_MANIFEST.md)：项目继承和全局Skills说明。
- [`docs/CODEX_ONBOARDING.md`](docs/CODEX_ONBOARDING.md)：供其他成员使用的统一Codex接入提示词。
- [`handoffs/README.md`](handoffs/README.md)：可选的成员成果存档入口。

### 计划中的目录

`data/raw/`、`data/interim/`、`data/processed/`、`code/stata/`、`output/`、`references/`、`logs/`等目录属于后续项目规范或开发阶段预留。`code/python/`目前包含02本地交付、尚待整改和正式合并的M1成果；不得将其解读为完整MVP、正式评分、模型效果或跨平台交付已经完成。

## 团队同步方式

本项目采用“若翎单点维护正式仓库、其他成员只读获取、任务成果直接交付”的方式。正式仓库为公开个人GitHub仓库：<https://github.com/RuoLing0802/transition-finance-assessment>。吴、钟、刘、夏无需加入Collaborator，只需使用公开地址 `clone`、`pull` 和读取；不得向远端推送、创建分支或发起拉取请求。

成员第一次使用时clone仓库；每次开始新工作前，在没有未保存本地改动的情况下执行 `git pull --ff-only origin main`，再读取最新版项目文档。完成后把建议、反馈、文档、代码片段、数据结果或ZIP直接发送给若翎。任务编号、任务卡、固定目录、`HANDOFF.md`、`SYNC_PROMPT.md`、固定ZIP结构和同步口令均不再是必要条件。

若翎长期使用少量固定对话：`01_项目总控与决策`负责总体计划、决策、状态、成果审查、正式合并和Git操作，不承担日常编码；`02_软件开发`负责工程实现、测试、桌面封装和部署；`03_数据、政策与评分体系`负责数据审计、政策标准、行业规则与评分校准。`00_项目上下文整理与Codex交接包`已完成、可归档，`04_报告、PPT与答辩`待后期再创建。完整规则见 [`docs/TEAM_ROLES.md`](docs/TEAM_ROLES.md)。

## 开发与集成边界

本对话`01_项目总控与决策`只形成开发方案、审查02成果并负责正式合并和Git操作；程序修改、测试、macOS/Windows封装与部署统一由`02_软件开发`执行。精确口令“开始开发MVP”继续作为启动新开发实施的长期授权边界。

M1本地成果和后续M2均可使用已登记的命题方配套模拟数据进行开发测试，但不得把它当作真实企业业务数据、正式评分标签或效果证明；如需构造额外测试样例，仍须说明生成规则并显式标注“模拟数据，不代表比赛正式数据”。原始数据、密钥和运行时文件不得上传公开仓库。

## Python环境约定

获得开发授权后，日常 Python 默认使用：

```text
/opt/anaconda3/bin/python
```

依赖安装使用同一解释器的 `-m pip`；不使用裸 `python3` 或 `pip3` 作为默认环境。本次任务不安装任何依赖。
