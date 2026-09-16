# Leo Express Night Train Monitoring — Use Case

## Goal

Track how prices and availability evolve over time for Leo Express night trains
(LE232/LE235, launched summer 2026) to understand their pricing mechanics and
market acceptance.

## Research Questions

### 1. Price Dynamics
- Do prices change based on demand (capacity-driven) or on a fixed schedule (date-driven)?
- How far in advance do price increases happen?
- Are there price drops for low-demand dates, or only increases?
- What are the discrete price tiers per class?

### 2. Demand & Capacity
- How fast do sleeper compartments sell?
- Which routes/days fill first?
- Is there a correlation between remaining capacity and price level?
- At what capacity threshold do prices jump?

### 3. Service Acceptance
- How quickly are seats selling compared to total capacity?
- Are certain weekdays consistently fuller?
- Does the Przemyśl route (new market) sell differently from Frankfurt (established corridor)?
- Is Business class used at all on the short Frankfurt leg?

### 4. Currency Arbitrage
- Do CZK/EUR/PLN prices move independently?
- Are there windows where one currency is significantly cheaper?
- Does the fixed 24:1 CZK:EUR internal rate create persistent arbitrage vs market rates (~25.3:1)?

## Timetable

### Service periods (Gültigkeit)

| # | Dates | Polish section | Frankfurt Flughafen | Notes |
|---|-------|----------------|---------------------|-------|
| 1 | 25.7 – 29.7 | No | No | Launch week |
| 2 | 30.7 | No | No | Transition day |
| 3 | 31.7 | LE235 only (Tue–Sat) | No | Transition day |
| 4 | 1.8 – 29.8 | Variant A only (5 days/wk) | No | Main summer |
| 5 | 30.8 – 16.9 | No | No | Daily, no variants |
| 6 | 17.9 – 12.12 | No (PL timetable pending) | Yes (partial) | Until timetable change |

### Period 4 (1.8–29.8) — Variants

| Variant | LE235 departs | LE232 arrives | Polish section |
|---------|---------------|---------------|----------------|
| A | Tue, Wed, Thu, Fri, Sat | Wed, Thu, Fri, Sat, Sun | Yes |
| B | Mon, Sun | Mon, Tue | No (Bohumín terminus) |

LE235 departs evening, arrives next morning — "Tue departure" = "Wed arrival".
LE232 Polish leg is a daytime feeder: Przemyśl 12:04 → Bohumín 17:57.

### Period 5 (30.8–16.9)

No variants, Bohumín ↔ Frankfurt only (all intermediate Moravian stops served),
same timings as period 1 (Bohumín dep 17:45 eastbound). **Not daily** — see the
data-verified operating days below (Tue is a full rest day, Mon/Wed run only on
the western leg).

### Period 6 (17.9–12.12) — Variants

| Variant | LE235 departs | LE232 arrives | Flughafen |
|---------|---------------|---------------|-----------|
| A | Mon, Sun | Mon, Tue | LE232 continues to Flughafen (arr 07:53) |
| B | Tue, Wed, Thu, Fri, Sat | Wed, Thu, Fri, Sat, Sun | LE235 starts from Flughafen (dep 14:39) |

Polish section not yet available for this period (timetable pending).
Slight timing differences: Frankfurt Süd arr 07:26 (A) vs 07:22 (B).

### Key times (stable across most periods)

| Station | LE232 (→ Frankfurt) | LE235 (→ East) |
|---------|--------------------|--------------------|
| Przemyśl Główny | dep 12:04 | arr 11:25 |
| Bohumín | dep 17:45/17:57 | dep 05:36/06:01 |
| Ostrava hl. n. | dep 17:56/18:05 | dep 05:27 |
| Olomouc hl. n. | dep 19:21 | dep 04:08 |
| Praha hl. n. | dep 22:32 | dep 01:17 |
| Dresden Hbf | dep 01:38 | dep 22:30 |
| Leipzig Hbf | dep 02:54 | dep 20:43 |
| Weimar | dep 04:07 | dep 18:59 |
| Erfurt Hbf | dep 04:23 | dep 18:44 |
| Fulda | dep 05:59 | dep 16:54 |
| Frankfurt/Main-Süd | arr 07:22–07:26 | dep 15:03 |
| Frankfurt Flughafen | arr 07:53 (P6 A) | dep 14:39 (P6 B) |

### Beförderungsverbot

Local trips between Polish stations (marked with same symbol) are forbidden —
the train cannot be used for domestic Polish travel.

### Operating days (data-verified across all snapshots, 2026-07-29 – 2026-09-07)

Derived from every travel date ever offered per route (error markers excluded),
grouped by ISO week. Two distinct patterns emerge:

**German/Czech core (Weimar ↔ Bohumín): daily, no reduction.**
Both directions sold all 7 weekdays every week from KW32 (3.8) through KW49
(30.11); the odd 6-day week is a single missing date, not a pattern. This leg
never thinned out.

**Polish section (Weimar ↔ Przemyśl): reduced on 2026-08-31 (KW35 → KW36).**

| Period | weimar→przemysl (east) | przemysl→weimar (west) |
|--------|------------------------|------------------------|
| KW32–35 (3.–29.8) | Tue, Wed, Thu, Fri, Sat (5 days) | Wed, Thu, Fri, Sat, Sun (5 days) |
| **KW36+ (from 31.8)** | **Thu, Fri, Sat (3 days)** | **Thu, Fri, Sat, Sun (4 days)** |

Tue+Wed dropped from the eastbound Przemyśl run; Wed dropped from the westbound.
The westbound weekday is shifted +1 vs eastbound because the Polish leg is a
daytime feeder (Przemyśl 12:04 → Bohumín 17:57, i.e. the day after the eastbound
overnight arrival).

This matches Scotty exactly (base clause Tue–Sat narrowed to Thu–Sat from 1.9)
and the website validity 29.8–24.10.2026.

**Answer to "was there ever daily service?"** Yes — but only on the Weimar↔Bohumín
core, which is still daily. The Przemyśl section was never daily: it started at 5
weekdays (Tue–Sat) and was cut to 3 (Thu–Sat eastbound) on **31.8.2026**. Cause
not stated by the operator (demand, rolling-stock rotation, or Polish-side
pathing).

Spot checks (all snapshots, not just the latest):
- Tue 2026-09-08 / Wed 2026-09-09: Weimar↔Bohumín **sold** (ECO ~100+ both
  directions); Weimar↔Przemyśl **never sold** → core runs, Polish leg does not.

Method note: judging operating days from a *single* (latest) snapshot is
misleading — near-term dates fall out of the rolling scrape window and look
"absent". Always aggregate across snapshots (as above). An earlier read of the
2026-09-07 snapshot alone wrongly suggested Tue was a full rest day.

Note: the scraper queries 6 routes (weimar↔przemysl, weimar↔frankfurt,
weimar↔bohumin) — there is no direct frankfurt↔przemysl query, so Przemyśl
coverage is via the weimar↔przemysl pair.

## Method

Daily automated snapshots at 00:00 (via `run-all.sh`) capture:
- 6 routes (3 city pairs × 2 directions) × 2 currencies (CZK, EUR)
- 136-day rolling window
- Per date: all travel classes with price, capacity, promo flag

Stored as JSON on Raspberry Pi (`~/Projects/leo-availability/data/`).
Filename format: `YYYYMMDD_route-currency.json`

### Bohumín fallback

On days without Przemyśl service, the script could query Weimar ↔ Bohumín
instead to still capture pricing/capacity for the night portion. These results
must be flagged (`"route_variant": "bohumin"`) to distinguish from full
Przemyśl runs in analysis.

## Observable Signals

| Signal | Indicates |
|--------|-----------|
| Price increase between snapshots | Demand threshold crossed |
| Capacity decrease without price change | Steady sales at current tier |
| Capacity decrease WITH price change | Dynamic pricing trigger |
| Price decrease | Demand management / unsold inventory |
| Capacity increase | Cancellations or released contingent |
| Flat prices + slow capacity decline | Low demand, no pricing response |
| EUR price diverging from CZK/24 | Independent EUR pricing (not just converted) |

## Data Quality & Detection Caveats

Snapshots occasionally contain gaps that must not be mistaken for real market
events. Two effects are known and handled in `lib/analysis.py`:

### 1. API error entries (`__error__`)

The Leo GraphQL endpoint sometimes returns an empty response for a single
travel-date query. The scraper stores this as `{"error": "Expecting value: line 1
column 1 (char 0)"}` for that date; the rest of the snapshot is intact (normal
file size). `lib/loaders.py` keeps these as an `__error__` marker
(`is_error_entry()`), and `anomaly_scan` skips any date whose entry errored in
either snapshot — so "data missing" is never reported as a sellout or a fresh
appearance.

