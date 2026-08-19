# PyInstaller spec for the macOS .app bundle.
from pathlib import Path

PYTHON_ROOT = Path(SPECPATH).resolve().parent
APP_ROOT = PYTHON_ROOT / "app"
PROJECT_ROOT = PYTHON_ROOT.parents[1]
WORKBOOK_CANDIDATES = [
    PROJECT_ROOT / "27-多模态技术与数据治理赛道-碳迹可循，绿贷智评：基于多维度数据与行业标准的企业转型金融评估系统" / "配套数据.xlsx",
    PYTHON_ROOT / "packaging" / "bundled_data" / "default_workbook.xlsx",
]
DEFAULT_WORKBOOK = next((path for path in WORKBOOK_CANDIDATES if path.is_file()), None)
bundled_datas = [(str(DEFAULT_WORKBOOK), "app/bundled_data")] if DEFAULT_WORKBOOK else []
hiddenimports = [
    "app.main",
    "uvicorn.config",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "webview.platforms.cocoa",
]

a = Analysis(
    [str(PYTHON_ROOT / "desktop" / "launcher.py")],
    pathex=[str(PYTHON_ROOT)],
    binaries=[],
    datas=[(str(APP_ROOT / "static"), "app/static"), *bundled_datas],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PyQt5", "PyQt6", "PySide", "PySide2", "PySide6", "tkinter",
        "paddleocr", "paddle", "paddlepaddle", "paddlex", "paddlenlp",
        "numpy", "pandas", "scipy", "matplotlib", "IPython", "ipython",
        "torch", "tensorflow", "sklearn", "skimage", "sympy", "statsmodels",
        "xarray", "dask", "numba", "llvmlite", "pyarrow", "h5py", "tables",
        "bokeh", "plotly", "altair", "panel", "astropy", "selenium", "playwright",
        "jieba", "nltk", "transformers", "jupyter", "notebook", "nbformat", "nbconvert",
        "zmq", "sqlalchemy", "distributed", "fsspec", "s3fs", "botocore", "boto3",
        "webview.platforms.qt", "webview.platforms.gtk", "webview.platforms.cef",
        "webview.platforms.winforms", "webview.platforms.mshtml", "webview.platforms.edgechromium",
        "webview.platforms.android", "qtpy",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TransitionFinanceAssessment",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="TransitionFinanceAssessment",
)
app = BUNDLE(
    coll,
    name="TransitionFinanceAssessment.app",
    icon=None,
    bundle_identifier="org.transitionfinance.assessment",
)
