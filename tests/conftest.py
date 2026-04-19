import json

import pytest


@pytest.fixture(autouse=True)
def env_records(monkeypatch, tmp_path):
    from route53_ddns.config import clear_settings_cache

    records = [
        {
            "hosted_zone_id": "ZTESTZONE",
            "record_name": "dyn.example.com.",
            "ttl": 300,
        }
    ]
    records_file = tmp_path / "records.json"
    records_file.write_text(json.dumps(records), encoding="utf-8")
    monkeypatch.setenv("ROUTE53_RECORDS_FILE", str(records_file))
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    clear_settings_cache()
    yield
    clear_settings_cache()
