# 第五届中国研究生金融科技创新大赛：企业转型金融评估

## 项目简介

本项目参加第五届中国研究生金融科技创新大赛“揭榜挂帅”赛道第27题：

**碳迹可循，绿贷智评：基于多维度数据与行业标准的企业转型金融评估系统。**

项目拟面向金融机构和企业，构建以标准规则、行业模板、多模态材料解析、数据质量控制、能耗与碳排放核算、动态补充提问、评分与风险提示、证据链和报告生成为核心的转型金融评估系统。系统输出用于授信审查和企业转型管理辅助，不自动批准或拒绝授信。

## 当前状态

- 阶段：M1—M5已完成01审查和正式集成；M6活动数据标准化与碳核算基础层策划完成，等待新建独立02 M6任务获得精确口令后实施。
- 正式总体计划：[`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) v1.14，是本项目唯一正式总体计划。
- 总体方案：采用11行业统一覆盖，不再设置第一/第二深验。允许按知识和规则成熟度分批建设，但11行业最终采用相同的来源、版本、证据、检索测试和人工复核门槛。
- 配套数据：命题方配套模拟数据已经取得，文件保存在本地未跟踪目录；该数据脱敏、模拟生成，仅用于比赛开发测试，不是真实企业业务数据。
- 数据缺口：当前仍未取得独立数据字典、训练/测试划分和正式评分标签；不得据此宣称模型效果、评分结果或真实企业结论。
- 工作簿分工：`基本信息`、`能耗信息`、`补充信息`为主要输入；`转型目录`为规则与知识来源；`转型规划结论`为参考结论和验证对照，不得作为同一模型输入特征。
- 03初步审计：已归档企业表主键闭合、缺失/重复、单位观察、语义一致性、目录覆盖缺口和泄漏风险；详见 [`docs/DATA_PROFILE.md`](docs/DATA_PROFILE.md)。候选数据契约详见 [`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md)，其中宽转长、缺失等级、目录ID和质量阻断规则仍待若翎确认。
- 工程审查：M1—M5均已通过01审查。M5专项为`16 passed`，Gold为`33 passed / 11 correct_degrade / 0 failed`；Python全量分拆覆盖78项，前端为`5 test files / 8 tests passed`。新增受控PDF缺失时的安全降级测试。详见[`docs/M5_DEVELOPMENT_REVIEW.md`](docs/M5_DEVELOPMENT_REVIEW.md) v1.0。
- 已接入技术：React、TypeScript、Vite、Ant Design、ECharts、FastAPI、Pydantic、原生`sqlite3`、LangGraph、LangChain Core、SQLite/FTS5知识检索、运行级检查点与知识版本冻结、离线回退。模型只负责会话调度和解释，不接管企业事实、规则、因子、评分或证据准入。
- 02开发指导：[`docs/DEVELOPMENT_BRIEF.md`](docs/DEVELOPMENT_BRIEF.md) v1.0记录当前正式基线；[`docs/M5_DEVELOPMENT_PROMPT.md`](docs/M5_DEVELOPMENT_PROMPT.md)保留为M5历史执行依据；[`docs/M6_DEVELOPMENT_PROMPT.md`](docs/M6_DEVELOPMENT_PROMPT.md) v1.0是M6当前执行说明。M6仍须在新02任务收到精确开发口令后才能启动。
- 后续顺序：M6活动数据与碳核算 → M7行业对标与转型行为 → M8评分与信贷支持 → 报告扩展、Windows与正式分发。该顺序不删减11行业统一覆盖范围。
- 政策规则进度：03定点整改已通过；本轮又接收43份唯一政策标准PDF和12篇中文全文，独立复核14条铜行业标准条款。国家温室气体排放因子库已登记为权威来源索引和M6候选因子来源，但M5只使用来源和适用性元数据，新增因子允许自动调用仍为0条。详见[`docs/POLICY_RULES_REVIEW.md`](docs/POLICY_RULES_REVIEW.md)和[`团队成果/03_数据政策评分/19_补充政策文献与国家因子库接收审查.md`](团队成果/03_数据政策评分/19_补充政策文献与国家因子库接收审查.md)。
- 公开边界：原始配套数据、ZIP、解压目录、政策/标准/文献PDF原件、本地受控备份和本地输出由`.gitignore`排除，不上传公开GitHub。
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
8. [`docs/PROJECT_STRUCTURE.md`](docs/PROJECT_STRUCTURE.md)（目录和十模块导航）
9. `项目材料/历史规划/企业转型金融智能评估系统-项目统领提示词-计划模式.md`（历史规划输入，仅作追溯）

