"""MemexMCP desktop GUI.

Layout:
- Left sidebar: collections list + "+ New".
- Main pane (tabs):
    - Sources: drop zone, source table, Embed / Remove buttons, progress bar.
    - Settings: tier radio, Gemini key, Ollama host, MCP config preview.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from memex import config as cfg_mod
from memex.config import TIERS
from memex.embedder import clear_gemini_key, gemini_key, get_embedder, set_gemini_key
from memex.gui_worker import run_embed
from memex.indexer import add_repo, rebuild_embeddings, remove_repo, suggest_repo_name
from memex.mcp_config import server_snippet
from memex.paths import collections_dir, ensure_dirs
from memex.store import open_db


DEFAULT_COLLECTION = "default"


def _resource_path(rel: str) -> Path:
    """Resolve a bundled resource both when frozen (_MEIPASS) and in dev."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / rel
    # In dev: repo_root/assets/... (this file lives at src/memex/gui.py)
    return Path(__file__).resolve().parents[2] / rel


def _app_icon() -> QIcon:
    png = _resource_path("assets/icon.png")
    if png.exists():
        return QIcon(str(png))
    return QIcon()


class DropZone(QFrame):
    """A visual drop target that emits a list of Paths."""

    def __init__(self, on_dropped) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumHeight(90)
        self.setStyleSheet(
            "QFrame { border: 2px dashed #888; border-radius: 8px; background: #fafafa; }"
        )
        self._on_dropped = on_dropped
        lay = QVBoxLayout(self)
        label = QLabel("Drop folders or files here  —  or click to browse")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont()
        f.setPointSize(11)
        label.setFont(f)
        lay.addWidget(label)

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent) -> None:
        paths = [Path(u.toLocalFile()) for u in e.mimeData().urls()]
        paths = [p for p in paths if p.exists()]
        if paths:
            self._on_dropped(paths)

    def mousePressEvent(self, _e) -> None:
        choice, ok = QInputDialog.getItem(
            self,
            "Add source",
            "Browse for:",
            ["Files", "Folder"],
            0,
            False,
        )
        if not ok:
            return
        if choice == "Folder":
            folder = QFileDialog.getExistingDirectory(self, "Choose folder")
            if folder:
                self._on_dropped([Path(folder)])
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose files")
        if paths:
            self._on_dropped([Path(p) for p in paths])


