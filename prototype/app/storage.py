import datetime
import json
import os

from .constants import DATA_FILE, DEFAULT_HABITS


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "habits": DEFAULT_HABITS,
        "log": [],
        "manual_close": {},
        "current_open_day": datetime.date.today().isoformat(),
        "auto_close_enabled": False,
        "auto_close_time": "21:00",
        "auto_last_close_date": None,
    }


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
