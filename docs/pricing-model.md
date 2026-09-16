# Pricing Model — Tier Mechanics, Capacity Thresholds, Surcharges

Cross-operator reference for how night-train fares move. All monitored operators
use **discrete, capacity-driven price tiers** (yield management): a fixed
contingent is sold up a ladder of fixed prices, and the price rises as capacity is
consumed. This document describes the shared model and the per-operator
differences. Operator-specific details live in their own docs
([leo](USE-CASE.md), [rdc](rdc.md), [sj](sj.md), [snalltaget](snalltaget.md),
[european-sleeper](european-sleeper.md)).

## Shared Model

- **Discrete tiers**: each fare class has a ladder of fixed prices, not a smooth curve.
- **Capacity-driven**: each tier holds a fixed allocation of seats/berths. When a
  tier's allocation is sold, the price steps to the next tier.
- **Reversible**: cancellations restore seats and can drop the price back to a lower
  tier. A tier downgrade between snapshots is normal, not an anomaly.
- **Route/class-specific ladders**: tier values differ per route and per class.
- **Searches don't block capacity**; only a created order holds a seat (and releases
  it on delete/expiry). This makes capacity probing via search free.

Two mechanisms move the observed price:
1. **Bookings** — consume the current tier, eventually trigger a step up.
2. **Cancellations** — restore capacity, can step the price down.

Any other change (all dates resetting at once, a price off the known ladder) is a
system/backend event, not organic demand — see the anomaly detection notes below.

## Per-Operator Tier Structure

| Operator | Tiers | Granularity | Multi-person pricing | Detail |
|----------|-------|-------------|----------------------|--------|
| Leo Express | ~5–6 per route/class | coarse (30–50% jumps) | flat (whole request steps together) | [USE-CASE.md](USE-CASE.md) |
| RDC EuroNight | 3–6 per entity | coarse | flat (whole request jumps together) | [rdc.md](rdc.md) |
| SJ | 40–65 per class/flex | fine (~10 SEK steps) | flat (whole request jumps together) | [sj.md](sj.md) |
| Snälltåget | tier ladder via calendar `quota` | medium | — | [snalltaget.md](snalltaget.md) |

**Multi-person pricing — all three jump flat (verified 2026-09-15 for LEO):**
- Exceeding the current tier's contingent raises the per-person price for *all*
  requested places at once. A createOrder for n persons returns n identical item
  prices; the level steps up with n against the tier's remaining capacity.
- This makes tier boundaries directly probeable: the n at which the per-person price
  (LEO) or `SinglePrice` (RDC/SJ) changes = remaining seats in the current tier.
- *Note: LEO previously (Aug 2026) cascaded (successive seats on increasing tiers,
  e.g. `2×T3 + 1×T4`). It now prices flat like RDC/SJ.*

## Leo Express — Detailed Ladder (Weimar–Przemyśl, Sleeper/Lady, EUR)

Sleeper and Lady share identical tier values:

```
37.5 → 68.7 → 102.9 → 137.0 → 205.8   (T2 = 52.9 exists on the Frankfurt route only)
```

Tier allocation (of 20 berths per half; Aug 29 snapshot):

| Tier | EUR | Sold-at threshold | Seats on tier | Increase |
|------|------|-------------------|---------------|----------|
| 1 | 37.5 | 0 | } 6 combined (T1+T2) | — |
| 2 | 52.9 | ? | } | +41% |
| 3 | 68.7 | 6 (30%) | 2 | +30% |
| 4 | 102.9 | 8 (40%) | 3 | +50% |
| 5 | 137.0 | 11 (55%) | 3 | +33% |
| 6 | 205.8 | 14 (70%) | 6 | +50% |

- Lady has broader cheap tiers (T1+T2+T3 = 8 seats vs 6) to incentivise filling the
  women-only half.
- The last 6 seats (top 30% of capacity) are always at max price (205.8€).
- Full spread T1→T6 = ×5.49 (+449%), far steeper than DB Sparpreis (~×2–3).
- CZK is the canonical currency; EUR = CZK ÷ 24 (fixed internal rate).