Occurrences of `Expecting value` (as of 2026-09-07): 165 total, concentrated on
2026-08-23 (161, a broad Leo API outage on bohumin-weimar / weimar-bohumin) plus
single hits on 01.08, 03.08, 04.08 and 06.09. The 06.09 hit removed
bohumin-weimar 2026-09-25 for that day only (capacity was 2 sleeper berths before
and after — no sellout).

The far more common `"Noch keine Tickets verfügbar"` (~10 200 entries) is not an
error: those are future dates before their sales window opens.

### 2. Scrape-window gaps (implausible capacity jumps)

On some days the scraper captured a smaller set of future dates, so many dates
are simply absent from that snapshot. Naively this looks like every class sold
out at once. Physically impossible: capacity is a hard limit that only moves via
bookings/cancellations, so a jump from many free places to "gone" in one daily
step is a data gap, not a sellout.

`anomaly_scan` therefore reports a sellout only when the previous snapshot's
remaining capacity was low (`SELLOUT_MAX_PREV_CAP = 10`). Example filtered out:
2026-08-19 flagged ~87 "sellouts" where the prior snapshot still showed ECO
capacity 82–104 — all scrape-window gaps, zero real sellouts.

**Net effect:** the two guards removed 87 false-positive Leo sellouts (down to 0
credible sellouts as of 2026-09-07). A genuine sellout (capacity declining to a
low single-digit remainder, then gone) is still reported.

## Analysis Plan

Once multiple days of data exist:
1. **Daily diff**: What changed since yesterday? (prices, capacity)
2. **Trend charts**: Price and capacity per class over time for a fixed travel date
3. **Fill rate**: Days until a class sells out (or stops declining)
4. **Price tier mapping**: Identify discrete price levels and what triggers transitions
5. **Weekend vs weekday**: Systematic demand differences
6. **Booking horizon effect**: Same travel date observed 30, 20, 10, 5 days out

## Expected Insights

- Leo likely uses 4-5 discrete price tiers per class (based on current data: 899, 1649, 2469, 3289, 4939 CZK for Sleeper)
- Frankfurt leg has flat pricing (low demand, short distance, mainly serves as feeder)
- Przemyśl route shows classic yield management with 449% price range
- CZK payment is structurally ~5% cheaper than EUR due to favorable internal exchange rate

## Sleeper Car Configuration (discovered 2026-07-31)

### Physical Layout: RIC B6-1

Single sleeper car per train, 10 compartments × 4 berths = 40 total.

| Compartments | Seats | Class | Category |
|---|---|---|---|
| 1–5 (front) | 1–20 | 8 (ECOSLEEPERLADY) | Women-only |
| 6–10 (rear) | 21–40 | 7 (ECOSLEEPER) | Mixed |

### Allocation Model: Static Pre-Assignment

Tested via `carsWithFreeSeats` API with two orders (one per class) on the same train:

- **Zero seat overlap** between Sleeper and Lady selections
- Sleeper ticket → only sees seats 21–40
- Lady ticket → only sees seats 1–20
- Both are in the same physical car (RIC B6-1, car ID 161)

Conclusion: Compartments are **permanently assigned** to their category, not dynamically allocated based on bookings. This means:
- Unsold Lady berths can never be sold to men, regardless of demand
- Unsold Sleeper berths can never be sold as Lady, even if Lady is full
- The 50/50 split is fixed at 20 berths each

### Pricing Implications

Lady typically sits at lower price tiers because:
1. Smaller addressable market (only women) → lower demand pressure
2. Fixed allocation means Leo must use low prices to fill the Lady half
3. The mixed Sleeper has higher demand (everyone books it) → fills tiers faster

*Sleeper and Lady share identische Preismodelle (gleiche Tier-Werte, gleicher km-Satz).
Der Preisunterschied entsteht rein durch unterschiedliche Nachfrage/Auslastung.*

On high-demand days, Sleeper sells out while Lady berths remain empty — this is structural waste from the fixed allocation, not a pricing failure.

### API Details

- Car: `RIC B6-1` (car ID 161 observed, may vary by date)
- `classes` field on car object: `[7, 8]` (both classes shown in same car)
- `carsWithFreeSeats` returns different `free_seats` lists depending on which ticket class is queried
- Seat `class_id` in assignment response matches the booked class (7 or 8)
- The API also shows RIC PRM2-1 (Economy, class 3) and RIC B3-1 (Business, class 1) but with 0 free seats for sleeper tickets

### Capacity Numbers in Availability Data

The `capacity` field from `searchConnections` counts **all remaining berths** in the respective half (including any seats temporarily held by unpaid orders). On Aug 13 at booking:
- System shows: Sleeper cap=55, Lady cap=46 (totals including held reservations)
- Actually selectable: Sleeper 9, Lady 15 (after subtracting booked + held)

Note: The capacity numbers exceed 20 per half because the API reports aggregate availability across all segments (different boarding stations share the same physical berths but are counted separately for each origin-destination pair).

## Pricing Model (confirmed 2026-07-31)

### Discrete Price Tiers

Sleeper and Lady use identical tier values (EUR): 37.5 → 68.7 → 102.9 → 137.0 → 205.8

*Note: The earlier observation of a 52.9€ tier was from the Frankfurt route.
The Przemyśl route has 5 tiers (without 52.9). Tier values are route-dependent
(see "Updated Tier Analysis" below).*

Each tier has a fixed allocation of seats. Once a tier's seats are sold, the price jumps to the next level. Confirmed via multi-person search queries (1–14 persons on Aug 29):

| Tier | EUR | Sleeper seats (Aug 29) | Lady seats (Aug 29) |
|------|------|----------------------|--------------------|
| 1 | 37.5 | (sold out) | (sold out) |
| 3 | 68.7 | 2 | (sold out) |
| 4 | 102.9 | 3 | 3 |
| 5 | 137.0 | 3 | 3 |
| 6 | 205.8 | 6 | 6 |

Total available: 14 Sleeper + 12 Lady = 26 (of 40 physical berths).

### Multi-Person Pricing

The API returns a single per-person price for an N-person request; total = N ×
per-person. All seats in one request are priced **flat at the same per-person
level**, and that level rises with N as the request is measured against the
current tier's remaining capacity. Verified live 2026-09-15 (Sleeper, weimar–
przemyśl 22.10., createOrder item prices):

- n=2: 150.8/pp (301.6 total)
- n=3: 176.2/pp (528.6 total) — all three items 176.2, **not** 2×150.8 + 1×higher
- n=4: 188.7/pp (754.8 total)
- n=5: 196.2/pp (981.0 total)

Every `order_item` in a createOrder carries the identical per-person price.

*Correction: an earlier observation (Aug 29) described cascading pricing where
successive seats sat on increasing tiers (e.g. 3 persons = 2×68.7 + 1×102.9). The
current behaviour is flat — one uniform per-person price for the whole request that
steps up with N.*

### Key Behaviors

- **Searches do not block seats** — capacity unchanged after 20 sequential queries
- **Unpaid orders do not affect search capacity** — createOrder holds a seat but searchConnections still shows it as available
- **Tiers are reversible** — cancellations restore seats and can drop the price to a lower tier
- **Class overflow** — searching for more persons than available shows capacity=0 for that class

### class_info Mapping (API quirk)

`searchConnections` returns `classes[]` and `class_info[]` arrays that are NOT index-aligned. The correct join key is `class_info[n].record_id == classes[m].id`. Naive index-based pairing produces wrong class-to-price assignments.

### Tier Thresholds (absolute and %)

Based on multi-person searches and snapshot data (20 berths per half):

| Tier | EUR | Starts at (sold) | Occupancy | Seats on tier | % increase |
|------|------|-----------------|-----------|---------------|------------|
| 1 | 37.5 | 0 | 0% | } 6 combined | — |
| 2 | 52.9 | ? | ? | } (T1+T2) | +41% |
| 3 | 68.7 | 6 | 30% | 2 | +30% |
| 4 | 102.9 | 8 | 40% | 3 | +50% |
| 5 | 137.0 | 11 | 55% | 3 | +33% |
| 6 | 205.8 | 14 | 70% | 6 | +50% |

Lady differs: T1+T2+T3 combined = 8 seats (vs 6 for Sleeper). Lady has broader cheap tiers to incentivize filling the women-only half.

The last 6 seats (30% remaining capacity) are always at max price (205.8 EUR).

### Next Steps

- After Aug 30 (Polish timetable change): full 40-berth capacity resets on new service pattern. Repeat multi-person test to determine T1/T2 split with fresh data.
- Track whether tier allocation changes seasonally or remains fixed.

