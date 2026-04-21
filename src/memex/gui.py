"""Memex desktop GUI.

Layout:
- Left sidebar: collections list + "+ New".
- Main pane (tabs):
    - Sources: drop zone, source table, Embed / Remove buttons, progress bar.
    - Settings: tier cards, Gemini key, Ollama host, MCP config preview.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
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
    QSizePolicy,
    QSplitter,
    QStackedLayout,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from memex import config as cfg_mod
from memex.config import TIERS, Tier
from memex.embedder import clear_gemini_key, gemini_key, get_embedder, set_gemini_key
from memex.gui_worker import run_embed
from memex.indexer import add_repo, rebuild_embeddings, remove_repo, suggest_repo_name
from memex.mcp_config import server_snippet
from memex.paths import collections_dir, ensure_dirs
from memex.store import open_db
from memex.style import apply_style


DEFAULT_COLLECTION = "default"


def _resource_path(rel: str) -> Path:
    """Resolve a bundled resource both when frozen (_MEIPASS) and in dev."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / rel
    return Path(__file__).resolve().parents[2] / rel


def _app_icon() -> QIcon:
    png = _resource_path("assets/icon.png")
    if png.exists():
        return QIcon(str(png))
    return QIcon()


def _repolish(w: QWidget) -> None:
    """Re-apply QSS after toggling a dynamic property like primary/selected."""
    w.style().unpolish(w)
    w.style().polish(w)


# ---------------------------------------------------------------------------
# DropZone
# ---------------------------------------------------------------------------

