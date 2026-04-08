import datetime
from collections import defaultdict


def ensure_manual_close(data):
    if "manual_close" not in data:
        data["manual_close"] = {}


def ensure_session_settings(data):
    today = datetime.date.today().isoformat()
    if "current_open_day" not in data or not data["current_open_day"]:
        data["current_open_day"] = today
    if "auto_close_enabled" not in data:
        data["auto_close_enabled"] = False
    if "auto_close_time" not in data:
        data["auto_close_time"] = "21:00"
    if "auto_last_close_date" not in data:
        data["auto_last_close_date"] = None
    if "day_open_time" not in data:
        data["day_open_time"] = "04:30"
    if "day_close_time" not in data:
        data["day_close_time"] = "20:30"
    if "streak_kind" not in data:
        data["streak_kind"] = None
    if "streak_count" not in data:
        data["streak_count"] = 0
    if "positive_streak_carry_active" not in data:
        data["positive_streak_carry_active"] = False
    if "positive_streak_carry_multiplier" not in data:
        data["positive_streak_carry_multiplier"] = 1.0
    if "positive_streak_carry_count" not in data:
        data["positive_streak_carry_count"] = 0
    if "multiplier_settings" not in data or not isinstance(data["multiplier_settings"], dict):
        data["multiplier_settings"] = {}
    ms = data["multiplier_settings"]
    if "positive_step_factor" not in ms:
        ms["positive_step_factor"] = 3.0
    if "negative_step_factor" not in ms:
        ms["negative_step_factor"] = 4.0
    if "negative_start_ratio_from_positive" not in ms:
        ms["negative_start_ratio_from_positive"] = 0.75
    if "positive_cap" not in ms:
        ms["positive_cap"] = 100.0
    if "negative_cap" not in ms:
        ms["negative_cap"] = 200.0


def ensure_tasks(data):
    if "tasks" not in data or not isinstance(data["tasks"], list):
        data["tasks"] = []
    for t in data["tasks"]:
        t.setdefault("id", datetime.datetime.now().isoformat())
        t.setdefault("name", "Unnamed task")
        t.setdefault("points", 0)
        t.setdefault("deadline", None)
        t.setdefault("status", "open")
        t.setdefault("created", datetime.datetime.now().isoformat())


def ensure_habit_metadata(data):
    habits = data.get("habits", [])
    for h in habits:
        if "category" not in h or not str(h.get("category", "")).strip():
            h["category"] = "General"
        if "execution_count" not in h:
            h["execution_count"] = 0


def recalc_habit_execution_counts(data):
    counts = defaultdict(int)
    for entry in data.get("log", []):
        name = str(entry.get("habit", "")).strip()
        if name:
            counts[name] += 1
    for h in data.get("habits", []):
        h["execution_count"] = counts.get(str(h.get("name", "")).strip(), 0)
