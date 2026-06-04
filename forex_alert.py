"""
ForexFactory → Discord Alert Bot
---------------------------------
Modes:
  python forex_alert.py summary               → send today's full USD orange/red summary to Discord
  python forex_alert.py alert                 → check for USD orange/red news in next 5 min, alert if found
  python forex_alert.py test                  → send a test message to Discord to verify webhook works
  python forex_alert.py dryrun --date 2026-06-03 --time 08:55 --mode alert
                                              → simulate what would fire at that date/time (no Discord send)
  python forex_alert.py dryrun --date 2026-06-03 --time 08:00 --mode summary

Env vars required:
  DISCORD_WEBHOOK_URL  — your Discord webhook URL (or set in .env)
"""

import os
import sys
import platform
import argparse
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv

load_dotenv()  # loads .env when running locally; no-op in GitHub Actions

# ── Config ──────────────────────────────────────────────────────────────────
WEBHOOK_URL   = os.environ.get("DISCORD_WEBHOOK_URL", "")
ET            = pytz.timezone("America/New_York")
UTC           = pytz.utc
CALENDAR_URL  = "https://www.forexfactory.com/calendar"

IMPACT_EMOJI = {
    "High":   "🔴",
    "Medium": "🟠",
}

FF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.forexfactory.com/",
}

IMPACT_CLASS_MAP = {
    "icon--ff-impact-red": "High",
    "icon--ff-impact-ora": "Medium",
    "icon--ff-impact-yel": "Low",
    "icon--ff-impact-gry": "Holiday",
}

# ── Fetch ────────────────────────────────────────────────────────────────────
def fetch_events():
    """
    Scrape ForexFactory calendar.
    Timezone trick: data-day-dateline is Unix midnight of that day in FF's served TZ.
    Time strings are in that same TZ. Adding hours/minutes as a UTC offset gives the
    correct absolute timestamp regardless of where this script runs.
    """
    resp = requests.get(CALENDAR_URL, headers=FF_HEADERS, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="calendar__table")
    if not table:
        raise RuntimeError("Could not find calendar table — FF layout may have changed.")

    events = []
    current_dateline = None
    current_time_str = None

    for row in table.find_all("tr", class_=lambda c: c and "calendar__row" in c):
        dateline = row.get("data-day-dateline")
        if dateline:
            current_dateline = int(dateline)

        if not row.get("data-event-id") or current_dateline is None:
            continue

        # Currency
        currency_td = row.find("td", class_="calendar__currency")
        currency = currency_td.get_text(strip=True) if currency_td else ""

        # Impact via CSS class
        impact = ""
        impact_td = row.find("td", class_="calendar__impact")
        if impact_td:
            span = impact_td.find("span", class_=True)
            if span:
                for cls in span.get("class", []):
                    if cls in IMPACT_CLASS_MAP:
                        impact = IMPACT_CLASS_MAP[cls]
                        break

        # Time — carry forward (FF only puts time on first row of a group)
        time_td = row.find("td", class_="calendar__time")
        raw_time = time_td.get_text(strip=True) if time_td else ""
        if raw_time:
            current_time_str = raw_time
        time_str = current_time_str or ""

        # Title
        event_td = row.find("td", class_="calendar__event")
        title = ""
        if event_td:
            span = event_td.find("span", class_="calendar__event-title")
            title = span.get_text(strip=True) if span else event_td.get_text(strip=True)

        # Forecast / Previous / Actual
        def get_cell(cls):
            td = row.find("td", class_=cls)
            return td.get_text(strip=True) if td else ""

        forecast = get_cell("calendar__forecast")
        previous = get_cell("calendar__previous")
        actual   = get_cell("calendar__actual")

        # Build datetime:
        # dateline = Unix timestamp of midnight-in-FF's-timezone for this day.
        # Time string is in that same timezone.
        # Adding time as a UTC offset gives the correct absolute UTC time.
        event_dt = None
        if time_str and time_str.lower() not in ("", "all day", "tentative", "data"):
            try:
                t = datetime.strptime(time_str.upper(), "%I:%M%p")
                midnight_utc = datetime.fromtimestamp(current_dateline, tz=UTC)
                event_utc = midnight_utc + timedelta(hours=t.hour, minutes=t.minute)
                event_dt = event_utc.astimezone(ET)
            except ValueError:
                pass

        if not title or not event_dt:
            continue

        events.append({
            "date":     event_dt.isoformat(),
            "country":  currency,
            "impact":   impact,
            "title":    title,
            "forecast": forecast,
            "previous": previous,
            "actual":   actual,
        })

    return events