class DropZone(QFrame):
    """Visual drop target. Click to browse; drop folders or files to add."""

    def __init__(self, on_dropped) -> None:
        super().__init__()
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setProperty("hover", False)
        self._on_dropped = on_dropped

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(4)

        title = QLabel("Drop folders or files here")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont()
        f.setPointSize(13)
        f.setWeight(QFont.Weight.DemiBold)
        title.setFont(f)
        lay.addWidget(title)

        sub = QLabel("…or click to browse. Code, Markdown, PDF, DOCX, HTML.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setProperty("muted", True)
        lay.addWidget(sub)

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.setProperty("hover", True)
            _repolish(self)

    def dragLeaveEvent(self, _e) -> None:
        self.setProperty("hover", False)
        _repolish(self)

    def dropEvent(self, e: QDropEvent) -> None:
        self.setProperty("hover", False)
        _repolish(self)
        paths = [Path(u.toLocalFile()) for u in e.mimeData().urls()]
        paths = [p for p in paths if p.exists()]
        if paths:
            self._on_dropped(paths)

    def mousePressEvent(self, _e) -> None:
        choice, ok = QInputDialog.getItem(
            self, "Add source", "Browse for:", ["Folder", "Files"], 0, False,
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


# ---------------------------------------------------------------------------
# CollectionView (the Sources tab)
# ---------------------------------------------------------------------------

class CollectionView(QWidget):
    status_message = Signal(str)

    def __init__(self, main: "MainWindow") -> None:
        super().__init__()
        self._main = main
        self._thread: QThread | None = None
        self._worker = None
        self._current_collection = DEFAULT_COLLECTION

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 14)
        lay.setSpacing(14)

        # Header row: collection name + small subtitle
        hdr_row = QHBoxLayout()
        self.collection_label = QLabel("default")
        f = QFont()
        f.setPointSize(16)
        f.setWeight(QFont.Weight.DemiBold)
        self.collection_label.setFont(f)
        hdr_row.addWidget(self.collection_label)
        hdr_row.addStretch(1)
        self.count_label = QLabel("")
        self.count_label.setProperty("muted", True)
        hdr_row.addWidget(self.count_label)
        lay.addLayout(hdr_row)

        # Drop zone
        self.drop = DropZone(self._on_paths_dropped)
        lay.addWidget(self.drop)

        # Sources table — wrapped in a QStackedLayout so we can show an
        # empty state without the gridlines screaming at first launch.
        self.table_stack = QWidget()
        stack = QStackedLayout(self.table_stack)
        stack.setContentsMargins(0, 0, 0, 0)

        self.empty = QLabel(
            "No sources in this collection yet.\nDrop a folder above to get started."
        )
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setProperty("muted", True)
        empty_f = QFont()
        empty_f.setPointSize(11)
        self.empty.setFont(empty_f)
        self.empty.setMinimumHeight(180)
        self.empty.setStyleSheet(
            "background:#fff; border:1px solid #e2e5ea; border-radius:8px;"
        )
        stack.addWidget(self.empty)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Path", "Files", "Chunks"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(34)
        stack.addWidget(self.table)

        lay.addWidget(self.table_stack, stretch=1)

        # Action row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.embed_btn = QPushButton("Embed all")
        self.embed_btn.setProperty("primary", True)
        self.embed_btn.clicked.connect(self._on_embed_clicked)
        self.remove_btn = QPushButton("Remove selected")
        self.remove_btn.setProperty("danger", True)
        self.remove_btn.clicked.connect(self._on_remove_clicked)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.cancel_btn.setEnabled(False)
        btn_row.addWidget(self.embed_btn)
        btn_row.addWidget(self.remove_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.cancel_btn)
        lay.addLayout(btn_row)

        # Progress
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")
        self.progress.setVisible(False)
        lay.addWidget(self.progress)

    # --- selection helpers ----------------------------------------------------

    def set_collection(self, name: str) -> None:
        self._current_collection = name
        self.collection_label.setText(name)
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
        total_files = total_chunks = 0
        for i, r in enumerate(rows):
            name_item = QTableWidgetItem(r["name"])
            path_item = QTableWidgetItem(r["path"])
            path_item.setToolTip(r["path"])
            files_item = QTableWidgetItem(f"{r['n_files']:,}")
            files_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            chunks_item = QTableWidgetItem(f"{r['n_chunks']:,}")
            chunks_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, path_item)
            self.table.setItem(i, 2, files_item)
            self.table.setItem(i, 3, chunks_item)
            total_files += r["n_files"]
            total_chunks += r["n_chunks"]

        # Empty state vs table
        stack: QStackedLayout = self.table_stack.layout()  # type: ignore[assignment]
        stack.setCurrentIndex(1 if rows else 0)

        # Header counts
        if rows:
            self.count_label.setText(
                f"{len(rows)} source{'s' if len(rows) != 1 else ''}  •  "
                f"{total_files:,} files  •  {total_chunks:,} chunks"
            )
        else:
            self.count_label.setText("empty collection")

    def _on_paths_dropped(self, paths: list[Path]) -> None:
        conn = open_db()
        added = 0
        for p in paths:
            name = suggest_repo_name(conn, p)
            add_repo(conn, name, p, collection=self._current_collection)
            added += 1
        self.status_message.emit(f"Added {added} source{'s' if added != 1 else ''} to '{self._current_collection}'")
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
            self.status_message.emit("No sources to embed — drop a folder first.")
            return
        self.embed_btn.setEnabled(False)
        self.remove_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.progress.setMaximum(100)
        self.progress.setFormat("starting…")
        self.status_message.emit("Embedding…")

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
        # Trim very long paths in the format string
        short = current
        if len(short) > 60:
            short = "…" + short[-57:]
        self.progress.setFormat(f"{done}/{total}  {short}")

    def _on_repo_done(self, name: str, summary: str) -> None:
        self.status_message.emit(f"{name} → {summary}")

    def _on_all_done(self) -> None:
        self.embed_btn.setEnabled(True)
        self.remove_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.refresh_sources()
        self.progress.setFormat("done")
        if self.progress.maximum() > 0:
            self.progress.setValue(self.progress.maximum())
        # Auto-hide the bar a beat after success
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2500, lambda: self.progress.setVisible(False))

    def _on_error(self, msg: str) -> None:
        self.status_message.emit(f"Error: {msg}")
        self.progress.setFormat("error")

    def _on_cancel(self) -> None:
        if self._worker:
            self._worker.cancel()
            self.status_message.emit("Cancelling…")

    def _on_remove_clicked(self) -> None:
        if not self.table.selectionModel().hasSelection():
            self.status_message.emit("Select sources first, then click Remove selected.")
            return
        conn = open_db()
        names = [
            self.table.item(r.row(), 0).text()
            for r in self.table.selectionModel().selectedRows()
        ]
        if QMessageBox.question(
            self, "Remove sources",
            f"Remove {len(names)} source{'s' if len(names) != 1 else ''} and all indexed content?\nThis cannot be undone.",
        ) != QMessageBox.StandardButton.Yes:
            return
        for n in names:
            remove_repo(conn, n)
        self.status_message.emit(f"Removed {len(names)} source{'s' if len(names) != 1 else ''}")
        self.refresh_sources()


