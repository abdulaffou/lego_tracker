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

Yes — and in both directions, which is the point.

**It would have saved money:**

| Set | Amazon | Toycra | You save |
|---|---|---|---|
| 42172 McLaren P1 | ₹37,079 | **₹29,399** | **₹7,680** |

**And it would have stopped you spending money badly:**

| Set | Looks like | Actually |
|---|---|---|
| 10316 Rivendell | ₹40,399 at Toycra — 20% off MRP, a ₹10,000 saving | Sits **75%** up its own yearly range. Amazon has sold it near **₹25,200**. |
| 76269 Avengers Tower | ₹48,999, same as always | **Above** its yearly high. It has been ₹24,501. |
| 10350 Tudor Corner | ₹24,499, steady | Sitting **at** its yearly peak. It has been ~₹14,500. |

That second table only became visible once the real Amazon history arrived. A
shops-only comparison called Rivendell a ₹10,000 win; against its own history it's an
expensive moment to buy. **Both halves matter, and the second half is the one that
protects real money.**

Every figure here was fetched or read from a chart during design — see §14.

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
| **BuyHatke** | Tested: "page not found" for LEGO sets. |
| **pricehistory.app** | **Partly in — see below.** Works, and has Amazon India history for LEGO. |

These stay out until the core works. Adding a shop later is one new file (§11).

### pricehistory.app — a free Amazon history source

Free, and it genuinely has LEGO. Verified for the Titanic: `Lowest ₹57,000 ·
Highest ₹98,999 · Average ₹86,415`, all three parseable with one regex.

*(An earlier check wrongly dismissed this — the probe hit `pricehistoryapp.com`
instead of `pricehistory.app`.)*

**Limit:** it can only be reached by its exact page URL. Lookup by ASIN 404s, and its
search API sits behind Cloudflare. So you paste the page link once per set, the same
way you paste the Amazon link — and from then on the tool **refreshes the low and high
automatically**, instead of those numbers going stale between screenshots.

Treated like Amazon: best-effort in the cloud, reliable from the local run.

### lego.in is not a separate shop

Worth recording so it never gets added twice: `lego.in` serves the **same catalogue**
as `lego.mybrickhouse.com` — identical Shopify product IDs. One shop, two domains.

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

**When a shop publishes no list price**, `mrp` falls back to the sticky maximum below.
This is common — on the official store, `compare_at_price` is frequently absent or
simply equal to the price, because the shop sells at MRP and has nothing to strike
through.

**MRP is a sticky maximum, not today's number.** Once we've seen a set at ₹41,199,
that stays the baseline even if the shop temporarily lists it lower. Without this, a
single-source set whose shop briefly marks *up* would anchor MRP to the inflated
figure, and the return to normal would read as a discount — exactly the fake-deal
behaviour the tool exists to catch.

---

## 7. Your Amazon price history

Amazon's app has **Rufus**, an AI assistant showing a one-year price chart. Real data,
genuinely good. Also unreachable by any script — it lives behind your login, inside
the app, with no public address and active bot protection. Scraping it would mean
impersonating your logged-in phone, which breaks constantly.

**So you hand the tool what Rufus already showed you. Once per set.**

You send a screenshot; the low and high get read off the chart into the watchlist:

```yaml
- set: 42172
  name: McLaren P1
  asin: B0CWH3TBGB
  amazon_low:  20600
  amazon_high: 40490
  seen_on: 2026-10-04
```

Thirty seconds per set, and the tool is useful on **day one** rather than after
months of watching. Where a `pricehistory.app` link exists (§4), those two numbers
refresh themselves and never go stale.

**Why this beats scraping Rufus.** Rufus knows one shop. Your tool watches four, and
Rufus can't email you at 2am when Toycra drops 30%.

**What these numbers are.** Rufus's own footnote: *lowest featured offer price per
week, Amazon only, excluding shipping*. So they describe Amazon's trading range, not
a cross-shop floor. Read off a graph, they're worth about ±5% — fine for deciding
roughly where in its range a price sits, which is all they're asked to do.

**Staleness.** After **180 days** they can only make the tool more cautious, never
less, and the weekly digest lists which sets want a fresh screenshot.

---

## 8. Deciding BUY vs WAIT

