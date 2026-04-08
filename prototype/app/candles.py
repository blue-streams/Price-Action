import datetime
from collections import defaultdict

from .time_utils import next_date_str


def compute_candlestick_data(log, manual_close):
    def _effective_date(entry):
        ts = str(entry.get("timestamp", "")).strip()
        if ts:
            try:
                return datetime.datetime.fromisoformat(ts).date().isoformat()
            except Exception:
                pass
        return entry.get("date")

    daily = defaultdict(list)
    for entry in log:
        day_key = _effective_date(entry)
        if not day_key:
            continue
        daily[day_key].append(entry["points"])

    all_dates = sorted(set(list(daily.keys()) + list(manual_close.keys())))
    result = []
    running_total = 0

    for date in all_dates:
        open_val = running_total
        events = daily.get(date, [])
        cum = open_val
        high_val = open_val
        low_val = open_val
        for p in events:
            cum += p
            high_val = max(high_val, cum)
            low_val = min(low_val, cum)

        close_val = cum
        running_total = close_val

        if date in manual_close:
            manual_val = manual_close[date]
            high_val = max(high_val, manual_val)
            low_val = min(low_val, manual_val)
            is_manual = True
        else:
            manual_val = None
            is_manual = False
        result.append(
            {
                "date": date,
                "open": open_val,
                "high": high_val,
                "low": low_val,
                "close": close_val,
                "is_manual": is_manual,
                "manual_close": manual_val,
            }
        )

    if result:
        last_date = result[-1]["date"]
        next_date = next_date_str(last_date)
        last_close = result[-1]["close"]
        result.append(
            {
                "date": next_date,
                "open": last_close,
                "high": last_close,
                "low": last_close,
                "close": last_close,
                "is_manual": False,
            }
        )

    return result
