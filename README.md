# ForexFactory → Discord Alerts

Sends Discord alerts for USD 🔴 High and 🟠 Medium impact news events:
- **5 min before** each event (runs every 5 min on GitHub Actions)
- **Daily 8 AM ET summary** of all USD high/medium events for the day

---

## Setup (5 minutes)

### 1. Create a GitHub repo

Go to [github.com/new](https://github.com/new) and create a **private** repo.

Upload these files:
```
forex_alert.py
.github/workflows/forex_alerts.yml
```

### 2. Add your Discord webhook as a secret

In your GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**

- Name:  `DISCORD_WEBHOOK_URL`
- Value: your webhook URL (e.g. `https://discord.com/api/webhooks/...`)

### 3. Enable Actions

Go to **Actions** tab in your repo → click **"I understand my workflows, go ahead and enable them"**

That's it. GitHub will run the workflow on schedule automatically.

---

## Schedule

| What | When |
|------|------|
| 5-min pre-news alert | Every 5 min, Mon–Fri, 7 AM – 5:55 PM ET |
| Daily summary | 8:00 AM ET, Mon–Fri |

> GitHub Actions schedules run in UTC. The workflow handles EDT/EST automatically.

---

## Manual trigger

Go to **Actions → ForexFactory Discord Alerts → Run workflow** and pick `alert` or `summary`.

---

## Data source

Uses [nfs.faireconomy.media](https://nfs.faireconomy.media/ff_calendar_thisweek.json) — a free community JSON feed of the ForexFactory calendar. No API key needed.

---

## Troubleshooting

- **No alerts firing?** Check the Actions tab for run logs. Each run prints what it found.
- **Wrong timezone?** The script uses `America/New_York` (ET). DST is handled automatically via `pytz`.
- **GitHub inactivates scheduled workflows** after 60 days of repo inactivity — just push any small change to reactivate.
