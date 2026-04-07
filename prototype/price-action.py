"""
Habit Tracker with Candlestick Chart
=====================================
Run with:  python3 habit_tracker.py
Requires:  pip install matplotlib

Features:
  - Log habits with point awards/deductions
  - Candlestick chart showing daily OHLC point history
  - Click any candle to edit that day's entries or set a manual close value
  - Data saved to habit_data.json automatically
"""

import json
import os
import datetime
import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import defaultdict

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
    {"name": "Exercise",        "points":  30, "emoji": "🏋️"},
    {"name": "Read 30 min",     "points":  20, "emoji": "📚"},
    {"name": "Meditate",        "points":  15, "emoji": "🧘"},
    {"name": "Drink 2L water",  "points":  10, "emoji": "💧"},
    {"name": "Sleep 8 hrs",     "points":  25, "emoji": "😴"},
    {"name": "Skipped workout", "points": -200, "emoji": "❌"},
    {"name": "Junk food",       "points": -150, "emoji": "🍔"},
    {"name": "Screen > 4 hrs",  "points": -100, "emoji": "📱"},
]

# ──────────────────────────────────────────────────────────────────────────────
# Data helpers
# ──────────────────────────────────────────────────────────────────────────────

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
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
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

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

def _next_date_str(date_str):
    d = datetime.date.fromisoformat(date_str)
    return (d + datetime.timedelta(days=1)).isoformat()

def compute_candlestick_data(log, manual_close):
    """
    Groups log entries by day and computes OHLC-style data.
    Close values always follow true cumulative logged points.
    If a day has a manual_close value, it is shown as a marker only and does
    not change cumulative totals.
    """
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
        events   = daily.get(date, [])
        cum      = open_val
        high_val = open_val
        low_val  = open_val
        for p in events:
            cum     += p
            high_val = max(high_val, cum)
            low_val  = min(low_val,  cum)

        natural_close = cum
        close_val = natural_close
        running_total = close_val

        if date in manual_close:
            manual_val = manual_close[date]
            high_val   = max(high_val, manual_val)
            low_val    = min(low_val,  manual_val)
            is_manual  = True
        else:
            manual_val = None
            is_manual  = False
        result.append({
            "date":      date,
            "open":      open_val,
            "high":      high_val,
            "low":       low_val,
            "close":     close_val,
            "is_manual": is_manual,
            "manual_close": manual_val,
        })
    # Mimic stock charts: once a day closes, show the next day's opening candle.
    # This "open day" starts at the latest close and has no movement yet.
    if result:
        last_date  = result[-1]["date"]
        next_date  = _next_date_str(last_date)
        last_close = result[-1]["close"]
        result.append({
            "date":      next_date,
            "open":      last_close,
            "high":      last_close,
            "low":       last_close,
            "close":     last_close,
            "is_manual": False,
        })

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Day-edit dialog
# ──────────────────────────────────────────────────────────────────────────────

