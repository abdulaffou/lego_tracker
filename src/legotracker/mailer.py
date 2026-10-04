"""Composing and sending the alert email."""
import logging
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

log = logging.getLogger(__name__)

XLSX_TYPE = ("application", "vnd.openxmlformats-officedocument."
             "spreadsheetml.sheet")

ORDER = {"BUY_NOW": 0, "GOOD": 1, "FAIR": 2, "WAIT": 3, "NEVER_DISCOUNTS": 4}
HEADLINE = {"BUY_NOW": "BUY NOW", "GOOD": "GOOD", "FAIR": "FAIR",
            "WAIT": "WAIT", "NEVER_DISCOUNTS": "never discounts"}
ALL_SHOPS = {"official", "toycra", "funcorp"}


def _digest_lines(digest: list[dict]) -> list[str]:
    lines = ["Everything you are watching:", ""]
    for entry in sorted(digest, key=lambda i: ORDER[i["verdict"].label]):
        label = HEADLINE[entry["verdict"].label]
        lines.append(f"  {label:<16} {entry['name']} -- "
                     f"Rs{entry['price']:,.0f} ({entry['verdict'].reason})")
    stale = [e["name"] for e in digest if e.get("stale")]
    if stale:
        lines += ["",
                  "These want a fresh Amazon price-history screenshot: "
                  + ", ".join(stale)]
    return lines


def compose(items: list[dict], failed_shops: list[str], today: str,
            digest: list[dict] | None = None
            ) -> tuple[str | None, str | None]:
    """Build (subject, body). Returns (None, None) when there is no news."""
    if not items:
        if ALL_SHOPS.issubset(set(failed_shops)):
            return ("LEGO tracker: could not check prices today",
                    "Could not check prices today -- every shop failed.\n"
                    f"Shops tried: {', '.join(sorted(failed_shops))}\n")
        if digest:
            return (f"LEGO weekly digest -- {today}",
                    "\n".join(_digest_lines(digest)))
        if failed_shops:
            # Silence must mean "nothing to report", never "it broke
            # three weeks ago".
            return ("LEGO tracker: a shop could not be reached",
                    "No price news today, but these could not be checked: "
                    f"{', '.join(sorted(failed_shops))}\n")
        return None, None

    ranked = sorted(items, key=lambda i: (ORDER[i["verdict"].label],
                                          -i["price"]))
    best = ranked[0]
    subject = (f"LEGO: {HEADLINE[best['verdict'].label]} on "
               f"{best['name']} -- Rs{best['price']:,.0f}")

    lines = [f"Price check for {today}", ""]
    for entry in ranked:
        verdict = entry["verdict"]
        lines += [
            f"{HEADLINE[verdict.label]} -- {entry['name']} ({entry['set_number']})",
            f"  Rs{entry['price']:,.0f} at {entry['shop']}",
            f"  {verdict.reason}",
            f"  Based on: {entry['sources']} shop"
            f"{'s' if entry['sources'] != 1 else ''}, "
            f"{entry['history_days']} days of our own records",
            f"  {entry['url']}",
            "",
        ]

    if failed_shops:
        lines.append(f"(Could not reach: {', '.join(sorted(failed_shops))})")
    if digest:
        lines += [""] + _digest_lines(digest)

    return subject, "\n".join(lines)


def send(subject: str, body: str, config: dict,
         attachment=None) -> None:
    """Send via SMTP. Credentials come from the environment only."""
    try:
        user = os.environ["SMTP_USER"]
        password = os.environ["SMTP_PASS"]
    except KeyError as missing:
        raise RuntimeError(
            f"{missing.args[0]} is not set. Add SMTP_USER and SMTP_PASS as "
            "repository secrets (see README), or run with --dry-run."
        ) from None
    settings = config["email"]

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings["from_addr"]
    message["To"] = settings["to"]
    message.set_content(body)

    if attachment:
        path = Path(attachment)
        try:
            message.add_attachment(path.read_bytes(), maintype=XLSX_TYPE[0],
                                   subtype=XLSX_TYPE[1], filename=path.name)
        except OSError as exc:
            # The news is the point; the spreadsheet is a convenience.
            log.warning("could not attach %s: %s", path, exc)

    with smtplib.SMTP(settings["smtp_host"], settings["smtp_port"],
                      timeout=30) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(message)
