from __future__ import annotations

from startup_risk.ingest.repository import RepositoryIngestor


def test_ingestor_reads_text_files_in_deterministic_repo_relative_order(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "b.py").write_text("print('do not run')\n", encoding="utf-8")
    (repo / "a.py").write_text("value = 1\n", encoding="utf-8")

    snapshot = RepositoryIngestor().ingest(str(repo))

    assert snapshot.source.kind == "local"
    assert [file.path for file in snapshot.files] == ["a.py", "b.py"]
    assert snapshot.files[0].text == "value = 1\n"
    assert all(not file.path.startswith("/") for file in snapshot.files)


def test_ingestor_ignores_configured_directories(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    ignored = repo / "node_modules"
    ignored.mkdir()
    (ignored / "package.json").write_text("{}", encoding="utf-8")

    snapshot = RepositoryIngestor().ingest(str(repo))

    assert [file.path for file in snapshot.files] == ["README.md"]


def test_ingestor_marks_binary_files(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "image.bin").write_bytes(b"\x00\x01\x02")

    snapshot = RepositoryIngestor().ingest(str(repo))

    assert snapshot.files[0].path == "image.bin"
    assert snapshot.files[0].text is None
    assert snapshot.files[0].is_binary is True
    assert snapshot.files[0].skipped_reason == "binary file"


def test_ingestor_marks_oversized_files(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "large.txt").write_text("abcdef", encoding="utf-8")

    snapshot = RepositoryIngestor(max_file_bytes=3).ingest(str(repo))

    assert snapshot.files[0].path == "large.txt"
    assert snapshot.files[0].text is None
    assert snapshot.files[0].is_binary is False
    assert snapshot.files[0].skipped_reason == "file exceeds max_file_bytes"


def test_ingestor_reads_uv_lock_under_structured_file_limit(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "uv.lock").write_text("[[package]]\nname = \"requests\"\nversion = \"2.31.0\"\n", encoding="utf-8")

    snapshot = RepositoryIngestor(max_file_bytes=3, structured_max_file_bytes=1_000).ingest(str(repo))

    assert snapshot.files[0].path == "uv.lock"
    assert snapshot.files[0].text is not None
    assert snapshot.files[0].skipped_reason is None
