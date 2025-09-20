import os, re, time, hashlib, html
from datetime import datetime
from dateutil import tz
from typing import List, Dict, Optional, Tuple
import feedparser, requests, yaml
from tenacity import retry, stop_after_attempt, wait_exponential

# -----------------------------
# Config
# -----------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

IST = tz.gettz("Europe/Istanbul")

# -----------------------------
# Helpers
# -----------------------------
def load_sources(path: str = "sources.yaml") -> Dict[str, List[str]]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def canonical_url(u: str) -> str:
    if not u: return u
    return u.split("?", 1)[0]

def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def hash_item(title: str, link: str) -> str:
    return hashlib.sha256((title + canonical_url(link)).encode("utf-8")).hexdigest()[:16]

def score_item(entry: dict) -> float:
    now = datetime.now(tz=IST)
    recency_hours = 9999
    published = entry.get("published_parsed")
    if published:
        try:
            pub_ts = time.mktime(published)
            pub_dt = datetime.fromtimestamp(pub_ts, tz=IST)
            recency_hours = max(1, (now - pub_dt).total_seconds() / 3600.0)
        except Exception:
            pass
    title_ok = len(entry.get("title", "")) > 0
    summary_len = len(entry.get("summary", ""))
    return (10.0 / recency_hours) + (1.0 if title_ok else 0.0) + min(1.5, summary_len / 400.0)

def fetch_feeds(feed_urls: List[str]) -> List[dict]:
    items = []
    for url in feed_urls:
        try:
            fp = feedparser.parse(url)
            items.extend(fp.entries[:30])
        except Exception:
            continue
    return items

# -----------------------------
# URL Shortener
# -----------------------------
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6))
def shorten_url(url: str) -> str:
    u = canonical_url(url)
    try:
        r = requests.get("https://is.gd/create.php", params={"format":"simple","url":u}, timeout=8)
        if r.ok and r.text.startswith("http"):
            return r.text.strip()
    except Exception:
        pass
    try:
        r = requests.get("https://tinyurl.com/api-create.php", params={"url":u}, timeout=8)
        if r.ok and r.text.startswith("http"):
            return r.text.strip()
    except Exception:
        pass
    return u

# -----------------------------
# Summarizer
# -----------------------------
def summarize_with_openai(title: str, text: str) -> Optional[str]:
    if not OPENAI_API_KEY:
        return None
    try:
        import json
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        prompt = f"""One sentence (max 28 words). Plain English. Focus on what changed and why it matters.
TITLE: {title}
CONTENT: {text}"""
        body = {"model": "gpt-4.1-mini", "input": [{"role":"user","content":prompt}]}
        r = requests.post("https://api.openai.com/v1/responses", headers=headers, json=body, timeout=30)
        r.raise_for_status()
        out = r.json()
        if isinstance(out.get("output"), dict):
            return normalize_text(out["output"].get("text",""))[:220]
        if isinstance(out.get("output"), list):
            for seg in out["output"]:
                if isinstance(seg, dict) and "content" in seg:
                    for c in seg["content"]:
                        if c.get("type")=="output_text" and c.get("text"):
                            return normalize_text(c["text"])[:220]
        if "choices" in out:
            for ch in out["choices"]:
                txt = ch.get("message", {}).get("content")
                if txt: return normalize_text(txt)[:220]
    except Exception:
        return None
    return None

def summarize(title: str, text: str) -> str:
    s = summarize_with_openai(title, text)
    return s if s else " ".join(normalize_text(text).split()[:28])

