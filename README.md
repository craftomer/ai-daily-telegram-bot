# AI Daily Telegram Bot

Posts **two daily digests** to your Telegram group:
- **AI in General — Top 3**
- **AI in Mobile Gaming — Top 3**

Each item: *Title · Two-sentence summary · Link*. Timezone: **Europe/Istanbul**.

## Quick Start

1) **Create a Telegram bot** via @BotFather and add it to your group as admin.  
2) **Grab** your `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.  
3) Clone this repo and run:

```bash
export TELEGRAM_BOT_TOKEN=123:ABC
export TELEGRAM_CHAT_ID=-1001234567890
# optional
export OPENAI_API_KEY=sk-...

pip install -r requirements.txt
python bot.py
```

You should see two messages appear immediately in your group.

## Sources
Edit `sources.yaml` to add/remove RSS feeds.

## Automation (GitHub Actions)
- Push this repo to GitHub.
- In **Settings → Secrets and variables → Actions**, add:
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_CHAT_ID`
  - (optional) `OPENAI_API_KEY`
- The workflow runs daily at **09:30 Istanbul** (cron: `30 6 * * *`, UTC).

## Notes
- If you don't set `OPENAI_API_KEY`, the bot will use a clean fallback summary (first ~40 words).
- To adjust time: change the cron in `.github/workflows/daily.yml`.
- To keep blocks short, we de-duplicate and rank by recency and summary quality.
