"""QThread worker that runs sync_repo off the UI thread."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from memex.embedder import EmbedError, get_embedder
from memex.indexer import sync_repo
from memex.store import open_db


class EmbedWorker(QObject):
    progress = Signal(int, int, str)    # done, total, current file
    repo_done = Signal(str, str)        # repo name, stats string
    all_done = Signal()
    error = Signal(str)

    def __init__(self, repo_ids_and_names: list[tuple[int, str]]) -> None:
        super().__init__()
        self._targets = list(repo_ids_and_names)
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            conn = open_db()
            embedder = get_embedder()
        except EmbedError as e:
            self.error.emit(str(e))
            self.all_done.emit()
            return
        except Exception as e:  # sqlite-vec load failure, dim mismatch, etc
            self.error.emit(f"startup: {e}")
            self.all_done.emit()
            return

        try:
            for repo_id, name in self._targets:
                if self._cancel:
                    break
                try:
                    def cb(done: int, total: int, current: str, _n=name) -> None:
                        self.progress.emit(done, total, f"{_n}: {current}")
                    stats = sync_repo(conn, repo_id, embedder=embedder, progress_cb=cb)
                    summary = (
                        f"indexed={stats.files_indexed} unchanged={stats.files_unchanged} "
                        f"skipped={stats.files_skipped} chunks={stats.chunks_written}"
                    )
                    self.repo_done.emit(name, summary)
                except Exception as e:
                    self.error.emit(f"{name}: {e}")
        finally:
            try:
                embedder.close()
            except Exception:
                pass
            self.all_done.emit()


def run_embed(parent: QObject, targets: list[tuple[int, str]]) -> tuple[QThread, EmbedWorker]:
    """Spin up a QThread + EmbedWorker. Caller wires up signals and keeps refs."""
    thread = QThread(parent)
    worker = EmbedWorker(targets)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.all_done.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)
    return thread, worker
