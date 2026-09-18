from pathlib import Path

from core import db as db_module
from core.config import get_local_db_path


def test_local_mode_uses_in_memory_db_url():
    assert db_module.get_db_url() == "sqlite:///:memory:"


def test_local_db_path_can_be_resolved_from_config():
    assert str(get_local_db_path()) == ":memory:"


def test_init_db_creates_local_directories_for_file_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(db_module.settings, "MEMWARD_MODE", "local")
    monkeypatch.setattr(db_module.settings, "MEMWARD_HOME", str(tmp_path / ".memward-test"))
    monkeypatch.setattr(db_module.settings, "MEMWARD_LOCAL_DB_PATH", str(tmp_path / ".memward-test" / "memward.db"))

    db_module.engine = None
    db_module.SessionLocal = None
    db_module.init_db()

    memward_home = Path(db_module.settings.MEMWARD_HOME)
    assert (memward_home / "checkpoints").exists()
    assert (memward_home / "logs").exists()
    assert (memward_home / "memward.db").exists()
