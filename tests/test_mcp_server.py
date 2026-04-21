from __future__ import annotations

from memex.mcp_server import ref_file
from memex.store import open_db


def test_ref_file_falls_back_to_indexed_content_for_binary_docs(monkeypatch, tmp_path):
    monkeypatch.setenv("MEMEX_HOME", str(tmp_path / "memex-home"))
    conn = open_db()

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pdf_path = repo_root / "guide.pdf"
    pdf_path.write_bytes(b"%PDF-\xff")

    repo_id = conn.execute(
        "INSERT INTO repos (name, path, collection) VALUES (?, ?, ?)",
        ("repo", str(repo_root), "default"),
    ).lastrowid
    file_id = conn.execute(
        "INSERT INTO files (repo_id, rel_path, sha256, language, loc) VALUES (?, ?, ?, ?, ?)",
        (repo_id, "guide.pdf", "sha", "pdf", 2),
    ).lastrowid
    conn.execute(
        "INSERT INTO chunks (file_id, start_line, end_line, content) VALUES (?, ?, ?, ?)",
        (file_id, 1, 1, "first page"),
    )
    conn.execute(
        "INSERT INTO chunks (file_id, start_line, end_line, content) VALUES (?, ?, ?, ?)",
        (file_id, 2, 2, "second page"),
    )
    conn.commit()

    out = ref_file("repo", "guide.pdf")

    assert out["start_line"] == 1
    assert out["end_line"] == 2
    assert out["total_lines"] == 2
    assert out["content"] == "[page 1]\nfirst page\n\n[page 2]\nsecond page"