Every set gets one number: **where today's price sits between the cheapest and
dearest it's known to have been.**

```
  cheapest known                    today                    dearest known
      ₹20,600  ──────────────────── ₹29,399 ──────────────────  ₹41,199
               └──────────── 43% of the way up ────────────┘
```

That's the whole rule.

### Building the two ends

| End | Taken from |
|---|---|
| **Top** | MRP, or your Amazon high if that's higher |
| **Bottom** | Your Amazon low, or the cheapest we've recorded — whichever is lower |

Both improve on their own over time: the top is a sticky maximum (§6), and the bottom
drops every time we record a new low.

### The verdict

| Position | | Emails you? |
|---|---|---|
| Bottom 10% | 🟢 **BUY NOW** | yes |
| Bottom 25% | 🟡 **GOOD** | yes |
| 25–50% | ⚪ **FAIR** | weekly digest only |
| Above 50% | 🔴 **WAIT** | no |

**Two sets never produce a buy signal at all.** If the whole range is narrower than
10%, the set simply doesn't discount — Project Hail Mary has been ₹11,999 every day
for a year; Shopping Street moves within ₹1,500. Flagging those would be noise.

**Out of stock is always WAIT.** A brilliant price you can't buy isn't a price.

### Why this replaced the earlier design

The first version had two separate tests — "15% off MRP" and "position in its range" —
plus different rules for single- and multi-source sets. Checking it against your real
data showed they were **the same calculation with different anchors**, and the merged
version produces identical verdicts on all eight sets with a quarter of the logic.

It also fixes a flaw the two-test version had. Titanic is **0% off MRP**, so the MRP
test dismissed it silently — yet its Amazon range is ₹57,000–₹98,999, putting today's
₹63,999 at **17%**, near its floor. For a LEGO exclusive the price *is* the MRP by
definition, so that test could never fire. Six of your eight sets sit in that state.
One rule, anchored on the real range, catches it.

### When there's no history at all

Minas Tirith: one shop, no Amazon listing, no recorded history. Nothing to compare
against, so it falls back to **% off MRP** (≥15% → 🟡) and otherwise stays silent.
Honest, and it starts working the moment any history exists.

### What every alert tells you

> Comparing against: your Amazon range ₹20,600–₹41,199 (read 4 Oct) · 3 shops · 12 days recorded

So you always know whether a verdict rests on solid ground or thin evidence.

### 8.1 Judging "discontinued"

Retired LEGO rises permanently and never comes back, so "wait for a deal" becomes
actively wrong advice on a dying set. That flips everything to ⚫ **BUY BEFORE IT'S
GONE**.

There is no public "retiring soon" flag — verified: Brickset only records `exitDate`
*after* a set is gone. So this is inferred from what we can watch ourselves:

1. The set **vanishes from the official LEGO store's catalogue** — the strongest
   signal, since LEGO pulls retiring sets from its own shop first, and
2. It's out of stock or absent at **every** other shop that carried it, and
3. That holds for **14 consecutive days** — not a restock gap or a feed hiccup

If a price is still visible somewhere and it's **above** our recorded average, that
confirms it: stock drying up, sellers marking up.

Because it's inference, the email says *"looks like it's being discontinued"* and
shows the evidence. Never stated as fact.

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
- Your Amazon figures are kept in their own columns, never written into price history
- A range narrower than 10% never produces a buy signal
- Verdicts are correct at the boundaries (just-above and just-below each threshold)
- No duplicate alerts; cooldown respected
- One dead shop doesn't fail the run
- Absurd price swings are flagged, not alerted

**End-to-end check before you trust it.** Run against the saved day-one data plus the
watchlist in §15, and confirm it produces exactly this:

| Set | Expected | Why |
|---|---|---|
| 10294 Titanic | 🟡 **GOOD** — ₹63,999 | 17% up its range, near its floor |
| 42172 McLaren P1 | ⚪ FAIR — ₹29,399 Toycra | 43% up its range — digest only |
| 10316 Rivendell | 🔴 WAIT | 60% up its range |
| 10350 Tudor Corner | 🔴 WAIT | at its yearly high |
| 76269 Avengers Tower | 🔴 WAIT | at its yearly high |
| 11389 Project Hail Mary | *silent* | range 0% wide — never discounts |
| 11371 Shopping Street | *silent* | range 6% wide — never discounts |
| 11377 Minas Tirith | 🔴 WAIT | no history; 0% off MRP |

