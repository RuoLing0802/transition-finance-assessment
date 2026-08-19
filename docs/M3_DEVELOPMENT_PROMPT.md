# M3 专业 Agent 工作台开发提示词

**版本**：v1.0
**日期**：2026-08-19
**适用对话**：`02_软件开发`
**制定与审查**：`01_项目总控与决策`
**当前状态**：M2核心基线已完成01审查与正式集成；等待若翎在02发送精确开发口令后执行
**文件性质**：M3正式开发提示词；与 [`DEVELOPMENT_BRIEF.md`](DEVELOPMENT_BRIEF.md) v0.6共同使用，但不单独构成开发授权

> 使用方式：若翎应先在 `02_软件开发` 中单独发送项目约定的精确开发口令，再发送本文件内容或要求 02 读取本文件。仅发送本文件不视为开发授权。

## 一、你的角色和任务边界

你是本项目的 `02_软件开发`。本轮实施 **M3：专业 Agent 工作台前端重构**。

本轮的目标不是增加碳核算、评分、知识库、报告或 Windows 功能，而是把当前信息密集型验收页面重构为一个面向企业转型金融评估的 Codex-like 专业智能体工作台，使用户能够清楚看到：

- 当前正在评估哪家企业；
- 当前评估运行处于哪个阶段；
- 已完成、存在问题、缺少依据和尚未建设的环节；
- Agent 当前做了什么、发现了什么、建议下一步做什么；
- 企业画像、数据质量、能耗、目录候选和证据分别在哪里查看。

本轮必须保留现有数据隔离、参考结论隔离、离线回退、工具白名单和模拟数据声明，不能为了 UI 效果改变业务事实或虚构功能状态。

## 二、M3 是否允许开始：G0 基线门

开始编写 M3 程序前，必须依次检查：

1. 读取 `AGENTS.md`、`README.md`、`docs/PROJECT_CONTEXT.md`、`docs/PROJECT_STATUS.md`、`docs/PROJECT_PLAN.md`、`docs/DECISIONS.md`、`docs/DATA_STATUS.md`、`docs/DEVELOPMENT_BRIEF.md`、`docs/DEVELOPMENT_REVIEW.md` 和本文件；
2. 执行 `git status --short --branch`、`git remote -v` 和 `git diff --check`；
3. 确认当前`main`包含01于2026-08-19审查形成的可追溯M2核心基线；
4. 如果当前仍存在来源不明、未审定或可能与 M3 冲突的本地改动，停止并报告，不得重置、覆盖、清理或偷偷带入 M3；
5. 02 不提交、不推送、不创建远端分支；阶段成果交给若翎和 01 审查；
6. Windows 打包脚本和报告扩展不属于本轮，不得因为工作树中已有相关文件而继续开发；
7. 原始 Excel、ZIP、运行数据库、缓存、API Key 和用户应用数据不得加入公开仓库；不得使用 `git add -A`。
8. 当前自定义模型API Key由后端保存在本机SQLite，属于待正式分发整改的本地MVP方案；M3不得把密钥保存到浏览器状态持久化、`localStorage`、日志或错误提示，也不得在读取接口中回显密钥。

如果本地版本尚未同步到该M2基线，只允许先执行`git pull --ff-only origin main`并重新检查；存在本地修改或分叉时停止并报告，不得强行同步。

## 三、M3 目标产品

将当前页面重构为：

> **命题方配套数据驱动的企业转型金融专业 Agent 工作台**

核心交互结构：

```text
┌───────────────┬────────────────────────────────┬──────────────────┐
│ 左侧任务栏      │ 中央 Agent 工作区                 │ 右侧评估检查器      │
│               │                                │                  │
│ 工作空间        │ 当前企业 / 当前阶段 / 模型          │ 评估进度            │
│ 新建企业评估     │                                │ 企业画像            │
│ 企业运行列表     │ Agent 对话                      │ 数据质量            │
│ 最近运行        │ 工具/状态卡片（默认折叠）           │ 能源表现            │
│               │ 分析结论和下一步建议               │ 碳核算准备度         │
│               │                                │ 行业对标            │
│ 设置            │ 附件 + 输入框 + 模型选择 + 发送      │ 转型路径 / 评分 / 证据 │
└───────────────┴────────────────────────────────┴──────────────────┘
```

一个工作空间可以管理多个企业；一次评估运行仍只绑定一家企业。用户评估另一家企业时创建或切换运行，不能把多家企业事实混入同一运行上下文。