### Price Tier Visualization

`
Preisstufen Leo Express Sleeper (EUR)

205.8 │                                          ██████████████████
      │                                          ██████████████████  +50%
137.0 │                              ████████████
      │                              ████████████  +33%
102.9 │                  ████████████
      │                  ████████████  +50%
 68.7 │          ████████
      │          ████████  +30%
 52.9 │      ████
      │      ████  +41%
 37.5 │  ████
      │  ████
      └──────────────────────────────────────────────────────────
         0%      ~20%    30%     40%      55%       70%      100%
         T1      T2      T3      T4       T5        T6
                    Auslastung (verkaufte Plätze)
`

### Percentage Increases Between Tiers

| Transition | Increase | Factor | Absolute Δ |
|---|---|---|---|
| T1 → T2 | +41% | ×1.41 | +15.4 € |
| T2 → T3 | +30% | ×1.30 | +15.8 € |
| T3 → T4 | +50% | ×1.50 | +34.2 € |
| T4 → T5 | +33% | ×1.33 | +34.1 € |
| T5 → T6 | +50% | ×1.50 | +68.8 € |
| **T1 → T6** | **+449%** | **×5.49** | **+168.3 €** |

Pattern: jumps alternate between ~30-41% and ~50%. The steepest absolute jump is T5→T6
(+68.8 €). Overall spread (×5.49) is significantly more aggressive than typical European
rail yield management (DB Sparpreis: ~×2-3 spread).

Early bookers at T1 pay less than one fifth of the last-minute price.

### Voucher × Tier Interaction (LE50 "1+50%")

The LE50 promo (see timeline, live from 14.09.2026) gives **50% off the cheaper
ticket of each pair** (= 25% off the pair when both sit on the same tier). It is
valid for Economy (3), Economy Sleeper (7), and Economy Sleeper Lady (8);
`conditions.class_id: [8, 7, 3]`. For n tickets it forms `floor(n/2)` pairs; an odd
leftover ticket stays full price.

This interacts badly with LEO's cascading multi-person pricing. Successive seats in
one search are priced at **increasing tiers** (not all at one tier — unlike RDC/SJ).
So a 2-seat request can already straddle a tier boundary, and the second, more
expensive seat can erode or exceed the voucher saving.

Decision rule for a pair with prices `p1 ≤ p2`:
- Voucher saving = `0.5 · p1`
- Tier-jump surcharge on the 2nd seat = `p2 − p1`
- **The voucher only pays off while `p2 − p1 ≤ 0.5 · p1`, i.e. `p2 ≤ 1.5 · p1`.**

Applied to the Sleeper ladder (37.5 / 68.7 / 102.9 / 137.0 / 205.8):

| Pair | Surcharge (p2−p1) | Saving (0.5·p1) | Verdict |
|------|-------------------|-----------------|---------|
| same tier | 0 | 0.5·p1 | full 25% saving |
| T3→T4 (68.7→102.9) | 34.2 | 34.4 | break-even (+0.1 in favour) |
| T4→T5 (102.9→137.0) | 34.1 | 51.5 | voucher wins (−17.4) |
| **T5→T6 (137.0→205.8)** | **68.8** | **68.5** | **surcharge eats saving (+0.3 worse)** |

Consequence for cheapest booking: **book in pairs where both seats stay on the same
tier.** Before booking, probe the multi-person search to find the n at which the
per-person average jumps (= remaining seats in the current tier), then book only as
many pairs as fit. The jump onto the top tier (T6) makes the voucher effectively
worthless. Because searches don't block seats and unpaid orders restore capacity on
delete, this probing is free.

### Voucher Pairing on Tariff Mixes (verified 2026-09-15)

With mixed tariffs the API forms pairs by **like tariff** (adult+adult,
child+child), not adult+child, and applies the 50% voucher to the cheaper ticket of
each pair. This is the **customer-favourable** pairing:

- 2 adult + 2 child → pairs (adult+adult) and (child+child)
  - LE50 = 0.5·adult + 0.5·child
- The naive alternative (two adult+child pairs) would discount the child in each
  pair → LE50 = 2 × 0.5·child, i.e. far less.

Verified: 2×113.3 (adult) + 2×32.1 (child) → LE50 56.7 (adult pair) + 16.1 (child
pair) = 72.8, vs. only 32.1 if paired adult+child. The rule generalises: because the
voucher hits the cheapest ticket in a pair, grouping the **expensive** tickets
together maximises the discount, and the API does exactly that.

4-tariff example (adult+student+child+child6, Lady): pairs (adult+student) and
(child+child6) → LE50 74.0 + 26.8.

Per-country reductions are CZ-heavy: children ride free in CZ (100%), student/senior
reductions apply on the CZ leg only; DE/PL legs stay closer to full fare.

### Cancellation Policy (from Transport Conditions PDF)

- Cancellation allowed up to **15 minutes before departure**
- Transaction fee: **30 CZK (~1.20 EUR)** per ticket (deducted from refund)
- Smile Club members: cancel up to departure, refund as Leo Credits (no fee)
- Promo tickets: cancellable but **no refund** of any kind
- Tickets <30 CZK: fee equals ticket price (i.e., no refund)
- Refund processed within 1 month
- Carbon offset fee: non-refundable

Delay compensation:
- 60–119 min delay: 25% of ticket price
- 120+ min delay: 50% of ticket price
- Claim within 6 months via le.cz/refund

### Booking Capacity Blocking (corrected 2026-07-31)

Previous finding was WRONG (caused by class_info mapping bug). Corrected:

- **GraphQL `createOrder` DOES block capacity immediately** (confirmed: 5 orders reduced Sleeper from 13→8)
- **Deleting the order restores capacity instantly**
- **Searches (`searchConnections`) do NOT block** anything (confirmed: 20 sequential searches, zero change)
- REST `/api/order/process-order` requires browser session (XSRF token), returns 500 without it

Implication: The 15-minute order timer is the blocking window. Unpaid orders hold seats for 15 min (extendable via `prolongOrder`), then auto-release.

### CZK Price Tiers (canonical values)

CZK is the internal base currency. EUR values are CZK÷24 (rounded). CZK shows cleaner patterns:

**Sleeper/Lady tiers (CZK):**

| Tier | CZK | EUR (÷24) | Δ CZK | Pattern |
|------|------|-----------|-------|---------|
| 1 | 899 | 37.5 | — | |
| 2 | 1269 | 52.9 | +370 | |
| 3 | 1649 | 68.7 | +380 | ~+380 |
| 4 | 2469 | 102.9 | +820 | ~2×380 |
| 5 | 3289 | 137.0 | +820 | ~2×380 |
| 6 | 4939 | 205.8 | +1650 | ~4×380 |

**Economy tiers (CZK, Weimar→Przemyśl):**

| Tier | CZK | EUR (÷24) | Δ CZK | Pattern |
|------|------|-----------|-------|---------|
| 1 | 829 | 34.5 | — | |
| 2 | 1239 | 51.6 | +410 | ~+410 |
| 3 | 1649 | 68.7 | +410 | ~+410 |
| 4 | 2469 | 102.9 | +820 | ~2×410 |

Capacity thresholds (observed from 8 daily snapshots, to be refined):

| Tier | Capacity range | Approx. threshold (seats sold) |
|------|---------------|-------------------------------|
| T1 | 57–62 | 0–~5 seats sold |
| T2 | 43–56 | ~6–~19 seats sold |
| T3 | 30–42 | ~20–~32 seats sold |
| T4 | 8–26 | ~36+ seats sold |

Total Economy seats: ~62 (max observed capacity).
Spread: ×3.0 (+198%). Significantly less aggressive than Sleeper/Business.

`
Preisstufen Leo Express Economy (EUR, Weimar→Przemyśl)

102.9 │                              ████████████████████████████
      │                              ████████████████████████████  +50%
 68.7 │                  ████████████
      │                  ████████████  +33%
 51.6 │          ████████
      │          ████████  +49%
 34.5 │  ████████
      │  ████████
      └──────────────────────────────────────────────────────────
         0%         ~10%        ~30%          ~55%          100%
         T1          T2          T3            T4
                    Auslastung (verkaufte Plätze)
`

Economy tier transitions:

| Transition | Increase | Factor | Absolute Δ |
|---|---|---|---|
| T1 → T2 | +49% | ×1.49 | +17.1 € |
| T2 → T3 | +33% | ×1.33 | +17.1 € |
| T3 → T4 | +50% | ×1.50 | +34.2 € |
| **T1 → T4** | **+198%** | **×2.98** | **+68.4 €** |

