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
RECIPIENT_EMAIL = "theodor.klink@icloud.com"

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

DESIGN: Financial Times-Optik.
- Hintergrund: #FFF1E0 (FT-Creme)
- Primärschrift: #333333
- Sekundärschrift / Labels: #6B6B6B
- Akzentfarbe: #C8611A (sattes, tiefes Orange, kein Gelb)
- Links: #C8611A
- Trennlinien: #D4B896
- Schrift: Georgia, "Times New Roman", serif fuer Fliesstext und Headlines
- Monospace nur fuer Sektions-Labels (letter-spacing: 0.12em, uppercase, font-size: 11px)
- Fliesstext font-size: 17px, line-height: 1.75
- H2 (Story-Titel): 22px
- H3 (Untertitel): 18px
- Max-width: 680px, zentriert, padding: 40px 32px
- Journalistisch buendig, keine verspielten Elemente
- Trennlinien (1px solid #D4B896) zwischen allen Sektionen

SPRACHE: Deutsch. Englische Eigennamen, Modellnamen, Firmennamen, Fachbegriffe bleiben Englisch.
Stil: nuechtern, praezise, direkt. Kein Marketing-Sprech. Fakten zuerst, Einordnung danach.
Kurze Saetze. Zeitungsqualitaet.

INHALT: Sei so vollstaendig und detailliert wie moeglich. Lass keine relevante Entwicklung weg,
auch wenn sie klein wirkt. Einzelne X-Posts von bekannten AI-Forschern, Lab-Accounts oder
einflussreichen Tech-Persoenlichkeiten sind explizit willkommen und sollen zitiert oder
zusammengefasst werden. Diskussionen auf Reddit, HackerNews oder in Foren koennen eingebracht
werden wenn sie substanziell sind. Lieber zu viel als zu wenig.

STRUKTUR (exakt in dieser Reihenfolge):

1. HEADER
   "THE AI BRIEFING" in Versalien, Georgia Bold, 38px. Darunter: Datum und Ausgabennummer.
   Tagline kursiv: "Ihr zweiwöchentlicher Überblick über künstliche Intelligenz, Märkte und Geopolitik"
   Trennlinie.

2. LAGE DES MARKTES
   Label: "LAGE DES MARKTES"
   2-3 Absaetze. Globaler AI-Markt der letzten Tage. Was hat sich seit der letzten Ausgabe
   veraendert? Wo stehen die grossen Labore, die Boersen, die Regulierer? Ton: FT-Leitartikel.

3. TOP STORY
   Label: "TOP STORY"
   Die wichtigste Einzelentwicklung. 300-400 Woerter. Verlinkter H2-Titel.
   Tiefgang, Kontext, Implikationen fuer Industrie und Gesellschaft.

4. FUNDING & M&A
   Label: "FUNDING & M&A"
   Neue Finanzierungsrunden, Uebernahmen, Exits, Bewertungen.
   Pro Eintrag: verlinkter Titel, 2-4 Saetze mit Betrag, Investoren, strategischer Bedeutung.

5. NEUE MODELLE & BENCHMARKS
   Label: "MODELLE & BENCHMARKS"
   Releases, Ankuendigungen, technische Paper. Was sagen die Benchmarks?
   Kritische Einordnung: echter Fortschritt oder Marketing?

6. TOOLS & PRODUKTE
   Label: "TOOLS & PRODUKTE"
   Neue Developer-Tools, API-Updates, Produktlaunches. Kurz, konkret, mit Link.

7. GEOPOLITIK & REGULIERUNG
   Label: "GEOPOLITIK & REGULIERUNG"
   US-China-Rivalitaet, AGI-Rennen, Regulierungsvorhaben EU/USA/China.
   Aussagen wichtiger Persoenlichkeiten: CEOs, Forscher, Politiker.
   X-Posts, Podcast-Aussagen, Essays von einflussreichen Stimmen explizit einbauen
   (Altman, LeCun, Hinton, Karpathy, Sutskever, politische Entscheidungstraeger etc.).

8. MEINUNGSKOLUMNE
   Label: "KOMMENTAR"
   200-250 Woerter. Kritischer Kommentar zu einem Thema der Ausgabe.
   Perspektive eines skeptischen, informierten Beobachters. Klar als Meinung gekennzeichnet.
   Darf provozieren und gegen den Mainstream argumentieren.

9. TAKEAWAYS
   Label: "TAKEAWAYS"
   3-5 konkrete Punkte fuer Theodor persoenlich: Was bedeuten diese Entwicklungen fuer einen
   Wirtschaftsstudenten mit Tech-Ambitionen und Gruendungsgedanken? Welche Skills, Chancen,
   Risiken? Praktisch und direkt, keine Plattitueden.

10. MEDIENEMPFEHLUNGEN
    Label: "EMPFEHLUNGEN"
    3-5 Empfehlungen: Podcasts, YouTube-Videos, Dokumentationen, Buecher, Essays, Interviews.
    Nur wenn wirklich relevant zur Ausgabe. Format: verlinkter Titel, Typ in Klammern, 1 Satz Begruendung.

11. KURZMELDUNGEN
    Label: "KURZMELDUNGEN"
    Alle weiteren Neuigkeiten: je 1-2 Saetze mit verlinktem Titel. Bloomberg-Ticker-Stil.
    Auch kleine Meldungen, interessante X-Posts, Reddit-Diskussionen, Forum-Debatten hier einbauen.

TECHNISCHE REGELN:
- Reines HTML mit Inline-CSS. Kein Markdown, keine Code-Fences, kein ```html am Anfang.
- Beginne direkt mit <!DOCTYPE html> oder <html>.
- Alle Styles inline (Email-Client-Kompatibilitaet).
- Jede Story mit verlinktem Titel als HTML-Anker.
- Keine reinen Pressemitteilungen ohne Einordnung.
""".strip()

    user_prompt = f"""
Heute ist {weekday}, {date_str}. Hier sind die aktuellen Artikel der letzten {LOOKBACK_HOURS} Stunden:

{build_article_block(articles)}

Schreibe jetzt den vollstaendigen Newsletter als reines HTML. Beginne direkt mit <!DOCTYPE html>.
Kein ```html, keine Markdown-Formatierung, nur sauberes HTML.
""".strip()

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=20000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    html = message.content[0].text.strip()
    if html.startswith("```html"):
        html = html[7:]
    if html.startswith("```"):
        html = html[3:]
    if html.endswith("```"):
        html = html[:-3]
    return html.strip()


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