# -----------------------------
# Craft Action rules (100+)
# -----------------------------
def craft_action(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()

    rules = {
        # Engines & Tools
        "unity": "Test Unity AI sprite/texture generation in one live update.",
        "unreal": "Leverage Unreal AI/MetaHuman for fast cutscene prototyping.",
        "metahuman": "Use MetaHuman Animator for real-time facial animation.",
        "roblox": "Study Roblox’s UGC AI features for inspiration.",
        "ugc": "Prototype UGC tools to boost retention.",
        "dlss": "Experiment with DLSS/neural rendering on mid-range devices.",
        "nvidia": "Evaluate NVIDIA ACE for NPC dialogues in Craft games.",
        "epic": "Track Epic’s AI updates for dev pipeline changes.",

        # Mobile / Stores
        "mobile": "Apply AI to cut asset pipeline time on mobile projects.",
        "android": "Check Google Play’s AI policy compliance.",
        "ios": "Review Apple rules for AI-generated content.",
        "app store": "Ensure App Store compliance on AI content.",
        "google play": "Stay alert for Play Store AI rules.",
        "hypercasual": "Prototype AI-generated levels for hypercasual loops.",
        "iap": "Model AI-personalized IAP offers and test uplift.",
        "ads": "Test AI-optimized ad creatives to boost ROAS.",
        "ad monetization": "AI-test ad placement for higher yields.",

        # Competitors
        "supercell": "Benchmark Supercell’s AI use for art/ops efficiency.",
        "zynga": "Study Zynga’s AI personalization in social loops.",
        "scopely": "Analyze Scopely’s AI live-ops for monetization tactics.",
        "netmarble": "Check Netmarble’s AI NPC/quest systems for MMO ideas.",

        # Content Creation
        "art": "Apply AI art tools for concept sketches.",
        "asset": "Adopt AI-assisted asset generation.",
        "animation": "AI-smooth animations for cutscenes.",
        "sound": "AI-augment sound effects cheaply.",
        "music": "Try adaptive AI-generated music.",
        "voice": "Prototype AI voice for NPCs/events.",

        # NPCs & Gameplay
        "npc": "Test NPCs with AI-driven memory/behavior.",
        "copilot": "Prototype in-game copilot for tips.",
        "agent": "Use AI agents for tutorials.",
        "chatbot": "Deploy AI chatbot for in-game Q&A.",

        # Localization / Markets
        "translation": "Add AI chat translation for global play.",
        "localization": "Localize content with AI at scale.",
        "brazil": "Consider AI-driven localization for Brazil.",
        "india": "Explore India mobile market with AI features.",
        "latam": "Check LATAM AI tools for expansion.",

        # Monetization & LiveOps
        "live ops": "Predict churn with AI and trigger offers.",
        "churn": "Build churn prediction models.",
        "personalization": "AI-personalize daily offers.",
        "retention": "AI-generate personal missions.",
        "engagement": "Automate quests with AI scoring.",
        "gacha": "Simulate gacha odds with AI ethically.",

        # Infra & Ops
        "server": "AI-auto scale live-ops servers.",
        "infra": "Monitor infra with AI anomaly detection.",
        "cloud": "Use AI to cut AWS/GCP bills.",
        "latency": "AI-optimize network latency.",
        "gpu": "Track GPU market shifts for costs.",

        # Funding / Industry
        "funding": "Expect API cost shifts after raises.",
        "valuation": "Big valuations mean more model competition.",
        "anthropic": "Consider Claude for NPC dialogue.",
        "openai": "Check OpenAI tools for creative use.",
        "xai": "Watch xAI for GPU partnerships.",
        "gemini": "Gemini may bring mobile integrations.",

        # Regulations / Safety
        "policy": "Stay aligned with AI content policies.",
        "ethics": "Draft Craft’s AI ethics stance early.",
        "safety": "Study Roblox Sentinel for moderation.",
        "moderation": "Test AI chat moderation in Craft games.",

        # Extra categories (to make 100+ over time; add new lines freely)
        "vr": "Explore AI-driven VR content pipelines.",
        "ar": "Test AR experiences with AI NPCs.",
        "esports": "AI-coach tools could integrate into esports titles.",
        "marketing": "Use AI for UA campaign optimization.",
        "influencer": "AI-match influencers to campaigns.",
        "prototype": "Use AI to auto-generate quick prototypes.",
        "qa": "AI-bot QA testing for bug hunting.",
        "trailer": "AI-generate quick trailers for new features.",
        "story": "Use AI to ideate branching storylines.",
        "dialogue": "AI-polish dialogue variations for NPCs."
    }

    for keyword, action in rules.items():
        if keyword in text:
            return action

    return "Identify a 1-week AI experiment in art, design, or ops to validate impact quickly."

# -----------------------------
# Selection & Formatting
# -----------------------------
def pick_top(items: List[dict], want: int) -> List[dict]:
    best: Dict[str, Tuple[float, dict]] = {}
    for e in items:
        title = normalize_text(e.get("title",""))
        link = canonical_url(e.get("link",""))
        if not title or not link: continue
        h = hash_item(title, link)
        s = score_item(e)
        if h not in best or s > best[h][0]:
            best[h] = (s,e)
    ranked = sorted([v[1] for v in best.values()], key=score_item, reverse=True)
    return ranked[:want]

def format_item(e: dict) -> str:
    title = normalize_text(e.get("title",""))
    link = canonical_url(e.get("link",""))
    rawsum = normalize_text(html.unescape(e.get("summary",""))) or title
    one_liner = summarize(title, rawsum)
    short = shorten_url(link)
    action = craft_action(title, rawsum)
    return f"Simple Summary: {one_liner}\n👉 {short}\nCraft Action: {action}"

def pad_to_three(items: List[dict], pool: List[dict]) -> List[dict]:
    seen = {hash_item(normalize_text(i.get("title","")), canonical_url(i.get("link",""))) for i in items}
    for e in pool:
        if len(items) >= 3: break
        h = hash_item(normalize_text(e.get("title","")), canonical_url(e.get("link","")))
        if h not in seen:
            items.append(e); seen.add(h)
    return items

def build_message(gaming_items: List[dict], general_items: List[dict]) -> str:
    lines = []
    lines.append("")  # 👈 leading blank line

    # Gaming header
    lines.append("**🔵 AI IN GAMING**")
    for e in gaming_items:
        lines.append("")
        lines.append(format_item(e))

    # Two blank lines between sections
    lines.append("")
    lines.append("")

    # General header
    lines.append("**🔷 AI IN GENERAL**")
    for e in general_items:
        lines.append("")
        lines.append(format_item(e))

    return "\n".join(lines)


# -----------------------------
# Telegram
# -----------------------------
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def send_telegram_message(text: str):
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

# -----------------------------
# Main
# -----------------------------
def build_and_send():
    sources = load_sources()
    general_all = fetch_feeds(sources.get("general_ai", []))
    mobile_all  = fetch_feeds(sources.get("mobile_gaming", []))  # <-- fixed line

    # siphon mobile-relevant from general into gaming pool
    siphoned = []
    for e in general_all:
        text = (e.get("title","") + " " + e.get("summary","")).lower()
        if any(k in text for k in ["mobile","android","ios","app store","google play","unity","roblox","snapdragon"]):
            siphoned.append(e)

    gaming_pool = mobile_all + siphoned
    general_pool = [e for e in general_all if e not in siphoned]

    top_gaming = pick_top(gaming_pool, 3)
    top_general = pick_top(general_pool, 3)

    if len(top_gaming) < 3:
        top_gaming = pad_to_three(top_gaming, general_pool)
    if len(top_general) < 3:
        remaining = [e for e in general_pool if e not in top_general and e not in top_gaming]
        top_general = pad_to_three(top_general, remaining)

    msg = build_message(top_gaming, top_general)
    send_telegram_message(msg)

if __name__ == "__main__":
    build_and_send()
