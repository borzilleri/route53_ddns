from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


def get_route53_client() -> Any:
    return boto3.client("route53")


def normalize_fqdn(name: str) -> str:
    n = name.strip()
    return n if n.endswith(".") else f"{n}."


def list_a_record_ip(client: Any, hosted_zone_id: str, record_name: str) -> str | None:
    """Return IPv4 for the first A record at record_name, or None if missing."""
    fqdn = normalize_fqdn(record_name)
    paginator = client.get_paginator("list_resource_record_sets")
    try:
        for page in paginator.paginate(HostedZoneId=hosted_zone_id):
            for rr in page.get("ResourceRecordSets", []):
                if rr.get("Name") == fqdn and rr.get("Type") == "A":
                    values = rr.get("ResourceRecords") or []
                    if not values:
                        return None
                    return (values[0].get("Value") or "").strip() or None
    except (ClientError, BotoCoreError) as e:
        logger.error("list_resource_record_sets failed: %s", e)
        raise
    return None


def format_txt_rdata(iso_timestamp: str) -> str:
    """Route53 TXT single string; quote for API."""
    return f'"{iso_timestamp}"'


def upsert_a_and_txt(
    client: Any,
    hosted_zone_id: str,
    a_name: str,
    ipv4: str,
    txt_name: str,
    update_time: datetime,
    ttl: int,
) -> None:
    fqdn_a = normalize_fqdn(a_name)
    fqdn_txt = normalize_fqdn(txt_name)
    ts = update_time.astimezone(timezone.utc).replace(microsecond=0)
    ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    txt_rdata = format_txt_rdata(ts_str)

    changes = [
        {
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": fqdn_a,
                "Type": "A",
                "TTL": ttl,
                "ResourceRecords": [{"Value": ipv4}],
            },
        },
        {
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": fqdn_txt,
                "Type": "TXT",
                "TTL": ttl,
                "ResourceRecords": [{"Value": txt_rdata}],
            },
        },
    ]
    try:
        client.change_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            ChangeBatch={"Comment": "route53-ddns update", "Changes": changes},
        )
    except (ClientError, BotoCoreError) as e:
        logger.error("change_resource_record_sets failed: %s", e)
        raise


def verify_credentials() -> None:
    """Log identity when credentials work; raise on failure."""
    sts = boto3.client("sts")
    ident = sts.get_caller_identity()
    logger.info(
        "AWS credentials OK; caller Account=%s Arn=%s",
        ident.get("Account"),
        ident.get("Arn"),
    )
