from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from route53_ddns.route53_ops import format_txt_rdata, normalize_fqdn, upsert_a_and_txt


def test_normalize_fqdn_adds_trailing_dot():
    assert normalize_fqdn("dyn.example.com") == "dyn.example.com."


def test_upsert_batches_a_and_txt():
    client = MagicMock()
    t = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
    upsert_a_and_txt(
        client,
        "Z123",
        "dyn.example.com",
        "203.0.113.1",
        "_ddns-last-update.dyn.example.com.",
        t,
        300,
    )
    client.change_resource_record_sets.assert_called_once()
    call_kw = client.change_resource_record_sets.call_args.kwargs
    batch = call_kw["ChangeBatch"]["Changes"]
    assert len(batch) == 2
    assert batch[0]["ResourceRecordSet"]["Type"] == "A"
    assert batch[0]["ResourceRecordSet"]["ResourceRecords"][0]["Value"] == "203.0.113.1"
    assert batch[1]["ResourceRecordSet"]["Type"] == "TXT"
    txt_val = batch[1]["ResourceRecordSet"]["ResourceRecords"][0]["Value"]
    assert "2026-04-18T12:00:00Z" in txt_val or "2026-04-18" in txt_val


def test_format_txt_rdata_quoted():
    s = format_txt_rdata("2026-04-18T12:00:00Z")
    assert s.startswith('"') and s.endswith('"')