# ---------------------------------------------------------------------------
# Tier cards (used in Settings — and a similar widget in the wizard)
# ---------------------------------------------------------------------------

class TierCard(QFrame):
    """A clickable card showing a tier's name, size, dim, and one-line description."""

    clicked = Signal(str)

    DESCRIPTIONS: dict[Tier, str] = {
        "small":  "Fastest setup, smallest disk. Great for code and short docs.",
        "medium": "Balanced — better recall on prose and longer files.",
        "large":  "Highest quality, biggest download. Best for nuanced search across mixed content.",
        "gemini": "Cloud embeddings via Google Gemini. Requires an API key.",
    }

    def __init__(self, tier_key: Tier, tier, *, recommended: bool = False) -> None:
        super().__init__()
        self.tier_key = tier_key
        self.setObjectName("tierCard")
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(12)

        self.radio = QRadioButton()
        self.radio.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        outer.addWidget(self.radio, alignment=Qt.AlignmentFlag.AlignTop)

        body = QVBoxLayout()
        body.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        name = QLabel(tier.label)
        nf = QFont()
        nf.setPointSize(11)
        nf.setWeight(QFont.Weight.DemiBold)
        name.setFont(nf)
        title_row.addWidget(name)
        if recommended:
            badge = QLabel("RECOMMENDED")
            badge.setProperty("badge", True)
            title_row.addWidget(badge)
        title_row.addStretch(1)
        meta = QLabel(
            f"~{tier.disk_mb} MB · dim {tier.dim}" if tier.disk_mb else f"cloud · dim {tier.dim}"
        )
        meta.setProperty("muted", True)
        title_row.addWidget(meta)
        body.addLayout(title_row)

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
# Settings
# ---------------------------------------------------------------------------

