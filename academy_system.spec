# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the Academy Membership System.

Build with:
    python -m PyInstaller --clean --noconfirm academy_system.spec

Output: dist/AcademySystem.exe (single file, Windows).
"""

import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None
project_root = os.path.abspath(os.path.dirname(SPEC))


# ---------------------------------------------------------------------------
# Data files: read-only resources bundled INTO the .exe
# ---------------------------------------------------------------------------
datas = [
    (os.path.join(project_root, "config", "academy_config.json"), "config"),
    (os.path.join(project_root, "translations"), "translations"),
    (os.path.join(project_root, "assets", "logo"), os.path.join("assets", "logo")),
    (os.path.join(project_root, "db", "schema.sql"), "db"),
    # Public key for license verification (private key never ships)
    (os.path.join(project_root, "license", "keys", "public_key.pem"),
     os.path.join("license", "keys")),
]

# ---------------------------------------------------------------------------
# Binaries: libzbar-64.dll required by pyzbar at runtime
#
# You must download it manually once and place it next to this .spec file
# at:  libzbar-64.dll
# Source: https://github.com/NaturalHistoryMuseum/pyzbar/issues/77#issuecomment-1133555141
#   or any Windows build of zbar's shared library.
# ---------------------------------------------------------------------------
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
    print("         Download it from the pyzbar README and place it in the project root.")


# ---------------------------------------------------------------------------
# Hidden imports — modules that PyInstaller's static analyzer can't see
# ---------------------------------------------------------------------------
hiddenimports = [
    "pyzbar.pyzbar",
    "PyQt6.QtSvg",
    "PyQt6.QtPrintSupport",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "cryptography",
    "cryptography.hazmat.primitives.asymmetric.ed25519",
    "cryptography.hazmat.primitives.serialization",
]
hiddenimports += collect_submodules("cv2")
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
        # Development / testing
        "tkinter",
        "pytest",
        "_pytest",
        "numpy.testing",

        # GUI libraries we don't use
        "matplotlib",
        "IPython",
        "jupyter",
        "notebook",
        "PyQt5",
        "PyQt5.QtCore",
        "PyQt5.QtGui",
        "PyQt5.QtWidgets",
        "PyQt5.QtSvg",
        "PyQt5.sip",

        # Scientific / ML libraries Anaconda ships that we don't use
        "tensorflow",
        "torch",
        "torchvision",
        "keras",
        "sklearn",
        "scipy",
        "pandas",
        "numba",
        "sympy",
        "astropy",
        "erfa",
        "h5py",
        "sqlalchemy",
        "bokeh",
        "dask",
        "distributed",
        "xarray",
        "statsmodels",
        "seaborn",
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="AcademySystem",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # If you have assets/logo/logo.ico, uncomment this line:
    icon=os.path.join(project_root, "assets", "logo", "logo.ico"),
)