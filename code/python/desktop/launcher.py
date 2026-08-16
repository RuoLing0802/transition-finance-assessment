from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any


APP_DATA_FOLDER = "TransitionFinanceAssessment"
DEFAULT_HOST = "127.0.0.1"


def application_data_root(*, home: Path | None = None, environ: dict[str, str] | None = None, os_name: str | None = None) -> Path:
    env = environ if environ is not None else os.environ
    platform_name = os_name if os_name is not None else os.name
    if platform_name == "nt":
        base = Path(env.get("LOCALAPPDATA", str((home or Path.home()) / "AppData" / "Local")))
    else:
        base = (home or Path.home()) / "Library" / "Application Support"
    return (base / APP_DATA_FOLDER).resolve()


def configure_runtime_environment(*, root: Path | None = None, environ: dict[str, str] | None = None) -> Path:
    env = environ if environ is not None else os.environ
    configured_root = env.get("TRANSITION_FINANCE_APP_DATA_ROOT")
    data_root = Path(configured_root).expanduser().resolve() if configured_root else (root or application_data_root(environ=env)).resolve()
    data_root.mkdir(parents=True, exist_ok=True)
    env.setdefault("TRANSITION_FINANCE_APP_DATA_ROOT", str(data_root))
    env.setdefault("M1_RUNTIME_ROOT", str(data_root / "m1-runtime"))
    return data_root


def choose_local_port(host: str = DEFAULT_HOST) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def import_application() -> Any:
    """Import the API only after desktop data paths are configured."""
    python_root = Path(__file__).resolve().parents[1]
    if str(python_root) not in sys.path:
        sys.path.insert(0, str(python_root))
    from app.main import app

    return app


def start_api_server(*, host: str = DEFAULT_HOST, port: int | None = None) -> tuple[Any, threading.Thread, int]:
    import uvicorn

    app = import_application()
    selected_port = port or choose_local_port(host)
    config = uvicorn.Config(
        app,
        host=host,
        port=selected_port,
        log_level=os.environ.get("TRANSITION_FINANCE_DESKTOP_LOG_LEVEL", "warning"),
        access_log=False,
        reload=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="transition-finance-api", daemon=True)
    thread.start()
    deadline = time.monotonic() + float(os.environ.get("TRANSITION_FINANCE_DESKTOP_STARTUP_TIMEOUT", "20"))
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=3)
        raise RuntimeError("本地评估服务启动失败或超时")
    return server, thread, selected_port


def wait_for_health(host: str, port: int, timeout: float = 10.0) -> dict[str, Any]:
    url = f"http://{host}:{port}/health"
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                import json

                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - timing depends on the local server
            last_error = exc
            time.sleep(0.05)
    raise RuntimeError(f"本地评估服务健康检查失败：{last_error}")


def stop_api_server(server: Any, thread: threading.Thread) -> None:
    server.should_exit = True
    thread.join(timeout=5)


def run_desktop(*, debug: bool = False) -> None:
    configure_runtime_environment()
    server, thread, port = start_api_server()
    try:
        wait_for_health(DEFAULT_HOST, port)
        import webview

        webview.create_window(
            "企业转型金融评估",
            f"http://{DEFAULT_HOST}:{port}/",
            width=1440,
            height=960,
            min_size=(1100, 720),
            text_select=True,
        )
        webview.start(debug=debug)
    finally:
        stop_api_server(server, thread)


def smoke_test() -> dict[str, Any]:
    configure_runtime_environment()
    server, thread, port = start_api_server()
    try:
        return wait_for_health(DEFAULT_HOST, port)
    finally:
        stop_api_server(server, thread)


def main() -> None:
    parser = argparse.ArgumentParser(description="企业转型金融评估桌面入口")
    parser.add_argument("--debug", action="store_true", help="开启PyWebView调试模式")
    parser.add_argument("--smoke-test", action="store_true", help="仅启动本地API并执行健康检查")
    args = parser.parse_args()
    if args.smoke_test:
        print(smoke_test())
    else:
        run_desktop(debug=args.debug)


if __name__ == "__main__":
    main()
