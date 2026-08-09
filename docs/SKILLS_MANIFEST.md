# Skills清单

**版本**：v0.1
**日期**：2026-08-09
**状态**：记录能力与替代方案；本轮不安装Skill

## 1. 使用说明

本项目当前没有独立的项目内 `.agents/skills/`目录，原工作台环境通过父级科研工作台的 `../.agents/skills/` 继承项目级Skills。复制、克隆或解压本项目时，Skills不会随项目目录自动同步；其他成员需要在自己的Codex环境单独检查可用能力。

本文件只列出与本项目直接相关的项目级和全局Skills，不把包内嵌套的参考 `SKILL.md` 误算成独立Skill。当前任务没有安装、更新或删除任何Skill。

## 2. 当前项目继承的科研工作台Skills

| Skill | 原环境位置 | 作用 | 项目必须能力 | 缺失时替代方式 |
|---|---|---|---|---|
| `idea-evaluator` | `../.agents/skills/idea-evaluator/` | 开发前审查致命缺陷、范围、竞赛价值和可行性 | 是，开发授权前优先 | 用人工检查表审查，不缩减MVP |
| `deep-research` | `../.agents/skills/deep-research/` | 系统性政策、行业和研究资料检索 | 研究阶段需要 | 以权威原文和人工来源表替代 |
| `econ-write` | `../.agents/skills/econ-write/` | 金融经济论证、业务价值和报告相关段落 | 报告阶段需要 | 按“主张—证据—机制—边界”手工写作 |
| `paper-spine` | `../.agents/skills/paper-spine/` | 统领报告结构、证据矩阵和章节衔接 | 报告阶段需要 | 用项目报告大纲和证据矩阵替代 |
| `paper-polish` | `../.agents/skills/paper-polish/` | 最终中文/英文表达收口 | 可选 | 人工校对，保持结论强度 |
| `office-academic-skill` | `../.agents/skills/office-academic-skill/` | 学术材料、Office交付和格式包装 | 竞赛材料阶段需要 | 手工编辑并按模板逐项检查 |
| `drawio-reconstruction` | `../.agents/skills/drawio-reconstruction/` | 架构、数据流、证据链图示 | 架构图阶段需要 | Mermaid或人工绘图，保留接口关系 |
| `scientific-toolkit-skill` | `../.agents/skills/scientific-toolkit-skill/` | 正式数据到达后的统计、机器学习和审计支持 | 数据阶段需要 | 使用已批准的本地工具并记录版本 |
| `Humanizer-zh` | `../.agents/skills/Humanizer-zh/` | 中文表达自然化和竞赛文案收口 | 可选 | 人工删改模板化表达 |

## 3. 当前全局可用且与项目相关的Skills

| Skill | 作用 | 当前阶段 | 缺失时替代方式 |
|---|---|---|---|
| `agent-reach` | 互联网检索、网页和公开来源研究 | 需要外部调研时使用 | 只使用已提供原文，或由成员人工检索并记录来源 |
| `nature-academic-search` | 多源学术检索、引用核验和文献表 | 文献研究时使用 | 建立文献卡片并逐条人工核验 |
| `nature-reader` | 论文/PDF的结构化阅读 | 阅读政策、标准和论文时使用 | `pdftotext`/PDF阅读工具加人工复核 |
| `pdf` | PDF提取、渲染、页面和布局检查 | 参赛指南、政策PDF和交付PDF | 使用Poppler或其他本地PDF工具，并说明视觉未验风险 |
| `docx` | DOCX读取、文本提取和结构检查 | 赛题书、技术文档 | `pandoc`/`python-docx`或人工阅读，保留来源 |
| `pptx` | PPTX模板读取、编辑和检查 | 精益画布、决赛PPT | 按模板人工检查字段、匿名性和页数 |
| `frontend-design` | 后续网页交互和视觉实现 | 开发授权后 | 由若翎按已确认技术栈实现 |
| `playwright` / `webapp-testing` | 后续网页流程、截图和可运行性测试 | 开发授权后 | 按测试矩阵手工操作并保留证据 |
| `documents:documents` / `presentations:Presentations` / `spreadsheets:Spreadsheets` | Office文件生成、处理和验证 | 交付材料阶段按需 | 本地Office工具和结构化检查 |

“当前全局可用”是原环境能力记录，不代表其他成员电脑一定安装，也不代表本轮已经调用所有Skill。涉及互联网、政策、文献、PDF、Office和开发测试时，先按实际可用性选择。

## 4. 推荐调用顺序

1. `idea-evaluator`：开发前范围、风险和竞赛价值审查；
2. `agent-reach`、`deep-research`、`nature-academic-search`：分别做公开来源、系统研究和学术引用核验；
3. `drawio-reconstruction`：形成系统架构、数据流和证据链图；
4. 正式数据到达后使用 `scientific-toolkit-skill` 做统计/机器学习审计；
5. `paper-spine`统领报告，`econ-write`处理金融经济论证，`paper-polish`与`Humanizer-zh`择一做语言收口；
6. `office-academic-skill`以及Office/PDF/PPT技能完成竞赛材料包装和验收；
7. 收到“开始开发MVP”后，再使用前端设计、Playwright和Web应用测试能力。

不要同时启用多套完整写作编排；Office技能不能替代证据研究；检索Skill不能直接生成未经复核的政策结论。
