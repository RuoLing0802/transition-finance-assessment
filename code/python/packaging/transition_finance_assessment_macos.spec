# PyInstaller spec for the macOS .app bundle.
from pathlib import Path

PYTHON_ROOT = Path(SPECPATH).resolve().parent
APP_ROOT = PYTHON_ROOT / "app"
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
    datas=[(str(APP_ROOT / "static"), "app/static")],
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
