"""First-launch setup wizard for Memex.

Shown when ``MEMEX_HOME/config.json`` doesn't exist yet. Walks the user
through tier choice, optional Gemini key, Ollama install, and model pull,
then drops the MCP config snippet so they can paste it into their MCP client.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from memex import config as cfg_mod
from memex.config import TIERS
from memex.embedder import set_gemini_key
from memex.mcp_config import server_snippet
from memex.paths import config_path, ensure_dirs, home


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ollama_exe_path() -> Path:
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "Programs" / "Ollama" / "ollama.exe"


def should_show_wizard() -> bool:
    """First run = no config file at the expected MEMEX_HOME location."""
    return not config_path().exists()


# ---------------------------------------------------------------------------
# Background download (Ollama installer) — QThread + httpx
# ---------------------------------------------------------------------------

class _DownloadWorker(QObject):
    progress = Signal(int, int)   # bytes received, total bytes (0 = unknown)
    finished = Signal(str)        # path on success, "" on failure
    error = Signal(str)

    def __init__(self, url: str, out_path: str) -> None:
        super().__init__()
        self.url = url
        self.out_path = out_path

    def run(self) -> None:
        try:
            import httpx
            with httpx.stream("GET", self.url, follow_redirects=True, timeout=300.0) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                done = 0
                with open(self.out_path, "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=1 << 20):
                        f.write(chunk)
                        done += len(chunk)
                        self.progress.emit(done, total)
            self.finished.emit(self.out_path)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit("")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

class WelcomePage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Welcome to Memex")
        self.setSubTitle("Local semantic search for your codebases and documents.")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            "Memex indexes your files into vector embeddings on this PC, then\n"
            "exposes them over MCP so Claude (or any MCP client) can search them.\n\n"
            "This wizard will:\n"
            "  • Pick an embedding model tier (Small / Medium / Large)\n"
            "  • Optionally save a Gemini API key (cloud embeddings)\n"
            "  • Install Ollama if you don't have it\n"
            "  • Download the chosen embedding model\n"
            "  • Show the MCP config snippet to paste into your client\n\n"
            "Click Next to begin."
        ))
        lay.addStretch(1)


class TierPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Embedding tier")
        self.setSubTitle("Pick a model. You can switch tiers later in Settings.")
        lay = QVBoxLayout(self)
        self._radios: dict[str, QRadioButton] = {}
        for key in ("small", "medium", "large"):
            t = TIERS[key]
            rb = QRadioButton(f"{t.label}    ~{t.disk_mb} MB,  dim {t.dim}")
            lay.addWidget(rb)
            self._radios[key] = rb
        self._radios["small"].setChecked(True)
        lay.addStretch(1)

    def selectedTier(self) -> str:
        for k, rb in self._radios.items():
            if rb.isChecked():
                return k
        return "small"

    def validatePage(self) -> bool:
        self.wizard().setProperty("tier", self.selectedTier())
        return True


class KeyPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Gemini API key (optional)")
        self.setSubTitle(
            "Paste a key to enable cloud embeddings. Saved to Windows Credential "
            "Manager (not to disk). Skip for local-only."
        )
        lay = QVBoxLayout(self)
        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit.setPlaceholderText("(leave blank to skip)")
        lay.addWidget(self.edit)
        lay.addStretch(1)

    def validatePage(self) -> bool:
        key = self.edit.text().strip()
        if key:
            try:
                set_gemini_key(key)
            except Exception as e:
                QMessageBox.warning(self, "Key save failed", str(e))
                return False
        return True


class OllamaPage(QWizardPage):
    """Detect Ollama; if missing, download installer + run silently."""

    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Ollama")
        self.setSubTitle("Memex uses Ollama to run local embedding models.")
        lay = QVBoxLayout(self)
        self.status = QLabel("…")
        self.bar = QProgressBar()
        self.bar.setVisible(False)
        self.install_btn = QPushButton("Install Ollama (~1 GB)")
        self.install_btn.clicked.connect(self._start_install)
        lay.addWidget(self.status)
        lay.addWidget(self.bar)
        lay.addWidget(self.install_btn)
        lay.addStretch(1)
        self._ready = False
        self._thread: QThread | None = None
        self._worker: _DownloadWorker | None = None
        self._setup_proc: QProcess | None = None

    def initializePage(self) -> None:
        self._check()

    def isComplete(self) -> bool:
        return self._ready

    def _check(self) -> None:
        exe = ollama_exe_path()
        if exe.exists():
            self.status.setText(f"✓ Ollama is installed.\n   {exe}")
            self.install_btn.setVisible(False)
            self.bar.setVisible(False)
            self._ready = True
        else:
            self.status.setText(
                "Ollama is not installed yet. Click below to download and install it (~1 GB)."
            )
            self.install_btn.setVisible(True)
            self.install_btn.setEnabled(True)
            self._ready = False
        self.completeChanged.emit()

    def _start_install(self) -> None:
        self.install_btn.setEnabled(False)
        self.status.setText("Downloading OllamaSetup.exe…")
        self.bar.setVisible(True)
        self.bar.setRange(0, 0)
        tmp = str(Path(os.environ.get("TEMP", str(Path.home()))) / "OllamaSetup.exe")
        self._thread = QThread(self)
        self._worker = _DownloadWorker("https://ollama.com/download/OllamaSetup.exe", tmp)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_dl_progress)
        self._worker.finished.connect(self._on_dl_done)
        self._worker.error.connect(self._on_dl_error)
        self._thread.start()

    def _on_dl_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.bar.setRange(0, total)
            self.bar.setValue(done)

    def _on_dl_error(self, msg: str) -> None:
        self.status.setText(f"Download failed: {msg}")
        self.install_btn.setEnabled(True)
        self.bar.setVisible(False)

    def _on_dl_done(self, path: str) -> None:
        if self._thread is not None:
            self._thread.quit()
        if not path:
            return
        self.status.setText("Running Ollama installer (silent)…")
        self.bar.setRange(0, 0)
        self._setup_proc = QProcess(self)
        self._setup_proc.finished.connect(self._on_setup_done)
        self._setup_proc.start(path, ["/SILENT"])

    def _on_setup_done(self, _code: int, _status: object) -> None:
        # File system needs a beat to settle after the installer reports done.
        QTimer.singleShot(3000, self._check)


class PullPage(QWizardPage):
    """Run ``ollama pull <model>`` and stream progress into a bar + log."""

    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Downloading embedding model")
        self.setSubTitle("Fetching the model. This takes a few minutes.")
        lay = QVBoxLayout(self)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(200)
        self.log.setFont(QFont("Consolas", 9))
        lay.addWidget(self.bar)
        lay.addWidget(self.log)
        self._done = False
        self._proc: QProcess | None = None

    def isComplete(self) -> bool:
        return self._done

    def initializePage(self) -> None:
        tier_key = self.wizard().property("tier") or "small"
        # Save config first so the rest of the app picks up the new tier.
        ensure_dirs()
        cfg_mod.save(cfg_mod.Config.from_tier(tier_key))
        model = TIERS[tier_key].model

        self.bar.setValue(0)
        self.log.clear()
        self._done = False
        self.completeChanged.emit()

        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyRead.connect(self._on_out)
        self._proc.finished.connect(self._on_done)
        self._proc.start(str(ollama_exe_path()), ["pull", model])

    def _on_out(self) -> None:
        assert self._proc is not None
        data = bytes(self._proc.readAll()).decode("utf-8", errors="replace")
        # Strip carriage-return progress redraws — keep the log scrollable.
        cleaned = data.replace("\r", "\n")
        cur = self.log.textCursor()
        cur.movePosition(cur.MoveOperation.End)
        self.log.setTextCursor(cur)
        self.log.insertPlainText(cleaned)
        # Latest percentage in this chunk wins.
        m = list(re.finditer(r"(\d{1,3})%", data))
        if m:
            pct = max(0, min(100, int(m[-1].group(1))))
            self.bar.setValue(pct)

    def _on_done(self, code: int, _status: object) -> None:
        if code == 0:
            self.bar.setValue(100)
        else:
            self.log.insertPlainText(f"\n[ollama exited with {code}]\n")
        self._done = True
        self.completeChanged.emit()


class DonePage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Setup complete")
        self.setSubTitle("Add this to your MCP client (e.g. Claude Desktop), then restart it.")
        lay = QVBoxLayout(self)
        self.snippet = QTextEdit()
        self.snippet.setReadOnly(True)
        self.snippet.setFont(QFont("Consolas", 10))
        row = QHBoxLayout()
        copy = QPushButton("Copy to clipboard")
        copy.clicked.connect(self._copy)
        row.addWidget(copy)
        row.addStretch(1)
        lay.addWidget(self.snippet)
        lay.addLayout(row)
        lay.addWidget(QLabel(
            "Click Finish to open Memex. You can drag files / folders in to start indexing."
        ))

    def initializePage(self) -> None:
        cfg = cfg_mod.load()
        text = server_snippet(cfg)
        self.snippet.setPlainText(text)
        # Persist a copy next to the exes for later reference.
        try:
            (home() / "mcp-config.json").write_text(text, encoding="utf-8")
        except OSError:
            pass

    def _copy(self) -> None:
        QApplication.clipboard().setText(self.snippet.toPlainText())


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------

class SetupWizard(QWizard):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Memex Setup")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.HaveHelpButton, False)
        self.addPage(WelcomePage())
        self.addPage(TierPage())
        self.addPage(KeyPage())
        self.addPage(OllamaPage())
        self.addPage(PullPage())
        self.addPage(DonePage())
        self.resize(720, 520)


def run_wizard_if_needed(parent_app: QApplication) -> bool:
    """Return True if the user completed (or skipped) setup, False if they cancelled."""
    if not should_show_wizard():
        return True
    wiz = SetupWizard()
    code = wiz.exec()
    return code == QWizard.DialogCode.Accepted