## 四、本轮技术架构

### 4.1 必须采用

- 前端：React、TypeScript、Vite；
- 组件基础：Ant Design；
- 图表：ECharts，仅用于已有真实数据支持的趋势展示；
- 后端：继续复用现有 Python、FastAPI、Pydantic 和 SQLite；
- API：继续使用现有 REST 资源和运行级接口；
- 样式：Ant Design `ConfigProvider` 主题令牌 + 项目 CSS 变量；
- 测试：前端单元/组件测试、TypeScript 类型检查、构建检查和 Playwright 浏览器验收；
- Python 命令继续使用 `/opt/anaconda3/bin/python`，不得改用其他解释器。

### 4.2 本轮不接入

- LangGraph；
- LangChain；
- LlamaIndex；
- Qdrant；
- RAGFlow；
- SQLAlchemy/Alembic/PostgreSQL迁移；
- 正式 Carbon Engine、Benchmark Engine、Transition Engine、Score Engine；
- Windows EXE/MSI；
- 报告模板、PDF/DOCX报告扩展；
- 新的模型供应商或模型效果优化。

### 4.3 为后续阶段预留的接口

M3 只预留前端和 API 边界，不引入上述依赖：

- `AgentWorkflowAdapter`：供 M4 接入 LangGraph；
- `KnowledgeRetriever`：供 M5 评估 LlamaIndex + Qdrant；
- `CarbonAssessmentResult`；
- `BenchmarkResult`；
- `TransitionAssessmentResult`；
- `ScoreResult`；
- `CreditSupportResult`。

预留接口必须返回明确状态，禁止用虚构结果填充：

```text
ready
running
warning
blocked
not_calculable
pending_methodology
not_implemented
```

## 五、现有架构的保留与迁移原则

以下成果必须保留，不得推倒重写：

1. FastAPI API 和当前领域对象；
2. `workspace → assessment_run → enterprise` 隔离；
3. 默认配套数据自动加载；
4. `基本信息`、`能耗信息`、`补充信息`输入边界；
5. `转型目录`规则/知识层定位；
6. `转型规划结论`参考层和模型上下文隔离；
7. OpenAI-compatible 模型适配器；
8. 工具白名单和企业/运行边界校验；
9. 模型不可用时的离线回退；
10. 多模态证据、置信度、冲突和人工复核状态；
11. SQLite 本地持久化和用户应用数据目录。

当前 `code/python/app/static/index.html` 是 800 行以上的 HTML/CSS/JavaScript 单文件实现。迁移时：

- 新建独立前端源码目录，不继续向原单文件堆叠组件；
- 在 React 版本完成业务回归前保留旧页面作为可回退基线；
- 不得先删除旧页面再验证新页面；
- 新前端稳定后再由 01 决定旧页面的归档或移除方式；
- 不复制第二套后端业务逻辑，前端只消费 API。

## 六、推荐目录结构

可在不破坏现有 Python 目录的前提下采用：

```text
code/
  frontend/
    package.json
    vite.config.ts
    tsconfig.json
    src/
      app/
        App.tsx
        routes.tsx
        theme.ts
      api/
        client.ts
        contracts.ts
        workspaces.ts
        runs.ts
        messages.ts
        attachments.ts
        models.ts
      components/
        shell/
          AppShell.tsx
          TaskSidebar.tsx
          InspectorSidebar.tsx
          SidebarEdgeToggle.tsx
        conversation/
          ConversationHeader.tsx
          MessageList.tsx
          MessageItem.tsx
          ToolActivityCard.tsx
          Composer.tsx
          AttachmentTray.tsx
        inspector/
          AssessmentPipeline.tsx
          CompanyProfilePanel.tsx
          DataQualityPanel.tsx
          EnergyPanel.tsx
          CarbonReadinessPanel.tsx
          BenchmarkPanel.tsx
          TransitionPanel.tsx
          ScorePanel.tsx
          EvidencePanel.tsx
          SourcePanel.tsx
        common/
          EmptyState.tsx
          ErrorState.tsx
          LoadingState.tsx
          StatusBadge.tsx
      features/
        workspaces/
        assessment-runs/
        conversation/
        inspector/
        attachments/
      hooks/
      styles/
      tests/
    README.md
  python/
    app/
    tests/
```

具体文件可以合并或细分，但必须保持任务栏、对话区、检查器、API契约和业务状态分离，不能再回到单文件大页面。

