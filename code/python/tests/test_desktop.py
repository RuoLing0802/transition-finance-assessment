from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from desktop.launcher import application_data_root, configure_runtime_environment


def test_application_data_root_follows_platform_conventions(tmp_path: Path) -> None:
    assert application_data_root(home=tmp_path, os_name="posix") == tmp_path / "Library" / "Application Support" / "TransitionFinanceAssessment"
    assert application_data_root(home=tmp_path, environ={"LOCALAPPDATA": str(tmp_path / "LocalAppData")}, os_name="nt") == tmp_path / "LocalAppData" / "TransitionFinanceAssessment"


def test_configure_runtime_environment_keeps_business_data_outside_install_tree(tmp_path: Path) -> None:
    environment: dict[str, str] = {}
    root = configure_runtime_environment(root=tmp_path / "application-data", environ=environment)
    assert root == tmp_path / "application-data"
    assert environment["TRANSITION_FINANCE_APP_DATA_ROOT"] == str(root)
    assert environment["M1_RUNTIME_ROOT"] == str(root / "m1-runtime")
    assert root.is_dir()


def test_desktop_smoke_entry_starts_and_stops_local_api(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["TRANSITION_FINANCE_APP_DATA_ROOT"] = str(tmp_path / "application-data")
    environment["M1_RUNTIME_ROOT"] = str(tmp_path / "m1-runtime")
    result = subprocess.run(
        [sys.executable, "-m", "desktop.launcher", "--smoke-test"],
        cwd=project_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert "'status': 'ok'" in result.stdout
    assert (tmp_path / "application-data").is_dir()
