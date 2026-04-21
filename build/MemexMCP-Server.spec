# PyInstaller spec for the MCP stdio server (console exe).
# Build: pyinstaller build/MemexMCP-Server.spec

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

hiddenimports = []
# keyring backends resolve dynamically on Windows
hiddenimports += collect_submodules("keyring")
hiddenimports += collect_submodules("keyring.backends")
# sqlite_vec ships a native extension that must be bundled
hiddenimports += ["sqlite_vec"]
# MCP server + its deps
hiddenimports += collect_submodules("mcp")
# Chunker optional deps (import-on-use, so PyInstaller can't see them)
hiddenimports += ["pypdf", "docx", "selectolax", "selectolax.parser"]

datas = []
datas += collect_data_files("sqlite_vec")

a = Analysis(
    ["../src/memex/mcp_server.py"],
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
    name="MemexMCP-Server",
    console=True,       # stdio MCP — must be console
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    upx=False,
    icon="../assets/icon.ico",
)
