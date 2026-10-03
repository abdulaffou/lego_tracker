"""Composing and sending the alert email."""
import os
import smtplib
from email.message import EmailMessage

ORDER = {"BUY_NOW": 0, "GOOD": 1, "FAIR": 2, "WAIT": 3, "NEVER_DISCOUNTS": 4}
HEADLINE = {"BUY_NOW": "BUY NOW", "GOOD": "GOOD", "FAIR": "FAIR",
            "WAIT": "WAIT", "NEVER_DISCOUNTS": "never discounts"}
ALL_SHOPS = {"official", "toycra", "funcorp"}


def compose(items: list[dict], failed_shops: list[str],
            today: str) -> tuple[str | None, str | None]:
    """Build (subject, body). Returns (None, None) when there is no news."""
    if not items:
        if ALL_SHOPS.issubset(set(failed_shops)):
            return ("LEGO tracker: could not check prices today",
                    "Could not check prices today -- every shop failed.\n"
                    f"Shops tried: {', '.join(sorted(failed_shops))}\n")
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

    return subject, "\n".join(lines)


def send(subject: str, body: str, config: dict) -> None:
    """Send via SMTP. Credentials come from the environment only."""
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASS"]
    settings = config["email"]

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings["from_addr"]
    message["To"] = settings["to"]
    message.set_content(body)

    with smtplib.SMTP(settings["smtp_host"], settings["smtp_port"],
                      timeout=30) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(message)
