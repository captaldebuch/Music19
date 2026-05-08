"""
corpus_expansion.py — Download new sources for Lexicon of Performance v3.

Sources fetched:
  Grove Vols. II–IV   → data_ocr/dictionaryofmusi02grovuoft/ etc.  (Internet Archive)
  Pedrell 1894        → data_ocr/pedrell_diccionario/               (Internet Archive)
  Vieira 1900         → data_ocr/vieira_musicos_portuguezes/        (Internet Archive)
  Fétis 1860 Vol. 1   → data_ocr/fetis_biographie_vol1/             (Gallica)
  Desrat 1895         → data_ocr/desrat_danse/                      (Gallica)
  Brockhaus (music)   → data_ocr/RU_BROCKHAUS/                      (Wikisource — re-scrape)

Run from the project root:
    python3 scripts/corpus_expansion.py
"""

import os
import time
import warnings
import requests
import urllib3
from bs4 import BeautifulSoup
import internetarchive as ia

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ROOT = os.path.dirname(os.path.abspath(__file__)) + "/.."
OCR_DIR = os.path.join(ROOT, "data_ocr")

# ── Internet Archive downloader ───────────────────────────────────────────────

def download_ia(identifier: str, out_dir: str) -> bool:
    dest = os.path.join(OCR_DIR, out_dir)
    os.makedirs(dest, exist_ok=True)

    # Already downloaded?
    existing = [f for f in os.listdir(dest) if f.endswith(".txt")]
    if existing:
        print(f"[SKIP] {identifier}: already have {existing[0]}")
        return True

    print(f"[IA] Downloading {identifier} …")
    try:
        item = ia.get_item(identifier)
        if not item.exists:
            print(f"  ✗ Item {identifier} not found on Archive.org")
            return False

        txt_files = [f["name"] for f in item.files if f["name"].endswith(".txt")]
        if not txt_files:
            print(f"  ✗ No .txt files for {identifier}")
            return False

        preferred = [f for f in txt_files if "djvu" in f] or txt_files
        fname = preferred[0]
        print(f"  → {fname}")
        item.download(files=[fname], destdir=dest, verbose=False)
        print(f"  ✓ Saved to {dest}/{identifier}/{fname}")
        # Move file up one level (ia creates a sub-folder)
        src = os.path.join(dest, identifier, fname)
        if os.path.exists(src):
            os.rename(src, os.path.join(dest, fname))
            try:
                os.rmdir(os.path.join(dest, identifier))
            except OSError:
                pass
        return True
    except Exception as exc:
        print(f"  ✗ Error: {exc}")
        return False


# ── Gallica downloader ────────────────────────────────────────────────────────

def download_gallica(ark: str, out_dir: str, max_pages: int = 300) -> bool:
    dest = os.path.join(OCR_DIR, out_dir)
    os.makedirs(dest, exist_ok=True)

    out_file = os.path.join(dest, f"{ark}_gallica.txt")
    if os.path.exists(out_file):
        print(f"[SKIP] Gallica {ark}: already have {out_file}")
        return True

    print(f"[Gallica] Downloading ark:{ark} (up to {max_pages} pages) …")
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; LexiconBot/1.0; research)"
    })
    session.verify = False

    # Page count from IIIF manifest
    try:
        manifest = session.get(
            f"https://gallica.bnf.fr/iiif/ark:/12148/{ark}/manifest.json", timeout=15
        ).json()
        num_pages = len(manifest["sequences"][0]["canvases"])
        print(f"  Manifest: {num_pages} pages")
    except Exception:
        num_pages = max_pages
        print(f"  Manifest failed, defaulting to {num_pages} pages")

    pages_text = []
    limit = min(num_pages, max_pages)
    for page in range(1, limit + 1):
        url = f"https://gallica.bnf.fr/ark:/12148/{ark}/f{page}.texteBrut"
        for attempt in range(3):
            try:
                r = session.get(url, timeout=15, verify=False)
                if r.status_code == 200 and len(r.text.strip()) > 20:
                    pages_text.append(f"--- Page {page} ---\n{r.text}")
                    break
                elif r.status_code in (403, 500):
                    time.sleep(4 * (attempt + 1))
            except requests.RequestException:
                time.sleep(3)
        if page % 50 == 0:
            print(f"  …page {page}/{limit}")
        time.sleep(0.35)

    if pages_text:
        with open(out_file, "w", encoding="utf-8") as fh:
            fh.write("\n".join(pages_text))
        print(f"  ✓ {len(pages_text)} pages → {out_file}")
        return True
    print("  ✗ No pages retrieved")
    return False


# ── Wikisource Russian Brockhaus scraper ─────────────────────────────────────

