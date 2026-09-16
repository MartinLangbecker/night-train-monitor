"""
Data-driven price-tier ladders for step-aware anomaly detection.

LEO Express (and similar step-priced operators) sell a fixed contingent that
climbs a discrete price ladder as capacity is consumed. Observed prices cluster
around a small set of canonical tiers, with weekend surcharges producing minor
sub-values within each cluster (e.g. 68.7 / 70.8 / 72 all belong to one tier).

This module reconstructs the ladder empirically from the observed price history
of a route/class (no hand-maintained table), so a single-step move (booking or
cancellation) can be distinguished from a genuine multi-step jump or a
system-wide reset.

Public API:
    build_ladders(snapshots)          -> {class_name: [tier_price, ...]}
    tier_index(price, ladder)         -> int index of nearest tier (surcharge-normalised)
    tier_delta(old, new, ladder)      -> signed step difference, or None if off-ladder
"""

from collections import defaultdict

# Two adjacent distinct prices belong to the SAME tier if the relative gap
# between them is at or below this. Observed LEO weekend surcharges are ~4-9%;
# the smallest gap BETWEEN real tiers (1269->1649 in CZK) is ~30%. A 15%
# boundary cleanly separates surcharge sub-values from real tier steps.
SURCHARGE_GAP = 0.15

# A price is considered "off ladder" (itself an anomaly) if its relative
# distance to the nearest known tier exceeds this. Generous enough to absorb
# surcharges, tight enough to flag a genuinely unexpected price.
OFF_LADDER_TOLERANCE = 0.18


def _cluster(prices):
    """
    Cluster a sorted list of distinct prices into tiers. A new tier starts
    whenever the relative gap to the previous price exceeds SURCHARGE_GAP.
    The tier's canonical value is the cluster minimum (the base price before
    any surcharge).
    """
    if not prices:
        return []
    prices = sorted(prices)
    ladders = []
    cluster_start = prices[0]
    prev = prices[0]
    for p in prices[1:]:
        if prev > 0 and (p - prev) / prev > SURCHARGE_GAP:
            ladders.append(cluster_start)  # close previous cluster
            cluster_start = p
        prev = p
    ladders.append(cluster_start)
    return ladders


def build_ladders(snapshots):
    """
    Reconstruct per-class tier ladders from a route's snapshot history.

    Returns {class_name: [tier_price_ascending, ...]}. Classes with fewer than
    two distinct tiers are still returned (single-tier ladders are harmless;
    callers treat an empty/one-tier ladder as "no step information").
    """
    prices_by_class = defaultdict(set)
    for snap in snapshots:
        for classes in snap.get('data', {}).values():
            if not isinstance(classes, dict):
                continue
            for cls_name, cd in classes.items():
                if not isinstance(cd, dict):
                    continue
                p = cd.get('price')
                if p is not None:
                    prices_by_class[cls_name].add(round(float(p), 2))

    return {cls: _cluster(prices) for cls, prices in prices_by_class.items()}


def tier_index(price, ladder):
    """
    Index of the nearest tier for a price (surcharge-normalised). Returns None
    if the ladder is empty or the price is off-ladder (beyond tolerance from
    every known tier), which is itself a signal worth surfacing.
    """
    if price is None or not ladder:
        return None
    best_i, best_rel = None, None
    for i, tier in enumerate(ladder):
        if tier <= 0:
            continue
        rel = abs(price - tier) / tier
        if best_rel is None or rel < best_rel:
            best_i, best_rel = i, rel
    if best_i is None:
        return None
    if best_rel > OFF_LADDER_TOLERANCE:
        return None  # off-ladder
    return best_i


def tier_delta(old, new, ladder):
    """
    Signed tier-step difference between two prices on the same ladder.
    Positive = climbed tiers (bookings), negative = dropped tiers (cancellations
    / reset). Returns None if either price is off-ladder or the ladder is
    unusable, so the caller can fall back to the percentage heuristic.
    """
    oi = tier_index(old, ladder)
    ni = tier_index(new, ladder)
    if oi is None or ni is None:
        return None
    return ni - oi