## 七、UI 信息架构

### 7.1 左侧任务栏

默认宽度约 248—272px；收起后仅保留图标栏。收起/展开按钮必须位于侧栏边缘，不放在中央页面顶部。

只保留：

- 项目/工作空间名称；
- 新建企业评估；
- 当前工作空间；
- 企业评估运行列表；
- 每个运行的企业代号、简短名称和状态；
- 最近运行；
- 设置/管理员入口；
- 收起按钮。

默认不展示：

- 文件哈希；
- 批次 ID；
- 大段模拟数据说明；
- 目录统计；
- 报告库大卡片；
- Windows/打包信息。

### 7.2 中央 Agent 工作区

中央区域是视觉焦点，保持简洁：

- 顶部只显示当前企业、运行名称、评估阶段和紧凑模型选择；
- 首次进入运行时，Agent 主动给出“已加载什么、发现什么、下一步做什么”；
- 消息区只展示用户消息、Agent回答、必要的结果卡片；
- 工具执行过程默认折叠，只显示安全的步骤摘要；
- 原始审计载荷、服务商内部信息、提示词和模型私有思维链不得展示；
- 底部固定输入区包含附件、文本输入、模型选择/当前模型和发送按钮；
- 附件上传不使用占据大面积的常驻拖放框，可通过回形针按钮或小型拖放反馈完成；
- 报告、企业对比和管理员诊断不得占据中央默认视图。

### 7.3 右侧评估检查器

默认宽度约 320—380px；可折叠，按钮位于右栏边缘。

按折叠区或标签页提供：

1. 评估进度；
2. 企业画像；
3. 数据质量；
4. 能源表现；
5. 碳排放测算准备度；
6. 行业对标；
7. 转型路径；
8. 转型评分；
9. 证据材料；
10. 数据来源与参考对照。

`转型规划结论`只能放在右侧“参考对照”区域，不得默认出现在中央对话，也不得进入模型上下文。

## 八、绿色金融视觉系统

视觉方向是 Codex-like，而不是传统绿色后台管理系统：

- 约 90% 使用中性色；
- 约 10% 使用品牌绿色；
- 不使用大面积深绿色铺满左栏、标题区和卡片；
- 背景采用暖白/浅灰，卡片边界轻，阴影克制；
- 绿色用于激活导航、主按钮、Agent状态和关键趋势；
- 琥珀色用于待确认/缺失；
- 红色只用于真实错误或高风险；
- `not_implemented`使用中性灰，不伪装成警告或成功；
- 信息密度通过留白、分层和折叠控制，不用大量彩色胶囊标签填满页面。

建议基础令牌：

```text
background       #FAFAF8
surface          #FFFFFF
surface-muted    #F5F5F1
text-primary     #202320
text-secondary   #66706A
border           #E5E8E3
brand-primary    #1F6A5A
brand-hover      #185447
success          #2F7D58
warning          #B7791F
danger           #B84A4A
```

最终颜色可微调，但需保持可访问性和明暗对比。

## 九、评估 Pipeline 可视化

右侧必须显示以下阶段，不要求 M3 实现其业务引擎：

```text
企业数据
数据质量
证据审查
碳排放测算
行业对标
转型路径识别
转型评分
信贷支持建议
```

状态必须来自当前真实能力或明确的能力配置：

- 企业数据：企业三张输入表已关联时可标记完成；
- 数据质量：根据真实质量问题标记完成/警告/阻断；
- 证据审查：根据附件解析和人工复核状态标记；
- 碳排放测算：当前显示 `not_calculable`，列出缺少的组织/核算边界、Scope、因子和版本；
- 行业对标：当前显示 `not_implemented` 或 `pending_methodology`；
- 转型路径：仅可展示现有目录候选，不能宣称正式行为识别完成；
- 转型评分：当前显示 `pending_methodology`；
- 信贷支持建议：当前显示 `not_implemented`，不得输出授信通过/拒绝。

如现有后端没有统一状态接口，可增加最小只读的运行能力/阶段状态接口，但不得借此实现碳核算或评分逻辑。接口响应要区分：

```json
{
  "stage": "carbon",
  "status": "not_calculable",
  "reason": "缺少正式核算边界和排放因子版本",
  "missing_requirements": [
    "organization_boundary",
    "scope_boundary",
    "emission_factor_version"
  ],
  "evidence_refs": []
}
```

