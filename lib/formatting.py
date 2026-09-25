"""
Output formatting helpers for night-train-monitor.
"""

from datetime import datetime, date

TODAY = date.today()


def section(title):
    """Print a section header."""
    print(f"\n{'─' * 70}")
    print(f"  {title}")
    print(f"{'─' * 70}\n")


def route_label(provider, route):
    """Format a route label like [ES] hamburg-paris."""
    return f"[{provider.upper()}] {route}"


def print_fill_summary(fill_curves, top_n=10):
    """Print the fastest-filling travel dates."""
    fast_fillers = []
    for travel_date, classes in fill_curves.items():
        for cls_name, points in classes.items():
            if len(points) < 2:
                continue
            first_cap = points[0][1]
            last_cap = points[-1][1]
            if first_cap is None or last_cap is None:
                continue
            if first_cap == 0:
                continue
            pct_sold = (first_cap - last_cap) / first_cap * 100
            days_span = (datetime.strptime(points[-1][0], '%Y%m%d') -
                         datetime.strptime(points[0][0], '%Y%m%d')).days
            if days_span == 0:
                continue
            rate = (first_cap - last_cap) / days_span
            fast_fillers.append({
                'travel_date': travel_date,
                'class': cls_name,
                'pct_sold': round(pct_sold, 1),
                'rate': round(rate, 2),
                'current_cap': last_cap,
                'first_cap': first_cap,
                'days_observed': days_span,
                'current_price': points[-1][2],
            })

    fast_fillers.sort(key=lambda x: -x['pct_sold'])

    if not fast_fillers:
        print("  No fill data available.")
        return

    print(f"  {'Date':<12} {'Class':<20} {'Sold%':>6} {'Rate':>6} {'Cap':>5} {'Price':>8} {'Observed':>9}")
    print(f"  {'─' * 12} {'─' * 20} {'─' * 6} {'─' * 6} {'─' * 5} {'─' * 8} {'─' * 9}")
    for item in fast_fillers[:top_n]:
        print(f"  {item['travel_date']:<12} {item['class']:<20} "
              f"{item['pct_sold']:>5.1f}% {item['rate']:>5.1f}/d "
              f"{item['current_cap']:>5} {item['current_price']:>7.1f}€ "
              f"{item['days_observed']:>7}d")


def print_sellout_predictions(fill_curves, top_n=10):
    """Print sellout predictions."""
    from . import analysis
    from datetime import datetime, date as date_cls
    today = date_cls.today()
    predictions = []
    for travel_date, classes in fill_curves.items():
        try:
            travel_dt = datetime.strptime(travel_date, '%Y-%m-%d').date()
        except ValueError:
            continue
        for cls_name, points in classes.items():
            result = analysis.sellout_prediction(points)
            if result and result['confidence'] > 0.3:
                days_to_departure = (travel_dt - today).days
                if result['days_to_sellout'] < days_to_departure:
                    predictions.append({
                        'travel_date': travel_date,
                        'class': cls_name,
                        **result,
                    })

    predictions.sort(key=lambda x: x['days_to_sellout'])

    if not predictions:
        print("  No sellout predictions (insufficient decline or data).")
        return

    print(f"  {'Date':<12} {'Class':<20} {'Sellout in':>10} {'Rate':>7} {'Cap':>5} {'R²':>5} {'Pts':>4}")
    print(f"  {'─' * 12} {'─' * 20} {'─' * 10} {'─' * 7} {'─' * 5} {'─' * 5} {'─' * 4}")
    for p in predictions[:top_n]:
        days_str = f"{p['days_to_sellout']:.0f}d"
        print(f"  {p['travel_date']:<12} {p['class']:<20} "
              f"{days_str:>10} {p['decline_rate']:>5.1f}/d "
              f"{p['current_capacity']:>5} {p['confidence']:>5.2f} {p['data_points']:>4}")


