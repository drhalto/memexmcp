# PyInstaller spec for the CLI (used by the installer + power users).

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

hiddenimports = []
hiddenimports += collect_submodules("keyring")
hiddenimports += collect_submodules("keyring.backends")
hiddenimports += ["sqlite_vec"]
hiddenimports += ["pypdf", "docx", "selectolax", "selectolax.parser"]

datas = []
datas += collect_data_files("sqlite_vec")

a = Analysis(
    ["../src/memex/cli.py"],
    pathex=["../src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["PySide6", "shiboken6", "tkinter"],
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
    name="memex-cli",
    console=True,
    disable_windowed_traceback=False,
    upx=False,
    icon="../assets/icon.ico",
)
