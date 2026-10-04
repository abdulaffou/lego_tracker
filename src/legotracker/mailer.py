"""Composing and sending the alert email."""
import logging
import os
import smtplib
from email.message import EmailMessage
from html import escape
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
        pieces = entry.get("pieces")
        per_piece = entry.get("price_per_piece")
        value = f"  Rs{per_piece:,.2f} per piece ({pieces:,} pieces)" \
            if per_piece else None
        lines += [
            f"{HEADLINE[verdict.label]} -- {entry['name']} ({entry['set_number']})",
            f"  Rs{entry['price']:,.0f} at {entry['shop']}",
            *( [value] if value else [] ),
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
         attachment=None, html: str | None = None) -> None:
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
    if html:
        # Plain text stays the fallback: some clients, and some people,
        # prefer it, and it is what lands in a notification preview.
        message.add_alternative(html, subtype="html")

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


# --------------------------------------------------------------------
# HTML email
#
# Email clients are not browsers. Gmail strips <style> blocks, so every
# rule is inline; it will not render <svg>, so the range bar is built
# from nested divs; and it proxies remote images, which is why the shop
# CDN photo works without us hosting anything.
# --------------------------------------------------------------------

INK = "#121a1a"
MUTED = "#6b7b7b"
RULE = "#e2e8e8"
TONE = {
    "BUY_NOW": ("#1f7a4d", "#e4f3ea"),
    "GOOD": ("#1f7a4d", "#e4f3ea"),
    "FAIR": ("#8a5d08", "#faf0d8"),
    "WAIT": ("#a8403a", "#f8e6e4"),
    "NEVER_DISCOUNTS": ("#6b7b7b", "#eef1f1"),
}


def _money(value: float) -> str:
    return f"\u20b9{value:,.0f}"


def _per_piece(value: float) -> str:
    """Per-piece prices live between Rs5 and Rs15, so paise matter here."""
    return f"\u20b9{value:,.2f}"


def _range_bar(item: dict) -> str:
    """Where today sits between the cheapest and dearest known price."""
    position = item["verdict"].position
    low, high = item.get("range_low"), item.get("range_high")
    if position is None or low is None or high is None:
        return ""
    clamped = max(0.0, min(100.0, position))
    colour = TONE.get(item["verdict"].label, TONE["WAIT"])[0]
    return (
        f'<div class="rangebar" style="margin-top:14px">'
        f'<div style="position:relative;height:8px;border-radius:4px;'
        f'background:#eef1f1">'
        f'<div style="position:absolute;top:0;bottom:0;left:{clamped:.0f}%;'
        f'width:4px;border-radius:2px;background:{colour}"></div></div>'
        f'<table role="presentation" cellpadding="0" cellspacing="0" '
        f'width="100%" style="margin-top:5px"><tr>'
        f'<td style="font:400 12px/1.4 ui-monospace,Menlo,monospace;'
        f'color:{MUTED}">{_money(low)}</td>'
        f'<td align="right" style="font:400 12px/1.4 ui-monospace,Menlo,'
        f'monospace;color:{MUTED}">{_money(high)}</td>'
        f'</tr></table></div>'
    )


def _card(item: dict) -> str:
    verdict = item["verdict"]
    colour, wash = TONE.get(verdict.label, TONE["NEVER_DISCOUNTS"])
    name = escape(item["name"])
    pieces = item.get("pieces")
    per_piece = item.get("price_per_piece")

    photo = ""
    if item.get("image"):
        photo = (
            f'<td width="92" valign="top" style="padding-right:16px">'
            f'<img src="{escape(item["image"], quote=True)}" width="92" '
            f'alt="{name}" style="display:block;width:92px;height:auto;'
            f'border-radius:6px;border:1px solid {RULE}"></td>'
        )

    meta = f'{item["set_number"]}'
    if pieces:
        meta += f' &middot; {pieces:,} pieces'

    value = ""
    if per_piece:
        value = (
            f'<div style="font:400 14px/1.5 -apple-system,Segoe UI,Roboto,'
            f'sans-serif;color:{MUTED};margin-top:3px">'
            f'<span style="font-family:ui-monospace,Menlo,monospace;'
            f'color:{INK}">{_per_piece(per_piece)}</span> per piece</div>'
        )

    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" '
        f'width="100%" style="border-top:1px solid {RULE};padding-top:22px;'
        f'margin-top:22px"><tr>{photo}<td valign="top">'
        f'<div><span style="display:inline-block;font:600 11px/1 '
        f'ui-monospace,Menlo,monospace;letter-spacing:.1em;'
        f'text-transform:uppercase;color:{colour};background:{wash};'
        f'padding:5px 9px;border-radius:3px">'
        f'{HEADLINE[verdict.label]}</span></div>'
        f'<div style="font:600 17px/1.3 -apple-system,Segoe UI,Roboto,'
        f'sans-serif;color:{INK};margin-top:10px">{name}</div>'
        f'<div style="font:400 12px/1.5 ui-monospace,Menlo,monospace;'
        f'color:{MUTED};margin-top:2px">{meta}</div>'
        f'<div style="font:600 25px/1.2 ui-monospace,Menlo,monospace;'
        f'color:{INK};margin-top:10px">{_money(item["price"])}'
        f'<span style="font:400 14px/1.2 -apple-system,Segoe UI,sans-serif;'
        f'color:{MUTED}"> at {escape(item["shop"])}</span></div>'
        f'{value}'
        f'<div style="font:400 14px/1.55 -apple-system,Segoe UI,Roboto,'
        f'sans-serif;color:{INK};margin-top:10px">'
        f'{escape(verdict.reason)}</div>'
        f'{_range_bar(item)}'
        f'<div style="margin-top:14px"><a href="{escape(item["url"], quote=True)}" '
        f'style="font:600 14px/1 -apple-system,Segoe UI,sans-serif;'
        f'color:#0f6e6b;text-decoration:none">View at '
        f'{escape(item["shop"])} &rarr;</a></div>'
        f'</td></tr></table>'
    )


def compose_html(items: list[dict], failed_shops: list[str],
                 today: str, digest: list[dict] | None = None) -> str:
    ranked = sorted(items, key=lambda i: (ORDER[i["verdict"].label],
                                          -i["price"]))
    cards = "".join(_card(entry) for entry in ranked)

    notes = []
    if failed_shops:
        notes.append("Could not reach: " + ", ".join(sorted(failed_shops)))
    if digest:
        notes.append(f"{len(digest)} sets watched &middot; weekly digest "
                     "attached as a spreadsheet")
    footer = ""
    if notes:
        footer = (
            f'<div style="border-top:1px solid {RULE};margin-top:26px;'
            f'padding-top:14px;font:400 13px/1.5 -apple-system,Segoe UI,'
            f'sans-serif;color:{MUTED}">' + " &middot; ".join(notes) + '</div>'
        )

    return (
        f'<div style="background:#f7f8f8;padding:26px 14px">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" '
        f'width="100%" style="max-width:560px;margin:0 auto;'
        f'background:#ffffff;border:1px solid {RULE};border-radius:10px">'
        f'<tr><td style="padding:26px 24px 30px">'
        f'<div style="font:600 11px/1 ui-monospace,Menlo,monospace;'
        f'letter-spacing:.14em;text-transform:uppercase;color:{MUTED}">'
        f'Price check &middot; {escape(today)}</div>'
        f'{cards}{footer}'
        f'</td></tr></table></div>'
    )