def print_booking_window(window_data):
    """Print optimal booking window analysis."""
    for cls_name, buckets in sorted(window_data.items()):
        if not buckets:
            continue
        print(f"  {cls_name}:")
        print(f"    {'Lead time':<10} {'Avg':>8} {'Min':>8} {'Max':>8} {'Samples':>8}")
        print(f"    {'─' * 10} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 8}")
        for b in buckets:
            print(f"    {b['bucket']:<10} {b['avg_price']:>7.1f}€ {b['min_price']:>7.1f}€ "
                  f"{b['max_price']:>7.1f}€ {b['samples']:>8}")
        valid = [b for b in buckets if b['samples'] >= 3]
        if valid:
            best = min(valid, key=lambda b: b['avg_price'])
            print(f"    → Sweet spot: {best['bucket']} (avg {best['avg_price']:.1f}€)")
        print()


def print_weekday_heatmap(heatmap_data):
    """Print weekday price/capacity heatmap."""
    weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    for cls_name, wd_data in sorted(heatmap_data.items()):
        if not wd_data:
            continue
        print(f"  {cls_name}:")
        header = "    " + "".join(f"{wd:>8}" for wd in weekdays)
        print(header)
        price_line = "    " + "".join(
            f"{wd_data[wd]['avg_price']:>7.1f}€" if wd in wd_data else f"{'—':>8}"
            for wd in weekdays
        )
        print(f"  € {price_line[4:]}")

        valid_wds = [(wd, wd_data[wd]['avg_price']) for wd in weekdays if wd in wd_data]
        if valid_wds:
            cheapest = min(valid_wds, key=lambda x: x[1])
            priciest = max(valid_wds, key=lambda x: x[1])
            if cheapest[1] < priciest[1]:
                print(f"    → Cheapest: {cheapest[0]} ({cheapest[1]:.1f}€), "
                      f"Most expensive: {priciest[0]} ({priciest[1]:.1f}€), "
                      f"Δ={((priciest[1] - cheapest[1]) / cheapest[1] * 100):.0f}%")
        print()


def print_tier_alerts(alerts, top_n=10):
    """Print tier-transition alerts."""
    cheap = [a for a in alerts if a['type'] == 'CHEAP']
    expensive = [a for a in alerts if a['type'] == 'EXPENSIVE']

    if cheap:
        print("  🟢 UNUSUALLY CHEAP (potential buy signals):")
        print(f"    {'Date':<12} {'Class':<20} {'Price':>7} {'Expected':>9} {'Δ':>6} {'Lead':>5} {'Cap':>5}")
        print(f"    {'─' * 12} {'─' * 20} {'─' * 7} {'─' * 9} {'─' * 6} {'─' * 5} {'─' * 5}")
        for a in cheap[:top_n]:
            cap_str = str(a['capacity']) if a['capacity'] is not None else '?'
            print(f"    {a['travel_date']:<12} {a['class']:<20} "
                  f"{a['price']:>6.1f}€ {a['expected']:>8.1f}€ "
                  f"{a['deviation_pct']:>+5.0f}% {a['lead_days']:>4}d {cap_str:>5}")
        print()

    if expensive:
        print("  🔴 UNUSUALLY EXPENSIVE (avoid or wait):")
        print(f"    {'Date':<12} {'Class':<20} {'Price':>7} {'Expected':>9} {'Δ':>6} {'Lead':>5} {'Cap':>5}")
        print(f"    {'─' * 12} {'─' * 20} {'─' * 7} {'─' * 9} {'─' * 6} {'─' * 5} {'─' * 5}")
        for a in expensive[:top_n]:
            cap_str = str(a['capacity']) if a['capacity'] is not None else '?'
            print(f"    {a['travel_date']:<12} {a['class']:<20} "
                  f"{a['price']:>6.1f}€ {a['expected']:>8.1f}€ "
                  f"{a['deviation_pct']:>+5.0f}% {a['lead_days']:>4}d {cap_str:>5}")
        print()

    if not cheap and not expensive:
        print("  No significant tier deviations detected.")