class SettingsView(QWidget):
    status_message = Signal(str)

    def __init__(self, main: "MainWindow") -> None:
        super().__init__()
        self._main = main
        cfg = cfg_mod.load()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(16)

        # ---- Tier cards ----
        tier_group = QGroupBox("Embedding tier")
        tier_lay = QVBoxLayout(tier_group)
        tier_lay.setSpacing(8)

        self._cards: dict[str, TierCard] = {}
        for tier_key, t in TIERS.items():
            card = TierCard(tier_key, t, recommended=(tier_key == "small"))
            card.clicked.connect(self._on_card_clicked)
            if tier_key == "gemini" and not gemini_key():
                card.setEnabled(False)
                card.setToolTip("Set a Gemini API key below to enable.")
            tier_lay.addWidget(card)
            self._cards[tier_key] = card
        self._set_selected_card(cfg.tier)

        apply_row = QHBoxLayout()
        apply_row.addStretch(1)
        self.apply_tier_btn = QPushButton("Apply tier")
        self.apply_tier_btn.setProperty("primary", True)
        self.apply_tier_btn.clicked.connect(self._on_apply_tier)
        apply_row.addWidget(self.apply_tier_btn)
        tier_lay.addLayout(apply_row)
        outer.addWidget(tier_group)

        # ---- Gemini key ----
        key_group = QGroupBox("Gemini API key  (stored in Windows Credential Manager)")
        key_lay = QHBoxLayout(key_group)
        key_lay.setSpacing(8)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText(
            "••• stored •••" if gemini_key() else "Paste key to save"
        )
        self.key_save_btn = QPushButton("Save")
        self.key_save_btn.setProperty("primary", True)
        self.key_save_btn.clicked.connect(self._on_save_key)
        self.key_clear_btn = QPushButton("Clear")
        self.key_clear_btn.clicked.connect(self._on_clear_key)
        key_lay.addWidget(self.key_edit, stretch=1)
        key_lay.addWidget(self.key_save_btn)
        key_lay.addWidget(self.key_clear_btn)
        outer.addWidget(key_group)

        # ---- Ollama host ----
        host_group = QGroupBox("Ollama host")
        host_lay = QHBoxLayout(host_group)
        host_lay.setSpacing(8)
        self.host_edit = QLineEdit(cfg.ollama_host)
        self.host_save_btn = QPushButton("Save")
        self.host_save_btn.setProperty("primary", True)
        self.host_save_btn.clicked.connect(self._on_save_host)
        host_lay.addWidget(self.host_edit, stretch=1)
        host_lay.addWidget(self.host_save_btn)
        outer.addWidget(host_group)

        # ---- MCP config preview ----
        mcp_group = QGroupBox("MCP client configuration")
        mcp_lay = QVBoxLayout(mcp_group)
        mcp_lay.setSpacing(8)
        hint = QLabel("Paste this into Claude Desktop's claude_desktop_config.json, then restart Claude.")
        hint.setProperty("muted", True)
        hint.setWordWrap(True)
        mcp_lay.addWidget(hint)
        self.mcp_preview = QTextEdit()
        self.mcp_preview.setReadOnly(True)
        self.mcp_preview.setFont(QFont("Consolas", 10))
        self.mcp_preview.setPlainText(server_snippet(cfg))
        self.mcp_preview.setMinimumHeight(160)
        mcp_lay.addWidget(self.mcp_preview)
        copy_row = QHBoxLayout()
        copy_row.addStretch(1)
        copy_btn = QPushButton("Copy to clipboard")
        copy_btn.setProperty("primary", True)
        copy_btn.clicked.connect(self._on_copy_mcp)
        copy_row.addWidget(copy_btn)
        mcp_lay.addLayout(copy_row)
        outer.addWidget(mcp_group)

        outer.addStretch(1)

    # --- helpers --------------------------------------------------------------

    def _selected_tier(self) -> str | None:
        for k, card in self._cards.items():
            if card.radio.isChecked():
                return k
        return None

    def _set_selected_card(self, tier: str) -> None:
        for k, card in self._cards.items():
            card.setSelected(k == tier)

    def _on_card_clicked(self, tier_key: str) -> None:
        if not self._cards[tier_key].isEnabled():
            return
        self._set_selected_card(tier_key)

    def _refresh_mcp(self) -> None:
        self.mcp_preview.setPlainText(server_snippet(cfg_mod.load()))

    # --- actions --------------------------------------------------------------

    def _on_apply_tier(self) -> None:
        tier = self._selected_tier()
        if not tier:
            return
        cfg = cfg_mod.load()
        t = TIERS[tier]
        if cfg.tier == tier:
            self.status_message.emit("Already on this tier.")
            return
        new_cfg = cfg_mod.Config.from_tier(tier, ollama_host=cfg.ollama_host)
        dim_change = cfg.dim != new_cfg.dim
        if dim_change:
            conn = open_db(dim=cfg.dim)
            n = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            if n > 0:
                if QMessageBox.question(
                    self, "Re-embed required",
                    f"Switching to {t.label} changes vector dim {cfg.dim} → {new_cfg.dim}.\n"
                    f"Re-embed {n:,} chunks now?",
                ) != QMessageBox.StandardButton.Yes:
                    return
            try:
                total = rebuild_embeddings(conn, new_cfg.dim, embedder=get_embedder(new_cfg))
            except Exception as e:
                QMessageBox.warning(self, "Tier switch failed", str(e))
                return
            cfg_mod.save(new_cfg)
            self.status_message.emit(f"Switched to {t.label}. Re-embedded {total:,} chunks.")
        else:
            cfg_mod.save(new_cfg)
            self.status_message.emit(f"Switched to {t.label}.")
        self._refresh_mcp()

    def _on_save_key(self) -> None:
        key = self.key_edit.text().strip()
        if not key:
            return
        set_gemini_key(key)
        self.key_edit.clear()
        self.key_edit.setPlaceholderText("••• stored •••")
        gem_card = self._cards.get("gemini")
        if gem_card is not None:
            gem_card.setEnabled(True)
            gem_card.setToolTip("")
        self.status_message.emit("Gemini key saved to Windows Credential Manager.")

    def _on_clear_key(self) -> None:
        clear_gemini_key()
        self.key_edit.clear()
        self.key_edit.setPlaceholderText("Paste key to save")
        gem_card = self._cards.get("gemini")
        if gem_card is not None:
            gem_card.setEnabled(False)
            gem_card.setToolTip("Set a Gemini API key to enable.")
        self.status_message.emit("Gemini key removed.")

    def _on_save_host(self) -> None:
        cfg = cfg_mod.load()
        cfg.ollama_host = self.host_edit.text().strip() or "http://localhost:11434"
        cfg_mod.save(cfg)
        self._refresh_mcp()
        self.status_message.emit("Ollama host saved.")

    def _on_copy_mcp(self) -> None:
        QApplication.clipboard().setText(self.mcp_preview.toPlainText())
        self.status_message.emit("MCP config copied to clipboard.")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

