from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PYTHON_ROOT = Path(__file__).resolve().parents[1]
PACKAGING_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = PYTHON_ROOT / "dist"


def run(command: list[str], *, cwd: Path | None = None) -> None:
    print("$", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def build(output_dir: Path, *, skip_pyinstaller: bool = False) -> Path:
    if platform.system() != "Darwin":
        raise RuntimeError("macOS构建必须在macOS环境执行")
    output_dir.mkdir(parents=True, exist_ok=True)
    spec = PACKAGING_ROOT / "transition_finance_assessment_macos.spec"
    python = os.environ.get("PYTHON", sys.executable)
    if not skip_pyinstaller:
        run([
            python,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(output_dir),
            "--workpath",
            str(output_dir / "build"),
            str(spec),
        ], cwd=PYTHON_ROOT)
    app_path = output_dir / "TransitionFinanceAssessment.app"
    if not app_path.is_dir():
        raise FileNotFoundError(f"未找到PyInstaller产物：{app_path}")

    identity = os.environ.get("CODESIGN_IDENTITY", "").strip()
    if identity:
        run(["codesign", "--deep", "--force", "--options", "runtime", "--sign", identity, str(app_path)])
    else:
        print("签名状态：未签名；未完成Apple公证，不得宣称生产分发验证通过。")

    dmg_path = output_dir / "TransitionFinanceAssessment-macos.dmg"
    with tempfile.TemporaryDirectory(prefix="transition-finance-dmg-") as temporary:
        staging = Path(temporary) / "TransitionFinanceAssessment"
        staging.mkdir()
        shutil.copytree(app_path, staging / app_path.name)
        (staging / "Applications").symlink_to("/Applications", target_is_directory=True)
        shutil.copy2(PACKAGING_ROOT / "DMG_README.txt", staging / "安装与运行说明.txt")
        run(["hdiutil", "create", "-volname", "TransitionFinanceAssessment", "-srcfolder", str(staging), "-ov", "-format", "UDZO", str(dmg_path)])

    print(f"macOS应用：{app_path}")
    print(f"macOS DMG：{dmg_path}")
    return dmg_path


def main() -> None:
    parser = argparse.ArgumentParser(description="构建企业转型金融评估macOS .app和DMG")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--skip-pyinstaller", action="store_true")
    args = parser.parse_args()
    build(args.output_dir.resolve(), skip_pyinstaller=args.skip_pyinstaller)


if __name__ == "__main__":
    main()
