# PyInstaller spec for the windowed GUI.
# Build: pyinstaller build/Memex.spec

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

hiddenimports = []
hiddenimports += collect_submodules("keyring")
hiddenimports += collect_submodules("keyring.backends")
hiddenimports += ["sqlite_vec"]
hiddenimports += collect_submodules("mcp")
hiddenimports += ["pypdf", "docx", "selectolax", "selectolax.parser"]
hiddenimports += collect_submodules("PySide6")

datas = []
datas += collect_data_files("sqlite_vec")
# Bundle the logo so the running GUI can find it via sys._MEIPASS
datas += [("../assets/icon.png", "assets")]

a = Analysis(
    ["../src/memex/gui.py"],
    pathex=["../src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
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
    name="Memex",
    console=False,      # windowed (no console flash)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    upx=False,
    icon="../assets/icon.ico",
)