不得以 0、空分数、假百分比、假进度或模拟计算结果代替未实现状态。

## 十、配套数据主流程

M3 应把命题方配套工作簿视为当前唯一默认业务场景：

```text
打开应用
→ 默认配套数据准备完成
→ 创建/选择工作空间
→ 选择企业
→ 创建评估运行
→ 自动载入企业事实
→ 展示企业画像、质量和能耗
→ Agent说明当前状态和下一步
```

普通用户不需要先上传工作簿。管理员/测试替换批次入口应放入设置或诊断区域。

PDF、DOCX、图片和其他文件是当前企业的补充证据。上传后必须继续执行企业代号冲突检查、来源记录、置信度和人工复核，不得把附件内容直接写入另一家企业。

## 十一、会话与 Agent 体验

M3 不替换现有 `OrchestrationService`，只优化呈现和交互：

- 用户进入运行时显示主动状态摘要；
- 给出 2—4 个与当前阶段有关的建议动作；
- 回答围绕当前企业和运行；
- 工具卡显示“正在读取企业详情”“正在检查质量”等可解释摘要；
- 外部模型不可用时明确显示“离线基础流程”，不阻断企业事实查看；
- 停止、重试和错误恢复保持可用；
- 当前模型选择器选择会话模型，不得暗示它决定评分或规则；
- 模型调用中的工具和上下文继续受后端白名单限制。

如果现有接口尚不支持 token 级流式响应，M3 可通过当前流程事件轮询或最小事件流接口实现渐进状态显示；不得为了“打字机效果”重写模型编排。真正的 LangGraph 检查点、暂停/恢复和人工中断放在 M4。

## 十二、状态与异常场景

必须设计并验收：

- 无工作空间；
- 有工作空间但无评估运行；
- 默认配套数据加载中/失败；
- 企业列表加载中/失败；
- 当前企业正常；
- 数据质量存在警告；
- 企业关联阻断；
- 外部模型不可用并回退离线；
- 附件解析中、解析失败、低置信度、企业冲突；
- 会话处理中、停止、重试和失败；
- 页面刷新后恢复当前工作空间和运行；
- 左右栏收起和恢复；
- 窄窗口下左右栏变为抽屉或覆盖层。

错误信息应说明“发生了什么、用户可以做什么”，不得只显示异常堆栈。

## 十三、M3 实施顺序

### M3-A 基线与契约冻结

- 完成 G0 检查；
- 盘点现有 API、业务对象和状态；
- 建立 TypeScript API 契约；
- 明确旧页面回退方式；
- 输出迁移清单，不修改业务规则。

### M3-B React 工程与设计系统

- 建立 React + TypeScript + Vite 工程；
- 接入 Ant Design 和 ECharts；
- 建立主题令牌、字体、间距、颜色、边框和响应式断点；
- 建立三栏 App Shell 与侧栏边缘按钮。

### M3-C 工作空间与企业运行

- 接入默认配套数据；
- 实现工作空间、企业选择、新建运行、运行列表、切换和恢复；
- 保证同一工作空间多企业、单运行一企业；
- 保证切换运行不串企。

### M3-D 中央 Agent 工作区

- 消息列表；
- Agent主动摘要；
- 输入框、附件、模型选择；
- 工具/过程卡片；
- 停止、重试和离线回退状态；
- 渐进处理状态。

### M3-E 右侧评估检查器

- 评估 Pipeline；
- 企业画像、质量、能源、目录和证据；
- Carbon/Benchmark/Score/Credit 等未实现状态；
- 数据来源和参考结论对照。

### M3-F 测试与回归

- 类型、构建、单元、组件和浏览器测试；
- 真实配套工作簿回归；
- API 兼容、运行隔离、参考结论隔离和离线回退；
- 视觉截图和窄窗口验收；
- 旧页面回退验证。

每完成一个阶段先自检；发现前一阶段失败应停线修复，不得用隐藏功能、删除测试或伪造状态继续。

## 十四、M3 验收标准

### 14.1 产品与视觉

- 桌面宽屏下清楚呈现左任务、中对话、右检查器；
- 左右侧栏都可通过边缘按钮收起/展开；
- 中央对话是视觉焦点，默认没有批次哈希、详细审计、参考表格和报告面板；
- 配色为中性为主、绿色强调，不能是大面积深绿色后台；
- 1440×900、1280×800、1024×768 三个视口可正常使用；
- 键盘焦点、按钮标签、对比度和滚动区域可用。