### Percentage Increases Between Tiers

| Transition | Increase | Factor | Absolute Δ |
|---|---|---|---|
| T1 → T2 | +41% | ×1.41 | +15.4 € |
| T2 → T3 | +30% | ×1.30 | +15.8 € |
| T3 → T4 | +50% | ×1.50 | +34.2 € |
| T4 → T5 | +33% | ×1.33 | +34.1 € |
| T5 → T6 | +50% | ×1.50 | +68.8 € |
| **T1 → T6** | **+449%** | **×5.49** | **+168.3 €** |

## Surcharges

Within a LEO tier, observed prices cluster with small sub-values (~4–9% above the
base tier). These are **weekend surcharges**, not separate tiers. Tier
reconstruction must map a price to its nearest base tier and treat the remainder as
a surcharge (see `lib/tiers.py` clustering and `tools/leo_surcharge_analysis.py`).

## Voucher × Tier Interaction (LE50 "1+50%")

The LE50 promo (live 14.–18.09.2026) gives **50% off the cheaper ticket of each
pair** (= 25% off the pair when both seats sit on the same tier). Valid for Economy
(3), Economy Sleeper (7), Economy Sleeper Lady (8); `conditions.class_id: [8,7,3]`.
For n tickets it forms `floor(n/2)` pairs; an odd leftover stays full price.

Because every extra person raises the per-person price for the whole request (flat
tier stepping), a larger group can push the pair onto a higher tier whose surcharge
erodes or exceeds the voucher saving.

Decision rule for a pair with prices `p1 ≤ p2`:
- Voucher saving = `0.5 · p1`
- Tier-jump surcharge on the 2nd seat = `p2 − p1`
- **The voucher pays off only while `p2 − p1 ≤ 0.5 · p1`, i.e. `p2 ≤ 1.5 · p1`.**

| Pair | Surcharge (p2−p1) | Saving (0.5·p1) | Verdict |
|------|-------------------|-----------------|---------|
| same tier | 0 | 0.5·p1 | full 25% saving |
| T3→T4 (68.7→102.9) | 34.2 | 34.4 | break-even (+0.1 in favour) |
| T4→T5 (102.9→137.0) | 34.1 | 51.5 | voucher wins (−17.4) |
| **T5→T6 (137.0→205.8)** | **68.8** | **68.5** | **surcharge eats saving (+0.3 worse)** |

**Cheapest-booking strategy:** book in pairs where both seats stay on the same tier.
Probe the multi-person search first to find the n at which the per-person average
jumps (= remaining seats in the current tier), then book only as many pairs as fit.
The jump onto the top tier (T6) makes the voucher effectively worthless. Probing is
free (searches don't block seats; unpaid orders restore capacity on delete).

Live-verified (weimar–przemyśl 22.10., 9× Sleeper): 1132.20€ → 880.60€ (4 pairs,
62.9€ discount each). See [timeline.md](timeline.md) (14.09.) and
[USE-CASE.md](USE-CASE.md) for the full trace.

**Tariff-mix pairing (verified 2026-09-15):** the API pairs by like tariff
(adult+adult, child+child), not adult+child, and discounts the cheaper ticket of
each pair — the customer-favourable choice, since grouping expensive tickets keeps
the discounted (cheapest-in-pair) ticket as high as possible. Example: 2 adult +
2 child → LE50 on one adult (56.7) + one child (16.1) = 72.8, vs. only ~32 if paired
adult+child. Reductions are CZ-heavy (children free in CZ; student/senior CZ-leg
only).

## Tier-Awareness in Anomaly Detection

`anomaly_scan` (`lib/analysis.py`) uses these tier ladders (reconstructed
empirically in `lib/tiers.py`) to suppress single-tier moves (normal
bookings/cancellations) and only report:
- multi-tier jumps (≥2 tiers) or off-ladder prices, and
- system-wide moves (≥50% of a class's active dates shifting the same direction in
  one snapshot interval — e.g. a backend reset to T1).

Operators without a usable ladder fall back to the percentage heuristic
(drop < −5%, spike > 20%). See README → "Tier-Aware Anomaly Detection".
