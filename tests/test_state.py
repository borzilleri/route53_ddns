from __future__ import annotations

from route53_ddns.config import Route53RecordConfig
from route53_ddns.state import AppState, RecordRuntime, record_needs_update


def test_record_needs_update():
    assert record_needs_update("1.1.1.1", "2.2.2.2")
    assert not record_needs_update("1.1.1.1", "1.1.1.1")
    assert record_needs_update(None, "1.1.1.1")
    assert record_needs_update("1.1.1.1", None)
    assert record_needs_update(None, None)


def test_snapshot_needs_update_and_any_row_out_of_date():
    rc = Route53RecordConfig(
        hosted_zone_id="Z1",
        record_name="dyn.example.com.",
        ttl=300,
    )
    state = AppState()
    state.records.append(
        RecordRuntime(index=0, config=rc, route53_ip="2.2.2.2"),
    )
    state.current_public_ip = "1.1.1.1"
    snap = state.snapshot_for_template()
    assert snap["records"][0]["needs_update"] is True
    assert snap["any_row_out_of_date"] is True

    state.current_public_ip = "2.2.2.2"
    snap = state.snapshot_for_template()
    assert snap["records"][0]["needs_update"] is False
    assert snap["any_row_out_of_date"] is False


def test_status_api_dict():
    from datetime import datetime, timezone

    rc = Route53RecordConfig(
        hosted_zone_id="Z1",
        record_name="dyn.example.com.",
        ttl=300,
    )
    state = AppState()
    t = datetime(2026, 4, 19, 12, 0, 0, tzinfo=timezone.utc)
    state.records.append(
        RecordRuntime(index=0, config=rc, last_dns_update_at=t),
    )
    d = state.status_api_dict()
    assert d["lastUpdated"] == t.isoformat()
    assert d["records"][0]["host"] == "dyn.example.com"
    assert d["records"][0]["lastUpdated"] == t.isoformat()


def test_status_api_dict_null_when_never_updated():
    rc = Route53RecordConfig(
        hosted_zone_id="Z1",
        record_name="a.example.com.",
        ttl=300,
    )
    state = AppState()
    state.records.append(RecordRuntime(index=0, config=rc))
    d = state.status_api_dict()
    assert d["lastUpdated"] is None
    assert d["records"][0]["lastUpdated"] is None