class CollectionView(QWidget):
    """The 'Sources' tab for one collection."""

    def __init__(self, main: "MainWindow") -> None:
        super().__init__()
        self._main = main
        self._thread: QThread | None = None
        self._worker = None

        lay = QVBoxLayout(self)

        self.collection_label = QLabel("Collection: —")
        f = QFont()
        f.setBold(True)
        f.setPointSize(12)
        self.collection_label.setFont(f)
        lay.addWidget(self.collection_label)

        self.drop = DropZone(self._on_paths_dropped)
        lay.addWidget(self.drop)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Path", "Files", "Chunks"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(1, self.table.horizontalHeader().ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        lay.addWidget(self.table, stretch=1)

        btn_row = QHBoxLayout()
        self.embed_btn = QPushButton("Embed")
        self.embed_btn.clicked.connect(self._on_embed_clicked)
        self.remove_btn = QPushButton("Remove selected")
        self.remove_btn.clicked.connect(self._on_remove_clicked)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.cancel_btn.setEnabled(False)
        btn_row.addWidget(self.embed_btn)
        btn_row.addWidget(self.remove_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        lay.addWidget(self.progress)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #666;")
        lay.addWidget(self.status)

    def set_collection(self, name: str) -> None:
        self._current_collection = name
        self.collection_label.setText(f"Collection: {name}")
        self.refresh_sources()

    def refresh_sources(self) -> None:
        conn = open_db()
        rows = conn.execute(
            "SELECT r.name, r.path, "
            " (SELECT COUNT(*) FROM files WHERE repo_id = r.id) AS n_files, "
            " (SELECT COUNT(*) FROM chunks c JOIN files f ON c.file_id = f.id WHERE f.repo_id = r.id) AS n_chunks "
            "FROM repos r WHERE r.collection = ? ORDER BY r.name",
            (self._current_collection,),
        ).fetchall()
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(r["name"]))
            self.table.setItem(i, 1, QTableWidgetItem(r["path"]))
            self.table.setItem(i, 2, QTableWidgetItem(str(r["n_files"])))
            self.table.setItem(i, 3, QTableWidgetItem(str(r["n_chunks"])))

    def _on_paths_dropped(self, paths: list[Path]) -> None:
        conn = open_db()
        added = 0
        for p in paths:
            name = suggest_repo_name(conn, p)
            add_repo(conn, name, p, collection=self._current_collection)
            added += 1
        self.status.setText(f"registered {added} source(s)")
        self.refresh_sources()

    def _selected_repo_ids(self) -> list[tuple[int, str]]:
        conn = open_db()
        if self.table.selectionModel().hasSelection():
            names = [
                self.table.item(r.row(), 0).text()
                for r in self.table.selectionModel().selectedRows()
            ]
        else:
            names = [self.table.item(i, 0).text() for i in range(self.table.rowCount())]
        if not names:
            return []
        placeholders = ",".join("?" * len(names))
        rows = conn.execute(
            f"SELECT id, name FROM repos WHERE collection = ? AND name IN ({placeholders})",
            (self._current_collection, *names),
        ).fetchall()
        return [(r["id"], r["name"]) for r in rows]

    def _on_embed_clicked(self) -> None:
        targets = self._selected_repo_ids()
        if not targets:
            self.status.setText("no sources to embed")
            return
        self.embed_btn.setEnabled(False)
        self.remove_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setValue(0)
        self.progress.setMaximum(100)
        self.status.setText("starting…")

        thread, worker = run_embed(self, targets)
        worker.progress.connect(self._on_progress)
        worker.repo_done.connect(self._on_repo_done)
        worker.all_done.connect(self._on_all_done)
        worker.error.connect(self._on_error)
        self._thread = thread
        self._worker = worker
        thread.start()

    def _on_progress(self, done: int, total: int, current: str) -> None:
        if total > 0:
            self.progress.setMaximum(total)
            self.progress.setValue(done)
        self.status.setText(f"{done}/{total}  {current}")

    def _on_repo_done(self, name: str, summary: str) -> None:
        self.status.setText(f"{name}: {summary}")

    def _on_all_done(self) -> None:
        self.embed_btn.setEnabled(True)
        self.remove_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.refresh_sources()
        if self.progress.maximum() > 0:
            self.progress.setValue(self.progress.maximum())

    def _on_error(self, msg: str) -> None:
        self.status.setText(f"error: {msg}")

    def _on_cancel(self) -> None:
        if self._worker:
            self._worker.cancel()
            self.status.setText("cancelling…")

    def _on_remove_clicked(self) -> None:
        if not self.table.selectionModel().hasSelection():
            return
        conn = open_db()
        names = [
            self.table.item(r.row(), 0).text()
            for r in self.table.selectionModel().selectedRows()
        ]
        if QMessageBox.question(self, "Remove", f"Remove {len(names)} source(s) and all indexed content?") \
                != QMessageBox.StandardButton.Yes:
            return
        for n in names:
            remove_repo(conn, n)
        self.status.setText(f"removed {len(names)}")
        self.refresh_sources()