def filter_usd_impactful(events):
    """Keep only USD High/Medium impact events."""
    return [
        e for e in events
        if e.get("country") == "USD" and e.get("impact") in ("High", "Medium")
    ]


def parse_dt(event):
    """Return event datetime as ET-aware datetime."""
    raw = event["date"]  # e.g. "2024-06-03T09:00:00-0400"
    dt = datetime.fromisoformat(raw)
    return dt.astimezone(ET)


def fmt_time(dt: datetime) -> str:
    """Format time without leading zero — cross-platform (Windows + Linux)."""
    if platform.system() == "Windows":
        return dt.strftime("%#I:%M %p ET")
    return dt.strftime("%-I:%M %p ET")


# ── Formatting ───────────────────────────────────────────────────────────────
def format_event_line(e):
    emoji = IMPACT_EMOJI.get(e["impact"], "⚪")
    dt    = parse_dt(e)
    time  = fmt_time(dt)
    line  = f"{emoji} **{e['title']}** @ {time}"

    extras = []
    if e.get("forecast") not in (None, ""):
        extras.append(f"Forecast: `{e['forecast']}`")
    if e.get("previous") not in (None, ""):
        extras.append(f"Prev: `{e['previous']}`")
    if e.get("actual") not in (None, ""):
        extras.append(f"Actual: `{e['actual']}`")
    if extras:
        line += "  |  " + "  ·  ".join(extras)
    return line


