from __future__ import annotations

import os

import pytest

from route53_ddns.config import FileConfig, load_env_from_files, load_file_config


def test_load_env_from_files_reads_and_strips(monkeypatch, tmp_path):
    secret = tmp_path / "key_id"
    secret.write_text("AKIAFROMFILE\n", encoding="utf-8")
    monkeypatch.delenv("AWS_ACCESS_KEY_ID")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID_FILE", str(secret))
    load_env_from_files()
    assert os.environ["AWS_ACCESS_KEY_ID"] == "AKIAFROMFILE"
    assert os.environ["AWS_SECRET_ACCESS_KEY"] == "testing"
    load_env_from_files()
    assert os.environ["AWS_ACCESS_KEY_ID"] == "AKIAFROMFILE"


def test_load_env_from_files_rejects_both_set(monkeypatch, tmp_path):
    secret = tmp_path / "secret"
    secret.write_text("x", encoding="utf-8")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY_FILE", str(secret))
    with pytest.raises(ValueError, match="Both AWS_SECRET_ACCESS_KEY and AWS_SECRET_ACCESS_KEY_FILE"):
        load_env_from_files()


def test_load_env_from_files_missing_file(monkeypatch, tmp_path):
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY_FILE", str(tmp_path / "nope"))
    with pytest.raises(ValueError, match="AWS_SECRET_ACCESS_KEY_FILE could not be read"):
        load_env_from_files()


def test_load_file_config_ok(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(
        """
poll_interval_seconds: 3600
checkip_url: https://example.com/ip
records:
  - hosted_zone_id: Z1
    record_name: test.example.com.
    ttl: 300
notifications:
  apprise_urls: []
""",
        encoding="utf-8",
    )
    fc = load_file_config(p)
    assert fc.poll_interval_seconds == 3600
    assert fc.checkip_url == "https://example.com/ip"
    assert len(fc.records) == 1
    assert fc.records[0].hosted_zone_id == "Z1"


def test_load_file_config_missing_file(tmp_path):
    with pytest.raises(ValueError, match="CONFIG_FILE"):
        load_file_config(tmp_path / "nope.yaml")


def test_file_config_requires_records():
    with pytest.raises(Exception):
        FileConfig.model_validate({"poll_interval_seconds": 100})
