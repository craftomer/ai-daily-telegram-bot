\
import os, re, time, hashlib, html
from datetime import datetime
from dateutil import tz
from typing import List, Dict, Optional, Tuple
import feedparser, requests, yaml
from tenacity import retry, stop_after_attempt, wait_exponential

# -----------------------------
# Configuration (env-driven)
# -----------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")   # e.g., -1001234567890
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")       # optional

# Istanbul timezone for timestamps
IST = tz.gettz("Europe/Istanbul")

# Keywords to steer categorization (simple but effective)
MOBILE_KEYWORDS = [
    "mobile", "android", "ios", "iphone", "ipad", "galaxy", "snapdragon", "apple silicon",
    "google play", "app store", "unity", "unreal", "apk", "react native", "flutter",
    "mobile game", "gacha", "hypercasual", "ad monetization", "iap", "sensor tower",
    "unity ads", "ironsource", "applovin", "roblox", "oculus quest", "vision pro"
]

def load_sources(path: str = "sources.yaml") -> Dict[str, List[str]]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def canonical_url(u: str) -> str:
    if not u:
        return u
    # Trim tracking params
    if "?" in u:
        base, _ = u.split("?", 1)
        return base
    return u

def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def hash_item(title: str, link: str) -> str:
    return hashlib.sha256((title + canonical_url(link)).encode("utf-8")).hexdigest()[:16]

def is_mobile_relevant(text: str) -> bool:
    low = (text or "").lower()
    return any(k in low for k in MOBILE_KEYWORDS)

def score_item(entry: dict) -> float:
    # Simple heuristic: recency + title presence + summary length
    now = datetime.now(tz=IST)
    published = entry.get("published_parsed")
    recency_hours = 9999
    if published:
        try:
            # feedparser returns time.struct_time
            import time as _t
            pub_ts = _t.mktime(published)
            from datetime import timezone
            pub_dt = datetime.fromtimestamp(pub_ts, tz=IST)
            recency_hours = max(1, (now - pub_dt).total_seconds() / 3600.0)
        except Exception:
            pass
    title_ok = len(entry.get("title", "")) > 0
    summary_len = len(entry.get("summary", ""))
    score = (10.0 / recency_hours) + (1.0 if title_ok else 0.0) + min(1.5, summary_len / 400.0)
    return score

def fetch_feeds(feed_urls: List[str]) -> List[dict]:
    items = []
    for url in feed_urls:
        try:
            fp = feedparser.parse(url)
            for e in fp.entries[:30]:
                items.append(e)
        except Exception:
            continue
    return items

def summarize_with_openai(title: str, text: str) -> Optional[str]:
    if not OPENAI_API_KEY:
        return None
    try:
        import json
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        prompt = f"""You are a news editor for a gaming CEO.
Summarize the following news in 2 crisp sentences, plain English, max 45 words, no emojis, no hype.
Focus on what changed and why it matters.
TITLE: {title}
CONTENT: {text}"""
        body = {
            "model": "gpt-4.1-mini",
            "input": [{"role":"user", "content": prompt}],
        }
        r = requests.post("https://api.openai.com/v1/responses", headers=headers, json=body, timeout=30)
        r.raise_for_status()
        out = r.json()
        # Try extracting a text field robustly
        summary = None
        # Common new Responses API output
        if isinstance(out.get("output"), dict):
            summary = out["output"].get("text")
        if not summary and isinstance(out.get("output"), list):
            # collect any output_text chunks
            parts = []
            for seg in out["output"]:
                if isinstance(seg, dict) and "content" in seg:
                    for c in seg["content"]:
                        if c.get("type") == "output_text" and c.get("text"):
                            parts.append(c["text"])
            if parts:
                summary = " ".join(parts)
        # Legacy-style choices
        if not summary and "choices" in out:
            for ch in out["choices"]:
                txt = ch.get("message", {}).get("content")
                if txt:
                    summary = txt
                    break
        if summary:
            return normalize_text(summary)[:400]
    except Exception:
        return None
    return None

def summarize(title: str, text: str) -> str:
    s = summarize_with_openai(title, text)
    if s:
        return s
    # Fallback: first ~40 words of provided summary/text
    words = normalize_text(text).split()
    return " ".join(words[:40])

def pick_top(items: List[dict], want: int) -> List[dict]:
    # de-dupe by (title+url) hash, keep best score
    best: Dict[str, Tuple[float, dict]] = {}
    for e in items:
        title = normalize_text(e.get("title", ""))
        link = canonical_url(e.get("link", ""))
        if not title or not link:
            continue
        h = hash_item(title, link)
        s = score_item(e)
        if h not in best or s > best[h][0]:
            best[h] = (s, e)
    ranked = sorted([v[1] for v in best.values()], key=score_item, reverse=True)
    return ranked[:want]

def make_block(title: str, entries: List[dict]) -> str:
    lines = [f"# {title} — Top {len(entries)} ({datetime.now(tz=IST).strftime('%b %d, %Y')})", ""]
    for i, e in enumerate(entries, 1):
        etitle = normalize_text(e.get("title", ""))
        link = canonical_url(e.get("link", ""))
        rawsum = normalize_text(html.unescape(e.get("summary", ""))) or etitle
        summary = summarize(etitle, rawsum)
        lines.append(f"{i}) *{etitle}*")
        lines.append(f"   {summary}")
        lines.append(f"   🔗 {link}")
        lines.append("")
    return "\n".join(lines).strip()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def send_telegram_message(text: str):
    assert TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID, "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    r = requests.post(url, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()

def build_and_send():
    sources = load_sources()
    general_items = fetch_feeds(sources.get("general_ai", []))
    mobile_items  = fetch_feeds(sources.get("mobile_gaming", []))

    # Keep mobile block truly mobile-focused by seeding it with mobile feeds
    # and also siphoning mobile-relevant posts from general AI feeds.
    general_filtered = []
    siphoned_to_mobile = []
    for e in general_items:
        text = (e.get("title","") + " " + e.get("summary",""))
        if is_mobile_relevant(text):
            siphoned_to_mobile.append(e)
        else:
            general_filtered.append(e)

    mobile_pool = mobile_items + siphoned_to_mobile

    top_general = pick_top(general_filtered, 3)
    top_mobile  = pick_top(mobile_pool, 3)

    block_general = make_block("AI in General", top_general)
    block_mobile  = make_block("AI in Mobile Gaming", top_mobile)

    # Send as two messages to keep each block focused
    send_telegram_message(block_general)
    send_telegram_message(block_mobile)

if __name__ == "__main__":
    build_and_send()
