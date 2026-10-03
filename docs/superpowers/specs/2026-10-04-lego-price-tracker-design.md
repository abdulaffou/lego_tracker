# LEGO Price Tracker — Design

**Date:** 2026-10-04
**Status:** Awaiting approval
**For:** Abdul (India, buying LEGO for himself)

---

## 1. What this is

A small program that checks LEGO prices across several Indian shops once a day,
remembers what it saw, and emails you **only when it's genuinely a good time to buy**.

It is not a dashboard you have to visit. It is not a shopping app. It is a thing
that stays quiet and then taps you on the shoulder.

**Done means:** you stop checking prices manually, and you don't miss a real drop
on a set you want.

### The one-sentence test

> If this tool had existed last week, would it have saved me money?

Yes — verified during design. Today, right now:

| Set | Amazon | Toycra | You save |
|---|---|---|---|
| 42172 McLaren P1 | ₹37,079 | **₹29,399** | **₹7,680** |
| 10316 Rivendell | ₹50,399 (official) | **₹40,399** | **₹10,000** |

Both were live and verified while writing this spec.

---

## 2. The honest problem this design must solve

Six of the eight sets on the watchlist are sold by **exactly one shop, at full price**:

```
SET    NAME                  SOURCES  PRICE     DISCOUNT
11389  Project Hail Mary        1     ₹11,999      0%
10294  Titanic                  1     ₹63,999      0%
11377  Minas Tirith             1     ₹69,999      0%
10350  Tudor Corner             1     ₹24,499      0%
11371  Shopping Street          1     ₹24,999      0%
76269  Avengers Tower           1     ₹48,999      0%
42172  McLaren P1               3     ₹29,399     29%   ← works
10316  Rivendell                2     ₹40,399     20%   ← works
```

These are LEGO exclusives. Third-party shops rarely get them.

A naive design — "compare shops, alert on the lowest" — produces **"WAIT" every day
forever** for 75% of the watchlist. That is the central problem, and everything below
is shaped by it.

**Three responses, in order of importance:**

1. **Your own Amazon price history becomes a first-class input** (§7). For the six
   single-source sets it's the only usable signal on day one.
2. **Amazon is promoted to a real source**, not an afterthought (§4). It's the only
   realistic second opinion for exclusives.
3. **The tool admits what it doesn't know.** Every alert states how many sources and
   how much history it's working from. No false confidence.

---

## 3. Shape of the system

```
   ONCE A DAY, IN THE CLOUD (free)
   ┌──────────────────────────────────────────────────┐
   │                                                  │
   │  1. FETCH    ask each shop for today's prices    │
   │       │       (each shop isolated — one can fail)│
   │       ▼                                          │
   │  2. MATCH    line sets up by LEGO set number     │
   │       ▼                                          │
   │  3. RECORD   append rows to prices.csv, commit   │
   │       ▼                                          │
   │  4. JUDGE    BUY NOW / GOOD / WAIT + a reason    │
   │       ▼                                          │
   │  5. ALERT    email — only if something changed   │
   │                                                  │
   └──────────────────────────────────────────────────┘
```

Five pieces, one job each, each testable alone. Written so that **any single shop
failing cannot bring down the run** — a dead shop is a missing row, not a crash.

---

## 4. Where prices come from

Every row below was verified by fetching it during design. Nothing here is assumed.

| Shop | How we read it | Products | Stock flag | Reliability |
|---|---|---|---|---|
| **Official LEGO store** (lego.mybrickhouse.com) | Shopify `products.json` | 880 | ✅ true/false | Rock solid |
| **Toycra** (toycra.com) | Shopify `products.json` | 653 | ⚠️ in-stock only | Rock solid |
| **FunCorp** (funcorp.in) | Shopify `products.json` | 129 LEGO | ✅ true/false | Rock solid |
| **Amazon.in** | direct `/dp/<ASIN>` page | per-set | via page | ⚠️ see below |

**1,036 unique LEGO sets** are reachable across the three Shopify feeds.

### Why Shopify feeds are the backbone

These shops publish a public JSON file listing every product with price, MRP, and
stock. It is the shop's own data, not scraped HTML. It does not break when the site
is redesigned, it does not need a browser, and it does not get blocked.

One detail that matters: use the **collection** endpoint
(`/collections/<x>/products.json`), not the single-product one. Verified — the
single-product endpoint omits the `available` field entirely.

### Why Amazon is harder

Amazon works fine from a home connection but frequently blocks data-centre IPs,
which is what the cloud schedule runs on.

**Decision: hybrid.** The cloud run tries Amazon and is allowed to get nothing. A
local command (`make check`) runs the same code from your Mac, where Amazon works.
Rather than leaving six sets single-source, you get a reliable manual top-up.