class SettingsView(QWidget):
    def __init__(self, main: "MainWindow") -> None:
        super().__init__()
        self._main = main
        cfg = cfg_mod.load()

        lay = QVBoxLayout(self)

        # Tier selection
        tier_group = QGroupBox("Embedding tier")
        tier_lay = QVBoxLayout(tier_group)
        self._tier_radios: dict[str, QRadioButton] = {}
        for tier_key, t in TIERS.items():
            rb = QRadioButton(f"{t.label}   (dim {t.dim}, ~{t.disk_mb} MB)" if t.disk_mb else f"{t.label}   (dim {t.dim}, cloud)")
            rb.setChecked(cfg.tier == tier_key)
            if tier_key == "gemini" and not gemini_key():
                rb.setEnabled(False)
                rb.setToolTip("Set a Gemini API key below to enable.")
            tier_lay.addWidget(rb)
            self._tier_radios[tier_key] = rb
        self.apply_tier_btn = QPushButton("Apply tier")
        self.apply_tier_btn.clicked.connect(self._on_apply_tier)
        tier_lay.addWidget(self.apply_tier_btn)
        lay.addWidget(tier_group)

        # Gemini key
        key_group = QGroupBox("Gemini API key (stored in Windows Credential Manager)")
        key_lay = QHBoxLayout(key_group)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("paste key to save" if not gemini_key() else "••• stored •••")
        self.key_save_btn = QPushButton("Save")
        self.key_save_btn.clicked.connect(self._on_save_key)
        self.key_clear_btn = QPushButton("Clear")
        self.key_clear_btn.clicked.connect(self._on_clear_key)
        key_lay.addWidget(self.key_edit, stretch=1)
        key_lay.addWidget(self.key_save_btn)
        key_lay.addWidget(self.key_clear_btn)
        lay.addWidget(key_group)

        # Ollama host
        host_group = QGroupBox("Ollama host")
        host_lay = QHBoxLayout(host_group)
        self.host_edit = QLineEdit(cfg.ollama_host)
        self.host_save_btn = QPushButton("Save")
        self.host_save_btn.clicked.connect(self._on_save_host)
        host_lay.addWidget(self.host_edit, stretch=1)
        host_lay.addWidget(self.host_save_btn)
        lay.addWidget(host_group)

        # MCP config preview
        mcp_group = QGroupBox("MCP client configuration (copy into your MCP client)")
        mcp_lay = QVBoxLayout(mcp_group)
        self.mcp_preview = QTextEdit()
        self.mcp_preview.setReadOnly(True)
        self.mcp_preview.setFont(QFont("Consolas", 10))
        self.mcp_preview.setPlainText(self._mcp_snippet())
        copy_btn = QPushButton("Copy to clipboard")
        copy_btn.clicked.connect(self._on_copy_mcp)
        mcp_lay.addWidget(self.mcp_preview)
        mcp_lay.addWidget(copy_btn)
        lay.addWidget(mcp_group)

        lay.addStretch(1)

    def _mcp_snippet(self) -> str:
        cfg = cfg_mod.load()
        return server_snippet(cfg)

    def _selected_tier(self) -> str | None:
        for k, rb in self._tier_radios.items():
            if rb.isChecked():
                return k
        return None

    def _on_apply_tier(self) -> None:
        tier = self._selected_tier()
        if not tier:
            return
        cfg = cfg_mod.load()
        t = TIERS[tier]
        if cfg.tier == tier:
            QMessageBox.information(self, "Tier", "Already on this tier.")
            return
        new_cfg = cfg_mod.Config.from_tier(tier, ollama_host=cfg.ollama_host)
        dim_change = cfg.dim != new_cfg.dim
        if dim_change:
            conn = open_db(dim=cfg.dim)
            n = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            if n > 0:
                if QMessageBox.question(
                    self, "Re-embed required",
                    f"Switching to {t.label} changes dim {cfg.dim} -> {new_cfg.dim}.\n"
                    f"Re-embed {n} chunks now?",
                ) != QMessageBox.StandardButton.Yes:
                    return
            try:
                total = rebuild_embeddings(conn, new_cfg.dim, embedder=get_embedder(new_cfg))
            except Exception as e:
                QMessageBox.warning(self, "Tier switch failed", str(e))
                return
            cfg_mod.save(new_cfg)
            QMessageBox.information(self, "Tier", f"Switched to {t.label}. Re-embedded {total} chunks.")
        else:
            cfg_mod.save(new_cfg)
            QMessageBox.information(self, "Tier", f"Switched to {t.label}.")
        self.mcp_preview.setPlainText(self._mcp_snippet())

    def _on_save_key(self) -> None:
        key = self.key_edit.text().strip()
        if not key:
            return
        set_gemini_key(key)
        self.key_edit.clear()
        self.key_edit.setPlaceholderText("••• stored •••")
        self._tier_radios["gemini"].setEnabled(True)
        self._tier_radios["gemini"].setToolTip("")
        QMessageBox.information(self, "Key saved", "Gemini key stored in Windows Credential Manager.")

    def _on_clear_key(self) -> None:
        clear_gemini_key()
        self.key_edit.clear()
        self.key_edit.setPlaceholderText("paste key to save")
        self._tier_radios["gemini"].setEnabled(False)
        self._tier_radios["gemini"].setToolTip("Set a Gemini API key to enable.")
        QMessageBox.information(self, "Key cleared", "Gemini key removed.")

    def _on_save_host(self) -> None:
        cfg = cfg_mod.load()
        cfg.ollama_host = self.host_edit.text().strip() or "http://localhost:11434"
        cfg_mod.save(cfg)
        self.mcp_preview.setPlainText(self._mcp_snippet())

    def _on_copy_mcp(self) -> None:
        QApplication.clipboard().setText(self.mcp_preview.toPlainText())


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Memex")
        self.setWindowIcon(_app_icon())
        self.resize(1100, 720)

        ensure_dirs()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)

        # Sidebar
        side = QWidget()
        side_lay = QVBoxLayout(side)
        side_lay.addWidget(QLabel("Collections"))
        self.collection_list = QListWidget()
        self.collection_list.currentItemChanged.connect(self._on_collection_changed)
        side_lay.addWidget(self.collection_list, stretch=1)
        new_btn = QPushButton("+ New collection")
        new_btn.clicked.connect(self._on_new_collection)
        side_lay.addWidget(new_btn)
        splitter.addWidget(side)

        # Main tabs
        self.tabs = QTabWidget()
        self.sources_view = CollectionView(self)
        self.settings_view = SettingsView(self)
        self.tabs.addTab(self.sources_view, "Sources")
        self.tabs.addTab(self.settings_view, "Settings")
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 880])

        self._populate_collections()

    def _populate_collections(self) -> None:
        # Collections = (existing in DB) ∪ (subdirs of collections/) ∪ {default}.
        conn = open_db()
        names: set[str] = {DEFAULT_COLLECTION}
        for r in conn.execute("SELECT DISTINCT collection FROM repos").fetchall():
            names.add(r["collection"])
        cdir = collections_dir()
        if cdir.exists():
            for p in cdir.iterdir():
                if p.is_dir():
                    names.add(p.name)
        self.collection_list.clear()
        for n in sorted(names):
            self.collection_list.addItem(QListWidgetItem(n))
        if self.collection_list.count() > 0:
            self.collection_list.setCurrentRow(0)

    def _on_collection_changed(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None:
            return
        self.sources_view.set_collection(current.text())

    def _on_new_collection(self) -> None:
        name, ok = QInputDialog.getText(self, "New collection", "Name:")
        if not ok or not name.strip():
            return
        clean = name.strip().replace(" ", "-").lower()
        (collections_dir() / clean).mkdir(parents=True, exist_ok=True)
        self._populate_collections()
        # Select the new one.
        for i in range(self.collection_list.count()):
            if self.collection_list.item(i).text() == clean:
                self.collection_list.setCurrentRow(i)
                break


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Memex")
    app.setWindowIcon(_app_icon())

    # First-launch setup. If the user cancels, exit without opening the main window.
    from memex.setup_wizard import run_wizard_if_needed
    if not run_wizard_if_needed(app):
        return 0

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
