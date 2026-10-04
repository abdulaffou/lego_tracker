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
simply do not discount. The exception: if such a set ever breaks below
its known floor, that is the most newsworthy thing it can do, so it is
reported.

A price that looks implausible -- a huge overnight swing, or a scraped
page price far from the same day's shop feeds -- is written to the
history with `suspect` set, and never used as a low, an MRP, or
tomorrow's baseline. One bad row cannot blind the tracker to a set.

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

## What arrives in your inbox

- A set hits BUY NOW or GOOD -- an email, at most once a week per set
  unless the price drops further.
- A shop cannot be reached -- a short notice, at most once a week, so a
  shop that broke three weeks ago never looks like a quiet day.
- Every Sunday -- a digest of all eight sets with their verdicts, and a
  list of any whose Amazon figures are over six months old and want a
  fresh screenshot.
- Nothing at all on a quiet day. That silence is meaningful.

## The spreadsheet

Every email carries **lego-prices.xlsx**, and `make check` writes it to
`data/` so you can open it any time.

- **Today** -- one row per set you watch: verdict (colour-coded), best
  price, which shop, how far off MRP, why, and a link straight to the
  product page. "Off MRP" is a live formula, so editing a price
  recalculates it.
- **History** -- every price recorded for your sets, newest first, one
  reading per shop per day. Implausible prices are shaded red and marked
  in the Suspect column; they are kept for the record and never used to
  judge anything.

Headers are frozen and filters are on, so you can sort by price or filter
to one shop without touching anything.

## Where the data lives

`data/prices-<year>.csv` -- every price ever seen, append-only,
committed after each run, one file per year. Opens in Excel.

| column | meaning |
|---|---|
| `mrp` | the shop's list price, blank if it publishes none |
| `source` | `feed` (the shop's own JSON) or `page` (scraped) |
| `suspect` | `true` = implausible, recorded but never trusted |
