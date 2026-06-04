"""
Run this to debug ForexFactory row data attributes and time values.
  python debug_scraper.py
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz

ET = pytz.timezone("America/New_York")

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Cookie": "timezone=America%2FNew_York",
}

resp = requests.get("https://www.forexfactory.com/calendar", headers=headers, timeout=20)
print(f"HTTP status: {resp.status_code}\n")

soup = BeautifulSoup(resp.text, "html.parser")
table = soup.find("table", class_="calendar__table")

rows = table.find_all("tr", class_=lambda c: c and "calendar__row" in c)
print(f"Total rows: {len(rows)}")
print("=" * 70)

# Print all data-* attributes + time cell for first 15 event rows
count = 0
for row in rows:
    if not row.get("data-event-id"):
        continue
    attrs = {k: v for k, v in row.attrs.items() if k.startswith("data-")}
    time_td = row.find("td", class_="calendar__time")
    currency_td = row.find("td", class_="calendar__currency")
    event_td = row.find("td", class_="calendar__event")
    title_span = event_td.find("span", class_="calendar__event-title") if event_td else None

    time_str  = time_td.get_text(strip=True) if time_td else "(empty)"
    currency  = currency_td.get_text(strip=True) if currency_td else ""
    title     = title_span.get_text(strip=True) if title_span else ""

    # Decode any Unix timestamps found in data attrs
    decoded = {}
    for k, v in attrs.items():
        try:
            ts = int(v)
            decoded[k] = f"{v}  →  {datetime.fromtimestamp(ts, tz=ET).strftime('%Y-%m-%d %H:%M ET')}"
        except (ValueError, OSError):
            decoded[k] = v

    print(f"[{currency}] {title}")
    print(f"  time cell : {time_str!r}")
    for k, v in decoded.items():
        print(f"  {k}: {v}")
    print()

    count += 1
    if count >= 15:
        break
