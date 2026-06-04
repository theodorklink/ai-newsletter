"""
AI Newsletter Generator
Fetches RSS feeds, generates a curated newsletter via Claude API,
and sends it to your iCloud email address.
"""

import feedparser
import anthropic
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from dateutil import parser as date_parser

# ── Configuration ─────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ICLOUD_EMAIL      = os.environ["ICLOUD_EMAIL"]        # e.g. yourname@icloud.com
ICLOUD_APP_PW     = os.environ["ICLOUD_APP_PASSWORD"] # App-specific password from Apple ID
RECIPIENT_EMAIL   = os.environ.get("RECIPIENT_EMAIL", ICLOUD_EMAIL)

# How many hours back to collect articles (48h = every 2 days)
LOOKBACK_HOURS = 48

# How many articles to pass to Claude (keeps costs low)
MAX_ARTICLES = 40

# ── RSS Feed Sources ───────────────────────────────────────────────────────────
# Curated stack covering research, policy, developer tools, and AI in media.
# Add or remove feeds freely — just keep the list format.

FEEDS = [
    # Research & Foundation Models
    ("The Gradient",            "https://thegradient.pub/rss/"),
    ("Hugging Face Blog",       "https://huggingface.co/blog/feed.xml"),
    ("DeepMind Blog",           "https://deepmind.google/blog/rss.xml"),
    ("Anthropic News",          "https://www.anthropic.com/news/rss.xml"),
    ("OpenAI Blog",             "https://openai.com/blog/rss.xml"),

    # AI Business & Policy
    ("MIT Tech Review AI",      "https://www.technologyreview.com/feed/"),
    ("VentureBeat AI",          "https://venturebeat.com/category/ai/feed/"),
    ("The Verge AI",            "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"),
    ("TechCrunch AI",           "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("Wired AI",                "https://www.wired.com/feed/tag/ai/latest/rss"),

    # Developer Tools & Practical
    ("Towards Data Science",    "https://towardsdatascience.com/feed"),
    ("Simon Willison's Blog",   "https://simonwillison.net/atom/everything/"),
    ("Ahead of AI (Sebastian)", "https://magazine.sebastianraschka.com/feed"),

    # AI in Media & Journalism
    ("NiemanLab",               "https://www.niemanlab.org/feed/"),
    ("Reuters Institute",       "https://reutersinstitute.politics.ox.ac.uk/news/rss.xml"),
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def fetch_recent_articles(lookback_hours: int = LOOKBACK_HOURS) -> list[dict]:
    """Pull articles from all feeds published within the lookback window."""
    cutoff = datetime.now(timezone.utc).timestamp() - lookback_hours * 3600
    articles = []

    for name, url in FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                # Parse publish date
                published = None
                for attr in ("published_parsed", "updated_parsed"):
                    val = getattr(entry, attr, None)
                    if val:
                        import calendar
                        published = calendar.timegm(val)
                        break

                if published and published >= cutoff:
                    articles.append({
                        "source":  name,
                        "title":   entry.get("title", "No title"),
                        "url":     entry.get("link", ""),
                        "summary": entry.get("summary", entry.get("description", ""))[:600],
                        "published": datetime.fromtimestamp(published, tz=timezone.utc).strftime("%d.%m. %H:%M"),
                    })
        except Exception as e:
            print(f"[WARN] Could not fetch {name}: {e}")

    # Sort newest first, cap total
    articles.sort(key=lambda a: a["published"], reverse=True)
    return articles[:MAX_ARTICLES]


def build_article_block(articles: list[dict]) -> str:
    """Format articles for the Claude prompt."""
    lines = []
    for i, a in enumerate(articles, 1):
        lines.append(
            f"{i}. [{a['source']}] {a['title']}\n"
            f"   URL: {a['url']}\n"
            f"   Published: {a['published']}\n"
            f"   Summary: {a['summary']}\n"
        )
    return "\n".join(lines)


def generate_newsletter(articles: list[dict]) -> str:
    """Call Claude API to generate the newsletter HTML."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    date_str = datetime.now().strftime("%d. %B %Y")

    system_prompt = """
You are writing a personalised AI newsletter for Theodor, a 21-year-old German business student
currently interning at Axel Springer's Strategic Investments & M&A team in New York.
He has a strong interest in: foundation models and research, AI policy & regulation,
AI's impact on media and journalism (directly relevant to his work), developer tools,
and AI startups. He is analytically sharp and dislikes fluff and marketing language.

Output a COMPLETE, self-contained HTML email. Requirements:
- Language: German, but keep English technical terms (model names, company names, etc.)
- Tone: Direct, analytical, slightly opinionated. Brief personal angle on each story.
- Structure:
    1. Short intro paragraph (3-4 sentences, conversational)
    2. "Top Story" section: 1 story treated in depth (200-300 words + link)
    3. "Weitere Highlights" section: 5-8 stories, each with 3-5 sentences of analysis + link
    4. "Quick Hits" section: remaining noteworthy items, 1-2 sentences each + link
    5. Short closing line
- Each story MUST include the original URL as a hyperlink on the article title.
- Do NOT include stories that are purely listicles, press releases, or sponsored content.
- HTML styling: clean, readable, dark navy background (#0f172a), white text,
  accent color #60a5fa (blue), monospace font for section labels,
  max-width 680px, generous padding. Make it look great in an email client.
- Do NOT include any markdown — pure HTML only.
""".strip()

    user_prompt = f"""
Today is {date_str}. Here are the latest articles collected from curated AI feeds:

{build_article_block(articles)}

Write the full newsletter HTML now.
""".strip()

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text


def send_email(html_body: str):
    """Send the newsletter via iCloud SMTP."""
    date_str = datetime.now().strftime("%d.%m.%Y")
    subject  = f"🤖 Dein AI-Newsletter — {date_str}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = ICLOUD_EMAIL
    msg["To"]      = RECIPIENT_EMAIL

    # Plain-text fallback
    plain = "Dein personalisierter AI-Newsletter. Bitte öffne diese E-Mail in einem HTML-fähigen Client."
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html_body, "html"))

with smtplib.SMTP_SSL("smtp.mail.me.com", 465) as server:
server.login(ICLOUD_EMAIL, ICLOUD_APP_PW)
        server.sendmail(ICLOUD_EMAIL, RECIPIENT_EMAIL, msg.as_string())

    print(f"[OK] Newsletter sent to {RECIPIENT_EMAIL}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("[1/3] Fetching recent articles...")
    articles = fetch_recent_articles()
    print(f"      Found {len(articles)} articles in the last {LOOKBACK_HOURS}h")

    if not articles:
        print("[WARN] No articles found. Skipping send.")
        return

    print("[2/3] Generating newsletter via Claude API...")
    html = generate_newsletter(articles)

    print("[3/3] Sending email...")
    send_email(html)


if __name__ == "__main__":
    main()
