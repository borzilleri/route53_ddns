/**
 * Format an instant in the viewer's local timezone (Intl, browser default locale).
 * @param {Date} date
 * @returns {string}
 */
function formatAbsoluteLocal(date) {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

/**
 * Relative time vs a base instant (default: now), using Intl.RelativeTimeFormat.
 * @param {Date} target
 * @param {Date} [base]
 * @returns {string}
 */
function formatRelativeToNow(target, base = new Date()) {
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  const diffSec = Math.round((target.getTime() - base.getTime()) / 1000);
  if (diffSec === 0) {
    return rtf.format(0, "second");
  }
  if (Math.abs(diffSec) < 60) {
    return rtf.format(diffSec, "second");
  }
  const diffMin = Math.round(diffSec / 60);
  if (Math.abs(diffMin) < 60) {
    return rtf.format(diffMin, "minute");
  }
  const diffHour = Math.round(diffSec / 3600);
  if (Math.abs(diffHour) < 24) {
    return rtf.format(diffHour, "hour");
  }
  const diffDay = Math.round(diffSec / 86400);
  if (Math.abs(diffDay) < 7) {
    return rtf.format(diffDay, "day");
  }
  const diffWeek = Math.round(diffSec / (86400 * 7));
  if (Math.abs(diffWeek) < 5) {
    return rtf.format(diffWeek, "week");
  }
  const diffMonth = Math.round(diffSec / (86400 * 30));
  if (Math.abs(diffMonth) < 12) {
    return rtf.format(diffMonth, "month");
  }
  const diffYear = Math.round(diffSec / (86400 * 365));
  return rtf.format(diffYear, "year");
}

function hydrateInstant(root) {
  const iso = root.getAttribute("data-utc");
  if (!iso) {
    return;
  }
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return;
  }
  const absEl = root.querySelector(".dt-abs");
  const relEl = root.querySelector(".dt-rel");
  const absText = formatAbsoluteLocal(d);
  const relText = formatRelativeToNow(d);
  if (absEl) {
    absEl.dateTime = iso;
    absEl.textContent = absText;
  }
  if (relEl) {
    relEl.textContent = relText;
  }
}

function hydrateAll() {
  document.querySelectorAll(".instant[data-utc]").forEach(hydrateInstant);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", hydrateAll);
} else {
  hydrateAll();
}
