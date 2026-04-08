DATA_FILE = "habit_data.json"
MAX_VISIBLE_CANDLES = 35

TIMEFRAME_OPTIONS = [
    ("1D", "1 day"),
    ("SESSION", "session"),
    ("1W", "1 week"),
    ("1M", "1 month"),
    ("6M", "6 months"),
    ("1Y", "1 year"),
    ("YTD", "YTD"),
]

DEFAULT_HABITS = [
    {"name": "Exercise", "points": 30, "emoji": "🏋️"},
    {"name": "Read 30 min", "points": 20, "emoji": "📚"},
    {"name": "Meditate", "points": 15, "emoji": "🧘"},
    {"name": "Drink 2L water", "points": 10, "emoji": "💧"},
    {"name": "Sleep 8 hrs", "points": 25, "emoji": "😴"},
    {"name": "Skipped workout", "points": -200, "emoji": "❌"},
    {"name": "Junk food", "points": -150, "emoji": "🍔"},
    {"name": "Screen > 4 hrs", "points": -100, "emoji": "📱"},
]
