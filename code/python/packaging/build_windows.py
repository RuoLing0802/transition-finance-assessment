from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


PYTHON_ROOT = Path(__file__).resolve().parents[1]
PACKAGING_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = PYTHON_ROOT / "dist"


def run(command: list[str], *, cwd: Path | None = None) -> None:
    print("$", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def build(output_dir: Path, *, skip_pyinstaller: bool = False) -> Path:
    if platform.system() != "Windows":
        raise RuntimeError("Windows EXE/MSI必须在真实Windows、Windows虚拟机或Windows CI环境执行")
    output_dir.mkdir(parents=True, exist_ok=True)
    spec = PACKAGING_ROOT / "transition_finance_assessment_windows.spec"
    python = os.environ.get("PYTHON", sys.executable)
    if not skip_pyinstaller:
        run([python, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(output_dir), "--workpath", str(output_dir / "build"), str(spec)], cwd=PYTHON_ROOT)
    onedir = output_dir / "TransitionFinanceAssessment"
    exe = onedir / "TransitionFinanceAssessment.exe"
    if not exe.is_file():
        raise FileNotFoundError(f"未找到PyInstaller产物：{exe}")
    wix = shutil.which("wix")
    if not wix:
        raise RuntimeError("已构建EXE，但未找到WiX v4的wix命令，无法生成MSI")
    harvested = output_dir / "TransitionFinanceAssessment-files.wxs"
    run(["heat", "dir", str(onedir), "-cg", "AppFiles", "-dr", "INSTALLFOLDER", "-gg", "-srd", "-sfrag", "-sreg", "-out", str(harvested)])
    template = (PACKAGING_ROOT / "transition_finance_assessment.wxs").read_text(encoding="utf-8")
    harvested_text = harvested.read_text(encoding="utf-8")
    fragment_start = harvested_text.find("<Fragment")
    fragment_end = harvested_text.rfind("</Fragment>")
    if fragment_start < 0 or fragment_end < 0:
        raise RuntimeError("WiX heat未生成可嵌入的Fragment")
    harvested_text = harvested_text[fragment_start : fragment_end + len("</Fragment>")]
    generated = output_dir / "transition_finance_assessment.generated.wxs"
    generated.write_text(template.replace("<!-- HARVESTED_COMPONENTS -->", harvested_text), encoding="utf-8")
    msi_path = output_dir / "TransitionFinanceAssessment-windows.msi"
    run([wix, "build", str(generated), "-o", str(msi_path)])
    print(f"Windows EXE：{exe}")
    print(f"Windows MSI：{msi_path}")
    return msi_path


def main() -> None:
    parser = argparse.ArgumentParser(description="构建企业转型金融评估Windows EXE和MSI")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--skip-pyinstaller", action="store_true")
    args = parser.parse_args()
    build(args.output_dir.resolve(), skip_pyinstaller=args.skip_pyinstaller)


if __name__ == "__main__":
    main()