**Amazon links are pasted by you, never searched for.** Verified during design:
searching `LEGO Technic McLaren P1 42172` on Amazon returned four products, **none of
them the McLaren** — a ₹998 item ranked first. The direct link returned the correct
₹37,079 and ₹41,199 immediately. Search is not trustworthy; direct links are.

### Deliberately excluded from v1

| Shop | Why not |
|---|---|
| **lego.com/en-in** | Returns 403. Needs a full browser; slow and fragile. |
| **Flipkart** | Prices load via JavaScript after the page. Same problem. |
| **Hamleys, Maya Toys** | Not on a feed platform. Custom scraping, breaks often. |
| **Keepa API** | Has real Amazon India history, but €49/month (~₹4,700) and only covers Amazon — blind to the ₹7,680 Toycra gap we found. |
| **BuyHatke / PriceHistoryApp** | Tested with set 42172: "product not found". They cover phones, not LEGO. |

These stay out until the core works. Adding a shop later is one new file (§11).

---

## 5. Matching sets across shops

The LEGO set number (`42172`) is the join key. Getting this right is the difference
between a useful tool and a confidently wrong one.

**Rule: read the set number from the SKU field only — never from the product title.**

This was learned the hard way during design. A title-based match produced:

```
10294 → "PartyCorp Christmas Tree Artificial 4 feet"   ✗
10316 → "PartyCorp Gold Mehndi Alphabet Foil Balloon"  ✗
```

A party balloon was being compared against the ₹63,999 Titanic. SKU-only matching
eliminated every false positive.

**Then: a per-shop rule for "is this actually LEGO?"**

| Shop | Rule | Why |
|---|---|---|
| Official store | accept everything | LEGO-only shop |
| Toycra | accept everything in `/collections/lego` | verified: all 653 have `vendor: LEGO` |
| FunCorp | require `vendor == "Lego"` | general toy shop — 2,000 products, 129 LEGO |

A naive "title must contain LEGO" filter was tried and **wrongly dropped Project Hail
Mary and Shopping Street**, because the official store titles them without the word
"LEGO". Per-shop rules fixed it.

**SKU formats seen in the wild** (all handled):

```
Official store   43269        bare number
Toycra           Lego42172    prefixed
FunCorp          LEG-77243    prefixed + dash
```

**Manual override.** `overrides.yaml` maps a stubborn shop URL to a set number by
hand, for the cases no rule catches. Expected to stay nearly empty; exists so one odd
product never requires a code change.

---

## 6. What gets stored

One append-only CSV, committed to the repo after every run. Plain text, opens in
Excel, readable in ten years, no database.

```csv
date,shop,set_number,price,mrp,in_stock,url,source
2026-10-04,toycra,42172,29399,41199,true,https://...,feed
2026-10-04,official,42172,41199,41199,true,https://...,feed
2026-10-04,amazon,42172,37079,41199,true,https://...,page
```

**Why every column earns its place:**

- `mrp` — separate from price so discounts survive a shop changing its list price
- `in_stock` — a ₹20,000 price on a sold-out set is not a deal
- `source` — `feed` (trustworthy) vs `page` (scraped) vs `manual` (from a screenshot),
  so the alert can say where a number came from
- `url` — so the email links straight to the buy button

Adding a column later leaves a permanent hole in the history. Getting this right
today costs nothing.

**MRP is a sticky maximum, not today's number.** Once we've seen a set at ₹41,199,
that stays the baseline even if the shop temporarily lists it lower. Without this, a
single-source set whose shop briefly marks *up* would anchor MRP to the inflated
figure, and the return to normal would read as a discount — exactly the fake-deal
behaviour the tool exists to catch.

---

## 7. Your Amazon price history (the Rufus workflow)

Amazon's app has **Rufus**, an AI assistant that shows a one-year price chart. It is
real data and it is excellent. It is also unreachable by any script: it lives behind
your login, inside the app, with no public address and active bot protection.

Scraping it would mean impersonating your logged-in phone. That breaks constantly and
is not something worth building.

**So: you hand the tool what Rufus already showed you. Once per set.**

You send a screenshot in a Claude session; the numbers get read off the chart and
written into the watchlist:

```yaml
- set: 42172
  name: McLaren P1
  asin: B0CWH3TBGB
  amazon_low: 20600       # lowest in last year, from Rufus
  amazon_high: 40490
  seen_on: 2026-10-04     # so we know when this went stale
```

Thirty seconds per set, on sets you've already decided you care about. It makes the
tool useful on **day one** instead of after months of watching.

### Why this is better than scraping Rufus would have been

Rufus knows one shop. Your tool watches four. Rufus can't email you at 2am when
Toycra drops 30%.

