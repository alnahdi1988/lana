from __future__ import annotations

from pathlib import Path

from doctrine_engine.config.settings import Settings


def test_settings_use_repo_root_for_local_paths(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    settings = Settings(operator_state_db_path=".doctrine/operations.db")

    expected = Path(__file__).resolve().parents[2] / ".doctrine" / "operations.db"
    assert Path(settings.operator_state_db_path) == expected.resolve()


def test_settings_env_file_is_repo_absolute():
    env_file = Settings.model_config.get("env_file")

    assert env_file is not None
    assert Path(str(env_file)).is_absolute()
    assert Path(str(env_file)).name == ".env"