Pattern: Economy uses the same building block as Sleeper (+410 CZK ≈ +380 CZK for Sleeper)
but has only 4 tiers. The T3→T4 jump doubles the delta, matching the Sleeper pattern.
Economy maxes out at the same CZK value as Sleeper T4 (2469 CZK) — there is no
Economy equivalent of Sleeper T5/T6.

**Business tiers (CZK, Weimar→Przemyśl):**

| Tier | CZK | EUR (÷24) | Δ CZK | Pattern |
|------|------|-----------|-------|---------|
| 1 | 599 | 25.0 | — | |
| 2 | 1069 | 44.5 | +470 | ~+470 |
| 3 | 1609 | 67.0 | +540 | ~+530 |
| 4 | 2139 | 89.1 | +530 | ~+530 |
| 5 | 3209 | 133.7 | +1070 | ~2×530 |

Capacity thresholds (observed, to be refined):

| Tier | Capacity range | Approx. threshold (seats sold) |
|------|---------------|-------------------------------|
| T1 | ~50 | 0 seats sold (launch price) |
| T2 | 39–49 | ~1–~11 seats sold |
| T3 | 32–43 | ~7–~18 seats sold |
| T4 | 24–32 | ~18–~26 seats sold |
| T5 | 12–22 | ~28+ seats sold |

Total Business seats: ~50 (max observed capacity).
Spread: ×5.4 (+436%). Comparable to Sleeper aggression.

Note: T1 (599 CZK = 25€) was only observed on 8 dates (fresh booking horizon opening).
It sells out extremely fast — most snapshots start at T2. T1 may be a promotional
launch tier or limited to the first 1–2 seats.

`
Preisstufen Leo Express Business (EUR, Weimar→Przemyśl)

133.7 │                                          ██████████████████
      │                                          ██████████████████  +50%
 89.1 │                          ████████████████
      │                          ████████████████  +33%
 67.0 │              ████████████
      │              ████████████  +51%
 44.5 │      ████████
      │      ████████  +78%
 25.0 │  ██
      │  ██
      └──────────────────────────────────────────────────────────
         0%   ~2%     ~15%        ~35%         ~55%         100%
         T1    T2      T3          T4           T5
                    Auslastung (verkaufte Plätze)
`

Business tier transitions:

| Transition | Increase | Factor | Absolute Δ |
|---|---|---|---|
| T1 → T2 | +78% | ×1.78 | +19.5 € |
| T2 → T3 | +51% | ×1.51 | +22.5 € |
| T3 → T4 | +33% | ×1.33 | +22.1 € |
| T4 → T5 | +50% | ×1.50 | +44.6 € |
| **T1 → T5** | **+436%** | **×5.36** | **+108.7 €** |

Pattern: Business has a massive T1→T2 jump (+78%), then stabilizes into the familiar
alternating +33%/+50% pattern. The T4→T5 jump doubles the delta (~1070 vs ~530 CZK),
consistent with the Sleeper upper-tier doubling.

### Cross-Class Tier Comparison

| Property | Economy | Business | Sleeper |
|----------|---------|----------|---------|
| Tiers | 4 | 5 | 6 |
| Base price (CZK) | 829 | 599 | 899 |
| Max price (CZK) | 2469 | 3209 | 4939 |
| Spread | ×3.0 | ×5.4 | ×5.5 |
| Base Δ (CZK) | ~410 | ~530 | ~380 |
| Doubling point | T3→T4 | T4→T5 | T3→T4 |
| Total seats | ~62 | ~50 | 20 |

Key insight: Business starts cheaper than Economy (599 vs 829 CZK) but overtakes it
at T3 (1609 vs 1649 CZK — nearly identical). By T5, Business is 30% more expensive
than Economy T4. The aggressive Business spread compensates for its lower seat count.

All three classes share the same structural pattern: linear deltas in lower tiers,
doubling in upper tiers. The doubling signals the "scarcity premium" zone where
remaining capacity drops below ~40%.

*Data basis: 14 daily snapshots (2026-07-29 to 2026-08-11), Weimar→Przemyśl route.
Tier boundaries have been significantly refined (see "Tier Boundaries" section below).*

### Full Multi-Person Test Data (Aug 29, Weimar→Przemyśl)

Sleeper (13 free, starts T3):
| # | EUR/pp | Δ EUR | CZK/pp | Δ CZK |
|---|--------|-------|--------|-------|
| 1 | 68.7 | 68.7 | 1649 | 1649 |
| 2 | 85.8 | 102.9 | 2059 | 2469 |
| 3 | 91.6 | 103.2 | 2199 | 2479 |
| 4 | 94.5 | 103.2 | 2269 | 2479 |
| 5 | 102.9 | 136.5 | 2469 | 3269 |
| 6 | 108.7 | 137.7 | 2609 | 3309 |
| 7 | 112.9 | 138.1 | 2709 | 3309 |
| 8 | 124.5 | 205.7 | 2989 | 4949 |
| 9 | 133.3 | 203.7 | 3199 | 4879 |
| 10 | 140.8 | 208.3 | 3379 | 4999 |
| 11 | 146.6 | 204.6 | 3519 | 4919 |
| 12 | 151.6 | 206.6 | 3639 | 4959 |
| 13 | 155.8 | 206.2 | 3739 | 4939 |

Deduced tier allocation for this day: 1×T3(1649) + 3×T4(2469) + 3×T5(3289) + 6×T6(4939) = 13 seats.

## Updated Tier Analysis (2026-08-08, 11 snapshots)

### Key findings

1. **Tiers are route-dependent** — different routes have entirely different price grids
   (not just offsets). Likely driven by distance and/or countries traversed.

2. **Direction does not matter** — W→PL and PL→W show identical tier values.

3. **Temporary surcharges exist** — on 2026-08-03 and 2026-08-04, all prices were ~3-5%
   above canonical tiers WITHOUT capacity changes. This reversed after 1-2 days.
   Possible explanations: A/B test, demand surge pricing layer, or weekend premium.

4. **Cheapest tiers sell out fast** — T1 (37.5€ on Przemyśl) was only observed once
   (first snapshot day, cap=15). By the time daily tracking started, most dates were
   already at T3+. September data (new booking horizon) will reveal full tier structure.

### Canonical tiers per route (EUR, from `leo-tiers.py`)

**Przemyśl route (Sleeper/Lady, 5 tiers):**

| Tier | EUR | CZK | Capacity range | Transition |
|------|-----|-----|----------------|------------|
| T1 | 37.5 | 899 | ~15 (full) | — |
| T2 | 68.7 | 1649 | 13-14 | +83% |
| T3 | 102.9 | 2469 | 10-12 | +50% |
| T4 | 137.0 | 3289 | 7-9 | +33% |
| T5 | 205.8 | 4939 | 1-6 | +50% |

Spread: ×5.49 (449%)

**Bohumín route (Sleeper/Lady, 5 tiers):**

| Tier | EUR | CZK | Capacity range | Transition |
|------|-----|-----|----------------|------------|
| T1 | 37.5 | 899 | ~14 | — |
| T2 | 64.1 | 1539 | 10-12 | +71% |
| T3 | 85.8 | 2059 | 7-9 | +34% |
| T4 | 128.3 | 3079 | ~5 | +50% |
| T5 | ? | ? | ? | (not yet observed) |

Spread (T1-T5): ×3.42 (242%)

**Frankfurt route (Sleeper/Lady, 2 tiers observed):**

| Tier | EUR | CZK | Capacity range | Transition |
|------|-----|-----|----------------|------------|
| T1 | 37.5 | 899 | ~15 | — |
| T2 | 52.9 | 1269 | 1-6 | +41% |

Spread: ×1.41 (41%) — likely more tiers exist but short route = less demand.

### Temporary surcharge pattern

Observed on snapshots 20260803/04 and 20260810/11 (weekly recurrence, see below):
- Affects ALL routes, ALL classes simultaneously
- Same capacity → not a tier change
- Reverts within 1-2 days
- Proportional increase (not flat amount) → percentage-based multiplier

### Analysis tool

Run `python3 leo-tiers.py` for the full per-route breakdown. Filters:
- `python3 leo-tiers.py weimar-przemysl` — specific route
- `python3 leo-tiers.py --class ECO` — specific class

### Next steps (September+)

- New booking horizon opens → observe T1/T2 filling behavior and exact seat allocations
- Track whether temporary surcharges recur (weekly pattern? random?)
- Verify Frankfurt route has more tiers once demand increases
- Determine if T1 (37.5€ Przemyśl / 899 CZK) is a promotional launch tier or permanent


## Updated Findings (2026-08-11, 13 snapshots)