**So the first email contains exactly one set: Titanic.** If it contains Rivendell or
Avengers Tower, the range maths is inverted and the tool is recommending the worst
prices of the year.

Then delete every `amazon_low`/`amazon_high` and re-run. Titanic should go quiet, and
McLaren and Rivendell should become 🟡 on the MRP fallback alone — proving the
no-history path works for a set you've not yet screenshotted.

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
| pricehistory.app has LEGO | fetched Titanic page | low ₹57,000 / high ₹98,999 / avg ₹86,415 |
| …but needs the exact URL | tried ASIN + search | 404, and Cloudflare on the API |
| lego.in duplicates mybrickhouse | compared product IDs | identical — one shop |
| Titanic *is* on Amazon, and dearer | found 2 listings | ₹75,890 and ₹97,990 vs ₹63,999 official |
| Minas Tirith not on Amazon India | searched | new set, official store only |

---

## 15. Starting watchlist

The watchlist holds **only what you supply**. Prices, shop counts and verdicts are
worked out fresh on every run — storing them here would let stale numbers masquerade
as truth.

Captured 2026-10-04 from Rufus screenshots, except Titanic (pricehistory.app).

```yaml
# watchlist.yaml — edit by hand, no code needed
- set: 11389
  name: Project Hail Mary
  amazon_low:  11999
  amazon_high: 11999        # flat all year — this set never discounts
  seen_on: 2026-10-04

- set: 10294
  name: Titanic
  asin: B09GPPP2NK
  amazon_low:  57000
  amazon_high: 98999        # avg 86,415 — Amazon is a bad place to buy this
  source: pricehistory.app
  seen_on: 2026-10-04

- set: 11377
  name: Minas Tirith
  # NO HISTORY — brand new set, not listed on Amazon India yet.
  # Official store only, ₹69,999. Recheck in a few months.

- set: 10350
  name: Tudor Corner
  amazon_low:  14500        # chart estimate
  amazon_high: 24501
  seen_on: 2026-10-04

- set: 11371
  name: Shopping Street
  amazon_low:  24479
  amazon_high: 25999        # very narrow band, barely moves
  seen_on: 2026-10-04

- set: 76269
  name: Avengers Tower
  amazon_low:  24501        # chart estimate
  amazon_high: 48021
  seen_on: 2026-10-04

- set: 42172
  name: McLaren P1
  asin: B0CWH3TBGB          # verified working
  amazon_low:  20600
  amazon_high: 40490
  seen_on: 2026-10-04

- set: 10316
  name: Rivendell
  amazon_low:  25200        # chart estimate
  amazon_high: 45392
  seen_on: 2026-10-04
```

**Chart estimates are eyeballed from a Rufus graph**, so treat them as roughly ±5%.
The ones Rufus states in words (₹20,600; ₹11,999) and the pricehistory.app figures are
exact. Precision isn't critical — these decide *roughly where in its range* a price
sits, not the verdict on their own.

### What this data immediately revealed

| Set | Today | Where it sits in its own range | Reading |
|---|---|---|---|
| 76269 Avengers Tower | ₹48,999 | **104%** — above its yearly high | Worst possible moment |
| 10350 Tudor Corner | ₹24,499 | **100%** — at its yearly high | Worst possible moment |
| 10316 Rivendell | ₹40,399 | **75%** | Expensive, despite 20% off MRP |
| 42172 McLaren P1 | ₹29,399 | **44%** | Fair, not a steal |
| 11371 Shopping Street | ₹24,999 | 34% | Barely moves; band is ₹1,500 wide |
| **10294 Titanic** | **₹63,999** | **17%** | **Genuinely cheap right now** |
| 11389 Project Hail Mary | ₹11,999 | flat | Has never discounted. Ever. |
| 11377 Minas Tirith | ₹69,999 | no data | Unknown |

Two sets are at or above their yearly peak. One (Titanic) is near its floor while
showing **0% off MRP** — which a discount-only rule would have dismissed. See §8.
