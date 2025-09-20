# AI Daily Telegram Bot (Mobile Gaming Focus) — v2

Posts one daily message to your Telegram group with:

- **AI in Gaming (3 items)**
- **AI in General (3 items)**

Each item has:
```
Simple Summary: <one sentence>
👉 <short link>
Craft Action: <one sentence, practical>
```

Links are shortened via is.gd (fallback: TinyURL).

## Quick Start

1. Create a Telegram bot via @BotFather and add it to your group as admin.  
2. Get `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.  
3. In GitHub → Settings → Secrets and variables → Actions, add:  
   - `TELEGRAM_BOT_TOKEN`  
   - `TELEGRAM_CHAT_ID`  
   - (optional) `OPENAI_API_KEY`  
4. The workflow runs daily at **09:30 Istanbul** or can be triggered manually in the Actions tab.

## Run locally

```bash
export TELEGRAM_BOT_TOKEN=123:ABC
export TELEGRAM_CHAT_ID=-1001234567890
# optional for nicer summaries
export OPENAI_API_KEY=sk-...
pip install -r requirements.txt
python bot.py
```