### 14.2 业务闭环

- 应用启动后默认配套数据可用；
- 用户能创建工作空间并选择 `TF0001` 建立运行；
- 能展示企业画像、质量问题和2024—2025能耗变化；
- 能新建 `TF0002` 运行并在左栏切换；
- 切换后中央消息、右栏事实、附件和模型上下文不串企；
- `转型规划结论`只在参考对照区显示，且不进入模型上下文；
- 外部模型不可用时仍可完成基础查看和离线回答；
- 页面刷新后恢复最近工作空间和运行；
- 附件上传、模型选择、停止和重试继续可用。

### 14.3 未实现能力表达

- Carbon 显示“暂不可计算”及缺少依据；
- Benchmark 显示“方法/基准待建设”；
- Transition 只展示目录候选，不冒充正式路径识别；
- Score 显示“评分方法待确认”；
- Credit Support 显示“尚未实现”，不生成授信通过/拒绝；
- 页面不得出现虚构分数、碳排放量、行业排名、模型准确率或企业业务效果。

### 14.4 工程质量

- TypeScript 类型检查通过；
- 前端生产构建通过；
- 前端单元/组件测试通过；
- Playwright 关键流程通过；
- 现有 Python 单元/接口测试不回退；
- `git diff --check`通过；
- 没有 API Key、原始配套数据、数据库或运行缓存进入待提交清单；
- 不修改 M3 范围外的 Windows 和报告代码。

## 十五、M3 明确不做

- 不实现正式碳排放计算；
- 不接入排放因子库；
- 不确定 Scope 1/2；
- 不确定行业基准、权重、阈值或第二深验行业；
- 不实现正式转型评分；
- 不实现授信通过/拒绝；
- 不接入 LangGraph、LangChain、LlamaIndex、Qdrant 或 RAGFlow；
- 不制作或扩展报告；
- 不构建 Windows EXE/MSI；
- 不重新设计 macOS 打包；
- 不迁移 SQLite 到 PostgreSQL；
- 不删除或缩减“8行业框架＋2行业深验”；
- 不把`转型规划结论`回灌为模型输入；
- 不把命题方模拟数据写成真实企业数据。

## 十六、M3 完成后的后续路线

- **M4**：LangGraph 状态机 + LangChain 组件层；把企业加载、画像、质量、证据审查、补问和人工确认做成可暂停/恢复流程；Carbon、Benchmark、Score先保留真实的未就绪节点。
- **M5**：知识检索层；在知识材料规模和来源确定后，评估 LlamaIndex + Qdrant 本地模式，先导入转型目录、政策、行业标准和排放因子说明。知识检索只提供候选证据，不直接写入规则或评分。
- **M6**：Carbon Engine；活动数据标准化、单位注册、排放因子注册、边界检查和计算轨迹。
- **M7**：Benchmark + Transition Engine；行业基准、规则版本、转型行为和路径识别。
- **M8**：Score Engine + Credit Support；在 03/01 确认方法后实现可解释评分、风险和信贷支持建议。
- **后置阶段**：报告扩展、Windows、三端回归和正式分发。

LangGraph 的官方定位是有状态、长运行 Agent 的低层编排和运行时，适合持久化、流式处理和人工介入；LangChain 1.x 的 Agent 建立在 LangGraph 之上。M3 不同时引入两者，是为了把 UI/API 边界与 Agent 状态迁移分开验收。参考：

- <https://docs.langchain.com/oss/python/concepts/products>
- <https://langchain-ai.github.io/langgraph/reference/>

## 十七、02 交付要求

02完成后直接向若翎和01报告，不自行提交或推送。报告至少包括：

1. M3-A—F 各阶段完成状态；
2. 新增和修改文件；
3. React 前端目录和构建方式；
4. API契约变化；
5. 三栏UI和各状态截图；
6. 配套数据主流程验证；
7. 企业运行隔离和参考结论隔离测试；
8. 前端类型、构建、单元、组件和Playwright测试结果；
9. Python回归测试结果；
10. 已验证、环境阻断、未验证和待01确认事项；
11. 明确确认未做LangGraph、知识库、碳核算、评分、Windows和报告扩展；
12. `git status --short --branch`和`git diff --check`结果。

如遇到需要改变API资源、领域对象、数据隔离、技术栈、MVP范围或本文件边界的问题，先停止并向若翎报告，不得自行扩大范围。
