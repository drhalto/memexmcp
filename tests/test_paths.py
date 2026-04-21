from __future__ import annotations

import sys

from memex.paths import home


def test_home_uses_executable_dir_for_frozen_build(monkeypatch, tmp_path):
    exe = tmp_path / "Memex.exe"
    exe.write_text("", encoding="utf-8")

    monkeypatch.delenv("MEMEX_HOME", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))

    assert home() == tmp_path
