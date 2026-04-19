from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def send_poll_cycle_notification(
    apprise_urls: list[str],
    updated_hosts: list[str],
    errors: list[str],
) -> None:
    """Send a single Apprise notification summarizing poll cycle results."""
    if not apprise_urls:
        return
    if not updated_hosts and not errors:
        return

    from apprise import Apprise

    apobj = Apprise()
    for url in apprise_urls:
        apobj.add(url)

    title = "Route53 DDNS"
    parts: list[str] = []
    if updated_hosts:
        parts.append("Updated: " + ", ".join(updated_hosts))
    if errors:
        parts.append("Errors:\n" + "\n".join(errors))
    body = "\n\n".join(parts)

    try:
        apobj.notify(title=title, body=body)
    except Exception:
        logger.exception("Apprise notification failed")
