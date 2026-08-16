# G阶段桌面封装说明

桌面入口位于 `desktop/launcher.py`，只负责配置用户数据目录、启动回环 FastAPI 服务、打开 PyWebView 窗口和在窗口关闭时回收服务；业务规则仍由 `app/` 执行。

## macOS

使用项目指定解释器安装封装依赖并构建：

```bash
/opt/anaconda3/bin/python -m pip install -r code/python/requirements.txt
/opt/anaconda3/bin/python code/python/packaging/build_macos.py
```

输出：

- `code/python/dist/TransitionFinanceAssessment.app`
- `code/python/dist/TransitionFinanceAssessment-macos.dmg`

应用数据根目录为 `~/Library/Application Support/TransitionFinanceAssessment/`。可用 `TRANSITION_FINANCE_APP_DATA_ROOT` 指向临时目录进行隔离 smoke test。未设置 `CODESIGN_IDENTITY` 时，脚本会明确标记未签名；本项目不把签名或公证状态写成已完成。

## Windows

必须在真实 Windows、Windows 虚拟机或 Windows CI 中执行，不能用 macOS 构建结果替代：

```powershell
python code/python/packaging/build_windows.py
```

脚本使用 `transition_finance_assessment_windows.spec` 生成 onedir EXE，再用 WiX v4 `heat` 收集文件并生成 MSI。安装数据根目录为 `%LOCALAPPDATA%/TransitionFinanceAssessment/`。G 阶段交付前必须在 Windows 环境完成首次安装、启动、关闭、重复启动、上传/恢复、报告读取、升级和卸载验证。

## 边界

构建脚本不包含 API key、业务原始数据或训练模型；构建时排除本项目未启用的科学计算和本地 OCR 大型可选依赖。签名、公证、Windows 实机安装和三平台回归需要相应平台环境，未验证前不得宣称完成。