class Sidebar(QWidget):
    new_collection_requested = Signal()
    collection_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 8, 14)
        lay.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        title = QLabel("Collections")
        f = QFont()
        f.setPointSize(11)
        f.setWeight(QFont.Weight.DemiBold)
        title.setFont(f)
        hdr.addWidget(title)
        hdr.addStretch(1)
        lay.addLayout(hdr)

        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._on_changed)
        lay.addWidget(self.list, stretch=1)

        self.new_btn = QPushButton("+ New collection")
        self.new_btn.clicked.connect(self.new_collection_requested.emit)
        lay.addWidget(self.new_btn)

    def populate(self, names: list[str], select: str | None = None) -> None:
        prev = select or (self.list.currentItem().text() if self.list.currentItem() else None)
        self.list.blockSignals(True)
        self.list.clear()
        for n in names:
            self.list.addItem(QListWidgetItem(n))
        # Restore selection if possible.
        target = prev if prev in names else (names[0] if names else None)
        if target is not None:
            for i in range(self.list.count()):
                if self.list.item(i).text() == target:
                    self.list.setCurrentRow(i)
                    break
        self.list.blockSignals(False)
        if target is not None:
            self.collection_changed.emit(target)

    def _on_changed(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None:
            return
        self.collection_changed.emit(current.text())


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Memex")
        self.setWindowIcon(_app_icon())
        self.resize(1180, 760)
        self.setMinimumSize(900, 600)

        ensure_dirs()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)

        self.sidebar = Sidebar()
        self.sidebar.collection_changed.connect(self._on_collection_changed)
        self.sidebar.new_collection_requested.connect(self._on_new_collection)
        splitter.addWidget(self.sidebar)

        self.tabs = QTabWidget()
        self.sources_view = CollectionView(self)
        self.settings_view = SettingsView(self)
        self.tabs.addTab(self.sources_view, "  Sources  ")
        self.tabs.addTab(self.settings_view, "  Settings  ")
        splitter.addWidget(self.tabs)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 940])
        splitter.setHandleWidth(1)

        # Status bar — single source of truth for transient feedback.
        self.setStatusBar(QStatusBar())
        self.sources_view.status_message.connect(self._show_status)
        self.settings_view.status_message.connect(self._show_status)

        self._populate_collections()

    def _show_status(self, msg: str) -> None:
        self.statusBar().showMessage(msg, 6000)

    def _populate_collections(self) -> None:
        conn = open_db()
        names: set[str] = {DEFAULT_COLLECTION}
        for r in conn.execute("SELECT DISTINCT collection FROM repos").fetchall():
            names.add(r["collection"])
        cdir = collections_dir()
        if cdir.exists():
            for p in cdir.iterdir():
                if p.is_dir():
                    names.add(p.name)
        self.sidebar.populate(sorted(names))

    def _on_collection_changed(self, name: str) -> None:
        self.sources_view.set_collection(name)

    def _on_new_collection(self) -> None:
        name, ok = QInputDialog.getText(self, "New collection", "Name:")
        if not ok or not name.strip():
            return
        clean = name.strip().replace(" ", "-").lower()
        (collections_dir() / clean).mkdir(parents=True, exist_ok=True)
        self._populate_collections()
        # Find + select the new one
        for i in range(self.sidebar.list.count()):
            if self.sidebar.list.item(i).text() == clean:
                self.sidebar.list.setCurrentRow(i)
                break
        self._show_status(f"Created collection '{clean}'.")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Memex")
    app.setWindowIcon(_app_icon())
    apply_style(app)

    # First-launch setup. If the user cancels, exit without opening the main window.
    from memex.setup_wizard import run_wizard_if_needed
    if not run_wizard_if_needed(app):
        return 0

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