### Surcharge recurrence confirmed

Weekly surcharge pattern, confirmed across 28 snapshots (4 full weeks).
Active on **Monday and Tuesday** snapshots (scraper runs 00:00), absent Wed–Sun.

| Snapshot | Avg surcharge | Weekday |
|----------|---------------|---------|
| 20260803 | +4.5% | Monday |
| 20260804 | +3.1% | Tuesday |
| 20260810 | +4.4% | Monday |
| 20260811 | +3.0% | Tuesday |
| 20260817 | +4.7% | Monday |
| 20260818 | +3.0% | Tuesday |
| 20260824 | +4.9% | Monday |
| 20260825 | +3.1% | Tuesday |

**The surcharge is perfectly deterministic:** identical percentage per class and
tier across all 4 observed weeks (0.000% variance). Not stochastic, not
demand-responsive — a fixed lookup table applied to each tier price.

**T1 prices are immune** (10.0€ ECO, 25.0€ BUS, 37.5€ Sleeper/Lady unchanged).

#### Complete surcharge table (Bohumín route, stable across all weeks)

| Class | Tier (€) | Monday | Tuesday | Mon price | Tue price |
|-------|----------|--------|---------|-----------|-----------|
| ECO | 10.8 | +3.70% | +3.70% | 11.2 | 11.2 |
| ECO | 21.6 | +4.17% | +1.85% | 22.5 | 22.0 |
| ECO | 32.0 | +5.31% | +4.06% | 33.7 | 33.3 |
| ECO | 42.9 | +4.90% | +2.80% | 45.0 | 44.1 |
| ECO | 64.1 | +5.30% | +3.28% | 67.5 | 66.2 |
| BUS | 27.9 | +5.73% | +2.87% | 29.5 | 28.7 |
| BUS | 42.0 | +4.05% | +2.14% | 43.7 | 42.9 |
| BUS | 55.8 | +4.48% | +3.05% | 58.3 | 57.5 |
| BUS | 83.3 | +5.04% | +3.00% | 87.5 | 85.8 |
| ECOSLEEPER | 42.9 | +4.90% | +2.80% | 45.0 | 44.1 |
| ECOSLEEPER | 64.1 | +5.30% | +3.28% | 67.5 | 66.2 |
| ECOSLEEPER | 85.8 | +4.90% | +2.91% | 90.0 | 88.3 |
| ECOSLEEPER | 128.3 | +4.83% | +2.88% | 134.5 | 132.0 |
| ECOSLEEPERLADY | 42.9 | +4.90% | +2.80% | 45.0 | 44.1 |
| ECOSLEEPERLADY | 64.1 | +5.30% | +3.28% | 67.5 | 66.2 |
| ECOSLEEPERLADY | 85.8 | +4.90% | +2.91% | 90.0 | 88.3 |
| ECOSLEEPERLADY | 128.3 | +4.83% | +2.88% | 134.5 | 132.0 |

#### Observations

- **Sleeper and Lady have identical surcharges** (same underlying pricing engine)
- **ECO T2 (10.8€) gets the same surcharge Mon and Tue** — unique exception
- **Monday > Tuesday** for all other tiers (Mon ~4.5–5.7%, Tue ~1.9–4.1%)
- Surcharge prices are rounded to nearest 0.1€ (CZK basis, then ÷24)
- The BUS surcharge on T5 (83.3→87.5) collides with Sleeper T4 canonical price (85.8€)
  — this caused early false "new tier" observations before the pattern was understood

#### Mechanism hypothesis

The surcharge is applied as a **percentage multiplier on the CZK price**, then
converted to EUR via ÷24. The exact CZK surcharge values (not yet verified in
CZK snapshots) would reveal whether this is a clean percentage or a fixed CZK
adder per tier. The per-tier variation (3.7%–5.7%) suggests it's NOT a single
global multiplier but a tier-specific lookup.

Timing: activated Sunday night, deactivated Tuesday night (both transitions
happen between 00:00 snapshots). Likely a "weekend/early-week demand premium"
aligned with leisure booking patterns.

### Micro-tier illusion (Economy, Bohumín)

`leo-tiers.py` reports 7 Economy tiers on the Bohumín route, but analysis of
snapshot days reveals that some are surcharge artifacts:

| Price (EUR) | Normal days | Surcharge days only | Verdict |
|-------------|-------------|---------------------|---------|
| 10.0 | ✅ (205×) | also present (109×) | Real tier (floor price, surcharge rounds to same) |
| 10.8 | ✅ (429×) | never | Real tier |
| 11.2 | never | ✅ (213×, only on 03/04/10/11.08.) | **Surcharge artifact** (10.8 × 1.037 ≈ 11.2) |
| 21.6 | ✅ | — | Real tier |
| 22.0/22.5 | — | ✅ | Surcharge on 21.6 |
| 32.0 | ✅ | — | Real tier |
| 33.3/33.7 | — | ✅ | Surcharge on 32.0 |
| 42.9 | ✅ | — | Real tier |
| 44.1/45.0 | — | ✅ | Surcharge on 42.9 |
| 64.1 | ✅ | — | Real tier |
| 66.2/67.5 | — | ✅ | Surcharge on 64.1 |

**Actual Economy tiers (Bohumín): 5** — 10.0 → 10.8 → 21.6 → 32.0 → 42.9 → 64.1

The 10.0/10.8 split remains unexplained — both appear on normal days. Possibly
10.0 is a promo/launch tier and 10.8 the standard T1. Or 10.0 is the absolute
floor that doesn't get the surcharge while 10.8 does (→ 11.2).

### Bohumín Sleeper: new tier discovered (T2 = 42.9€ / 1029 CZK)

Previous documentation listed 4 Bohumín Sleeper tiers (37.5 → 64.1 → 85.8 → 128.3).
With 13 snapshots, a 5th tier is now confirmed:

| Tier | EUR | CZK | Capacity | Δ CZK | Transition |
|------|-----|-----|----------|-------|------------|
| T1 | 37.5 | 899 | 15–16 | — | — |
| **T2** | **42.9** | **1029** | **13–14** | **+130** | **+14%** |
| T3 | 64.1 | 1539 | 10–12 | +510 | +50% |
| T4 | 85.8 | 2059 | 7–9 | +520 | +34% |
| T5 | 128.3 | 3079 | 1–6 | +1020 | +50% |

T2 (42.9€) appears on 9 normal snapshot days — confirmed real, not a surcharge.
The T1→T2 gap (+130 CZK) is much smaller than subsequent gaps (+510/+520/+1020),
suggesting T1 and T2 share the "introductory" zone (first ~6 seats sold).

Spread: ×3.42 (242%). Pattern: +14%, then alternating +50%/+34%/+50% — consistent
with the Przemyśl route structure.

### Bohumín Business: 5 real tiers + 1 questionable

| Tier | EUR | CZK | Capacity | Transition |
|------|-----|-----|----------|------------|
| T1 | 25.0 | 599 | 50–54 | — |
| T2 | 27.9 | 669 | 40–49 | +12% |
| T3 | 42.0 | 1009 | 32–43 | +51% |
| T4 | 55.8 | 1339 | 23–32 | +33% |
| T5 | 83.3 | 1999 | 7–18 | +49% |
| T6? | 87.5 | 2099 | 22 | +5% (single observation) |

T6 at 87.5€ has only 1 observation with suspiciously high capacity (22) — likely
a surcharge on T5 rather than a real tier. The +5% gap is inconsistent with the
pattern. Effective tiers: 5.

### Period 5 (30.8.–16.9.): Full service confirmed (Sleeper available)

*Corrected 2026-08-26. Earlier finding (Economy-only) was based on data from
before the Polish timetable was released.*

Live data (snapshot 20260826) confirms: Period 5 offers all 4 classes on the
Bohumín route: BUS, ECO, ECOSLEEPER, ECOSLEEPERLADY. The Sleeper car IS attached.

Service pattern in Period 5: 5 days on, 2 days off (Tuesday + Wednesday = no service).
This matches the Period 4 variant structure.

The Przemyśl route also shows full 4-class service from 03.09. onward (same
5-on/2-off pattern). Tickets were released on 15.08.2026 (see below).

### Polish section status — tickets reopened 15.08.2026

Per Leo Express website (Aug 2026): "Tickets für den Streckenabschnitt
Bohumín–Przemyśl verkaufen wir bis zum 29. August, wenn in Polen die Gültigkeit
des aktuellen Fahrplans endet. Der Verkauf für den nächsten Zeitraum wird im
Laufe des Augusts gestartet."