统一接入提示词见 [`docs/CODEX_ONBOARDING.md`](docs/CODEX_ONBOARDING.md)。

## 当前目录

### 已有材料

- `项目材料/赛题与赛事/重点赛题/27-多模态技术与数据治理赛道-江西普惠征信-碳迹可循，绿贷智评：基于多维度数据与行业标准的企业转型金融评估系统.docx`：目标赛题书重点入口。
- `27-多模态技术与数据治理赛道-碳迹可循，绿贷智评：基于多维度数据与行业标准的企业转型金融评估系统/配套数据.xlsx`：命题方配套脱敏模拟数据，已到达但不纳入公开仓库。
- `项目材料/赛题与赛事/赛事附件/附件1：第五届中国研究生金融科技创新大赛参赛指南.pdf`：赛事流程、提交要求和统一可运行性测试要求。
- `项目材料/赛题与赛事/赛事附件/附件3：第五届中国研究生金融科技创新大赛精益画布模板.pptx`：精益画布模板。
- `项目材料/赛题与赛事/全部赛题/`：全部揭榜赛题材料，用于横向理解赛道和技术要求。
- `项目材料/往届经验参考/`：往届作品经验分享图，仅作评审偏好和表达方式参考，不得照搬成果、指标或技术选型。
- `项目材料/历史规划/企业转型金融智能评估系统-项目统领提示词-计划模式.md`：本项目此前的一次性规划输入，仅作历史追溯，不再作为当前任务指令。
- `团队成果/`：成员原始交付存档；不会自动成为正式项目结论。

### 项目治理文档

