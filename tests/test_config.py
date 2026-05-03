"""Tests for bestman.config"""
import importlib
from pathlib import Path
from unittest.mock import patch

import yaml

from bestman import config


class TestBestmanHome:
    def test_path_is_dot_bestman_in_home(self):
        home = Path("/Users/testuser")
        expected = home / ".bestman"
        with patch.object(Path, "home", return_value=home):
            importlib.reload(config)
            assert config.BESTMAN_HOME == expected


class TestEnsureHome:
    def test_creates_directory_if_not_exists(self, tmp_path):
        bestman_dir = tmp_path / ".bestman"
        assert not bestman_dir.exists()

        with patch.object(config, "BESTMAN_HOME", bestman_dir):
            config.ensure_home()

        assert bestman_dir.exists()
        assert bestman_dir.is_dir()

    def test_creates_config_yaml_if_not_exists(self, tmp_path):
        bestman_dir = tmp_path / ".bestman"
        bestman_dir.mkdir()
        yaml_path = bestman_dir / "config.yaml"
        assert not yaml_path.exists()

        with patch.object(config, "BESTMAN_HOME", bestman_dir):
            config.ensure_home()

        assert yaml_path.exists()
        data = yaml.safe_load(yaml_path.read_text())
        assert "voyage" in data
        assert "default_daily_task" in data["voyage"]

    def test_does_not_overwrite_existing_config(self, tmp_path):
        bestman_dir = tmp_path / ".bestman"
        bestman_dir.mkdir()
        yaml_path = bestman_dir / "config.yaml"
        yaml_path.write_text("voyage:\n  total_days: 365\n")

        with patch.object(config, "BESTMAN_HOME", bestman_dir):
            config.ensure_home()

        data = yaml.safe_load(yaml_path.read_text())
        assert data["voyage"]["total_days"] == 365


class TestLoadConfig:
    def test_returns_defaults_when_no_config_file(self, tmp_path):
        bestman_dir = tmp_path / ".bestman"
        bestman_dir.mkdir()

        with patch.object(config, "BESTMAN_HOME", bestman_dir):
            cfg = config.load_config()

        assert cfg["voyage"]["total_days"] == 175
        assert "default_daily_task" in cfg["voyage"]

    def test_merges_user_config_over_defaults(self, tmp_path):
        bestman_dir = tmp_path / ".bestman"
        bestman_dir.mkdir()
        yaml_path = bestman_dir / "config.yaml"
        yaml_path.write_text("voyage:\n  total_days: 30\n")

        with patch.object(config, "BESTMAN_HOME", bestman_dir):
            cfg = config.load_config()

        assert cfg["voyage"]["total_days"] == 30
        assert "default_daily_task" in cfg["voyage"]

    def test_preserves_default_keys_not_in_user_config(self, tmp_path):
        bestman_dir = tmp_path / ".bestman"
        bestman_dir.mkdir()
        yaml_path = bestman_dir / "config.yaml"
        yaml_path.write_text("profile:\n  name: TestUser\n")

        with patch.object(config, "BESTMAN_HOME", bestman_dir):
            cfg = config.load_config()

        assert cfg["profile"]["name"] == "TestUser"
        assert cfg["voyage"]["total_days"] == 175


class TestDefaultConfig:
    def test_has_required_keys(self):
        assert "voyage" in config.DEFAULT_CONFIG
        assert "total_days" in config.DEFAULT_CONFIG["voyage"]
        assert "default_daily_task" in config.DEFAULT_CONFIG["voyage"]
        assert config.DEFAULT_CONFIG["voyage"]["total_days"] == 175
