import pytest
import yaml


@pytest.fixture(autouse=True)
def env_config(monkeypatch, tmp_path):
    from route53_ddns.config import clear_settings_cache

    records = [
        {
            "hosted_zone_id": "ZTESTZONE",
            "record_name": "dyn.example.com.",
            "ttl": 300,
        }
    ]
    payload = {
        "poll_interval_seconds": 14400,
        "checkip_url": "https://checkip.amazonaws.com",
        "records": records,
        "notifications": {"apprise_urls": []},
    }
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.safe_dump(payload), encoding="utf-8")
    monkeypatch.setenv("CONFIG_FILE", str(config_file))
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    clear_settings_cache()
    yield
    clear_settings_cache()