**Update 2026-08-26:** Tickets for the new Polish timetable period were released
on **15.08.2026** (detected in snapshot 20260815 — first day with 4 classes on
Przemyśl dates that previously returned "error"). All September dates appeared
simultaneously with full capacity (T1 pricing, 37.5€ Sleeper).

Service days in the new period: same 5+2 pattern (Tue+Wed off).
Bookable through at least 24.10.2026.

### Updated next steps

- [x] Confirm surcharge recurrence pattern (weekly Mon/Tue, not Sun/Mon)
- [x] Resolve micro-tier question (surcharge artifacts, not real tiers)
- [x] Discover Bohumín Sleeper T2 (42.9€ / 1029 CZK)
- [x] Period 5 = full service with Sleeper (earlier Economy-only finding was premature)
- [x] Polish tickets reopened 15.08. — T1 filling captured from zero
- [x] Sleeper/Lady pricing coupled since 18.08. (shared 40-berth tier counter)
- [ ] When Period 6 starts (17.9.): check if Frankfurt Flughafen activates
- [ ] Determine if 10.0€ vs 10.8€ is promo vs standard (need fresh horizon opening)
- [x] Verify Frankfurt Sleeper tier structure (Frankfurt<->Weimar) → 4 tiers (37.5/52.9/54.5/55.8€), flat micro-tiers (weekend surcharge artifacts). Eastbound currently T1 only, westbound up to T3 (07.09.)
- [x] Check if Sleeper/Lady coupling persists or reverts → persists (07.09., stable since 18.08., 0 divergences over 21 days)


### Tier Boundaries — Exakte Kapazitätsgrenzen (2026-08-11)

Abgeleitet aus beobachteten Preiswechseln an einzelnen Reisetagen über alle
Snapshots (Surcharge-Tage ausgeschlossen). Stornos bestätigen die Grenzen
bidirektional.

#### Bohumín Sleeper (EUR)

| Tier | Preis | Gilt bei cap | Plätze | Evidenz |
|------|-------|-------------|--------|---------|
| T1 | 37.5€ | ≥ 15 (Annahme: ≥ 15, Start bei 20) | **6** (Annahme) | Nur cap 15–16 beobachtet; Annahme: 20→15 = 6 Plätze |
| T2 | 42.9€ | 12–14 | **3** | 3× Aufwärts bei cap 14 beobachtet |
| T3 | 64.1€ | 10–11 | **2** | Aufwärts bei cap 11/12; Rückfall bei cap 10/11 |
| T4 | 85.8€ | 7–9 | **3** | 8× Aufwärts bei cap 8/9; Rückfall bei cap 10 |
| T5 | 128.3€ | 1–6 | **6** | Aufwärts bei cap 4/5/6 |

Total: 6+3+2+3+6 = **20** (passt zu 20 physischen Betten)

#### Schlüssel-Beobachtungen

**Bidirektionale Bestätigung (Stornos):**
- cap 10 → Preis fällt von 85.8€ auf 64.1€ (T4→T3): 5× beobachtet
- cap 9 → Preis fällt von 128.3€ auf 85.8€ (T5→T4): 1× beobachtet
- cap 14 → Preis fällt von 64.1€ auf 42.9€ (T3→T2): 1× beobachtet

**Ping-Pong (18.08.2026):**
Reisetag springt mehrfach zwischen cap 9/10 und T3/T4 — Buchungen und Stornos
an der Grenze. Bestätigt cap=10 als exakte T3-Untergrenze eindeutig.

**Übersprungene Tiers (11./12./13.08.):**
64.1€→128.3€ bei cap 5/6 — T4 (85.8€) wurde übersprungen. Vermutung: mehrere
Buchungen zwischen zwei Snapshots (tägliche Auflösung zu grob für Einzeltickets).

#### T1-Annahme: 6 Plätze (cap 20→15)

Begründung:
- Physische Kapazität = 20 Betten pro Hälfte (bestätigt via Seat-API)
- Höchste beobachtete Kapazität = 16 (T1 aktiv)
- T1→T2-Wechsel bei cap 14 (3× beobachtet)
- Ergo: T1 gilt bei cap 15–20, T2 beginnt bei cap 14
- Plätze auf T1: 20 - 14 = **6**
- Wir haben nie cap 17–20 gesehen → T1 war bei Erfassungsbeginn schon
  teilweise verkauft (Buchungshorizont bereits offen)

**Zu verifizieren bei:**
- Storno auf einem Datum das aktuell bei T2 (cap 14) liegt → falls cap auf 15+
  steigt und Preis auf 37.5€ fällt, ist die Grenze bestätigt
- Polnischer Fahrplan-Verkaufsstart → frische Daten ab cap 20

#### Przemyśl Sleeper (EUR) — bestätigt via Tier-Wechsel

| Tier | Preis | Gilt ab cap | Plätze | Evidenz |
|------|-------|-------------|--------|---------|
| T1 | 37.5€ | ≥ 15 | **6** (Annahme) | Storno 68.7→37.5 bei cap 15 (Lady) |
| T2 | 68.7€ | 13–14 | **2** | Aufwärts bei cap 13/14 (3×); Storno bei cap 13/14 (3×) |
| T3 | 102.9€ | 10–12 | **3** | Aufwärts bei cap 11/12 (7×); Storno bei cap 10–12 (5×) |
| T4 | 137.0€ | 7–9 | **3** | Aufwärts bei cap 8/9 (12×); Storno bei cap 7/9 (3×) |
| T5 | 205.8€ | 1–6 | **6** | Aufwärts bei cap 5/6 (4×); Storno bei cap 7 (2×) |

Total: 6+2+3+3+6 = **20** ✓

Hinweis: Sleeper zeigt Aufwärts bei cap 9 (10×) und bei cap 8 (2×). Die Grenze
liegt bei **cap ≤ 9 → T4 aktiv**. Cap 8 entsteht durch zwei Buchungen zwischen
Snapshots (tägliche Auflösung zu grob).

Przemyśl hat nur 5 Tiers (nicht 6 wie zuvor vermutet). T5 deckt cap 1–6 ab
(6 Plätze), genau wie Bohumín T5.

#### Vergleich Kapazitätsgrenzen (beide Routen)

| Grenze | Bohumín | Przemyśl | Identisch? |
|--------|---------|----------|------------|
| T1 → T2 bei cap | 14 | 14 (Lady) / Sleeper: nie beobachtet | ✅ |
| T2 → T3 bei cap | 11 | 12 (Lady) / 11 (Sleeper) | ≈ (±1) |
| T3 → T4 bei cap | 9 | 9 | ✅ |
| T4 → T5 bei cap | 6 | 6 | ✅ |

Die Kapazitätsschwellen sind routenübergreifend identisch. Nur die Preisbeträge
pro Tier unterscheiden sich (distanzabhängig). Der Algorithmus ist derselbe.

#### Stufenbreite zusammengefasst (beide Routen, Sleeper/Lady)

```
cap 20 ┌───────────────────┐
       │     T1 (37.5€)    │  6 Plätze (Annahme, zu verifizieren)
cap 15 ├───────────────────┤
       │     T2            │  2 Plätze
cap 13 ├───────────────────┤
       │     T3            │  3 Plätze
cap 10 ├───────────────────┤
       │     T4            │  3 Plätze
cap  7 ├───────────────────┤
       │     T5 (max)      │  6 Plätze
cap  1 └───────────────────┘
```

T1-Annahme (6 Plätze) zu verifizieren bei:
- Storno eines Datums von T2 (cap 14) zurück auf cap 15+ → Preis muss auf 37.5€ fallen
- Polnischer Fahrplan-Verkaufsstart → erste Erfassung bei cap 20


### Economy & Business — Tier Boundaries (2026-08-11)

#### Business (beide Routen, ~50 Plätze total)

T1-Preis ist routenunabhängig (25.0€), Kapazitätsgrenzen identisch.

| Tier | Bohumín | Przemyśl | Gilt ab cap | Plätze | Evidenz |
|------|---------|----------|-------------|--------|---------|
| T1 | 25.0€ | 25.0€ | ≥ 50 | **~6** | ↑ cap 47–49; ↓ cap 50 |
| T2 | 27.9€ | 44.5€ | 44–49 | **~6** | ↑ cap 35–43 (breit); ↓ cap 44 |
| T3 | 42.0€ | 67.0€ | 33–43 | **~11** | ↑ cap 28–32; ↓ cap 33 |
| T4 | 55.8€ | 89.1€ | 22–32 | **~11** | ↑ cap 12–18 |
| T5 | 83.3€ | 133.7€ | 1–21 | **~21** | wenig Daten (selten erreicht) |

Total: 6+6+11+11+21 ≈ 55 (API meldet max 54)

