"""
meyers_scraper.py — Download music articles from Meyers Konversations-Lexikon 4th ed.
(1885–1890; supplements through 1892) via German Wikisource, category:Musik.

Music-related articles are available under:
  Kategorie:Musik (Meyers Konversations-Lexikon)

Output: data_ocr/meyers_konversations_lexikon/meyers_music_articles.txt
Format: === TITLE ===\n{article text}\n  (compatible with BROCKHAUS_ARTICLE parser)
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup

OUTPUT_DIR = "data_ocr/meyers_konversations_lexikon"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "meyers_music_articles.txt")

WIKISOURCE_API = "https://de.wikisource.org/w/api.php"
WIKISOURCE_BASE = "https://de.wikisource.org/wiki"

# Boilerplate prefix patterns to strip from rendered article text
_BOILERPLATE = re.compile(
    r"^.{0,600}?(?=\[\s*\d+\s*\])",  # everything before "[PAGE_NUM]"
    re.DOTALL,
)
# Navigation footer to strip
_FOOTER = re.compile(
    r"(?:Empfohlene Zitierweise|Indexseite|Von\s*„\s*https?://|"
    r"Dieser Text wurde anhand).{0,2000}$",
    re.DOTALL,
)


def fetch_category_members(session: requests.Session) -> list[str]:
    """
    Return all page titles in Kategorie:Musik (Meyers Konversations-Lexikon).
    """
    titles = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": "Kategorie:Musik (Meyers Konversations-Lexikon)",
        "cmlimit": "500",
        "cmtype": "page",
        "format": "json",
    }
    while True:
        resp = session.get(WIKISOURCE_API, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        members = data.get("query", {}).get("categorymembers", [])
        titles.extend(m["title"] for m in members)
        cont = data.get("continue", {}).get("cmcontinue")
        if not cont:
            break
        params["cmcontinue"] = cont
        time.sleep(0.3)
    return titles


def fetch_article_html(title: str, session: requests.Session) -> str | None:
    """
    Fetch and clean the rendered HTML text of a Wikisource article.
    Returns cleaned plain text or None.
    """
    url = f"{WIKISOURCE_BASE}/{requests.utils.quote(title, safe=':')}"
    try:
        resp = session.get(url, timeout=20)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        content = soup.find(id="mw-content-text")
        if not content:
            return None
        text = content.get_text(separator=" ", strip=True)
        # Normalise whitespace
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\n +", "\n", text)
        # Strip boilerplate header (everything before the first [PAGE_NUM] marker)
        m = re.search(r"\[\s*\d+\s*\]", text)
        if m:
            text = text[m.start():]
        # Strip navigation footer
        text = _FOOTER.sub("", text).strip()
        # Remove isolated page-number markers like [ 916 ]
        text = re.sub(r"\[\s*\d+\s*\]", " ", text)
        text = re.sub(r"\s{2,}", " ", text)
        return text.strip() if len(text.strip()) >= 30 else None
    except Exception as e:
        print(f"    Error fetching {title}: {e}")
        return None


def label_from_title(title: str) -> str:
    """Extract a clean label from 'MKL1888:SomeTerm' → 'SomeTerm'."""
    return title.split(":")[-1].strip()


def scrape_meyers(output_path: str) -> int:
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "LexiconC19-Research/1.0 (academic musicology, Sorbonne; "
            "contact: scai@sorbonne-universite.fr; "
            "fetching public-domain Wikisource text)"
        )
    })

    print("Fetching category members from de.wikisource.org...")
    titles = fetch_category_members(session)
    print(f"Found {len(titles)} articles in Kategorie:Musik (Meyers Konversations-Lexikon)")

    if not titles:
        print("Category returned no members. Check connectivity or category name.")
        return 0

    articles = []
    skipped = 0
    for i, title in enumerate(titles):
        label = label_from_title(title)
        text = fetch_article_html(title, session)
        if text:
            articles.append(f"=== {label} ===\n{text}\n")
            print(f"  [{i+1}/{len(titles)}] OK: {label} ({len(text)} chars)")
        else:
            skipped += 1
            if (i + 1) % 20 == 0:
                print(f"  [{i+1}/{len(titles)}] (skipped {skipped} so far)")
        # Polite delay: ~0.8s average
        time.sleep(0.6 + (i % 4) * 0.1)

    print(f"\nFetched: {len(articles)}  Skipped/empty: {skipped}")

    if articles:
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(articles))
        print(f"Saved → {output_path}")

    return len(articles)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")

    print("=== Meyers Konversations-Lexikon Scraper (de.wikisource.org) ===\n")

    if os.path.exists(OUTPUT_FILE):
        print(f"Output already exists: {OUTPUT_FILE}")
        print("Delete it and re-run to refresh.")
        return

    n = scrape_meyers(OUTPUT_FILE)

    if n == 0:
        print(
            "\nNo articles fetched. Manual option:\n"
            "  Place Meyers OCR text files in data_ocr/meyers_konversations_lexikon/\n"
            "  Format: each file as plain text with entries 'HEADWORD. Definition...'\n"
        )
    else:
        print(f"\nDone ({n} articles). Run scripts/build_dataset.py to rebuild the dataset.")


if __name__ == "__main__":
    main()