def print_prediction_results(resolved, predictions_data):
    """Print prediction validation results."""
    if resolved:
        correct = sum(1 for r in resolved if r.get('outcome', '').startswith('correct'))
        wrong = sum(1 for r in resolved if r.get('outcome', '').startswith('wrong'))
        print(f"  Resolved since last run: {len(resolved)} ({correct} correct, {wrong} wrong)")
        for r in resolved:
            o = r.get('outcome', '')
            icon = '✓' if o.startswith('correct') else '✗' if o.startswith('wrong') else '?'
            print(f"    {icon} [{r['provider'].upper()}] {r['route']} {r['travel_date']} "
                  f"{r['class']} — {o}: {r.get('actual', '')}")
        print()

    from . import predictions as pred_mod
    stats = pred_mod.accuracy_stats(predictions_data)
    if stats['total']:
        print(f"  Overall accuracy: {stats['correct']}/{stats['correct'] + stats['wrong']} = "
              f"{stats['accuracy_pct']:.0f}% (total tracked: {stats['total']})")

    open_preds = predictions_data['predictions']
    if open_preds:
        print(f"\n  Open predictions ({len(open_preds)}):")
        for p in sorted(open_preds, key=lambda x: x['predicted_sellout_date'])[:10]:
            pred_dt = datetime.strptime(p['predicted_sellout_date'], '%Y-%m-%d').date()
            days_left = (pred_dt - TODAY).days
            eff_conf = p.get('effective_confidence', p['confidence'])
            pred_status = p.get('prediction_status', 'active')
            if days_left > 0:
                status = f"in {days_left}d"
            elif pred_status == 'fading':
                status = "FADING"
            else:
                status = "OVERDUE"
            conf_str = f"R²={eff_conf:.2f}" if pred_status != 'active' else f"R²={p['confidence']:.2f}"
            print(f"    [{p['provider'].upper()}] {p['route']} {p['travel_date']} "
                  f"{p['class']} — sellout {status} ({conf_str})")


def print_anomaly_summary(anomalies, top_n=10):
    """Print anomaly scan results."""
    drops = anomalies['price_drops']
    spikes = anomalies['price_spikes']
    sellouts = anomalies['sellouts']
    appearances = anomalies['appearances']
    sysmoves = anomalies.get('system_moves', [])

    if sysmoves:
        print(f"  System-wide tier moves ({len(sysmoves)}):")
        for snap, cls, direction, moved, active, _from, to_tier in sysmoves[:top_n]:
            arrow = "↓" if direction == 'down' else "↑"
            dest = f" → tier {to_tier}" if to_tier is not None else ""
            print(f"    [{snap}] {cls:<22} {arrow} {moved}/{active} dates{dest}")
        print()

    if drops:
        print(f"  Price drops ({len(drops)} total, showing top {min(top_n, len(drops))}):")
        for snap, dt, cls, old, new, pct, lead in drops[:top_n]:
            lead_str = f"{lead}d" if lead is not None else "?"
            print(f"    [{snap}] {dt}  {cls:<22} {old:>7.1f} → {new:>7.1f}  ({pct:>+.0f}%)  lead={lead_str}")
        print()

    if spikes:
        print(f"  Price spikes ({len(spikes)} total, showing top {min(top_n, len(spikes))}):")
        for snap, dt, cls, old, new, pct, lead in spikes[:top_n]:
            lead_str = f"{lead}d" if lead is not None else "?"
            print(f"    [{snap}] {dt}  {cls:<22} {old:>7.1f} → {new:>7.1f}  ({pct:>+.0f}%)  lead={lead_str}")
        print()

    if sellouts:
        print(f"  Sellouts ({len(sellouts)}):")
        for snap, dt, classes, lead in sellouts[:top_n]:
            lead_str = f"{lead}d" if lead is not None else "?"
            print(f"    [{snap}] {dt}  {', '.join(classes)}  lead={lead_str}")
        print()

    if appearances:
        print(f"  New availability ({len(appearances)}):")
        for snap, dt, classes, lead in appearances[:top_n]:
            lead_str = f"{lead}d" if lead is not None else "?"
            print(f"    [{snap}] {dt}  {', '.join(classes)}  lead={lead_str}")
        print()

    if not any([drops, spikes, sellouts, appearances, sysmoves]):
        print("  No anomalies detected.")