class DayEditDialog(tk.Toplevel):
    """
    Modal dialog that lets the user:
      - View and delete individual log entries for a chosen date
      - Add a new habit entry manually
      - Set or clear a manual close value for the candlestick
    """

    def __init__(self, parent, app, date_str):
        super().__init__(parent)
        self.app      = app
        self.date_str = date_str
        self.title(f"Edit day — {date_str}")
        self.configure(bg="#0f0f0f")
        self.resizable(False, False)
        self.grab_set()
        self._build()
        self._center()

    def _center(self):
        self.update_idletasks()
        pw = self.master.winfo_rootx() + self.master.winfo_width()  // 2
        ph = self.master.winfo_rooty() + self.master.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{pw - w//2}+{ph - h//2}")

    def _build(self):
        PAD = {"padx": 12, "pady": 6}

        tk.Label(self, text=f"Editing: {self.date_str}",
                 bg="#0f0f0f", fg="#ffffff",
                 font=("Courier New", 13, "bold")).pack(**PAD)

        day_state = tk.Frame(self, bg="#0f0f0f")
        day_state.pack(fill=tk.X, padx=12, pady=(0, 4))
        tk.Button(day_state, text="Open this day for logging",
                  bg="#10223a", fg="#7fb5ff", activebackground="#163154",
                  font=("Courier New", 9), relief="flat", padx=8,
                  command=self._set_open_day_here).pack(side=tk.LEFT)
        if self.app.data.get("current_open_day") == self.date_str:
            tk.Label(day_state, text="  currently OPEN",
                     bg="#0f0f0f", fg="#6ea8ff",
                     font=("Courier New", 9, "bold")).pack(side=tk.LEFT)

        # ── Existing entries ──────────────────────────────────────────────── #
        tk.Label(self, text="Logged habits  (select row to delete)",
                 bg="#0f0f0f", fg="#888888",
                 font=("Courier New", 9)).pack(anchor="w", padx=12)

        list_frame = tk.Frame(self, bg="#0f0f0f")
        list_frame.pack(fill=tk.BOTH, padx=12, pady=(2, 6))
        sb = tk.Scrollbar(list_frame, bg="#1a1a2e", troughcolor="#0f0f0f")
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox = tk.Listbox(
            list_frame, bg="#111122", fg="#cccccc",
            selectbackground="#252545", selectforeground="#ffffff",
            font=("Courier New", 10), relief="flat",
            height=7, width=48, yscrollcommand=sb.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH)
        sb.config(command=self.listbox.yview)
        self._populate_listbox()

        btn_row = tk.Frame(self, bg="#0f0f0f")
        btn_row.pack(fill=tk.X, padx=12, pady=(0, 6))
        tk.Button(btn_row, text="Delete selected",
                  bg="#3a1010", fg="#ff6666", activebackground="#551111",
                  font=("Courier New", 9), relief="flat", padx=8,
                  command=self._delete_selected).pack(side=tk.LEFT)
        tk.Button(btn_row, text="Delete ALL entries for this day",
                  bg="#2a0808", fg="#cc4444", activebackground="#441111",
                  font=("Courier New", 9), relief="flat", padx=8,
                  command=self._delete_all).pack(side=tk.LEFT, padx=(8, 0))

        tk.Frame(self, bg="#222222", height=1).pack(fill=tk.X, padx=12, pady=6)

        # ── Add new entry ─────────────────────────────────────────────────── #
        tk.Label(self, text="Add a habit entry to this day",
                 bg="#0f0f0f", fg="#888888",
                 font=("Courier New", 9)).pack(anchor="w", padx=12)

        add_row = tk.Frame(self, bg="#0f0f0f")
        add_row.pack(fill=tk.X, padx=12, pady=(2, 4))

        self.new_habit_var = tk.StringVar()
        self.new_pts_var   = tk.StringVar()
        habit_names = [h["name"] for h in self.app.data["habits"]]
        if habit_names:
            self.new_habit_var.set(habit_names[0])

        habit_menu = ttk.Combobox(add_row, textvariable=self.new_habit_var,
                                  values=habit_names, width=22,
                                  font=("Courier New", 10), state="normal")
        habit_menu.pack(side=tk.LEFT, ipady=4)

        tk.Label(add_row, text=" pts:", bg="#0f0f0f", fg="#888888",
                 font=("Courier New", 10)).pack(side=tk.LEFT)
        tk.Entry(add_row, textvariable=self.new_pts_var,
                 bg="#1a1a2e", fg="#e8e8e8", insertbackground="#e8e8e8",
                 font=("Courier New", 10), relief="flat",
                 highlightthickness=1, highlightcolor="#333366",
                 width=7).pack(side=tk.LEFT, ipady=4, padx=(2, 6))

        def _autofill(event=None):
            for h in self.app.data["habits"]:
                if h["name"] == self.new_habit_var.get():
                    self.new_pts_var.set(str(h["points"]))
                    break
        habit_menu.bind("<<ComboboxSelected>>", _autofill)

        tk.Button(add_row, text="Add entry",
                  bg="#0a2a1a", fg="#00cc66", activebackground="#0d3d25",
                  font=("Courier New", 9), relief="flat", padx=8,
                  command=self._add_entry).pack(side=tk.LEFT)

        tk.Frame(self, bg="#222222", height=1).pack(fill=tk.X, padx=12, pady=6)

        # ── Manual close override ─────────────────────────────────────────── #
        mc = self.app.data["manual_close"].get(self.date_str)
        tk.Label(self, text="Manual close override  (overrides natural close, cascades forward)",
                 bg="#0f0f0f", fg="#888888",
                 font=("Courier New", 9)).pack(anchor="w", padx=12)

        mc_row = tk.Frame(self, bg="#0f0f0f")
        mc_row.pack(fill=tk.X, padx=12, pady=(2, 10))

        self.mc_var = tk.StringVar(value=str(mc) if mc is not None else "")
        tk.Entry(mc_row, textvariable=self.mc_var,
                 bg="#1a1a2e", fg="#ffcc44", insertbackground="#ffcc44",
                 font=("Courier New", 11, "bold"), relief="flat",
                 highlightthickness=1, highlightcolor="#554400",
                 width=10).pack(side=tk.LEFT, ipady=5)

        tk.Button(mc_row, text="Set close",
                  bg="#1a1500", fg="#ffcc44", activebackground="#2a2200",
                  font=("Courier New", 9), relief="flat", padx=8,
                  command=self._set_manual_close).pack(side=tk.LEFT, padx=(8, 4))
        tk.Button(mc_row, text="Clear override",
                  bg="#111111", fg="#666666", activebackground="#1e1e1e",
                  font=("Courier New", 9), relief="flat", padx=8,
                  command=self._clear_manual_close).pack(side=tk.LEFT)
        if mc is not None:
            tk.Label(mc_row, text=f"  currently: {mc:+d}",
                     bg="#0f0f0f", fg="#aa8800",
                     font=("Courier New", 9)).pack(side=tk.LEFT)

        # ── Done ─────────────────────────────────────────────────────────── #
        tk.Button(self, text="Done — close editor",
                  bg="#1a1a2e", fg="#aaaaee", activebackground="#252545",
                  font=("Courier New", 10), relief="flat", padx=12,
                  command=self.destroy).pack(pady=(0, 12))

    def _populate_listbox(self):
        self.listbox.delete(0, tk.END)
        self._day_entries = [e for e in self.app.data["log"]
                             if e["date"] == self.date_str]
        if not self._day_entries:
            self.listbox.insert(tk.END, "  (no habit entries for this day)")
        for e in self._day_entries:
            sign = "+" if e["points"] >= 0 else ""
            ts   = e.get("timestamp", "")[:16].replace("T", " ")
            self.listbox.insert(
                tk.END, f"  {sign}{e['points']:>4}  {e['habit']:<28} {ts}")

    def _delete_selected(self):
        sel = self.listbox.curselection()
        if not sel or not self._day_entries:
            return
        idx = sel[0]
        if idx >= len(self._day_entries):
            return
        entry = self._day_entries[idx]
        if messagebox.askyesno("Delete entry",
                               f"Remove '{entry['habit']}' ({entry['points']:+d} pts)?",
                               parent=self):
            self.app.data["log"].remove(entry)
            save_data(self.app.data)
            self._populate_listbox()
            self.app._update_display()
            self.app._refresh_chart()

    def _delete_all(self):
        if not self._day_entries:
            return
        if messagebox.askyesno("Delete all",
                               f"Delete ALL {len(self._day_entries)} entries for {self.date_str}?",
                               parent=self):
            self.app.data["log"] = [e for e in self.app.data["log"]
                                    if e["date"] != self.date_str]
            save_data(self.app.data)
            self._populate_listbox()
            self.app._update_display()
            self.app._refresh_chart()

    def _add_entry(self):
        name    = self.new_habit_var.get().strip()
        pts_str = self.new_pts_var.get().strip()
        if not name:
            messagebox.showwarning("Missing name", "Enter a habit name.", parent=self)
            return
        try:
            pts = int(pts_str)
        except ValueError:
            messagebox.showerror("Bad points", "Points must be an integer.", parent=self)
            return
        entry = {
            "date":      self.date_str,
            "habit":     name,
            "points":    pts,
            "timestamp": f"{self.date_str}T12:00:00",
        }
        self.app.data["log"].append(entry)
        save_data(self.app.data)
        self._populate_listbox()
        self.app._update_display()
        self.app._refresh_chart()

    def _set_manual_close(self):
        try:
            val = int(self.mc_var.get().strip())
        except ValueError:
            messagebox.showerror("Bad value",
                                 "Close value must be an integer.", parent=self)
            return
        self.app.data["manual_close"][self.date_str] = val
        save_data(self.app.data)
        self.app._update_display()
        self.app._refresh_chart()
        messagebox.showinfo("Close set",
                            f"Manual close for {self.date_str} set to {val:+d}.\n"
                            "Candlestick closes continue to follow logged total points.\n"
                            "Manual close is shown as a marker.",
                            parent=self)

    def _clear_manual_close(self):
        if self.date_str in self.app.data["manual_close"]:
            del self.app.data["manual_close"][self.date_str]
            save_data(self.app.data)
            self.app._update_display()
            self.app._refresh_chart()
        self.mc_var.set("")
        messagebox.showinfo("Cleared",
                            f"Manual close for {self.date_str} removed.",
                            parent=self)

    def _set_open_day_here(self):
        self.app._set_open_day(self.date_str)
        messagebox.showinfo(
            "Open day changed",
            f"Habits will now log into {self.date_str}.",
            parent=self
        )
        self.destroy()


# ──────────────────────────────────────────────────────────────────────────────
# Main application
# ──────────────────────────────────────────────────────────────────────────────

class HabitTrackerApp:
    def __init__(self, root):
        self.root  = root
        self.root.title("Habit Tracker")
        self.root.configure(bg="#0b1220")
        self.root.geometry("1150x740")
        self.root.resizable(True, True)

        self.data  = load_data()
        ensure_manual_close(self.data)
        ensure_session_settings(self.data)
        self.today = datetime.date.today().isoformat()

        self._candle_dates = []   # populated by _refresh_chart
        self._chart_view_start = 0
        self._visible_start = 0
        self._visible_len = 0
        self._chart_timeframe = "6M"
        self._timeframe_buttons = {}
        self._ui_anim_tick = 0
        self._live_chart_text = None

        self._build_ui()
        self._refresh_chart()
        self._start_ui_animations()

    # ── UI ────────────────────────────────────────────────────────────────── #

    def _make_broker_button(self, parent, text, command, fg="#d6e6ff",
                            bg="#1a263a", hover_bg="#243653"):
        btn = tk.Button(
            parent, text=text, command=command,
            bg=bg, fg=fg, activebackground=hover_bg, activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"), relief="flat", bd=0, padx=8
        )
        btn.bind("<Enter>", lambda _e: btn.config(bg=hover_bg))
        btn.bind("<Leave>", lambda _e: btn.config(bg=bg))
        return btn

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame",  background="#0b1220")
        style.configure("TLabel",  background="#0b1220", foreground="#d6deea",
                         font=("Segoe UI", 10))
        style.configure("Header.TLabel", background="#0b1220", foreground="#f4f7fc",
                         font=("Segoe UI", 15, "bold"))
        style.configure("Points.TLabel", background="#0b1220", foreground="#22d3a6",
                         font=("Consolas", 24, "bold"))
        style.configure("TButton", background="#1a263a", foreground="#dbe8ff",
                         font=("Segoe UI", 9, "bold"), borderwidth=0, relief="flat")
        style.map("TButton",
                  background=[("active", "#243653")],
                  foreground=[("active", "#ffffff")])

        # Left panel
        left = ttk.Frame(self.root, width=300)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(16, 8), pady=16)
        left.pack_propagate(False)

        ttk.Label(left, text="HABIT TRACKER", style="Header.TLabel").pack(pady=(0, 4))

        pts_frame = ttk.Frame(left)
        pts_frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(pts_frame, text="total points", style="TLabel").pack()
        self.points_var = tk.StringVar(value="0")
        ttk.Label(pts_frame, textvariable=self.points_var,
                  style="Points.TLabel").pack()

        ttk.Label(left, text=f"Today: {self.today}",
                  font=("Courier New", 9), foreground="#666666",
                  background="#0f0f0f").pack(pady=(0, 6))

        self.open_day_var = tk.StringVar()
        self.open_day_label = ttk.Label(
            left, textvariable=self.open_day_var,
            font=("Courier New", 9, "bold"),
            foreground="#6ea8ff", background="#0f0f0f"
        )
        self.open_day_label.pack(pady=(0, 6))

        session_box = tk.Frame(left, bg="#0f0f0f")
        session_box.pack(fill=tk.X, pady=(0, 6))
        self._make_broker_button(
            session_box, "Close candle now", self._manual_close_open_day,
            fg="#ff8f9a", bg="#3a1b26", hover_bg="#4f2633"
        ).pack(side=tk.LEFT)
        self._make_broker_button(
            session_box, "Open previous day", self._open_previous_day
        ).pack(side=tk.LEFT, padx=(6, 0))

        auto_box = tk.Frame(left, bg="#0f0f0f")
        auto_box.pack(fill=tk.X, pady=(0, 8))
        self.auto_close_enabled_var = tk.BooleanVar(
            value=bool(self.data.get("auto_close_enabled", False))
        )
        tk.Checkbutton(
            auto_box, text="Auto close", variable=self.auto_close_enabled_var,
            bg="#0f0f0f", fg="#bbbbbb", activebackground="#0f0f0f",
            activeforeground="#ffffff", selectcolor="#1a1a2e",
            font=("Courier New", 9), command=self._save_auto_close_settings
        ).pack(side=tk.LEFT)
        self.auto_close_time_var = tk.StringVar(
            value=str(self.data.get("auto_close_time", "21:00"))
        )
        tk.Entry(auto_box, textvariable=self.auto_close_time_var,
                 bg="#1a1a2e", fg="#e8e8e8", insertbackground="#e8e8e8",
                 font=("Courier New", 9), relief="flat",
                 highlightthickness=1, highlightcolor="#333366",
                 width=6).pack(side=tk.LEFT, padx=(6, 4), ipady=2)
        self._make_broker_button(auto_box, "Set time", self._save_auto_close_settings).pack(side=tk.LEFT)

        day_window_box = tk.Frame(left, bg="#0f0f0f")
        day_window_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(day_window_box, text="Day window",
                 bg="#0f0f0f", fg="#bbbbbb",
                 font=("Courier New", 9)).pack(side=tk.LEFT)
        self.day_open_time_var = tk.StringVar(
            value=str(self.data.get("day_open_time", "04:30"))
        )
        tk.Entry(day_window_box, textvariable=self.day_open_time_var,
                 bg="#1a1a2e", fg="#e8e8e8", insertbackground="#e8e8e8",
                 font=("Courier New", 9), relief="flat",
                 highlightthickness=1, highlightcolor="#333366",
                 width=6).pack(side=tk.LEFT, padx=(6, 4), ipady=2)
        tk.Label(day_window_box, text="to",
                 bg="#0f0f0f", fg="#888888",
                 font=("Courier New", 9)).pack(side=tk.LEFT)
        self.day_close_time_var = tk.StringVar(
            value=str(self.data.get("day_close_time", "20:30"))
        )
        tk.Entry(day_window_box, textvariable=self.day_close_time_var,
                 bg="#1a1a2e", fg="#e8e8e8", insertbackground="#e8e8e8",
                 font=("Courier New", 9), relief="flat",
                 highlightthickness=1, highlightcolor="#333366",
                 width=6).pack(side=tk.LEFT, padx=(4, 4), ipady=2)
        self._make_broker_button(day_window_box, "Apply 16h", self._save_day_window_settings).pack(side=tk.LEFT)

        csv_box = tk.Frame(left, bg="#0f0f0f")
        csv_box.pack(fill=tk.X, pady=(0, 8))
        self._make_broker_button(csv_box, "Export CSV", self._export_csv, fg="#8dd7ff").pack(side=tk.LEFT)
        self._make_broker_button(csv_box, "Import CSV", self._import_csv, fg="#ffd49a").pack(side=tk.LEFT, padx=(6, 0))

        ttk.Separator(left, orient="horizontal").pack(fill=tk.X, pady=6)
        ttk.Label(left, text="LOG A HABIT",
                  font=("Courier New", 11, "bold"),
                  background="#0f0f0f", foreground="#ffffff").pack(pady=(0, 6))

        habit_list_frame = tk.Frame(left, bg="#0f0f0f")
        habit_list_frame.pack(fill=tk.X)

        habit_scrollbar = tk.Scrollbar(
            habit_list_frame, bg="#1a1a2e", troughcolor="#0f0f0f"
        )
        habit_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.habit_canvas = tk.Canvas(
            habit_list_frame, bg="#0f0f0f", highlightthickness=0, height=200,
            yscrollcommand=habit_scrollbar.set
        )
        self.habit_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.habit_frame = ttk.Frame(self.habit_canvas)
        self.habit_canvas.create_window((0, 0), window=self.habit_frame, anchor="nw")
        habit_scrollbar.config(command=self.habit_canvas.yview)
        self.habit_frame.bind("<Configure>",
            lambda e: self.habit_canvas.config(
                scrollregion=self.habit_canvas.bbox("all")))
        self._build_habit_buttons()

        ttk.Separator(left, orient="horizontal").pack(fill=tk.X, pady=8)
        ttk.Label(left, text="ADD CUSTOM HABIT",
                  font=("Courier New", 10, "bold"),
                  background="#0f0f0f", foreground="#ffffff").pack(pady=(0, 4))

        self.custom_name = tk.StringVar()
        self.custom_pts  = tk.StringVar()

        name_e = tk.Entry(left, textvariable=self.custom_name,
                          bg="#1a1a2e", fg="#e8e8e8", insertbackground="#e8e8e8",
                          font=("Courier New", 10), relief="flat",
                          highlightthickness=1, highlightcolor="#333366")
        name_e.insert(0, "habit name")
        name_e.pack(fill=tk.X, pady=2, ipady=5)

        pts_e = tk.Entry(left, textvariable=self.custom_pts,
                         bg="#1a1a2e", fg="#e8e8e8", insertbackground="#e8e8e8",
                         font=("Courier New", 10), relief="flat",
                         highlightthickness=1, highlightcolor="#333366")
        pts_e.insert(0, "points (e.g. -10 or +20)")
        pts_e.pack(fill=tk.X, pady=2, ipady=5)

        ttk.Button(left, text="Add & Log Habit →",
                   command=self._add_custom_habit).pack(fill=tk.X, pady=(6, 0))

        ttk.Separator(left, orient="horizontal").pack(fill=tk.X, pady=8)
        ttk.Label(left, text="OPEN DAY LOG",
                  font=("Courier New", 10, "bold"),
                  foreground="#aaaaaa", background="#0f0f0f").pack(pady=(0, 4))
        log_frame = tk.Frame(left, bg="#0f0f0f")
        log_frame.pack(fill=tk.BOTH, expand=True)

        log_scrollbar = tk.Scrollbar(log_frame, bg="#1a1a2e", troughcolor="#0f0f0f")
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(log_frame, bg="#0f0f0f", fg="#888888",
                                font=("Courier New", 9), relief="flat",
                                height=8, wrap=tk.WORD, state=tk.DISABLED,
                                yscrollcommand=log_scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.config(command=self.log_text.yview)

        # Right panel
        right = ttk.Frame(self.root)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True,
                   padx=(0, 16), pady=16)

        hdr = tk.Frame(right, bg="#0f0f0f")
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="PERFORMANCE CHART  (Candlestick)",
                 bg="#0b1220", fg="#ffffff",
                 font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
        tk.Label(hdr, text="  ← click any candle to edit that day",
                 bg="#0b1220", fg="#6c83a1",
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, pady=(4, 0))

        tabs = tk.Frame(right, bg="#0f0f0f")
        tabs.pack(fill=tk.X, pady=(8, 2))
        tk.Label(tabs, text="Timeframe:",
                 bg="#0f0f0f", fg="#888888",
                 font=("Courier New", 9)).pack(side=tk.LEFT, padx=(0, 8))
        for tf_key, tf_label in TIMEFRAME_OPTIONS:
            btn = tk.Button(
                tabs,
                text=tf_label,
                bg="#1a1a2e",
                fg="#aaaaaa",
                activebackground="#252545",
                activeforeground="#ffffff",
                relief="flat",
                bd=0,
                padx=8,
                pady=3,
                font=("Courier New", 9),
                command=lambda key=tf_key: self._set_chart_timeframe(key),
            )
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self._timeframe_buttons[tf_key] = btn
        self._update_timeframe_tabs()

        self.fig, self.ax = plt.subplots(facecolor="#0f0f0f")
        self.ax.set_facecolor("#0f0f0f")
        self.canvas_widget = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas_widget.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.fig.canvas.mpl_connect("button_press_event", self._on_chart_click)

        self.chart_scroll = tk.Scale(
            right, from_=0, to=0, orient=tk.HORIZONTAL,
            bg="#0f0f0f", fg="#888888", troughcolor="#1a1a2e",
            highlightthickness=0, relief="flat", showvalue=False,
            command=self._on_chart_scroll
        )
        self.chart_scroll.pack(fill=tk.X, pady=(4, 0))

        self._update_display()
        self._sync_auto_close_clock()

    def _build_habit_buttons(self):
        for w in self.habit_frame.winfo_children():
            w.destroy()
        for habit in self.data["habits"]:
            pts   = habit["points"]
            color = "#00cc66" if pts >= 0 else "#cc3333"
            sign  = "+" if pts > 0 else ""
            label = f"{habit.get('emoji','●')}  {habit['name']}  ({sign}{pts})"
            btn = tk.Button(
                self.habit_frame, text=label,
                bg="#1a263a", fg=color, activebackground="#243653",
                activeforeground=color, font=("Segoe UI", 9),
                relief="flat", anchor="w", padx=8,
                command=lambda h=habit: self._log_habit(h)
            )
            btn.bind("<Enter>", lambda _e, b=btn: b.config(bg="#243653"))
            btn.bind("<Leave>", lambda _e, b=btn: b.config(bg="#1a263a"))
            btn.pack(fill=tk.X, pady=2, ipady=4)

    def _start_ui_animations(self):
        self._animate_market_ui()

    def _animate_market_ui(self):
        self._ui_anim_tick += 1
        phase = self._ui_anim_tick % 24
        glow = 145 + (phase if phase <= 12 else 24 - phase) * 5
        ttk.Style().configure("Points.TLabel", foreground=f"#22{glow:02x}a6")
        if self._live_chart_text is not None:
            dot = "●" if phase < 12 else "○"
            self._live_chart_text.set_text(f"{dot} LIVE  {datetime.datetime.now().strftime('%H:%M:%S')}")
            self._live_chart_text.set_color("#28d7ab" if phase < 12 else "#4f708a")
            self.canvas_widget.draw_idle()
        self.root.after(450, self._animate_market_ui)

    # ── Actions ───────────────────────────────────────────────────────────── #

    def _apply_streak_multiplier(self, base_points):
        """
        Consecutive habits of the same sign build a streak multiplier.
        Negative streak growth is intentionally stronger than positive.
        """
        if base_points > 0:
            kind = "positive"
            growth = 0.10
        elif base_points < 0:
            kind = "negative"
            growth = 0.25
        else:
            self.data["streak_kind"] = None
            self.data["streak_count"] = 0
            return base_points, 1.0

        prev_kind = self.data.get("streak_kind")
        prev_count = int(self.data.get("streak_count", 0))
        if prev_kind == kind:
            streak_count = prev_count + 1
        else:
            streak_count = 1

        # Linear for first two habits; exponential from the third onward.
        if streak_count <= 2:
            multiplier = 1.0 + (streak_count - 1) * growth
        else:
            # Third in a row is the pivot: growth compounds after that.
            multiplier = (1.0 + growth) * ((1.0 + growth) ** (streak_count - 2))
        adjusted_points = int(round(base_points * multiplier))

        self.data["streak_kind"] = kind
        self.data["streak_count"] = streak_count
        return adjusted_points, multiplier

    def _log_habit(self, habit):
        self._maybe_auto_close_day()
        adjusted_points, streak_multiplier = self._apply_streak_multiplier(habit["points"])
        log_date = self.data.get("current_open_day", self.today)
        self.data["log"].append({
            "date":      log_date,
            "habit":     habit["name"],
            "points":    adjusted_points,
            "base_points": habit["points"],
            "streak_kind": self.data.get("streak_kind"),
            "streak_count": self.data.get("streak_count", 0),
            "streak_multiplier": streak_multiplier,
            "timestamp": datetime.datetime.now().isoformat(),
        })
        save_data(self.data)
        self._update_display()
        self._refresh_chart()

    def _add_custom_habit(self):
        name    = self.custom_name.get().strip()
        pts_str = self.custom_pts.get().strip()
        if not name or not pts_str:
            messagebox.showwarning("Missing info", "Enter a habit name and points.")
            return
        try:
            pts = int(pts_str)
        except ValueError:
            messagebox.showerror("Invalid points",
                                 "Points must be an integer (e.g. 20 or -10).")
            return
        habit = {"name": name, "points": pts, "emoji": "★"}
        self.data["habits"].append(habit)
        save_data(self.data)
        self._build_habit_buttons()
        self._log_habit(habit)

    def _on_chart_click(self, event):
        if event.inaxes != self.ax or not self._candle_dates:
            return
        if event.xdata is None:
            return
        local_idx = int(round(event.xdata))
        global_idx = self._visible_start + local_idx
        if 0 <= local_idx < self._visible_len and 0 <= global_idx < len(self._candle_dates):
            self._open_day_editor(self._candle_dates[global_idx])

    def _open_day_editor(self, date_str):
        DayEditDialog(self.root, self, date_str)

    def _on_chart_scroll(self, value):
        try:
            self._chart_view_start = int(float(value))
        except (TypeError, ValueError):
            self._chart_view_start = 0
        self._refresh_chart()

    def _set_chart_timeframe(self, timeframe_key):
        if timeframe_key not in self._timeframe_buttons:
            return
        if self._chart_timeframe == timeframe_key:
            return
        self._chart_timeframe = timeframe_key
        self._chart_view_start = 0
        self._update_timeframe_tabs()
        self._refresh_chart()

    def _update_timeframe_tabs(self):
        for key, btn in self._timeframe_buttons.items():
            active = key == self._chart_timeframe
            btn.config(
                bg="#2b4a70" if active else "#1a1a2e",
                fg="#ffffff" if active else "#aaaaaa",
                relief="sunken" if active else "flat",
            )

    def _filter_candles_by_timeframe(self, candles):
        if not candles:
            return candles
        candle_dates = [datetime.date.fromisoformat(c["date"]) for c in candles]
        anchor = candle_dates[-1]
        tf = self._chart_timeframe
        if tf == "1D":
            start = anchor
        elif tf == "SESSION":
            return candles
        elif tf == "1W":
            start = anchor - datetime.timedelta(days=6)
        elif tf == "1M":
            start = anchor - datetime.timedelta(days=29)
        elif tf == "6M":
            start = anchor - datetime.timedelta(days=182)
        elif tf == "1Y":
            start = anchor - datetime.timedelta(days=365)
        elif tf == "YTD":
            start = datetime.date(anchor.year, 1, 1)
        else:
            return candles

        filtered = [
            c for c, d in zip(candles, candle_dates)
            if start <= d <= anchor
        ]
        return filtered if filtered else [candles[-1]]

    def _entry_datetime(self, entry):
        ts = str(entry.get("timestamp", "")).strip()
        if ts:
            try:
                return datetime.datetime.fromisoformat(ts)
            except Exception:
                pass
        d = entry.get("date")
        if d:
            try:
                return datetime.datetime.combine(
                    datetime.date.fromisoformat(d),
                    datetime.time(hour=12, minute=0),
                )
            except Exception:
                pass
        return None

    def _build_1d_intraday_candles(self):
        """
        Session view: current 16-hour day window based on configured open/close.
        Each logged habit entry inside that window becomes one candlestick.
        """
        now = datetime.datetime.now()
        try:
            _, _, open_h, open_m, close_h, close_m = self._parse_day_window_times()
        except ValueError:
            open_h, open_m, close_h, close_m = 4, 30, 20, 30

        today = now.date()
        session_open = datetime.datetime.combine(today, datetime.time(hour=open_h, minute=open_m))
        session_close = datetime.datetime.combine(today, datetime.time(hour=close_h, minute=close_m))
        if now < session_open:
            prev = today - datetime.timedelta(days=1)
            session_open = datetime.datetime.combine(prev, datetime.time(hour=open_h, minute=open_m))
            session_close = datetime.datetime.combine(prev, datetime.time(hour=close_h, minute=close_m))

        enriched = []
        for e in self.data.get("log", []):
            dt = self._entry_datetime(e)
            if dt is None:
                continue
            enriched.append((dt, e))
        enriched.sort(key=lambda x: x[0])

        session_end = min(now, session_close)
        window = [(dt, e) for (dt, e) in enriched if session_open <= dt <= session_end]
        if not window:
            return []

        first_dt = window[0][0]
        start_total = 0
        for dt, e in enriched:
            if dt >= first_dt:
                break
            try:
                start_total += int(e.get("points", 0))
            except Exception:
                continue

        multi_day = len({(e.get("date") or "") for _, e in window}) > 1

        candles = []
        running_total = start_total
        last_habit = None
        for dt, e in window:
            try:
                delta = int(e.get("points", 0))
            except Exception:
                continue

            current_habit = str(e.get("habit", ""))
            if candles and current_habit and current_habit == last_habit:
                # Merge back-to-back same-habit logs into the existing candle.
                c = candles[-1]
                close_val = c["close"] + delta
                c["close"] = close_val
                c["high"] = max(c["high"], close_val)
                c["low"] = min(c["low"], close_val)
                running_total = close_val
            else:
                open_val = running_total
                close_val = open_val + delta
                candles.append({
                    "date": e.get("date") or dt.date().isoformat(),
                    "open": open_val,
                    "high": max(open_val, close_val),
                    "low": min(open_val, close_val),
                    "close": close_val,
                    "is_manual": False,
                    "manual_close": None,
                    "x_label": dt.strftime("%m-%d %H:%M") if multi_day else dt.strftime("%H:%M"),
                })
                running_total = close_val
            last_habit = current_habit

        return candles

    def _build_session_hourly_candles(self):
        """
        Build automatic 1-hour candles within the configured daily session window.
        Values are cumulative and include all streak/multiplier-adjusted points.
        """
        now = datetime.datetime.now()
        try:
            _, _, open_h, open_m, close_h, close_m = self._parse_day_window_times()
        except ValueError:
            open_h, open_m, close_h, close_m = 4, 30, 20, 30

        today = now.date()
        session_open = datetime.datetime.combine(today, datetime.time(hour=open_h, minute=open_m))
        session_close = datetime.datetime.combine(today, datetime.time(hour=close_h, minute=close_m))
        if now < session_open:
            prev = today - datetime.timedelta(days=1)
            session_open = datetime.datetime.combine(prev, datetime.time(hour=open_h, minute=open_m))
            session_close = datetime.datetime.combine(prev, datetime.time(hour=close_h, minute=close_m))

        enriched = []
        for e in self.data.get("log", []):
            dt = self._entry_datetime(e)
            if dt is None:
                continue
            enriched.append((dt, e))
        enriched.sort(key=lambda x: x[0])
        if not enriched:
            return []

        start_total = 0
        for dt, e in enriched:
            if dt >= session_open:
                break
            try:
                start_total += int(e.get("points", 0))
            except Exception:
                continue

        bins = []
        for i in range(16):
            bin_start = session_open + datetime.timedelta(hours=i)
            bin_end = bin_start + datetime.timedelta(hours=1)
            if bin_start >= session_close:
                break
            if now < bin_start:
                break
            bins.append((bin_start, min(bin_end, session_close, now)))

        if not bins:
            return []

        candles = []
        running_total = start_total
        for bin_start, bin_end in bins:
            delta = 0
            for dt, e in enriched:
                if bin_start <= dt < bin_end:
                    try:
                        delta += int(e.get("points", 0))
                    except Exception:
                        continue
            open_val = running_total
            close_val = open_val + delta
            candles.append({
                "date": bin_start.date().isoformat(),
                "open": open_val,
                "high": max(open_val, close_val),
                "low": min(open_val, close_val),
                "close": close_val,
                "is_manual": False,
                "manual_close": None,
                "x_label": bin_start.strftime("%H:%M"),
            })
            running_total = close_val

        return candles

    # ── Display ───────────────────────────────────────────────────────────── #

    def _total_points(self):
        return sum(e["points"] for e in self.data["log"])

    def _open_day_entries(self):
        open_day = self.data.get("current_open_day", self.today)
        return [e for e in self.data["log"] if e["date"] == open_day]

    def _set_open_day(self, date_str):
        self.data["current_open_day"] = date_str
        save_data(self.data)
        self._update_display()
        self._refresh_chart()

    def _manual_close_open_day(self):
        self._maybe_auto_close_day()
        current_open = self.data.get("current_open_day", self.today)
        self.data["current_open_day"] = _next_date_str(current_open)
        save_data(self.data)
        self._update_display()
        self._refresh_chart()

    def _open_previous_day(self):
        current_open = self.data.get("current_open_day", self.today)
        prev_day = datetime.date.fromisoformat(current_open) - datetime.timedelta(days=1)
        self.data["current_open_day"] = prev_day.isoformat()
        save_data(self.data)
        self._update_display()
        self._refresh_chart()

    def _parse_auto_close_time(self):
        return parse_hhmm(self.auto_close_time_var.get())

    def _parse_day_window_times(self):
        open_norm, open_h, open_m = parse_hhmm(self.day_open_time_var.get())
        close_norm, close_h, close_m = parse_hhmm(self.day_close_time_var.get())
        open_minutes = open_h * 60 + open_m
        close_minutes = close_h * 60 + close_m
        if close_minutes <= open_minutes:
            raise ValueError("Close must be later than open on the same day.")
        if (close_minutes - open_minutes) != (16 * 60):
            raise ValueError("Daily candlestick window must be exactly 16 hours.")
        return open_norm, close_norm, open_h, open_m, close_h, close_m

    def _save_auto_close_settings(self):
        try:
            normalized, _, _ = self._parse_auto_close_time()
        except ValueError:
            messagebox.showerror("Invalid time",
                                 "Use HH:MM in 24-hour format (example: 21:00).")
            self.auto_close_time_var.set(str(self.data.get("auto_close_time", "21:00")))
            return
        self.auto_close_time_var.set(normalized)
        self.data["auto_close_enabled"] = bool(self.auto_close_enabled_var.get())
        self.data["auto_close_time"] = normalized
        save_data(self.data)
        self._maybe_auto_close_day()
        self._update_display()

    def _save_day_window_settings(self):
        try:
            open_norm, close_norm, _, _, _, _ = self._parse_day_window_times()
        except ValueError as exc:
            messagebox.showerror(
                "Invalid day window",
                f"{exc}\nExample: open 04:30 and close 20:30.",
            )
            self.day_open_time_var.set(str(self.data.get("day_open_time", "04:30")))
            self.day_close_time_var.set(str(self.data.get("day_close_time", "20:30")))
            return
        self.day_open_time_var.set(open_norm)
        self.day_close_time_var.set(close_norm)
        self.data["day_open_time"] = open_norm
        self.data["day_close_time"] = close_norm
        save_data(self.data)
        self._refresh_chart()

    def _export_csv(self):
        default_name = f"habit_points_{datetime.date.today().isoformat()}.csv"
        path = filedialog.asksaveasfilename(
            title="Export daily points & activity log",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return

        candles = compute_candlestick_data(self.data["log"], self.data.get("manual_close", {}))
        candles_by_date = {
            c["date"]: c for c in candles if c["date"] in {e["date"] for e in self.data["log"]}
        }
        sorted_log = sorted(
            self.data["log"], key=lambda e: (e.get("date", ""), e.get("timestamp", ""))
        )

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "row_type", "date", "habit", "points", "timestamp",
                "open", "high", "low", "close"
            ])
            for e in sorted_log:
                c = candles_by_date.get(e["date"])
                writer.writerow([
                    "activity", e.get("date", ""), e.get("habit", ""),
                    e.get("points", 0), e.get("timestamp", ""),
                    "", "", "", ""
                ])
                if c:
                    # Optional daily snapshot row to make graph re-import easy.
                    writer.writerow([
                        "daily", c["date"], "", "", "",
                        c["open"], c["high"], c["low"], c["close"]
                    ])
                    candles_by_date.pop(e["date"], None)

        messagebox.showinfo("Export complete", f"CSV exported to:\n{path}")

    def _import_csv(self):
        path = filedialog.askopenfilename(
            title="Import activity/daily graph CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            with open(path, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except Exception as exc:
            messagebox.showerror("Import failed", f"Could not read CSV:\n{exc}")
            return

        if not rows:
            messagebox.showwarning("Import failed", "CSV has no data rows.")
            return

        new_log = []
        cumulative_from_close = []
        daily_net_rows = []

        for row in rows:
            row_type = str(row.get("row_type", "")).strip().lower()
            date_val = str(row.get("date", "")).strip()
            if not date_val:
                continue

            if row_type == "activity" or ("habit" in row and "points" in row and row_type == ""):
                try:
                    pts = int(str(row.get("points", "0")).strip())
                except ValueError:
                    continue
                habit = str(row.get("habit", "Imported activity")).strip() or "Imported activity"
                ts = str(row.get("timestamp", "")).strip() or f"{date_val}T12:00:00"
                new_log.append({
                    "date": date_val,
                    "habit": habit,
                    "points": pts,
                    "timestamp": ts,
                })
                continue

            close_raw = str(row.get("close", "")).strip()
            points_raw = str(row.get("points", "")).strip()
            if close_raw:
                try:
                    close_val = int(float(close_raw))
                except ValueError:
                    continue
                cumulative_from_close.append((date_val, close_val))
            elif points_raw:
                try:
                    day_points = int(float(points_raw))
                except ValueError:
                    continue
                daily_net_rows.append((date_val, day_points))

        if not new_log and cumulative_from_close:
            cumulative_from_close.sort(key=lambda x: x[0])
            prev_close = 0
            for d, close_val in cumulative_from_close:
                delta = close_val - prev_close
                new_log.append({
                    "date": d,
                    "habit": "Imported close",
                    "points": delta,
                    "timestamp": f"{d}T12:00:00",
                })
                prev_close = close_val

        if not new_log and daily_net_rows:
            daily_net_rows.sort(key=lambda x: x[0])
            for d, pts in daily_net_rows:
                new_log.append({
                    "date": d,
                    "habit": "Imported daily points",
                    "points": pts,
                    "timestamp": f"{d}T12:00:00",
                })

        if not new_log:
            messagebox.showwarning(
                "Import failed",
                "No valid rows found. Use columns like:\n"
                "- activity: date, habit, points[, timestamp]\n"
                "- graph: date, close  OR  date, points"
            )
            return

        replace = messagebox.askyesno(
            "Import mode",
            "Replace current log with imported CSV?\n\n"
            "Yes = replace\nNo = append"
        )
        if replace:
            self.data["log"] = new_log
        else:
            self.data["log"].extend(new_log)

        for entry in new_log:
            if not any(h["name"] == entry["habit"] for h in self.data["habits"]):
                self.data["habits"].append({
                    "name": entry["habit"], "points": entry["points"], "emoji": "★"
                })

        if self.data["log"]:
            first_date = min(e["date"] for e in self.data["log"])
            self.data["current_open_day"] = first_date

        save_data(self.data)
        self._build_habit_buttons()
        self._update_display()
        self._refresh_chart()
        messagebox.showinfo("Import complete", f"Imported {len(new_log)} rows from CSV.")

    def _maybe_auto_close_day(self):
        if not self.data.get("auto_close_enabled"):
            return
        close_raw = str(self.data.get("auto_close_time", "21:00"))
        try:
            hour = int(close_raw.split(":")[0])
            minute = int(close_raw.split(":")[1])
        except Exception:
            return
        now = datetime.datetime.now()
        today = now.date().isoformat()
        close_dt = datetime.datetime.combine(now.date(), datetime.time(hour=hour, minute=minute))
        already_closed_today = self.data.get("auto_last_close_date") == today
        if now >= close_dt and not already_closed_today:
            current_open = self.data.get("current_open_day", today)
            self.data["current_open_day"] = _next_date_str(current_open)
            self.data["auto_last_close_date"] = today
            save_data(self.data)
            self._refresh_chart()

    def _sync_auto_close_clock(self):
        self._maybe_auto_close_day()
        self._update_display()
        self.root.after(60000, self._sync_auto_close_clock)

    def _update_display(self):
        self._maybe_auto_close_day()
        total = self._total_points()
        self.points_var.set(f"{total:+d}" if total != 0 else "0")
        open_day = self.data.get("current_open_day", self.today)
        self.open_day_var.set(f"Open candlestick day: {open_day}")
        today_log = self._open_day_entries()
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        if not today_log:
            self.log_text.insert(tk.END, "No habits logged for the current open day.")
        for e in reversed(today_log):
            sign = "+" if e["points"] > 0 else ""
            self.log_text.insert(tk.END, f"{sign}{e['points']:>4}  {e['habit']}\n")
        self.log_text.configure(state=tk.DISABLED)

    def _refresh_chart(self):
        self.ax.clear()
        all_candles = compute_candlestick_data(
            self.data["log"], self.data.get("manual_close", {}))
        if self._chart_timeframe == "1D":
            candles = self._build_1d_intraday_candles()
        elif self._chart_timeframe == "SESSION":
            candles = self._build_session_hourly_candles()
        else:
            candles = self._filter_candles_by_timeframe(all_candles)
        self._candle_dates = [c["date"] for c in candles]

        if not candles:
            self.ax.text(0.5, 0.5,
                         "No data yet.\nLog some habits to see your chart!",
                         ha="center", va="center", color="#58708a",
                         fontsize=12, transform=self.ax.transAxes)
            self.canvas_widget.draw()
            return

        total = len(candles)
        max_start = max(0, total - MAX_VISIBLE_CANDLES)
        self._chart_view_start = min(max(self._chart_view_start, 0), max_start)
        self.chart_scroll.config(to=max_start)
        self.chart_scroll.set(self._chart_view_start)
        self.chart_scroll.config(state=tk.NORMAL if max_start > 0 else tk.DISABLED)

        start = self._chart_view_start
        visible_candles = candles[start:start + MAX_VISIBLE_CANDLES]
        self._visible_start = start
        self._visible_len = len(visible_candles)

        # Keep candle body size and Y-axis padding proportional to the
        # currently visible value range so each timeframe scales naturally.
        y_min = min(c["low"] for c in visible_candles)
        y_max = max(c["high"] for c in visible_candles)
        visible_span = y_max - y_min
        if visible_span <= 0:
            ref = max(abs(y_max), 1.0)
            visible_span = ref * 0.1
        min_body_height = max(visible_span * 0.015, 0.05)

        width = 0.5
        for i, c in enumerate(visible_candles):
            bearish = c["close"] < c["open"] or c["close"] < 0
            body_color = "#e65757" if bearish else "#22d3a6"

            # Wick
            self.ax.plot([i, i], [c["low"], c["high"]],
                         color=body_color, linewidth=1.5, zorder=2)

            # Body
            body_bottom = min(c["open"], c["close"])
            body_height = max(abs(c["close"] - c["open"]), min_body_height)
            self.ax.add_patch(mpatches.FancyBboxPatch(
                (i - width / 2, body_bottom), width, body_height,
                boxstyle="square,pad=0", linewidth=0,
                facecolor=body_color, alpha=0.85, zorder=3))

            # Manual-close marker: gold tick
            if c.get("is_manual"):
                self.ax.plot([i - width * 0.65, i + width * 0.65],
                             [c["manual_close"], c["manual_close"]],
                             color="#ffcc44", linewidth=2.5,
                             zorder=5, solid_capstyle="round")

        self.ax.axhline(y=0, color="#3b4f67", linewidth=0.8,
                        linestyle="--", zorder=1)

        visible_x = list(range(self._visible_len))

        self.ax.set_facecolor("#0b1220")
        self.ax.set_xlim(-0.8, self._visible_len - 0.2)
        self.ax.set_xticks(visible_x)
        if self._chart_timeframe in {"1D", "SESSION"}:
            labels = [c.get("x_label", c["date"][5:]) for c in visible_candles]
        else:
            labels = [c["date"][5:] for c in visible_candles]
        self.ax.set_xticklabels(
            labels,
            rotation=40, ha="right", color="#8ea1b9", fontsize=8)

        # Dynamic Y-scale for the visible timeframe.
        pad = max(visible_span * 0.10, min_body_height * 1.5)
        self.ax.set_ylim(y_min - pad, y_max + pad)

        self.ax.yaxis.set_tick_params(colors="#8ea1b9", labelsize=8)
        for spine in self.ax.spines.values():
            spine.set_color("#1f2d42")
        self.ax.tick_params(colors="#8ea1b9", which="both")
        self.ax.set_ylabel("Cumulative Points", color="#8ea1b9", fontsize=9)
        timeframe_label = dict(TIMEFRAME_OPTIONS).get(self._chart_timeframe, self._chart_timeframe)
        self.ax.set_title(
            f"Daily Habit Points — Candlestick View [{timeframe_label}]  (click a candle to edit)",
            color="#d6deea", fontsize=10, pad=10)
        self.ax.yaxis.grid(True, color="#162131", linewidth=0.6, zorder=0)

        self.ax.legend(
            handles=[
                mpatches.Patch(color="#22d3a6", label="Gain day"),
                mpatches.Patch(color="#e65757", label="Loss day"),
                mpatches.Patch(color="#ffcc44", label="Manual close"),
            ],
            loc="upper left", fontsize=8,
            facecolor="#111827", edgecolor="#1f2d42", labelcolor="#d6deea")

        self._live_chart_text = self.ax.text(
            0.985, 0.985, "● LIVE",
            transform=self.ax.transAxes,
            ha="right", va="top",
            color="#28d7ab", fontsize=9, fontweight="bold"
        )

        self.fig.tight_layout()
        self.canvas_widget.draw()


# ──────────────────────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    HabitTrackerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
