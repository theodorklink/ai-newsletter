"""
AI Newsletter Generator
Fetches RSS feeds, generates a curated newsletter via Claude API,
and sends it via SendGrid.
"""

import feedparser
import anthropic
import sendgrid
import os
from sendgrid.helpers.mail import Mail
from datetime import datetime, timezone

# ── Configuration ─────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SENDGRID_API_KEY  = os.environ["SENDGRID_API_KEY"]
ICLOUD_EMAIL      = os.environ["ICLOUD_EMAIL"]
RECIPIENT_EMAIL   = os.environ.get("RECIPIENT_EMAIL", ICLOUD_EMAIL)

LOOKBACK_HOURS = 72
MAX_ARTICLES   = 50

# ── RSS Feed Sources ───────────────────────────────────────────────────────────

FEEDS = [
    # Research & Foundation Models
    ("The Gradient",             "https://thegradient.pub/rss/"),
    ("Hugging Face Blog",        "https://huggingface.co/blog/feed.xml"),
    ("DeepMind Blog",            "https://deepmind.google/blog/rss.xml"),
    ("Anthropic News",           "https://www.anthropic.com/news/rss.xml"),
    ("OpenAI Blog",              "https://openai.com/blog/rss.xml"),
    ("Ahead of AI",              "https://magazine.sebastianraschka.com/feed"),

    # AI Business, Funding & M&A
    ("TechCrunch AI",            "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("VentureBeat AI",           "https://venturebeat.com/category/ai/feed/"),
    ("The Information",          "https://www.theinformation.com/feed"),
    ("Bloomberg Technology",     "https://feeds.bloomberg.com/technology/news.rss"),

    # Policy, Geopolitics & Society
    ("MIT Tech Review AI",       "https://www.technologyreview.com/feed/"),
    ("Wired AI",                 "https://www.wired.com/feed/tag/ai/latest/rss"),
    ("The Verge AI",             "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"),
    ("Financial Times Tech",     "https://www.ft.com/technology?format=rss"),

    # Opinions & Influential Voices
    ("Benedict Evans",           "https://www.ben-evans.com/benedictevans/rss.xml"),
    ("Simon Willison",           "https://simonwillison.net/atom/everything/"),
    ("Stratechery",              "https://stratechery.com/feed/"),

    # AI in Media & Journalism
    ("NiemanLab",                "https://www.niemanlab.org/feed/"),
    ("Reuters Institute",        "https://reutersinstitute.politics.ox.ac.uk/news/rss.xml"),
]

# ── Helpers ────────────────────────────────────────────────────────────────────

def fetch_recent_articles(lookback_hours: int = LOOKBACK_HOURS) -> list[dict]:
    import calendar
    cutoff   = datetime.now(timezone.utc).timestamp() - lookback_hours * 3600
    articles = []

    for name, url in FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                published = None
                for attr in ("published_parsed", "updated_parsed"):
                    val = getattr(entry, attr, None)
                    if val:
                        published = calendar.timegm(val)
                        break
                if published and published >= cutoff:
                    articles.append({
                        "source":    name,
                        "title":     entry.get("title", "No title"),
                        "url":       entry.get("link", ""),
                        "summary":   entry.get("summary", entry.get("description", ""))[:600],
                        "published": datetime.fromtimestamp(published, tz=timezone.utc).strftime("%d.%m. %H:%M"),
                    })
        except Exception as e:
            print(f"[WARN] Could not fetch {name}: {e}")

    articles.sort(key=lambda a: a["published"], reverse=True)
    return articles[:MAX_ARTICLES]


def build_article_block(articles: list[dict]) -> str:
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
    client   = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    date_str = datetime.now().strftime("%d. %B %Y")
    weekday  = datetime.now().strftime("%A")

    system_prompt = """
Du schreibst einen professionellen, zweimal wöchentlich erscheinenden AI-Newsletter für Theodor.
Er ist 21 Jahre alt, deutscher BWL-Student an der WHU, aktuell Praktikant im Strategic Investments
& M&A Team von Axel Springer in New York. Er baut gezielt seine Tech-Kompetenz aus und denkt
langfristig über eine eigene Gründung nach.

DESIGN: Financial Times-Optik. Creme-weißer Hintergrund (#FFF1E0), dunkelbraune Schrift (#333333),
FT-typischer Akzent in Lachs/Rosa (#F2A56A). Serifenschrift: Georgia oder "Times New Roman" für
Fließtext und Headlines. Monospace nur für Labels/Tags. Klare Spaltenstruktur, journalistisch bündig,
kein verspieltes Design. Max-width 680px. Wirkungsvoller Header mit Ausgabennummer und Datum.
Trennlinien zwischen Sektionen. Kompakte Paragraphen, linksbündig, kein Flattersatz.

SPRACHE: Deutsch. Englische Eigennamen, Modellnamen, Firmennamen und Fachbegriffe bleiben Englisch.
Stil: nüchtern, präzise, direkt. Kein Marketing-Sprech, keine Superlative ohne Substanz.
Fakten zuerst, Einordnung danach. Kurze Sätze bevorzugen.

STRUKTUR (exakt in dieser Reihenfolge):

1. HEADER
   FT-typischer Zeitungskopf: "THE AI BRIEFING" in Versalien, Ausgabedatum, Tagline.

2. LAGE DES MARKTES (2-3 Absätze)
   Überblick über den globalen AI-Markt der letzten Tage. Wo stehen wir gerade?
   Was hat sich seit der letzten Ausgabe verändert? Tonalität wie ein FT-Leitartikel.

3. TOP STORY (300-400 Wörter)
   Die wichtigste Einzelentwicklung der Periode. Tiefgang, Kontext, Implikationen.
   Verlinkter Titel als H2-Überschrift.

4. FUNDING & M&A
   Neue Finanzierungsrunden, Übernahmen, Exits. Pro Eintrag: 2-3 Sätze mit Betrag,
   Investoren, strategischer Bedeutung. Verlinkter Titel.

5. NEUE MODELLE & BENCHMARKS
   Welche Modelle wurden released oder angekündigt? Was sagen die Benchmarks?
   Einordnung: Ist das ein echter Fortschritt oder Marketing?

6. TOOLS & PRODUKTE
   Neue Developer-Tools, Produktlaunches, API-Updates. Kurz und konkret.

7. GEOPOLITIK & REGULIERUNG
   US-China-Rivalität, AGI-Rennen, Regulierungsvorhaben in EU/USA/China.
   Aussagen wichtiger Stimmen aus der Industrie (CEOs, Forscher, Politiker).
   Was sagen einflussreiche Stimmen auf Twitter/X, in Podcasts, in Essays?

8. MEINUNGSKOLUMNE (200-250 Wörter)
   Ein kritischer Kommentar zu einem Thema der Ausgabe. Geschrieben aus der Perspektive
   eines skeptischen, informierten Beobachters. Klar als Meinung gekennzeichnet.
   Darf provozieren und gegen den Mainstream argumentieren.

9. FUR DICH ALS STUDENT & ZUKUNFTIGER GRUNGER
   3-5 konkrete Punkte: Was bedeuten die Entwicklungen dieser Ausgabe für einen
   Wirtschaftsstudenten mit Tech-Ambitionen? Welche Skills, welche Chancen, welche Risiken?
   Praktisch, nicht abstrakt.

10. MEDIENEMPFEHLUNGEN
    3-5 Empfehlungen: Podcasts, YouTube-Videos, Dokumentationen, Bücher, Essays, Interviews.
    Nur wenn wirklich relevant zur Ausgabe. Format: Titel, Typ, 1 Satz warum.

11. KURZMELDUNGEN
    Restliche Neuigkeiten: je 1-2 Sätze mit Link. Kompakt wie Bloomberg-Ticker.

REGELN:
- Jede Story mit verlinktem Titel (HTML-Anker auf Original-URL).
- Keine reinen Pressemitteilungen oder Sponsored Content.
- Keine Bullet-Point-Wüsten: fliessender Zeitungstext bevorzugen.
- HTML only, kein Markdown. Vollstaendiges, selbststaendiges HTML-Dokument.
- Inline-CSS fuer alle Styles (Email-Client-kompatibel).
""".strip()

    user_prompt = f"""
Heute ist {weekday}, {date_str}. Hier sind die aktuellen Artikel der letzten {LOOKBACK_HOURS} Stunden:

{build_article_block(articles)}

Schreibe jetzt den vollstaendigen Newsletter als HTML.
""".strip()

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text


def send_email(html_body: str):
    date_str = datetime.now().strftime("%d.%m.%Y")
    subject  = f"The AI Briefing — {date_str}"

    message = Mail(
        from_email=ICLOUD_EMAIL,
        to_emails=RECIPIENT_EMAIL,
        subject=subject,
        html_content=html_body,
    )

    sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
    response = sg.send(message)
    print(f"[OK] Newsletter sent. Status: {response.status_code}")


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
