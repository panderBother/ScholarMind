import os
from pathlib import Path

import pytest

from file_writer.paths import allowed_roots, resolve_writable_path


def test_resolve_under_repo_exports(monkeypatch, tmp_path):
    repo = Path(__file__).resolve().parents[2]
    exports = repo / "data" / "exports"
    monkeypatch.setenv("FILE_WRITER_ALLOWED_ROOTS", str(exports))
    target = exports / "nested" / "out.md"
    resolved = resolve_writable_path(str(target))
    assert resolved == target.resolve()


def test_reject_path_outside_roots(monkeypatch, tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside" / "x.md"
    monkeypatch.setenv("FILE_WRITER_ALLOWED_ROOTS", str(allowed))
    with pytest.raises(ValueError, match="不在允许范围"):
        resolve_writable_path(str(outside))


def test_reject_path_traversal(monkeypatch, tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setenv("FILE_WRITER_ALLOWED_ROOTS", str(allowed))
    evil = allowed / ".." / "escape.md"
    with pytest.raises(ValueError, match="不在允许范围"):
        resolve_writable_path(str(evil))


def test_default_roots_non_empty():
    os.environ.pop("FILE_WRITER_ALLOWED_ROOTS", None)
    assert len(allowed_roots()) >= 1
