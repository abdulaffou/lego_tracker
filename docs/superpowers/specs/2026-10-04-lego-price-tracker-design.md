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

`amazon_low` lives in its **own column** and is **never arithmetically combined** with
prices the tool recorded itself. It never shifts MRP, never counts as an observed low,
and never enters the discount calculation.

It does get used — as a **separate gate applied after** the MRP verdict is decided
(§8.1), with its own sentence in the email naming it as your Amazon figure. Separate
check, separate wording, separate column. Never a blended number.

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
| ⚫ **BUY BEFORE IT'S GONE** | Don't wait | Looks discontinued (§8.2) — overrides WAIT |

**Why 15%:** below that, a "discount" is usually just shop-to-shop noise. Of the 555
sets sold by both the official store and Toycra, the median gap was 0% — real
discounts sit well clear of that line. Both of today's genuine deals (29% and 20%)
clear it comfortably. The number lives in one config file, changeable without
touching code.

### 8.1 The Amazon-history gate

When you've supplied a Rufus low **and** high, we know the set's real trading range,
which is far more informative than any single number. Today's best price is placed
within it:

```
       ₹20,600                    ₹29,399                   ₹40,490
       your low  ────────────────── today ────────────────── your high
                 └─────── 44% of the way up the range ───────┘
```

| Where today sits | Effect on the verdict |
|---|---|
| Bottom 25% of the range | Confirms 🟢 — email says "near the lowest you've seen" |
| Middle | 🟢 downgraded to 🟡 — "good, but it has been cheaper" |
| Top 50% | Downgraded to 🔴 — "this is an expensive moment for this set" |

Worked through on your actual numbers: the McLaren at ₹29,399 is 29% off MRP, which
alone would be 🟢. But it sits **44% up its own range**, so it lands at 🟡 — *"good
price, though Amazon has had it at ₹20,600."* That's the honest call, and it's exactly
the judgement the raw MRP discount would have got wrong.

If only `amazon_low` is supplied (no high), fall back to a simple rule: more than 25%
above the low downgrades one step.

For **multi-source** sets this gate can only ever **lower** a verdict. Your Amazon
figure talks you out of a purchase, never into one. For single-source sets a
different rule applies — §8.3.

### 8.3 Single-source sets: history becomes the main signal

Discovered on 2026-10-04 when the real Rufus data arrived, and it broke the design as
written.

**The Titanic case.** Today it's ₹63,999 at the official store — **0% off MRP**, so
the MRP rule says 🔴 WAIT and stays silent. But its Amazon range is ₹57,000–₹98,999,
average ₹86,415, which puts ₹63,999 at **17% — near its floor.** It's one of the best
prices this set has had all year, and the tool would have said nothing.

The flaw: for a LEGO exclusive sold only at the official store, the price **is** the
MRP by definition. "% off MRP" is permanently 0%, so the gate that decides whether to
even consult history never opens. Six of eight watchlist sets are in this state.

**The fix — which signal leads depends on how many shops stock the set:**

| | Leading signal | History's role |
|---|---|---|
| **2+ shops** | % off MRP | Checks and can downgrade (§8.1) |
| **1 shop** | Position in its own range | **Decides** |

For a single-source set with history:

| Position in range | Verdict |
|---|---|
| Bottom 25% | 🟡 **GOOD** — *"near the cheapest this has been"* |
| Bottom 10% | 🟢 **BUY NOW** |
| Above 50% | 🔴 **WAIT** — *"this is a pricey moment"* |

**Safety rails**, because this path can now trigger a buy on history alone:

- Needs **both** `amazon_low` and `amazon_high` — a lone low isn't a range
- Figures older than **180 days** can only downgrade, never promote
- Must be **in stock**
- The email always names the source: *"based on your Amazon history from 4 Oct"*
- A range narrower than **10%** is treated as "never discounts" — no buy signal ever
  (Project Hail Mary is flat at ₹11,999 all year; Shopping Street moves in a ₹1,500
  band. Neither should ever produce excitement.)

**Why this is safe.** The thing being prevented is a confident alert on bad data. Here
the data is yours, read off Amazon's own chart, with its age shown in the email. The
larger risk was the original design: silently saying nothing about six of your eight
sets, forever.

### 8.2 Judging "discontinued"

Deliberately built from **only what we can observe ourselves** — no external API, no
guessing a release year from the set number (set numbers don't encode one, and our own
history starts empty, so any age test would be silent for years).

All three must hold:

1. The set **disappears from the official LEGO store's catalogue** — the strongest
   signal available, since LEGO pulls retiring sets from its own shop first, and
2. It is out of stock or absent at **every** other shop that used to carry it, and
3. This holds for **14 consecutive days** (not a restock gap or a feed hiccup)

Then, if a price is still visible anywhere and it's **above** our recorded average,
that's the confirmation — stock is drying up and resellers are marking up.

Because this is inference, the email says *"looks like it's being discontinued"* and
shows the evidence. It never states it as fact.

*(Set release year from Brickset's free API would sharpen this. Left out of v1 — it
needs its own API key, and the three signals above work without one.)*

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

**End-to-end check before you trust it.** Run against the saved day-one data and
confirm it produces exactly this, with no history and no Rufus figures supplied:

| Set | Expected | Why |
|---|---|---|
| 42172 McLaren P1 | 🟢 **BUY NOW** — ₹29,399 Toycra | 29% off MRP, cheapest on record |
| 10316 Rivendell | 🟢 **BUY NOW** — ₹40,399 Toycra | 20% off MRP, cheapest on record |
| other six | *silent* | 0% off, single source |

Then re-run with the McLaren's Rufus figures (`amazon_low: 20600`,
`amazon_high: 40490`) and confirm the gate does its job:

| Set | Expected | Why |
|---|---|---|
| 42172 McLaren P1 | 🟡 **GOOD** (downgraded) | 44% up its own range — "it has been ₹20,600" |

If that second run still says 🟢, the §8.1 gate isn't wired up, and the tool would be
telling you to spend ₹29,399 without mentioning the set has sold for ₹20,600.

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
showing **0% off MRP** — which the MRP rule alone would have dismissed. See §8.3.
