# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for AcademyPro.

Build with:
    python -m PyInstaller --clean --noconfirm academy_system.spec

Output: dist/AcademyPro/AcademyPro.exe (one-folder build).
The folder is what the Inno Setup installer packages.
"""

import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
project_root = os.path.abspath(os.path.dirname(SPEC))

datas = [
    (os.path.join(project_root, "config", "academy_config.json"), "config"),
    (os.path.join(project_root, "translations"), "translations"),
    (os.path.join(project_root, "assets", "logo"), os.path.join("assets", "logo")),
    (os.path.join(project_root, "license", "keys", "public_key.pem"),
     os.path.join("license", "keys")),
    (os.path.join(project_root, "LICENSES.txt"), "."),
    (os.path.join(project_root, "migrations"), "migrations"),
]

binaries = []
_libzbar = os.path.join(project_root, "libzbar-64.dll")
if os.path.exists(_libzbar):
    binaries.append((_libzbar, "."))
_libiconv = os.path.join(project_root, "libiconv.dll")
if os.path.exists(_libiconv):
    binaries.append((_libiconv, "."))
else:
    print("WARNING: libzbar-64.dll not found next to academy_system.spec.")
    print("         The built .exe will crash on the first QR scan.")

hiddenimports = [
    "pyzbar.pyzbar",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtSvg",
    "PySide6.QtPrintSupport",
    "PySide6.QtNetwork",
    "cryptography",
    "cryptography.hazmat.primitives.asymmetric.ed25519",
    "cryptography.hazmat.primitives.serialization",
]
hiddenimports += collect_submodules("pyzbar")


a = Analysis(
    ["main.py"],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "pytest", "_pytest", "numpy.testing",
        "matplotlib", "IPython", "jupyter", "notebook",
        "PyQt5", "PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.QtWidgets", "PyQt5.QtSvg", "PyQt5.sip",
        "PyQt6", "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets", "PyQt6.QtSvg", "PyQt6.sip",
        "tensorflow", "torch", "torchvision", "keras", "sklearn", "scipy",
        "pandas", "numba", "sympy", "astropy", "erfa", "h5py",
        "sqlalchemy", "bokeh", "dask", "distributed", "xarray",
        "statsmodels", "seaborn",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AcademyPro",              # <-- changed from AcademySystem
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_root, "assets", "logo", "logo.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AcademyPro",              # <-- changed from AcademySystem
)