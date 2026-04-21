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
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from memex import config as cfg_mod
from memex.config import TIERS, Tier
from memex.embedder import set_gemini_key
from memex.mcp_config import server_snippet
from memex.paths import config_path, ensure_dirs, home


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resource_path(rel: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / rel
    return Path(__file__).resolve().parents[2] / rel


def _repolish(w: QWidget) -> None:
    w.style().unpolish(w)
    w.style().polish(w)


def ollama_exe_path() -> Path:
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "Programs" / "Ollama" / "ollama.exe"


def should_show_wizard() -> bool:
    return not config_path().exists()


def _h1(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("h1", True)
    return lbl


def _muted(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("muted", True)
    lbl.setWordWrap(True)
    return lbl


# ---------------------------------------------------------------------------
# Background download (Ollama installer) — QThread + httpx
# ---------------------------------------------------------------------------

class _DownloadWorker(QObject):
    progress = Signal(int, int)
    finished = Signal(str)
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
# Tier card
# ---------------------------------------------------------------------------

class _TierCard(QFrame):
    clicked = Signal(str)

    DESCRIPTIONS: dict[Tier, str] = {
        "small":  "Fastest setup, smallest disk. Great for code and short docs.",
        "medium": "Balanced — better recall on prose and longer files.",
        "large":  "Highest quality, biggest download. Best for nuanced search.",
    }

    def __init__(self, tier_key: Tier, tier, *, recommended: bool = False) -> None:
        super().__init__()
        self.tier_key = tier_key
        self.setObjectName("tierCard")
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(82)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(14)

        self.radio = QRadioButton()
        self.radio.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        outer.addWidget(self.radio, alignment=Qt.AlignmentFlag.AlignTop)

        body = QVBoxLayout()
        body.setSpacing(4)

        head = QHBoxLayout()
        head.setSpacing(10)
        name = QLabel(tier.label)
        nf = QFont()
        nf.setPointSize(11)
        nf.setWeight(QFont.Weight.DemiBold)
        name.setFont(nf)
        head.addWidget(name)
        if recommended:
            badge = QLabel("RECOMMENDED")
            badge.setProperty("badge", True)
            head.addWidget(badge)
        head.addStretch(1)
        meta = QLabel(f"~{tier.disk_mb} MB · dim {tier.dim}")
        meta.setProperty("muted", True)
        head.addWidget(meta)
        body.addLayout(head)

        desc = QLabel(self.DESCRIPTIONS.get(tier_key, ""))
        desc.setProperty("muted", True)
        desc.setWordWrap(True)
        body.addWidget(desc)

        outer.addLayout(body, stretch=1)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.tier_key)
        super().mousePressEvent(e)

    def setSelected(self, selected: bool) -> None:
        self.radio.setChecked(selected)
        self.setProperty("selected", selected)
        _repolish(self)


# ---------------------------------------------------------------------------
# Page bases
# ---------------------------------------------------------------------------

class _Page(QWizardPage):
    """Base wizard page that uses our own header instead of Qt's banner."""

    HEADING = "Page"
    SUBTITLE: str | None = None

    def __init__(self) -> None:
        super().__init__()
        # Empty Qt title so the wizard's own banner stays minimal.
        self.setTitle(" ")

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(8, 8, 8, 8)
        self._root.setSpacing(14)

        self._build_header()
        self.build_body(self._root)
        self._root.addStretch(1)

    def _build_header(self) -> None:
        self._root.addWidget(_h1(self.HEADING))
        if self.SUBTITLE:
            self._root.addWidget(_muted(self.SUBTITLE))

    def build_body(self, lay: QVBoxLayout) -> None:
        """Subclasses fill this in."""


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

class WelcomePage(_Page):
    HEADING = "Welcome to Memex"
    SUBTITLE = "Local semantic search for your codebases and documents."

    def _build_header(self) -> None:
        # Hero with icon on the left, title + subtitle on the right.
        hero = QHBoxLayout()
        hero.setSpacing(18)
        icon_path = _resource_path("assets/icon.png")
        if icon_path.exists():
            icon_lbl = QLabel()
            pix = QPixmap(str(icon_path)).scaled(
                88, 88,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            icon_lbl.setPixmap(pix)
            hero.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(_h1(self.HEADING))
        col.addWidget(_muted(self.SUBTITLE))
        hero.addLayout(col, stretch=1)
        self._root.addLayout(hero)

    def build_body(self, lay: QVBoxLayout) -> None:
        body = QLabel(
            "Memex indexes your files into vector embeddings on this PC, then "
            "exposes them over MCP so Claude (or any MCP client) can search them.\n\n"
            "This wizard will:\n"
            "    •  Pick an embedding model tier (Small / Medium / Large)\n"
            "    •  Optionally save a Gemini API key (cloud embeddings)\n"
            "    •  Install Ollama if you don't have it\n"
            "    •  Download the chosen embedding model\n"
            "    •  Show the MCP config snippet to paste into your client\n\n"
            "Click Next to begin."
        )
        body.setWordWrap(True)
        lay.addWidget(body)


class TierPage(_Page):
    HEADING = "Pick an embedding tier"
    SUBTITLE = (
        "You can switch tiers later in Settings. Switching across vector dims "
        "re-embeds existing chunks automatically."
    )

    def build_body(self, lay: QVBoxLayout) -> None:
        self._cards: dict[str, _TierCard] = {}
        for key in ("small", "medium", "large"):
            card = _TierCard(key, TIERS[key], recommended=(key == "small"))
            card.clicked.connect(self._on_card_clicked)
            lay.addWidget(card)
            self._cards[key] = card
        self._cards["small"].setSelected(True)

    def _on_card_clicked(self, tier_key: str) -> None:
        for k, c in self._cards.items():
            c.setSelected(k == tier_key)

    def selectedTier(self) -> str:
        for k, c in self._cards.items():
            if c.radio.isChecked():
                return k
        return "small"

    def validatePage(self) -> bool:
        self.wizard().setProperty("tier", self.selectedTier())
        return True


class KeyPage(_Page):
    HEADING = "Gemini API key"
    SUBTITLE = "Optional. Skip if you only want local models."

    def build_body(self, lay: QVBoxLayout) -> None:
        card = QFrame()
        card.setObjectName("tierCard")  # reuse the white card styling
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(10)

        label = QLabel("Paste a key to enable Gemini cloud embeddings.")
        cl.addWidget(label)

        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit.setPlaceholderText("Leave blank to skip")
        cl.addWidget(self.edit)

        note = _muted(
            "The key is stored in Windows Credential Manager (service: 'memex', "
            "user: 'gemini-api-key') and never written to disk. You can change "
            "or remove it anytime in Settings."
        )
        cl.addWidget(note)

        lay.addWidget(card)

    def validatePage(self) -> bool:
        key = self.edit.text().strip()
        if key:
            try:
                set_gemini_key(key)
            except Exception as e:
                QMessageBox.warning(self, "Key save failed", str(e))
                return False
        return True


class OllamaPage(_Page):
    HEADING = "Install Ollama"
    SUBTITLE = "Memex uses Ollama to run local embedding models."

    def build_body(self, lay: QVBoxLayout) -> None:
        card = QFrame()
        card.setObjectName("tierCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(12)

        self.status = QLabel("Checking…")
        sf = QFont()
        sf.setPointSize(11)
        self.status.setFont(sf)
        cl.addWidget(self.status)

        self.bar = QProgressBar()
        self.bar.setVisible(False)
        self.bar.setTextVisible(True)
        cl.addWidget(self.bar)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.install_btn = QPushButton("Install Ollama  (~1 GB)")
        self.install_btn.setProperty("primary", True)
        self.install_btn.clicked.connect(self._start_install)
        btn_row.addWidget(self.install_btn)
        cl.addLayout(btn_row)

        lay.addWidget(card)

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
            self.status.setText(f"✓  Ollama is installed.\n     {exe}")
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
        self.bar.setFormat("downloading…")
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
            mb = done / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            self.bar.setFormat(f"{mb:.0f} / {mb_total:.0f} MB")

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
        self.bar.setFormat("installing…")
        self._setup_proc = QProcess(self)
        self._setup_proc.finished.connect(self._on_setup_done)
        self._setup_proc.start(path, ["/SILENT"])

    def _on_setup_done(self, _code: int, _status: object) -> None:
        QTimer.singleShot(3000, self._check)


class PullPage(_Page):
    HEADING = "Downloading the embedding model"
    SUBTITLE = "Fetching the model. This takes a few minutes."

    def build_body(self, lay: QVBoxLayout) -> None:
        card = QFrame()
        card.setObjectName("tierCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(12)

        self.status_lbl = QLabel("Starting…")
        cl.addWidget(self.status_lbl)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(True)
        self.bar.setFormat("%p%")
        cl.addWidget(self.bar)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(180)
        self.log.setFont(QFont("Consolas", 9))
        cl.addWidget(self.log)

        lay.addWidget(card)

        self._done = False
        self._proc: QProcess | None = None
        self._model = "?"

    def isComplete(self) -> bool:
        return self._done

    def initializePage(self) -> None:
        tier_key = self.wizard().property("tier") or "small"
        ensure_dirs()
        cfg_mod.save(cfg_mod.Config.from_tier(tier_key))
        self._model = TIERS[tier_key].model

        self.status_lbl.setText(f"Pulling model: {self._model}")
        self.bar.setValue(0)
        self.bar.setFormat("%p%")
        self.log.clear()
        self._done = False
        self.completeChanged.emit()

        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyRead.connect(self._on_out)
        self._proc.finished.connect(self._on_done)
        self._proc.start(str(ollama_exe_path()), ["pull", self._model])

    def _on_out(self) -> None:
        assert self._proc is not None
        data = bytes(self._proc.readAll()).decode("utf-8", errors="replace")
        cleaned = data.replace("\r", "\n")
        cur = self.log.textCursor()
        cur.movePosition(cur.MoveOperation.End)
        self.log.setTextCursor(cur)
        self.log.insertPlainText(cleaned)
        m = list(re.finditer(r"(\d{1,3})%", data))
        if m:
            pct = max(0, min(100, int(m[-1].group(1))))
            self.bar.setValue(pct)

    def _on_done(self, code: int, _status: object) -> None:
        if code == 0:
            self.bar.setValue(100)
            self.status_lbl.setText(f"✓  {self._model} downloaded.")
        else:
            self.status_lbl.setText(f"ollama exited with code {code}")
            self.log.insertPlainText(f"\n[ollama exited with {code}]\n")
        self._done = True
        self.completeChanged.emit()


class DonePage(_Page):
    HEADING = "You're all set"
    SUBTITLE = "Add this to your MCP client (e.g. Claude Desktop), then restart it."

    def build_body(self, lay: QVBoxLayout) -> None:
        card = QFrame()
        card.setObjectName("tierCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(12)

        self.snippet = QTextEdit()
        self.snippet.setReadOnly(True)
        self.snippet.setFont(QFont("Consolas", 10))
        self.snippet.setMinimumHeight(180)
        cl.addWidget(self.snippet)

        row = QHBoxLayout()
        copy = QPushButton("Copy to clipboard")
        copy.setProperty("primary", True)
        copy.clicked.connect(self._copy)
        row.addWidget(copy)
        row.addStretch(1)
        cl.addLayout(row)

        lay.addWidget(card)

        lay.addWidget(_muted(
            "Click Finish to open Memex. Drag folders or files into a collection, "
            "then click Embed."
        ))

    def initializePage(self) -> None:
        cfg = cfg_mod.load()
        text = server_snippet(cfg)
        self.snippet.setPlainText(text)
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
        self.setOption(QWizard.WizardOption.NoCancelButtonOnLastPage, True)
        icon_path = _resource_path("assets/icon.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.addPage(WelcomePage())
        self.addPage(TierPage())
        self.addPage(KeyPage())
        self.addPage(OllamaPage())
        self.addPage(PullPage())
        self.addPage(DonePage())
        self.resize(820, 620)


def run_wizard_if_needed(parent_app: QApplication) -> bool:
    if not should_show_wizard():
        return True
    wiz = SetupWizard()
    code = wiz.exec()
    return code == QWizard.DialogCode.Accepted
