# M1—M5本地运行说明

本目录实现 `docs/DEVELOPMENT_BRIEF.md` 规定的M1闭环和B阶段领域层基础：

`Excel上传 → 五张表校验 → 企业代号关联 → 企业详情 → 2024—2025能耗变化 → 缺失提示 → 转型目录匹配 → 基础报告 → 参考结论对照`

并提供工作空间、数据批次、企业档案、评估运行、消息、报告索引和对比视图的SQLite元数据持久化。工作簿只作为命题方脱敏模拟数据处理，所有页面和报告都保留“命题方脱敏模拟数据，仅用于比赛开发测试，不代表真实企业业务数据”声明。

D阶段新增运行级多模态附件：PDF原生文本/表格、DOCX段落/表格、XLSX批次绑定，以及图片/扫描PDF的后端外部多模态解析适配器。解析结果保留页码、段落、表格单元格或图片位置、置信度、企业代号冲突和人工复核状态；补充材料不会跨评估运行共享事实。未配置外部API时，图片和扫描PDF自动降级为“待复核”，不会伪称解析成功。

E阶段新增会话模型能力发现、运行级上下文、只读工具白名单、停止/重试、失败降级和编排审计。外部会话模型只负责理解当前运行意图、选择受控工具并解释结构化结果；模型不能修改原始事实、规则、因子、权重、阈值、运行状态或授信结论。`转型规划结论`不会进入模型上下文，目录仍是独立规则/知识层。未配置外部会话模型时，模型列表为空，消息自动降级为离线受控流程。

M4使用LangGraph管理运行级状态图和LangChain Core包装确定性节点；SQLite保存检查点、版本和人工确认状态。M5增加记录级知识准入、四级可见性、SQLite/FTS5确定性检索、关键词降级、运行级知识版本冻结、检索日志、只读`search_knowledge`工具和知识依据面板。普通检索不会自动构建索引，首次使用前需要管理员在受控入口执行dry-run和rebuild。M5知识只作为候选证据，不执行因子、碳核算、评分或授信决定。

当前内置 Token Plan 可用模型目录包括：`qwen3.8-max`、`qwen3.7-plus`、`qwen3.7-max`、`qwen3.6-flash`、`deepseek-v4-pro-0813`、`deepseek-v4-pro`、`deepseek-v4-flash-0731`、`glm-5.2`。图片和扫描PDF不使用图片生成、语音或视频模型；若当前会话模型不支持视觉理解（例如 DeepSeek），系统自动使用 `qwen3.6-flash` 提取候选证据，再将结构化证据交回当前会话模型。支持视觉的千问模型直接处理。该路由只负责证据提取，不进入评分、规则或授信判断。

## 启动

在仓库根目录执行：

```bash
/opt/anaconda3/bin/python code/python/run_m1.py
```

打开 `http://127.0.0.1:8015/`。系统会自动发现并解析项目内的比赛配套工作簿 `配套数据.xlsx`，首次启动后即可直接创建企业评估，不要求用户重复上传；上传入口仅用于管理员替换或测试其他工作簿。M1兼容流程的批次原件、元数据和报告保存在 `code/python/.m1_runtime/`，该目录已被 `.gitignore` 排除。B阶段域层默认使用：macOS `~/Library/Application Support/TransitionFinanceAssessment/`，Windows `%LOCALAPPDATA%/TransitionFinanceAssessment/`；测试可用 `TRANSITION_FINANCE_APP_DATA_ROOT` 指向临时目录。

图片和扫描PDF的外部解析使用后端受控的OpenAI兼容接口；配置 `TRANSITION_FINANCE_MULTIMODAL_API_BASE_URL`、`TRANSITION_FINANCE_MULTIMODAL_API_KEY`、`TRANSITION_FINANCE_MULTIMODAL_MODEL`，可选配置 `TRANSITION_FINANCE_MULTIMODAL_PROVIDER`、`TRANSITION_FINANCE_MULTIMODAL_PROMPT_VERSION` 和 `TRANSITION_FINANCE_MULTIMODAL_TIMEOUT_SECONDS`。密钥不进入前端、报告、普通日志或能力接口响应；接口未配置或失败时保留原件并进入人工复核。

会话模型使用另一组后端环境变量：`TRANSITION_FINANCE_SESSION_API_BASE_URL`、`TRANSITION_FINANCE_SESSION_API_KEY`，可选 `TRANSITION_FINANCE_SESSION_MODEL`、`TRANSITION_FINANCE_SESSION_PROVIDER`、`TRANSITION_FINANCE_SESSION_TIMEOUT` 和 `TRANSITION_FINANCE_SESSION_MAX_RETRIES`。未设置默认模型时使用内置默认会话模型 `qwen3.7-plus`。用户也可以在工作台“添加模型”中填写兼容OpenAI Chat Completions的接口地址、API key和模型名称；配置只保存到本机后端应用数据中的SQLite，不回传API key，模型列表只显示脱敏配置。`GET /api/v1/model-providers` 和 `GET /api/v1/models` 会合并环境变量模型与用户自定义模型；`POST/GET/DELETE /api/v1/model-configs` 提供对应配置接口。LangGraph只负责状态编排，LangChain Core只包装受控节点/工具，二者不接管事实、规则、因子、评分或证据准入。真实供应商联调必须在受控环境配置兼容接口后单独验收，仓库测试使用本地模拟传输。

