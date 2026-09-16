"""
Prediction tracking: persist forecasts, validate against reality.
"""

import json
import os
from datetime import datetime, timedelta, date

from . import analysis

TODAY = date.today()


def get_predictions_file():
    """Path to predictions JSON file."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, 'data', 'predictions.json')


def load():
    """Load existing predictions from disk."""
    path = get_predictions_file()
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {'predictions': [], 'history': []}


def save(data, path=None):
    """Save predictions to disk (strips transient fields).

    Args:
        data: {'predictions': [...], 'history': [...]}
        path: target file. Defaults to the production predictions.json.
    """
    if path is None:
        path = get_predictions_file()
    # Strip transient display fields before persisting
    transient = ('effective_confidence', 'prediction_status')
    clean = {
        'predictions': [
            {k: v for k, v in p.items() if k not in transient}
            for p in data['predictions']
        ],
        'history': [
            {k: v for k, v in p.items() if k not in transient}
            for p in data['history']
        ],
    }
    with open(path, 'w') as f:
        json.dump(clean, f, indent=2)


def _compute_effective_confidence(pred):
    """
    Compute decayed confidence for overdue predictions.
    Returns (effective_confidence, status) where status is 'active', 'fading', or 'overdue'.
    """
    predicted_sellout = pred.get('predicted_sellout_date')
    if not predicted_sellout:
        return pred.get('confidence', 0), 'active'

    predicted_dt = datetime.strptime(predicted_sellout, '%Y-%m-%d').date()
    days_overdue = (TODAY - predicted_dt).days

    if days_overdue <= 0:
        return pred.get('confidence', 0), 'active'

    base_confidence = pred.get('confidence', 0)
    decay_factor = max(0.3, 1.0 - 0.15 * days_overdue)
    effective = round(base_confidence * decay_factor, 3)

    status = 'fading' if days_overdue <= 3 else 'overdue'
    return effective, status


def validate(predictions_data, all_snapshots_by_route):
    """
    Check open predictions against current data.
    Move resolved predictions to history with outcome.
    Computes effective_confidence for remaining open predictions.
    Returns list of newly resolved predictions.
    """
    still_open = []
    newly_resolved = []

    for pred in predictions_data['predictions']:
        resolved = _check_single(pred, all_snapshots_by_route)
        if resolved:
            pred['outcome'] = resolved['outcome']
            pred['resolved_date'] = TODAY.isoformat()
            pred['actual'] = resolved.get('actual')
            newly_resolved.append(pred)
        else:
            # Compute transient decay fields (not persisted but available for display)
            eff_conf, status = _compute_effective_confidence(pred)
            pred['effective_confidence'] = eff_conf
            pred['prediction_status'] = status
            still_open.append(pred)

    predictions_data['predictions'] = still_open
    predictions_data['history'].extend(newly_resolved)
    return newly_resolved


def _find_sellout_date(snapshots, target_date, target_class):
    """Find the first snapshot date where capacity hit 0."""
    for snap in snapshots:
        classes = snap['data'].get(target_date, {})
        cap = classes.get(target_class, {}).get('capacity')
        if cap is not None and cap == 0:
            return datetime.strptime(snap['snap_date'], '%Y%m%d').date()
    return None


def _find_disappearance_date(snapshots, target_date, target_class):
    """Find the first snapshot date where a class disappeared from the data."""
    was_present = False
    for snap in snapshots:
        classes = snap['data'].get(target_date, {})
        if target_class in classes:
            was_present = True
        elif was_present and classes and target_class not in classes:
            return datetime.strptime(snap['snap_date'], '%Y%m%d').date()
    return None


def _check_single(pred, all_snapshots_by_route):
    """
    Check if a sellout prediction has come true or can be invalidated.
    Returns {'outcome': str, 'actual': str} or None if still open.
    """
    route_key = (pred['provider'], pred['route'])
    snapshots = all_snapshots_by_route.get(route_key, [])
    if not snapshots:
        return None

    target_date = pred.get('travel_date')
    target_class = pred.get('class')
    predicted_sellout = pred.get('predicted_sellout_date')

    # Direction reversal: capacity rose significantly since prediction
    if target_date and target_class and snapshots:
        latest_snap = snapshots[-1]
        latest_classes = latest_snap['data'].get(target_date, {})
        current_cap = latest_classes.get(target_class, {}).get('capacity')
        pred_cap = pred.get('current_capacity', 0)
        if current_cap is not None and current_cap > pred_cap + 2:
            return {
                'outcome': 'invalidated',
                'actual': f'capacity rose from {pred_cap} to {current_cap}',
            }

    if not all([target_date, target_class, predicted_sellout]):
        return {'outcome': 'invalid', 'actual': 'missing fields'}

    predicted_dt = datetime.strptime(predicted_sellout, '%Y-%m-%d').date()
    travel_dt = datetime.strptime(target_date, '%Y-%m-%d').date()

    # Travel date passed — check final state
    if travel_dt < TODAY:
        for snap in reversed(snapshots):
            snap_dt = datetime.strptime(snap['snap_date'], '%Y%m%d').date()
            if snap_dt <= travel_dt:
                classes = snap['data'].get(target_date, {})
                # Class missing from data = sold out
                if classes and target_class not in classes:
                    actual_sellout = _find_disappearance_date(snapshots, target_date, target_class)
                    delta = abs((actual_sellout - predicted_dt).days) if actual_sellout else 0
                    outcome = 'correct_exact' if delta <= 2 else 'correct_late'
                    return {
                        'outcome': outcome,
                        'actual': f'class disappeared (sold out, delta={delta}d)',
                    }
                actual_cap = classes.get(target_class, {}).get('capacity')
                if actual_cap is not None:
                    if actual_cap == 0:
                        # Find when it actually sold out (first snap with cap=0)
                        actual_sellout = _find_sellout_date(snapshots, target_date, target_class)
                        if actual_sellout and predicted_dt:
                            delta = abs((actual_sellout - predicted_dt).days)
                            outcome = 'correct_exact' if delta <= 1 else 'correct_late'
                            return {'outcome': outcome, 'actual': f'sold out (delta={delta}d)'}
                        else:
                            return {'outcome': 'correct_exact', 'actual': 'sold out'}
                    else:
                        # Not sold out — was there at least a strong decline?
                        pred_cap = pred.get('current_capacity', 0)
                        if pred_cap > 0 and actual_cap <= pred_cap * 0.5:
                            return {
                                'outcome': 'wrong_trend',
                                'actual': f'capacity fell {pred_cap}->{actual_cap} but not sold out',
                            }
                        return {
                            'outcome': 'wrong_reversal' if actual_cap > pred_cap else 'wrong_trend',
                            'actual': f'capacity={actual_cap} (was {pred_cap} at prediction)',
                        }
                break
        return {'outcome': 'expired', 'actual': 'no data at travel date'}

    # Predicted sellout date passed but travel date hasn't
    if predicted_dt < TODAY:
        latest = snapshots[-1]
        classes = latest['data'].get(target_date, {})
        if classes and target_class not in classes:
            # Class disappeared from data = sold out
            actual_sellout = _find_disappearance_date(snapshots, target_date, target_class)
            delta = abs((actual_sellout - predicted_dt).days) if actual_sellout else 0
            outcome = 'correct_exact' if delta <= 2 else 'correct_late'
            return {
                'outcome': outcome,
                'actual': f'class disappeared (sold out, delta={delta}d)',
            }
        actual_cap = classes.get(target_class, {}).get('capacity')
        if actual_cap is not None:
            if actual_cap == 0:
                delta = (TODAY - predicted_dt).days
                outcome = 'correct_exact' if delta <= 1 else 'correct_late'
                return {'outcome': outcome, 'actual': f'sold out (confirmed, {delta}d late)'}
            margin_days = (TODAY - predicted_dt).days
            if margin_days > 3:
                pred_cap = pred.get('current_capacity', 0)
                if actual_cap > pred_cap:
                    outcome = 'wrong_reversal'
                elif pred_cap > 0 and actual_cap <= pred_cap * 0.5:
                    outcome = 'wrong_trend'
                else:
                    outcome = 'wrong_reversal'
                return {
                    'outcome': outcome,
                    'actual': f'still {actual_cap} seats on {TODAY.isoformat()} (was {pred_cap})',
                }

    return None  # still open


def create_sellout_predictions(fill_curves, provider, route, min_confidence=0.7, max_days=30):
    """
    Generate new sellout predictions from fill curve analysis.
    Returns list of prediction dicts.
    """
    new_predictions = []

    for travel_date, classes in fill_curves.items():
        try:
            travel_dt = datetime.strptime(travel_date, '%Y-%m-%d').date()
        except ValueError:
            continue
        if travel_dt < TODAY:
            continue

        for cls_name, points in classes.items():
            result = analysis.sellout_prediction(points)
            if not result:
                continue
            if result['current_capacity'] < 3 or result['decline_rate'] < 0.1:
                continue
            if result['confidence'] > min_confidence and result['days_to_sellout'] < max_days:
                sellout_date = TODAY + timedelta(days=result['days_to_sellout'])
                if sellout_date < travel_dt:
                    new_predictions.append({
                        'provider': provider,
                        'route': route,
                        'travel_date': travel_date,
                        'class': cls_name,
                        'predicted_sellout_date': sellout_date.isoformat(),
                        'confidence': result['confidence'],
                        'decline_rate': result['decline_rate'],
                        'current_capacity': result['current_capacity'],
                        'created_date': TODAY.isoformat(),
                    })

    return new_predictions


def _should_supersede(old, new, days_threshold=2):
    """Check if a new prediction should replace an existing one."""
    old_sellout = old.get('predicted_sellout_date', '')
    new_sellout = new.get('predicted_sellout_date', '')
    if old_sellout and new_sellout:
        old_dt = datetime.strptime(old_sellout, '%Y-%m-%d').date()
        new_dt = datetime.strptime(new_sellout, '%Y-%m-%d').date()
        if abs((new_dt - old_dt).days) > days_threshold:
            return True
    old_conf = old.get('confidence', 0)
    new_conf = new.get('confidence', 0)
    if abs(new_conf - old_conf) > 0.15:
        return True
    return False


def add_new(predictions_data, new_predictions, supersede_days_threshold=7):
    """
    Add new predictions, superseding stale ones if significantly different.
    Skips keys that were recently invalidated (same resolved_date = today).
    Returns count of actually added predictions.
    """
    # Build cooldown set: keys invalidated or wrong today (avoid re-creation loops)
    cooldown_keys = set()
    for h in predictions_data['history']:
        if h.get('resolved_date') == TODAY.isoformat():
            if h.get('outcome') in ('invalidated', 'wrong_reversal'):
                key = (h.get('provider'), h.get('route'), h.get('travel_date'), h.get('class'))
                cooldown_keys.add(key)

    existing_by_key = {}
    for i, p in enumerate(predictions_data['predictions']):
        key = (p['provider'], p['route'], p['travel_date'], p['class'])
        existing_by_key[key] = i

    added = 0
    superseded_indices = set()

    for pred in new_predictions:
        key = (pred['provider'], pred['route'], pred['travel_date'], pred['class'])
        if key in cooldown_keys:
            continue
        if key not in existing_by_key:
            predictions_data['predictions'].append(pred)
            existing_by_key[key] = len(predictions_data['predictions']) - 1
            added += 1
        else:
            idx = existing_by_key[key]
            old = predictions_data['predictions'][idx]
            if _should_supersede(old, pred, days_threshold=supersede_days_threshold):
                # Move old to history as superseded
                old['outcome'] = 'superseded'
                old['resolved_date'] = TODAY.isoformat()
                old['actual'] = f"superseded by prediction from {pred['created_date']}"
                predictions_data['history'].append(old)
                # Replace with new
                predictions_data['predictions'][idx] = pred
                superseded_indices.add(idx)
                added += 1

    return added


def accuracy_stats(predictions_data):
    """
    Compute accuracy statistics from history.
    Returns dict with total, correct, wrong, expired, accuracy_pct.
    """
    history = predictions_data.get('history', [])
    total = len(history)
    correct = sum(1 for h in history if h.get('outcome', '').startswith('correct'))
    wrong = sum(1 for h in history if h.get('outcome', '').startswith('wrong'))
    expired = sum(1 for h in history if h.get('outcome') == 'expired')
    invalidated = sum(1 for h in history if h.get('outcome') == 'invalidated')
    superseded = sum(1 for h in history if h.get('outcome') == 'superseded')
    evaluated = correct + wrong
    accuracy = (correct / evaluated * 100) if evaluated > 0 else 0

    # Weighted score: correct_exact=1.0, correct_late=0.7, wrong_trend=0.3, wrong_reversal=0.0
    weighted_sum = 0
    weighted_count = 0
    for h in history:
        o = h.get('outcome', '')
        if o == 'correct_exact':
            weighted_sum += 1.0; weighted_count += 1
        elif o == 'correct_late':
            weighted_sum += 0.7; weighted_count += 1
        elif o == 'wrong_trend':
            weighted_sum += 0.3; weighted_count += 1
        elif o == 'wrong_reversal':
            weighted_sum += 0.0; weighted_count += 1
    weighted_score = (weighted_sum / weighted_count * 100) if weighted_count > 0 else 0

    return {
        'total': total,
        'correct': correct,
        'wrong': wrong,
        'expired': expired,
        'invalidated': invalidated,
        'superseded': superseded,
        'accuracy_pct': round(accuracy, 1),
        'weighted_score': round(weighted_score, 1),
    }