### The rule that stops this backfiring

`amazon_low` lives in its **own column** and is **never blended** with prices the tool
recorded itself.

Rufus's own footnote says it's the *lowest featured offer price per week, Amazon only,
excluding shipping* — a festival-sale floor. If that were mixed with our observed
lows, a genuinely excellent ₹29,399 at Toycra would be judged against an Amazon flash
sale and the tool would say "wait" forever.

Every alert states which number it compared against. Blank is fine — sets without it
lean on the other signals.

### Staleness

A Rufus low from a year ago is not evidence about today. After **180 days**, alerts
mark it `(stale)` and the weekly digest lists which sets want a fresh screenshot.

---

## 8. Deciding BUY vs WAIT

Five inputs, each with a known trust level:

| Signal | Source | Available from |
|---|---|---|
| Cheapest of all shops today | live feeds | run 1 ✅ |
| Discount vs MRP | live feeds | run 1 ✅ |
| Your Rufus low | you, once | run 1 ✅ |
| Cheapest we've ever recorded | our history | grows weekly 📈 |
| Being discontinued? | age + stock vanishing | run 1, as a hint |

**The verdicts:**

| | Meaning | Exact condition |
|---|---|---|
| 🟢 **BUY NOW** | Best price we can justify | ≥15% off MRP **and** cheapest we've ever recorded **and** in stock |
| 🟡 **GOOD** | Worth considering | ≥15% off MRP, but we've recorded cheaper before |
| 🔴 **WAIT** | At or near full price | Under 15% off MRP |
| ⚫ **BUY BEFORE IT'S GONE** | Don't wait | Looks discontinued (§8.1) — overrides WAIT |

**Why 15%:** below that, a "discount" is usually just shop-to-shop noise. Of the 555
sets sold by both the official store and Toycra, the median gap was 0% — real
discounts sit well clear of that line. Both of today's genuine deals (29% and 20%)
clear it comfortably. The number lives in one config file, changeable without
touching code.

**If `amazon_low` exists**, one extra rule applies: a 🟢 is downgraded to 🟡 when the
price is more than 25% above your Rufus low. That stops the tool calling ₹37,079 a
great deal on a set that has been ₹20,600. It is a separate check with its own
sentence in the email — never silently folded into the MRP maths (§7).

### 8.1 Judging "discontinued"

All three must hold, so a single quiet week doesn't trigger it:

1. Set is **3+ years old** (from its set number / first-seen date), and
2. Out of stock, or vanished from the feed, at **every** shop that used to carry it,
   for **14 consecutive days**, and
3. Where any price is still visible, it's **above** the recorded average

Fewer than three sources makes this weaker, so the email says *"looks like"* and
shows the evidence rather than stating it as fact.

That last one matters: retired LEGO sets rise permanently. "Wait for a deal" is the
wrong advice on a dying set, and a tool that only ever says "wait" would quietly cost
you money.

**Retirement is a hint, not a fact.** There is no public "retiring soon" flag —
verified: Brickset only records `exitDate` *after* a set is gone. We infer from set
age plus stock disappearing across shops, and the email says "looks like" rather than
claiming certainty.

**Every alert shows its own confidence:**

> Comparing against: your Amazon low (₹20,600, 3 days old) · 1 shop · 12 days of history

So you always know whether you're reading a strong signal or a weak one.

---

## 9. Not spamming you

A naive version emails "lowest price!" every day until the sale ends, and you start
ignoring it. Within two weeks the tool is worthless.

The tool remembers what it last told you about each set and emails only on **real
news**:

- a new lowest price
- the verdict changed (🔴 → 🟢)
- back in stock after being gone
- price rose sharply on a set that looks like it's retiring

Plus two rules:
- **Cooldown:** no repeat alert for the same set within 7 days unless the price drops
  further.
- **One email, not six.** All sets with news go in a single message, best deal first.

**Quiet days produce no email at all.** Silence means "nothing worth your attention",
and that's what makes the alerts trustworthy.

An optional **weekly digest** (Sunday) shows everything you're watching, whether or
not there's news — so you never wonder if it's still running.

---

## 10. Where it runs

**GitHub Actions, once a day, free.** Works while your Mac is shut. Price history
saves itself into the repo automatically, so you get a durable dataset at no cost.

```
GitHub Actions (daily)    →  3 Shopify feeds + Amazon attempt  →  commit  →  email
Your Mac (`make check`)   →  same code, Amazon works reliably  →  commit  →  email
```

**What you'll need to set up** — three things, with a walkthrough:

1. A **GitHub account** (free) — runs it and stores your history
2. A **Gmail app password** — so it can email you (stored as a GitHub secret, never
   in the code)
3. ~~A server~~ — not needed. No hosting, no database, no monthly cost.