- [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md)：跨成员、跨Codex任务的主上下文。
- [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md)：唯一正式总体计划、实施阶段和MVP范围。
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)：当前进度、阻塞和下一步。
- [`docs/DECISIONS.md`](docs/DECISIONS.md)：重大决策登记。
- [`docs/DATA_STATUS.md`](docs/DATA_STATUS.md)：正式数据状态、需求和审计流程。
- [`docs/DATA_PROFILE.md`](docs/DATA_PROFILE.md)：03配套数据初步画像、事实性审计结果和缺口。
- [`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md)：初步审计后的候选数据契约，待确认，不是程序实现规范。
- [`docs/DATA_AUDIT_REVIEW_AND_FLOW_READINESS.md`](docs/DATA_AUDIT_REVIEW_AND_FLOW_READINESS.md)：审计复核、问题完善顺序和流程软件准备清单。
- [`docs/DEVELOPMENT_BRIEF.md`](docs/DEVELOPMENT_BRIEF.md)：02软件开发的当前执行版、M1—M5历史验收、领域模型、接口、赛题映射和M6阶段门槛。
- [`docs/M4_DEVELOPMENT_REVIEW.md`](docs/M4_DEVELOPMENT_REVIEW.md)：M4工作流编排、隔离边界、整改、测试和正式采纳记录。
- [`docs/M5_DEVELOPMENT_REVIEW.md`](docs/M5_DEVELOPMENT_REVIEW.md)：M5准入、检索、运行隔离、Gold结果和正式采纳记录。
- [`docs/DEVELOPMENT_REVIEW.md`](docs/DEVELOPMENT_REVIEW.md)：M1—M5成果审查、十个产品模块、技术栈、实际接入状态和未实现边界。
- [`docs/POLICY_RULES_REVIEW.md`](docs/POLICY_RULES_REVIEW.md)：钟同学政策规则交付审查、冲突、采纳边界和M5知识源准备。
- [`docs/M5_DEVELOPMENT_PROMPT.md`](docs/M5_DEVELOPMENT_PROMPT.md)：M5记录级白名单、知识分层、本地检索、运行隔离、接口和验收要求。
- [`docs/M6_DEVELOPMENT_PROMPT.md`](docs/M6_DEVELOPMENT_PROMPT.md)：M6活动数据标准化、因子冻结、确定性碳核算、不可计算状态、接口与验收要求。
- [`团队成果/03_数据政策评分/19_补充政策文献与国家因子库接收审查.md`](团队成果/03_数据政策评分/19_补充政策文献与国家因子库接收审查.md)：补充政策标准、中文文献、铜行业条款和国家因子库的接收审查。
- [`docs/PROJECT_STRUCTURE.md`](docs/PROJECT_STRUCTURE.md)：物理目录、十模块导航和文件权威层级。
- [`docs/M3_DEVELOPMENT_PROMPT.md`](docs/M3_DEVELOPMENT_PROMPT.md)：02实施M3专业Agent工作台时使用的历史开发提示词。
- [`docs/TEAM_ROLES.md`](docs/TEAM_ROLES.md)：固定Codex对话、5人动态分工和成果审查机制。
- [`docs/TASK_BOARD.md`](docs/TASK_BOARD.md)：可选的简要待办清单，不是任务启动前置条件。
- [`docs/SYNC_WORKFLOW.md`](docs/SYNC_WORKFLOW.md)：单向GitHub、成员直接交付和项目总控接收流程。
- [`docs/SKILLS_MANIFEST.md`](docs/SKILLS_MANIFEST.md)：项目继承和全局Skills说明。
- [`docs/CODEX_ONBOARDING.md`](docs/CODEX_ONBOARDING.md)：供其他成员使用的统一Codex接入提示词。
- [`handoffs/README.md`](handoffs/README.md)：可选的成员成果存档入口。

### 目录约定

`code/`、`docs/`、`data/`和`handoffs/`保持英文兼容路径；赛题材料集中在`项目材料/`，成员交付集中在`团队成果/`。十模块逻辑导航和新增文件规则见[`docs/PROJECT_STRUCTURE.md`](docs/PROJECT_STRUCTURE.md)。本地配套数据目录因软件默认加载路径暂留根目录并继续忽略，不上传公开GitHub。

## 团队同步方式

本项目采用“若翎单点维护正式仓库、其他成员只读获取、任务成果直接交付”的方式。正式仓库为公开个人GitHub仓库：<https://github.com/RuoLing0802/transition-finance-assessment>。吴、钟、刘、夏无需加入Collaborator，只需使用公开地址 `clone`、`pull` 和读取；不得向远端推送、创建分支或发起拉取请求。

成员第一次使用时clone仓库；每次开始新工作前，在没有未保存本地改动的情况下执行 `git pull --ff-only origin main`，再读取最新版项目文档。完成后把建议、反馈、文档、代码片段、数据结果或ZIP直接发送给若翎。任务编号、任务卡、固定目录、`HANDOFF.md`、`SYNC_PROMPT.md`、固定ZIP结构和同步口令均不再是必要条件。

若翎长期使用少量职责分区：`01_项目总控与决策`负责总体计划、决策、状态、成果审查、正式合并和Git操作，不承担日常编码；`02_软件开发`负责工程实现、测试、封装和部署，并可按M5维护、M6开发等主要里程碑建立独立任务；`03_数据、政策与评分体系`负责数据审计、政策标准、行业规则、因子准入与评分校准。`00`已完成、可归档，`04`待后期再创建。完整规则见 [`docs/TEAM_ROLES.md`](docs/TEAM_ROLES.md)。

## 开发与集成边界

本对话`01_项目总控与决策`只形成开发方案、审查02成果并负责正式合并和Git操作；程序修改、测试、macOS/Windows封装与部署统一由`02_软件开发`执行。精确口令“开始开发MVP”继续作为启动新开发实施的长期授权边界。

M2基线和后续M3均可使用已登记的命题方配套模拟数据进行开发测试，但不得把它当作真实企业业务数据、正式评分标签或效果证明；如需构造额外测试样例，仍须说明生成规则并显式标注“模拟数据，不代表比赛正式数据”。原始数据、密钥和运行时文件不得上传公开仓库。

## Python环境约定

获得开发授权后，日常 Python 默认使用：

```text
/opt/anaconda3/bin/python
```

依赖安装使用同一解释器的 `-m pip`；不使用裸 `python3` 或 `pip3` 作为默认环境。本次任务不安装任何依赖。