Kapazitätsgrenzen bestätigt durch Stornos (beide Routen identisch):
- ↓ cap 50 → Preis fällt auf T1 (25.0€)
- ↓ cap 44 → Preis fällt auf T2
- ↓ cap 33 → Preis fällt auf T3

Muster: T1/T2 schmal (6 Plätze Lockpreis), T3/T4 breit (11 Plätze Mitte),
T5 sehr breit (21 Plätze, ~40% der Kapazität zum Höchstpreis).

#### Economy — Bohumín (~108 Plätze, 6 Tiers)

| Tier | Preis | Gilt ab cap | Plätze | Evidenz |
|------|-------|-------------|--------|---------|
| T1 | 10.0€ | ≥ 107 | **~8** | ↑ cap 100–106; ↓ cap 107 |
| T2 | 10.8€ | 99–106 | **~8** | ↑ cap 94–98; ↓ cap 99–100 |
| T3 | 21.6€ | 57–98 | **~42** | ↑ cap 53–56; ↓ cap 57–58 |
| T4 | 32.0€ | 42–56 | **~15** | ↑ cap 36–42 |
| T5 | 42.9€ | 27–41 | **~15** | ↑ cap 24–27 |
| T6 | 64.1€ | 1–26 | **~26** | letzter Tier |

Total: 8+8+42+15+15+26 ≈ 114 (API meldet max 108, Differenz durch Messunschärfe)

Auffällig: T3 ist extrem breit (42 Plätze, ~39% der Kapazität). Das bedeutet
die meiste Zeit steht Economy bei 21.6€ — der "Normalpreis". T1/T2 (10.0/10.8€)
sind nur für die allerersten ~16 Buchungen verfügbar.

#### Economy — Przemyśl (~62 Plätze, 4 Tiers)

| Tier | Preis | Gilt ab cap | Plätze | Evidenz |
|------|-------|-------------|--------|---------|
| T1 | 34.5€ | ≥ 56 | **~8** | ↑ cap 49–56 |
| T2 | 51.6€ | 42–55 | **~14** | ↑ cap 37–42; ↓ cap 48 |
| T3 | 68.7€ | 26–41 | **~16** | ↑ cap 24–26 |
| T4 | 102.9€ | 1–25 | **~25** | letzter Tier |

Total: 8+14+16+25 ≈ 63 (passt zu max 62 beobachtet)

#### Cross-Route-Vergleich Kapazitätsgrenzen

**Business:**
- Bohumín und Przemyśl: identische Schwellen (50, 44, 33, 22)
- T1 routenunabhängig bei 25.0€

**Economy:**
- Nicht direkt vergleichbar (unterschiedliche Gesamtkapazität: 108 vs 62)
- Aber gleiche Struktur: schmale Lockpreis-Tiers oben, breite Mitte, großer Restblock

**Sleeper (Referenz):**
- Bohumín und Przemyśl: identische Schwellen (15, 13, 10, 7)
- T1 routenunabhängig bei 37.5€

#### Zusammenfassung: T1 ist immer routenunabhängig

| Klasse | T1-Preis | Kapazität | T1-Breite |
|--------|----------|-----------|-----------|
| Economy (Bohumín) | 10.0€ | ~108 | ~8 Plätze (7%) |
| Economy (Przemyśl) | 34.5€ | ~62 | ~8 Plätze (13%) |
| Business | 25.0€ | ~50 | ~6 Plätze (12%) |
| Sleeper/Lady | 37.5€ | ~20 | ~6 Plätze (30%) |

Economy Bohumín hat den niedrigsten T1 (10€) — nahe am Symbolpreis.
Economy Przemyśl startet bei 34.5€ — deutlich höher, distanzbedingt.


## Distanzbasiertes Preismodell (2026-08-11, Segment-Analyse)

### Methode

Alle Teilstrecken-Preise für ein festes Datum (28.08.2026, Tier-Basispreis T1)
abgefragt: fester Start Frankfurt Süd → jeder Zwischenhalt als Ziel, und
umgekehrt jeder Zwischenhalt als Start → festes Ziel Przemyśl.

Tool: `leo-segment-pricing.py` (4 Perspektiven: Ost/West × fixer Start/festes Ziel)

### Ergebnis: Preis korreliert fast perfekt mit Distanz

Lineare Regression (nur Datenpunkte oberhalb Floor-Preis, R² jeweils >0.98):

| Klasse | Floor | Grundpreis | €/km | €/100km | R² | Floor greift <km |
|--------|-------|-----------|------|---------|-----|-----------------|
| Economy | 10.0€ | 4.8€ | 0.046 | 4.60€ | 0.980 | 113 km |
| Business | 25.0€ | 17.9€ | 0.049 | 4.88€ | 0.984 | 146 km |
| Sleeper | 37.5€ | 10.5€ | 0.123 | 12.26€ | 0.996 | 220 km |
| Sleeper Lady | 37.5€ | 31.8€ | 0.105 | 10.45€ | 0.994 | 55 km |

*Hinweis: "Floor" ist der absolute Mindestpreis über alle Routen (Frankfurt→x).
T1-Werte pro Route (z.B. Weimar→Przemyśl: Eco T1=34.5€) liegen höher, weil
sie bereits eine Mindest-Distanz beinhalten. Der Floor hier (10€) entspricht
dem Economy-Preis auf den kürzesten Teilstrecken (Bohumín-Route).*

**Formeln (T1-Basispreis):**

```
Economy:      max(10.0€,  4.8€ + 0.046€ × km)
Business:     max(25.0€, 17.9€ + 0.049€ × km)
Sleeper:      max(37.5€, 10.5€ + 0.123€ × km)
Sleeper Lady: max(37.5€, 31.8€ + 0.105€ × km)
```

### Interpretation

- **Economy und Business haben fast identische km-Sätze** (~4.6-4.9 ct/km),
  unterscheiden sich nur im Grundpreis (+13€ für Business).
- **Sleeper ist ~2.5× so teuer pro km wie Economy** (12.3 vs 4.6 ct/km).
- **Sleeper und Sleeper Lady haben identisches Preismodell** (gleiche Tiers,
  gleicher km-Satz). Der scheinbare Unterschied in der Regression (10.5 vs 12.3
  ct/km) ist ein Artefakt: Lady stand am Stichtag auf mehr Segmenten noch in
  T1, während Sleeper durch höhere Nachfrage bereits in T2/T3 war.
  Tatsächlicher Preis hängt nur von der Auslastung ab.
- **Der Floor-Preis dominiert auf kurzen Strecken:** Unter 220 km zahlt man für
  den Sleeper immer 37.5€ (Floor), egal ob 50 km oder 200 km. Economy-Floor
  (10€) greift erst unter 113 km.

### Abweichungen vom linearen Modell

| Zone | Abweichung | Erklärung |
|------|-----------|-----------|
| Deutschland (Frankfurt→Bad Schandau) | +1-5% | Leicht über Modell |
| Tschechien (Prag→Bohumín) | -8 bis -13% | Systematisch günstiger (niedrigeres Länderniveau?) |
| Polen <220 km (Krakau→Jarosław) | Floor dominiert | 37.5€ Sleeper für jede Strecke |

### Konsequenz für Buchungsstrategie

**ICE + Leo Kombi vs. Durchgangsticket:**

Da Leo linear nach km abrechnet (~12 ct/km Sleeper), lohnt eine Kombination wenn:
- ICE-Sparpreis für den deutschen Tagabschnitt < Leo-Aufschlag für denselben Abschnitt
- Beispiel: Frankfurt→Leipzig per ICE (30€) + Leipzig→Przemyśl per Leo (129€ Sleeper)
  = 159€ statt 173€ Durchgangsticket. Ersparnis: 14€.

**Nachteile der Kombi:**
- Umstieg (kein durchgehendes Bett)
- Verspätungsrisiko (Leo wartet nicht)
- Leo-Tagabschnitt Frankfurt→Leipzig ist nur Sitzplatz, kein Bett (Nacht erst ab Leipzig/Dresden)

**Breakeven:** Solange der ICE-Sparpreis < 0.12€/km × Strecke ist, lohnt die Kombi.
ICE-Supersparpreis liegt bei ~5-8 ct/km, normaler Sparpreis bei 10-15 ct/km.
→ Mit Supersparpreis immer günstiger, mit normalem Sparpreis marginal.

### Sonderfälle

- **Frankfurt→Offenbach/Hanau (5€ Eco, 7.5€ Bus):** Absurd günstige Kurzstrecke.
  Der Floor liegt deutlich unter dem Modellpreis — vermutlich bewusst als
  Zubringer-Symbolpreis gesetzt.
