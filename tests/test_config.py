from __future__ import annotations

import pytest

from route53_ddns.config import FileConfig, load_file_config


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
