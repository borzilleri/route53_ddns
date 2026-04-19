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