- **Radymno→Przemyśl (0.8€ Eco):** Unter-Floor-Preis, vermutlich API-Artefakt
  oder Sondertarif für die letzte Haltestelle vor dem Endpunkt.
- **Zábřeh na Moravě:** Nur Eco+Bus verfügbar, kein Sleeper. Möglicherweise
  liegt dieser Halt außerhalb der Schlafwagen-Buchungszone.


### Dresden-Neustadt Preisanomalie

Frankfurt→Dresden-Neustadt kostet 128.3€ Sleeper (Bohumín-T5-Niveau), während
Frankfurt→Dresden Hbf (12 min später, gleicher Zug LE235) nur 64.1€ kostet.
Economy: 48€ vs 24€ — exakt Faktor 2.

Vermutlich interne Fehlklassifikation: Neustadt wird als anderes Preissegment
behandelt als Hbf. Praktische Konsequenz: nie ein Ticket nach Neustadt buchen,
immer nach Hbf (oder vor Neustadt aussteigen und umbuchen).

### Capacity-Verlauf und Zusteiger-Erkennung

Die Segment-Analyse zeigt für jede Station die verbleibende Capacity. Differenz
zwischen aufeinanderfolgenden Stationen = Zusteiger auf diesem Abschnitt.

Beispiel 28.08. (Sleeper, ostwärts ab Frankfurt):

| Abschnitt | Cap vorher | Cap nachher | Zusteiger |
|-----------|-----------|-------------|-----------|
| Frankfurt→Fulda | 13 | 13 | 0 |
| Fulda→Erfurt | 13 | 12 | 1 |
| Erfurt→Leipzig | 12 | 12 | 0 |
| Leipzig→Dresden | 12 | 8 | **4** |
| Dresden→Prag | 8 | 8 | 0 |
| Prag→Bohumín | 8 | 8 | 0 |
| Bohumín→Przemyśl | 8 | 8 | 0 |

Dresden ist der Haupt-Zustiegspunkt nach Frankfurt (4 von 12 Sleeper-Buchungen).

### Beförderungsverbote (erweitert)

Neben dem bekannten innerpolnischen Beförderungsverbot (Katowice) gibt es
weitere Einschränkungen:

**CZ-Stationen → Przemyśl blockiert:**
- Děčín hl.n., Ústí nad Labem, Kralupy n.Vltavou → Przemyśl: "Auf dieser
  Strecke fahren wir nicht"
- Zábřeh na Moravě: kein Sleeper/Lady verfügbar (nur Eco+Bus)

**Westwärts:**
- Frankfurt Flughafen: am 28.08. blockiert (nur in Period 6 Variant A bedient)

Vermutung: Die CZ-Elbtal-Stationen sind nur als Ausstieg erlaubt (Frankfurt→Děčín
funktioniert), nicht als Einstieg Richtung PL. Möglicherweise eine
Wettbewerbsschutz-Regelung für RegioJet/ČD auf dieser Strecke.

### Richtungsasymmetrie (kein Modellfehler)

Am 28.08. kosten Frankfurt→Przemyśl und Przemyśl→Frankfurt in Sleeper/Business
identisch (173€/84.5€). Economy und Lady weichen ab:

- Economy: ostwärts 65€, westwärts 86.6€ (+33%)
- Lady: ostwärts 173€, westwärts 130€ (-25%)

Das ist kein Modellunterschied, sondern unterschiedliche Tier-Auslastung pro
Richtung am gleichen Datum. Das bestätigt: **Hin- und Rückfahrt werden unabhängig
bepreist** (separate Kapazitätspools, separates Yield Management pro Richtung).


#### Dresden-Neustadt ×2-Bug: Detailanalyse

Der Bug ist systematisch und persistent über alle Daten:

| Datum | Neustadt | Hbf | Faktor |
|---|---|---|---|
| Mi 12.08. | 96.2€ | 47.9€ | ×2.0 |
| Do 13.08. | 128.3€ | 64.1€ | ×2.0 |
| Fr 14.08. | 128.3€ | 64.1€ | ×2.0 |
| Sa 15.08. | 192.0€ | 95.8€ | ×2.0 |
| So 16.08. | 96.2€ | 47.9€ | ×2.0 |
| Mo 17.08. | 96.2€ | 47.9€ | ×2.0 |
| Di 18.08. | 128.3€ | 64.1€ | ×2.0 |
| Mi 19.08. | 192.0€ | 95.8€ | ×2.0 |
| So 23.08. | 64.1€ | 37.5€ | ×1.7 |
| Mo 24.08. | 37.5€ | 37.5€ | ×1.0 |
| So 30.08. | 64.1€ | 47.9€ | ×1.3 |
| Mo 31.08. | 64.1€ | 37.5€ | ×1.7 |

**Eigenschaften:**
- Fast immer exakt Faktor 2.0 — Neustadt kostet das Doppelte von Hbf
- Beide Preise bewegen sich mit der Nachfrage (verschiedene Tiers)
- Bei Floor (37.5€) verschwindet der Bug (Faktor 1.0 am 24.08.)
- Abweichende Faktoren (1.3/1.7) treten auf wenn ein Preis am Floor ist und
  der andere nicht (Floor-Clipping verhindert exakte Verdopplung)
- Bug existiert NUR für die Relation Frankfurt Süd → Dresden-Neustadt
- Ab Fulda, Erfurt, Weimar, Leipzig: identische Preise für beide Stationen
- Als Abfahrtsstation (Dresden-Neustadt → x): kein Bug, normale Preise

**Vermutung:** Die Preismatrix berechnet Frankfurt→Dresden-Neustadt intern als
zwei separate Segmente und addiert die Preise, statt den korrekten
Durchgangspreis zu verwenden. Exakter Faktor 2.0 deutet auf eine
Doppelberechnung hin.

**Praktische Konsequenz:** Wer ab Frankfurt Richtung Osten fährt und in
Dresden-Neustadt aussteigen will, bucht bis Dresden Hbf und steigt 12 Minuten
früher aus. Ersparnis: 50% auf den Sleeper-Preis.



## Snälltåget Pricing Anomalies (August 2026)

### Per-Origin Contingent Discovery

Snälltåget allocates capacity separately per boarding station. The same physical
train D 10300/10301 shows different prices depending on the booking origin,
because each origin has its own yield tier progression.

Hamburg receives 3–5× more contingent than Berlin (e.g., 143 vs 33 seats).
Despite having more inventory, Hamburg reaches higher price tiers faster due to
higher demand — DB Navigator doesn't show the slow Berlin→Hamburg segment, so
travelers default to booking from Hamburg.

Berlin/Dresden contingent often sits in the lowest tier, creating 'dead
inventory' that Snälltåget can't sell because customers don't know to book from
there.

### Overshoot Pricing (Hidden City Ticketing)

Because each origin has independent yield tiers, the same compartment can cost
4,000 SEK (~360€) more when booked from Hamburg than from Berlin — on the same
train, same date, same physical cabin.

Examples (27.08.2026 snapshot):
- 04.09. NB Compartment: Hamburg 7,999, Berlin 3,999 → 4,000 SEK saving
- 11.09. SB Compartment: Hamburg/Berlin 5,999, Dresden 4,999 → 1,000 SEK saving
- 27.11. SB Comp-Flex: Hamburg 6,499, Dresden 4,499 → 2,000 SEK saving

Southbound (Stockholm→Dresden): Book to a further station, exit early. No
enforcement risk — ticket covers the earlier stop.

Northbound (X→Stockholm): Book from an earlier origin. Compartment stays
reserved. Practical for private compartments where no-show at origin doesn't
affect other passengers.

### Berth-Seat Price Inversion

On transfer routes (D 300+3940), shared berths can be cheaper than seats:
NTBSF 1,248 SEK vs SPSF 1,498 SEK on 30.08.2026. The 250 SEK inversion occurs
because seat and berth have separate yield tiers — seats face higher demand for
the daytime Malmö→Stockholm leg.

### Tier Mechanics

The calendar `quota` field tracks remaining seats at the current tier price.
When quota approaches 0 (avg 4.8 at jump), the `amount` (display price) jumps
to the next tier. Price increases average quota=4.8 before jump, price decreases
(cancellations) average quota=11.8.

16 distinct calendar price levels observed across all routes. Compartment
products show 7 tiers (1,999–7,999 SEK), transfer berths show 11+ tiers with
finer granularity.

### Tools

- `snalltaget_compare.py overshoot` — cross-route price comparison
- `snalltaget_compare.py inversion` — berth<seat anomaly detection
- `snalltaget_compare.py tiers` — tier jumps, cross-origin comparison, dead inventory
- `snalltaget_compare.py diff/trend` — standard snapshot comparison