# Music-related article titles in the Russian Brockhaus-Efron on Wikisource.
# These are the headwords we want as discrete entries.
BROCKHAUS_MUSIC_ARTICLES = [
    "Музыка", "Опера", "Симфония", "Скрипка", "Орган_(инструмент)",
    "Оркестр", "Хор_(музыка)", "Контрапункт", "Гармония_(музыка)",
    "Ария", "Соната", "Концерт_(музыка)", "Балет", "Романс_(музыка)",
    "Певец", "Сопрано", "Тенор", "Бас_(голос)", "Баритон", "Контральто",
    "Флейта", "Гобой", "Кларнет", "Фагот", "Валторна", "Труба_(инструмент)",
    "Тромбон", "Фортепиано", "Клавесин", "Арфа", "Лютня", "Виолончель",
    "Альт_(инструмент)", "Контрабас", "Барабан", "Литавры", "Колокол",
    "Трубадур", "Менестрель", "Бард", "Жонглёр", "Скоморох",
    "Полифония", "Монодия", "Григорианское_пение", "Мотет", "Мадригал",
    "Месса", "Кантата", "Оратория", "Литургия", "Гимн",
    "Вальс", "Полька", "Мазурка", "Контрданс", "Гавот", "Менуэт",
    "Глинка_Михаил_Иванович", "Мусоргский_Модест_Петрович",
    "Чайковский_Пётр_Ильич", "Римский-Корсаков_Николай_Андреевич",
    "Бетховен_Людвиг_ван", "Моцарт_Вольфганг_Амадей", "Бах_Иоганн_Себастьян",
    "Шуберт_Франц", "Шопен_Фредерик", "Лист_Ференц",
    "Гендель_Георг_Фридрих", "Вагнер_Рихард", "Верди_Джузеппе",
]

def scrape_brockhaus_music(out_dir: str) -> bool:
    dest = os.path.join(OCR_DIR, out_dir)
    os.makedirs(dest, exist_ok=True)
    out_file = os.path.join(dest, "brockhaus_music_articles.txt")

    if os.path.exists(out_file):
        # Check if it has substantial content
        with open(out_file, encoding="utf-8") as fh:
            if len(fh.read()) > 5000:
                print(f"[SKIP] Brockhaus: already have {out_file}")
                return True

    print(f"[Wikisource] Scraping Brockhaus-Efron music articles ({len(BROCKHAUS_MUSIC_ARTICLES)} targets)…")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; LexiconBot/1.0; research)"})
    session.verify = False

    collected = []
    base = "https://ru.wikisource.org"

    for title in BROCKHAUS_MUSIC_ARTICLES:
        # First try Brockhaus-Efron article namespace
        candidates = [
            f"{base}/wiki/ЭСБЕ/{title}",
            f"{base}/wiki/Энциклопедический_словарь_Брокгауза_и_Ефрона/{title}",
            f"{base}/wiki/{title}",
        ]
        found = False
        for url in candidates:
            try:
                r = session.get(url, timeout=15)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    content = soup.find(id="mw-content-text")
                    if content:
                        text = content.get_text(separator="\n", strip=True)
                        if len(text) > 100:
                            # Clean heading from display title
                            display = title.replace("_", " ").split("/")[-1]
                            collected.append(f"=== {display} ===\n{text}\n")
                            found = True
                            break
            except requests.RequestException:
                pass
        if not found:
            # Try Wikipedia as fallback for stub content
            try:
                r = session.get(
                    f"https://ru.wikipedia.org/wiki/{title}", timeout=10
                )
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    # Extract first paragraph only from Wikipedia
                    content = soup.find(id="mw-content-text")
                    if content:
                        first_p = content.find("p")
                        if first_p and len(first_p.get_text()) > 50:
                            display = title.replace("_", " ")
                            collected.append(f"=== {display} ===\n{first_p.get_text()}\n")
                            found = True
            except requests.RequestException:
                pass
        if not found:
            print(f"  ✗ Not found: {title}")
        time.sleep(0.4)

    if collected:
        with open(out_file, "w", encoding="utf-8") as fh:
            fh.write("\n".join(collected))
        print(f"  ✓ {len(collected)} articles → {out_file}")
        return True
    print("  ✗ No articles retrieved")
    return False


# ── Orchestration ─────────────────────────────────────────────────────────────

SOURCES = [
    # (description, download_fn, *args)
    ("Grove Vol. II",   download_ia, "dictionaryofmusi02grovuoft", "grove_vol2"),
    ("Grove Vol. III",  download_ia, "dictionaryofmusi03grovuoft", "grove_vol3"),
    ("Grove Vol. IV",   download_ia, "dictionaryofmusi04grovuoft", "grove_vol4"),
    ("Pedrell (ES)",    download_ia, "diccionariotcnic00pedr",     "pedrell_diccionario"),
    ("Vieira (PT)",     download_ia, "diccionariobiog00vieigoog",   "vieira_musicos_portuguezes"),
    ("Fétis Vol. 1 (FR)", download_gallica, "bpt6k54394200",       "fetis_biographie_vol1"),
    ("Desrat (FR)",     download_gallica, "bpt6k834353",           "desrat_danse"),
    ("Brockhaus (RU)",  scrape_brockhaus_music, "RU_BROCKHAUS"),
]


def main():
    os.chdir(ROOT)
    results = {}
    for entry in SOURCES:
        label = entry[0]
        fn    = entry[1]
        args  = entry[2:]
        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")
        ok = fn(*args)
        results[label] = "✓" if ok else "✗"

    print("\n\n=== DOWNLOAD SUMMARY ===")
    for label, status in results.items():
        print(f"  {status}  {label}")


if __name__ == "__main__":
    main()
