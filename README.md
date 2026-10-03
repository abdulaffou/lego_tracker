# LEGO Price Tracker

Checks LEGO prices across four Indian shops every morning and emails you
only when a set you want reaches a genuinely good price.

Quiet days mean nothing worth your attention. That silence is the point.

## What it watches

The official LEGO store (lego.mybrickhouse.com), Toycra, FunCorp, and
Amazon.in. Sets to track live in `watchlist.yaml`.

## How it decides

One rule: where does today's price sit between the cheapest and dearest
this set is known to have been?

| Position | Verdict | Emails you? |
|---|---|---|
| Bottom 10% | BUY NOW | yes |
| Bottom 25% | GOOD | yes |
| 25-50% | FAIR | no |
| Above 50% | WAIT | no |

Sets whose whole price range is under 10% wide never trigger -- they
simply do not discount.

## Setting it up

**1. Make a Gmail app password**

Google Account -> Security -> 2-Step Verification -> App passwords.
Create one for "Mail". You get a 16-character code.

**2. Add it to GitHub**

Repository -> Settings -> Secrets and variables -> Actions -> New secret:

- `SMTP_USER` -- your Gmail address
- `SMTP_PASS` -- the 16-character app password (not your real password)

**3. Turn the schedule on**

Push to GitHub. It then runs at 07:00 IST daily. To test it immediately:
Actions tab -> "Daily LEGO price check" -> Run workflow.

## Running it yourself

```bash
make setup                  # one time
make test                   # run the test suite
make check                  # check prices now (Amazon works from home)
```

Add `--dry-run` to print the email instead of sending it:

```bash
PYTHONPATH=src .venv/bin/python -m legotracker.cli --local --dry-run
```

## Adding a set

Add it to `watchlist.yaml`:

```yaml
- set: "10497"
  name: Galaxy Explorer
  asin: B0XXXXXXXX          # optional, from the Amazon URL
  amazon_low: 8000          # optional, from Rufus in the Amazon app
  amazon_high: 14000
  seen_on: 2026-10-04
```

Set number and name are enough to start. The Amazon figures make it
useful on day one instead of after weeks of watching -- open the set in
the Amazon app, tap "Price history", and read the low and high off the
chart.

## Where the data lives

`data/prices.csv` -- every price ever seen, append-only, committed after
each run. Opens in Excel.
