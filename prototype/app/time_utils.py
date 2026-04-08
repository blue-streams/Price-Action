import datetime


def parse_hhmm(raw):
    text = str(raw).strip()
    parts = text.split(":")
    if len(parts) != 2:
        raise ValueError
    hour = int(parts[0])
    minute = int(parts[1])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError
    return f"{hour:02d}:{minute:02d}", hour, minute


def next_date_str(date_str):
    d = datetime.date.fromisoformat(date_str)
    return (d + datetime.timedelta(days=1)).isoformat()