普通用户界面默认不展示模型、工具和审计调试信息。团队管理员可在受控环境设置 `TRANSITION_FINANCE_ADMIN_PASSWORD` 后，从工作台的“团队管理员入口”进入诊断视图；未配置口令时该入口不可用，不提供默认密码。管理员入口只控制诊断界面展示，不改变规则、评分、事实或报告边界。

## API

- `POST /api/v1/documents`
- `GET /api/v1/jobs/{batch_id}`
- `GET /api/v1/batches/{batch_id}/companies`
- `GET /api/v1/companies/{company_code}?batch_id={batch_id}`
- `GET /api/v1/companies/{company_code}/energy-trend?batch_id={batch_id}`
- `GET /api/v1/companies/{company_code}/catalog-matches?batch_id={batch_id}`
- `POST /api/v1/reports/basic`
- `POST/GET /api/v1/workspaces`
- `GET /api/v1/source-batches/default`
- `POST /api/v1/source-batches`
- `POST/GET /api/v1/workspaces/{workspace_id}/runs`
- `GET/PATCH /api/v1/assessment-runs/{assessment_run_id}`
- `POST/GET /api/v1/assessment-runs/{assessment_run_id}/messages`
- `POST/GET /api/v1/assessment-runs/{assessment_run_id}/reports`
- `GET /api/v1/assessment-runs/{assessment_run_id}/reports/{report_artifact_id}/download`
- `POST /api/v1/assessment-runs/{assessment_run_id}/reports/{report_artifact_id}/export`
- `POST /api/v1/assessment-runs/{assessment_run_id}/reports/{report_artifact_id}/open-directory`
- `GET /api/v1/parsers/capabilities`
- `GET /api/v1/model-providers`
- `GET /api/v1/models`
- `POST/GET/DELETE /api/v1/model-configs`
- `POST/GET /api/v1/assessment-runs/{assessment_run_id}/attachments`
- `GET /api/v1/assessment-runs/{assessment_run_id}/attachments/{attachment_id}`
- `POST /api/v1/assessment-runs/{assessment_run_id}/conversation/turn`
- `POST /api/v1/assessment-runs/{assessment_run_id}/conversation/stop`
- `POST /api/v1/assessment-runs/{assessment_run_id}/conversation/retry`
- `GET /api/v1/assessment-runs/{assessment_run_id}/conversation/events`
- `GET /api/v1/assessment-runs/{assessment_run_id}/conversation/summary`（普通用户可见的安全处理摘要）
- `GET /api/v1/assessment-runs/{assessment_run_id}/workflows`
- `POST /api/v1/assessment-runs/{assessment_run_id}/workflows/start`
- `POST /api/v1/assessment-runs/{assessment_run_id}/workflows/{workflow_name}/pause|resume|review`
- `GET /api/v1/knowledge/indexes/current`
- `POST /api/v1/knowledge/indexes/dry-run|rebuild`（管理员受控接口）
- `GET /api/v1/knowledge/sources`、`GET /api/v1/knowledge/tests/gold`（管理员受控接口）
- `POST /api/v1/assessment-runs/{assessment_run_id}/knowledge/search`
- `GET /api/v1/assessment-runs/{assessment_run_id}/knowledge/retrievals`
- `GET /api/v1/assessment-runs/{assessment_run_id}/knowledge/chunks/{chunk_id}`
- `POST/GET /api/v1/comparison-views`
- `GET /api/v1/workspaces/{workspace_id}/comparison-views`（刷新恢复已保存对比视图）

原始编排事件只允许管理员诊断会话读取；普通用户只读取去除服务商、模型、原始载荷和证据引用的处理摘要。F阶段已提供报告预览、下载、导出、目录打开和企业对比；G阶段提供共享桌面入口、macOS PyWebView/PyInstaller `.app`/DMG封装，以及Windows PyInstaller/WiX构建配置。桌面运行数据不写入安装目录：macOS使用 `~/Library/Application Support/TransitionFinanceAssessment/`，Windows使用 `%LOCALAPPDATA%/TransitionFinanceAssessment/`。

macOS构建（必须使用指定Python环境）：

```bash
/opt/anaconda3/bin/python -m desktop.launcher --smoke-test
/opt/anaconda3/bin/python code/python/packaging/build_macos.py
```

当前macOS `.app`和DMG已在 Apple Silicon macOS 本机完成构建及离线 API 健康检查；产物未签名、未完成Apple公证，不代表可直接生产分发。Windows构建必须在真实Windows、Windows虚拟机或Windows CI中执行，并安装WiX v4：

```powershell
python code/python/packaging/build_windows.py
```

Windows EXE/MSI的实际构建、安装、升级、卸载和三平台回归尚未在本机验证。外部模型密钥仍须从受控环境变量读取，不写入应用包、前端、报告、普通日志或公开仓库。外部多模态API只负责候选证据提取，会话模型只负责受控工具编排和解释，不负责评分、目录规则或授信判断。