**Note for the build:** Python's SSL certificates are broken on this Mac (verified —
`CERTIFICATE_VERIFY_FAILED` on every HTTPS call). The project uses a virtual
environment with `certifi` so this doesn't surface later as a mystery failure.

---

## 11. When things break

The tool runs unattended, so failure must be visible but never silent or total.

| What breaks | What happens |
|---|---|
| One shop is down | Skip it, record nothing, note it in the email footer |
| A shop changes its feed | Validate on read; bad rows skipped, never written |
| Amazon blocks the cloud run | Expected. Silent. Local run fills the gap. |
| Price looks absurd (±70% overnight) | Record it, flag it, **don't alert** — likely a glitch |
| Every shop fails | Email: "couldn't check prices today" — never silent |
| Email fails | Run is marked failed so GitHub notifies you |

**The principle:** a quiet day must mean *"nothing to report"*, never *"it broke three
weeks ago"*.

Price history is append-only. A bad run can never corrupt what's already recorded.

---

## 12. How we'll know it's right

The thing that must never happen is a **confidently wrong alert** — telling you to
spend ₹60,000 on a bad deal. Testing is aimed squarely at that.

**Tested against saved real responses** (captured during design, so tests don't hit
the network and don't break when shops change stock):

- Set numbers extract correctly from all three SKU formats
- The party balloon never matches the Titanic
- Project Hail Mary and Shopping Street are *not* dropped by the LEGO filter
- MRP never ratchets down
- Rufus low never contaminates recorded lows
- Verdicts are correct at the boundaries (just-above and just-below each threshold)
- No duplicate alerts; cooldown respected
- One dead shop doesn't fail the run
- Absurd price swings are flagged, not alerted

**End-to-end check before you trust it:** run against the saved day-one data and
confirm it produces exactly the two alerts we already know are correct — McLaren at
₹29,399 and Rivendell at ₹40,399 — and stays silent on the other six.

---

## 13. Deliberately not in v1

Kept out to get something working and trustworthy first:

- lego.com and Flipkart (need a browser)
- A web dashboard — email is the product; a chart is a nice-to-have
- Buying anything automatically
- Price prediction
- Tracking minifigures or used sets
- Telegram/WhatsApp alerts (easy to add later; email first)

---

## 14. Appendix — evidence gathered during design

Everything checked live on 2026-10-04:

| Claim | How verified | Result |
|---|---|---|
| Shopify feeds work | fetched all three | 880 / 653 / 2,000 products |
| SKU = set number | inspected variants | `43269`, `Lego42172`, `LEG-77243` |
| Stock flag present | counted values | Official ✅, FunCorp ✅, Toycra in-stock-only |
| Title matching is unsafe | ran it | balloon matched Titanic |
| "Must say LEGO" is unsafe | ran it | dropped 2 of 8 watchlist sets |
| `vendor` is a clean filter | counted | Toycra 653/653 LEGO; FunCorp 129/2,000 |
| Shops really differ | compared 555 shared sets | median 0%, but up to **34% apart** |
| lego.com blocks us | curl | HTTP 403 |
| Flipkart needs JS | curl | titles present, prices absent |
| Amazon readable directly | `/dp/B0CWH3TBGB` | ₹37,079 + MRP ₹41,199 — matches screenshot |
| Amazon search unreliable | searched set name + number | 4 results, **none the McLaren** |
| Rufus not in page source | grepped mobile + desktop | 0 occurrences |
| Keepa covers India but costs | API probe + pricing | domain 10 valid; €49/mo floor |
| Free history sites don't cover LEGO | queried 42172 | "product not found" |
| No public retirement flag | Brickset docs | only `exitDate`, set *after* retirement |
| Wayback backfill too thin | CDX index | zero snapshots of the feeds |
| Python SSL broken on this Mac | urllib call | `CERTIFICATE_VERIFY_FAILED` |

---

## 15. Starting watchlist

```yaml
- { set: 11389, name: Project Hail Mary,  sources: 1, price: 11999 }
- { set: 10294, name: Titanic,            sources: 1, price: 63999 }
- { set: 11377, name: Minas Tirith,       sources: 1, price: 69999 }
- { set: 10350, name: Tudor Corner,       sources: 1, price: 24499 }
- { set: 11371, name: Shopping Street,    sources: 1, price: 24999 }
- { set: 76269, name: Avengers Tower,     sources: 1, price: 48999 }
- { set: 42172, name: McLaren P1,         sources: 3, price: 29399, asin: B0CWH3TBGB }
- { set: 10316, name: Rivendell,          sources: 2, price: 40399 }
```

Six of these need an Amazon link and a Rufus screenshot to become useful. That's the
first thing to do after the build.
