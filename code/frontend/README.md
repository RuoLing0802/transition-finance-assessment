# M3 专业 Agent 工作台前端

本目录是 M3 新建的 React + TypeScript + Vite 前端，使用 Ant Design 组件和 ECharts 趋势图。旧版 `code/python/app/static/index.html` 保留为回退基线；本前端只消费现有 FastAPI `/api/v1` 接口，不复制后端业务逻辑。

## 本地开发

在项目根目录启动后端：

```bash
/opt/anaconda3/bin/python code/python/run_m1.py
```

另开终端启动前端：

```bash
cd code/frontend
npm install
npm run dev
```

访问 `http://127.0.0.1:5173/`。Vite开发服务器会把 `/api`和`/health`代理到 `8015`。

## 构建并由FastAPI提供

```bash
cd code/frontend
npm run typecheck
npm run test
npm run build
```

构建结果写入被 Git 忽略的 `code/python/app/static/frontend-dist/`。重新启动 FastAPI 后，访问 `http://127.0.0.1:8015/` 会优先加载该构建结果；如果构建结果不存在，则回退到旧版静态页面。

## M3边界

- 默认载入命题方配套脱敏模拟数据，不要求普通用户重新上传工作簿；补充PDF、DOCX和图片通过当前运行上传。
- 工作空间可管理多个企业，一次评估运行只绑定一家企业；消息、附件和企业事实按运行隔离。
- `转型规划结论`只在右侧“参考对照”显示，不进入模型上下文。
- 碳核算、行业对标、正式转型评分和授信结论显示真实的未就绪状态，不填充假分数或假排放量。
- M3不引入 LangChain、LangGraph、知识库、报告扩展或 Windows 打包。