# ── Discord ──────────────────────────────────────────────────────────────────
def send_discord(content: str):
    if not WEBHOOK_URL:
        print("ERROR: DISCORD_WEBHOOK_URL not set in .env or environment")
        sys.exit(1)

    resp = requests.post(WEBHOOK_URL, json={"content": content}, timeout=10)
    if resp.status_code not in (200, 204):
        print(f"Discord error {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    else:
        print(f"✅ Sent to Discord.")


def print_dryrun(label: str, content: str):
    """Print what would have been sent to Discord."""
    print(f"\n{'─'*60}")
    print(f"[DRY RUN — {label}]")
    print(f"{'─'*60}")
    print(content)
    print(f"{'─'*60}\n")


# ── Build messages ────────────────────────────────────────────────────────────
def build_summary_message(now: datetime, events: list):
    """Returns (message_str, found_events_bool)."""
    today = now.date()
    today_events = sorted(
        [e for e in events if parse_dt(e).date() == today],
        key=parse_dt
    )
    if not today_events:
        return None, False

    date_str = now.strftime("%A, %b %d")
    lines = [f"📅  **USD News Today — {date_str}**", ""]
    for e in today_events:
        lines.append(format_event_line(e))
    lines += ["", "━━━━━━━━━━━━━━━━━━━━━━━━", "React 🔔 to get pinged 5 min before each event!"]
    return "\n".join(lines), True


def build_alert_messages(now: datetime, events: list):
    """Returns list of alert messages for events in the 5-min window."""
    window_lo = now + timedelta(minutes=4)
    window_hi = now + timedelta(minutes=6)
    upcoming  = [e for e in events if window_lo <= parse_dt(e) <= window_hi]

    messages = []
    for e in upcoming:
        dt     = parse_dt(e)
        emoji  = IMPACT_EMOJI.get(e["impact"], "⚪")
        impact = e["impact"].upper()
        time   = fmt_time(dt)
        lines  = [
            f"@everyone",
            f"⚠️  **{impact} IMPACT NEWS IN ~5 MIN**  {emoji}",
            "",
            format_event_line(e),
            "",
            f"🕐 Releases at **{time}**",
        ]
        messages.append("\n".join(lines))
    return messages


# ── Modes ────────────────────────────────────────────────────────────────────
def run_summary():
    now    = datetime.now(ET)
    events = filter_usd_impactful(fetch_events())
    msg, found = build_summary_message(now, events)
    if not found:
        print("No USD high/medium impact events today — skipping summary.")
        return
    send_discord(msg)


def run_alert():
    now      = datetime.now(ET)
    events   = filter_usd_impactful(fetch_events())
    messages = build_alert_messages(now, events)
    if not messages:
        print(f"[{now.strftime('%H:%M')} ET] No events in 5-min window.")
        return
    for msg in messages:
        send_discord(msg)


def run_test():
    """Send a test message to Discord to verify the webhook is working."""
    now = datetime.now(ET)
    msg = (
        f"✅  **ForexFactory Bot — Test Message**\n"
        f"Webhook is working! Sent at {now.strftime('%I:%M %p ET on %A, %b %d')}."
    )
    print("Sending test message to Discord...")
    send_discord(msg)


def run_dryrun(date_str: str, time_str: str, mode: str):
    """
    Simulate what the bot would do if it ran at the given date+time.
    Fetches live calendar data but prints output instead of sending to Discord.
    """
    # Parse simulated datetime
    try:
        sim_naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        print("ERROR: --date must be YYYY-MM-DD and --time must be HH:MM (24h)")
        sys.exit(1)

    sim_now = ET.localize(sim_naive)
    print(f"\n🕐 Simulating run at: {sim_now.strftime('%A, %b %d %Y  %I:%M %p ET')}")
    print(f"   Mode: {mode}")

    events = filter_usd_impactful(fetch_events())
    print(f"   Fetched {len(events)} USD high/medium events from calendar\n")

    if mode == "summary":
        msg, found = build_summary_message(sim_now, events)
        if not found:
            print("→ No USD high/medium events on this date — summary would be skipped.")
        else:
            print_dryrun("SUMMARY MESSAGE", msg)

    elif mode == "alert":
        messages = build_alert_messages(sim_now, events)
        if not messages:
            window_lo = sim_now + timedelta(minutes=4)
            window_hi = sim_now + timedelta(minutes=6)
            print(
                f"→ No events in window "
                f"{window_lo.strftime('%H:%M')}–{window_hi.strftime('%H:%M')} ET. "
                f"No alert would fire."
            )
        else:
            for i, msg in enumerate(messages, 1):
                print_dryrun(f"ALERT #{i}", msg)

    else:
        print(f"ERROR: --mode must be 'alert' or 'summary'")
        sys.exit(1)


# ── Entry ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ForexFactory Discord Alert Bot")
    parser.add_argument("mode", choices=["summary", "alert", "test", "dryrun"],
                        help="Run mode")
    parser.add_argument("--date", help="Date for dryrun (YYYY-MM-DD)", default=None)
    parser.add_argument("--time", help="Time for dryrun in 24h format (HH:MM)", default=None)
    parser.add_argument("--mode", dest="dryrun_mode", choices=["alert", "summary"],
                        default="alert", help="Which mode to simulate in dryrun")

    args = parser.parse_args()

    if args.mode == "summary":
        run_summary()
    elif args.mode == "alert":
        run_alert()
    elif args.mode == "test":
        run_test()
    elif args.mode == "dryrun":
        if not args.date or not args.time:
            print("ERROR: dryrun requires --date (YYYY-MM-DD) and --time (HH:MM)")
            sys.exit(1)
        run_dryrun(args.date, args.time, args.dryrun_mode)
