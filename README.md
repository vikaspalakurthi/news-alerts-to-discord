# ForexFactory → Discord Alert Bot

Automatically posts USD 🔴 High and 🟠 Medium impact news alerts to a Discord channel — 5 minutes before each event fires, plus a daily morning summary. Runs free on GitHub Actions, no server required.

---

## What it does

**5-minute pre-news alert** — sent ~5 min before any USD red/orange event:
```
@everyone
⚠️  HIGH IMPACT NEWS IN ~5 MIN  🔴

🔴 ISM Services PMI @ 10:00 AM ET  |  Forecast: `53.7`  ·  Prev: `53.6`

🕐 Releases at 10:00 AM ET
```

**Daily morning summary** — sent at 8:00 AM ET every weekday:
```
📅  USD News Today — Wednesday, Jun 03

🔴 ADP Non-Farm Employment Change @ 8:15 AM ET  |  Forecast: `118K`  ·  Prev: `105K`
🔴 ISM Services PMI @ 10:00 AM ET  |  Forecast: `53.7`  ·  Prev: `53.6`
🟠 Treasury Sec Bessent Speaks @ 10:00 AM ET
🟠 Factory Orders m/m @ 10:00 AM ET  |  Forecast: `4.6%`  ·  Prev: `1.8%`

━━━━━━━━━━━━━━━━━━━━━━━━
React 🔔 to get pinged 5 min before each event!
```

---

## How it works

```
┌─────────────────────────────────────────────────────────┐
│                    GitHub Actions                        │
│                                                         │
│  Every 5 min (Mon–Fri, 7 AM–6 PM ET)                   │
│       └─► forex_alert.py alert                         │
│              └─► Scrape ForexFactory calendar           │
│              └─► Filter: USD + High/Medium impact       │
│              └─► Any event in next 4–6 min?             │
│                     YES → POST to Discord webhook       │
│                     NO  → exit silently                 │
│                                                         │
│  Daily at 8:00 AM ET (Mon–Fri)                         │
│       └─► forex_alert.py summary                       │
│              └─► Scrape ForexFactory calendar           │
│              └─► Filter: USD + High/Medium, today only  │
│              └─► POST full day summary to Discord       │
└─────────────────────────────────────────────────────────┘
```

**Timezone handling** — ForexFactory serves event times in the browser's local timezone. The scraper avoids this by using the row's `data-day-dateline` Unix timestamp (midnight of that day) and adding the displayed time as an offset. This gives the correct absolute UTC timestamp regardless of where the script runs.

**Impact detection** — FF uses CSS classes on the impact icon (`icon--ff-impact-red` = High, `icon--ff-impact-ora` = Medium), not text — the scraper reads those classes directly.

**Time carry-forward** — FF only puts the time on the first row of a same-time group (e.g. ISM, Treasury, and Factory Orders all at 10:00 AM share one time cell). The scraper carries the last seen time forward to handle this.

---

## Files

```
forex_alert.py                        Main script (all modes)
.github/workflows/forex_alerts.yml   GitHub Actions schedule (already configured)
requirements.txt                      Python dependencies
.env.example                          Template for local secrets
.env                                  Your local secrets (git-ignored)
.gitignore                            Keeps .env out of git
debug_scraper.py                      Dev tool — inspect FF HTML structure
```

---

## Setup

### 1. Create a Discord webhook

In your Discord server: **Server Settings → Integrations → Webhooks → New Webhook → Copy Webhook URL**

### 2. Create a GitHub repository

Go to [github.com/new](https://github.com/new), create a **private** repo, and push all files — maintain the folder structure (`.github/workflows/` must be at the root).

### 3. Add the GitHub secret

In your repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|-------------|-------|
| `DISCORD_WEBHOOK_URL` | Your full Discord webhook URL |

That's the only secret needed.

### 4. Enable GitHub Actions

Go to the **Actions** tab → click **"I understand my workflows, go ahead and enable them"**

Done. The workflow is pre-configured and runs automatically on schedule.

---

## Run locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up your .env
cp .env.example .env
# Open .env and paste your Discord webhook URL

# 3. Verify webhook works
python forex_alert.py test

# 4. Send today's summary to Discord
python forex_alert.py summary

# 5. Check right now for any 5-min events (alert mode)
python forex_alert.py alert
```

---

## Testing without sending to Discord (dry run)

Simulate what the bot would do at any date and time. Fetches live calendar data, prints to terminal — nothing sent to Discord.

```bash
# What alert would fire 5 min before the 10:00 AM ET events?
python forex_alert.py dryrun --date 2026-06-03 --time 09:55 --mode alert

# What would the morning summary look like?
python forex_alert.py dryrun --date 2026-06-03 --time 08:00 --mode summary
```

| Flag | Description |
|------|-------------|
| `--date` | YYYY-MM-DD |
| `--time` | Simulated current time in 24h ET (e.g. `09:55` catches a 10:00 AM event) |
| `--mode` | `alert` or `summary` |

---

## Manual trigger from GitHub

**Actions → ForexFactory Discord Alerts → Run workflow** → pick `alert` or `summary` → **Run workflow**

Useful for testing the live workflow on demand without waiting for the schedule.

---

## Schedule details

| What | Cron | When (ET) |
|------|------|-----------|
| Pre-news alerts | `*/5 11-21 * * 1-5` | Every 5 min, Mon–Fri, 7 AM–5:55 PM |
| Morning summary (EDT/summer) | `0 12 * * 1-5` | 8:00 AM ET, Mar–Nov |
| Morning summary (EST/winter) | `0 13 * * 1-5` | 8:00 AM ET, Nov–Mar |

The workflow auto-detects `summary` vs `alert` mode based on the UTC hour at execution time. No manual configuration needed for DST changes.

> **GitHub scheduling note:** Scheduled runs can be delayed up to ~5 minutes under high load — acceptable for trading alerts since you still get the heads-up before the event.

> **Inactivity:** GitHub disables scheduled workflows after 60 days of no repo activity. Just push any small commit to re-enable.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No alerts in Discord | Check **Actions** tab for run logs. Confirm `DISCORD_WEBHOOK_URL` secret is set. |
| Workflow not running | Actions may be disabled — go to Actions tab and re-enable. Push a commit if inactive >60 days. |
| `404` Discord error | Webhook was deleted in Discord. Create a new one, update the secret. |
| Wrong event times in dryrun | `--time` is the simulated *current* time in 24h ET. Use `09:55` to catch a `10:00 AM ET` event. |
| "Could not find calendar table" | ForexFactory updated their HTML. Run `python debug_scraper.py` and share output to diagnose. |
