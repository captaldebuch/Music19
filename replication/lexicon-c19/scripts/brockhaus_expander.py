"""
Brockhaus-Efron Wikisource expander.

Fetches targeted performance-relevant articles from the Russian Wikisource
edition of the Entsiklopedichesky Slovar Brokgauza i Efrona (ESBE).

URL pattern: https://ru.wikisource.org/wiki/ЭСБЕ/<Headword>

Articles are appended to data_ocr/RU_BROCKHAUS/brockhaus_expanded.txt
in the same === TITLE === format used by the existing brockhaus_music_articles.txt.

Already in brockhaus_music_articles.txt (69 articles) — these are skipped.
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://ru.wikisource.org/wiki/ЭСБЕ/"
OUTPUT_DIR = "data_ocr/RU_BROCKHAUS"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "brockhaus_expanded.txt")

# Articles already scraped — skip to avoid duplicates
ALREADY_HAVE = {
    "Музыка", "Опера", "Симфония", "Скрипка", "Орган (инструмент)", "Оркестр",
    "Контрапункт", "Гармония (музыка)", "Ария", "Соната", "Балет",
    "Романс (музыка)", "Певец", "Сопрано", "Тенор", "Бас (голос)", "Баритон",
    "Контральто", "Флейта", "Гобой", "Кларнет", "Фагот", "Валторна",
    "Труба (инструмент)", "Тромбон", "Фортепиано", "Клавесин", "Арфа", "Лютня",
    "Виолончель", "Альт (инструмент)", "Контрабас", "Барабан", "Литавры",
    "Колокол", "Трубадур", "Менестрель", "Бард", "Жонглёр", "Скоморох",
    "Полифония", "Монодия", "Григорианское пение", "Мотет", "Мадригал",
    "Месса", "Кантата", "Оратория", "Литургия", "Гимн",
    "Вальс", "Полька", "Мазурка", "Контрданс", "Гавот", "Менуэт",
    "Глинка Михаил Иванович", "Мусоргский Модест Петрович",
    "Чайковский Пётр Ильич", "Римский-Корсаков Николай Андреевич",
    "Бетховен Людвиг ван", "Моцарт Вольфганг Амадей", "Бах Иоганн Себастьян",
    "Шуберт Франц", "Шопен Фредерик", "Лист Ференц", "Гендель Георг Фридрих",
    "Вагнер Рихард", "Верди Джузеппе",
}

# Comprehensive target list organised by category
TARGET_ARTICLES = {

    # ── INSTRUMENTS ──────────────────────────────────────────────────────────
    "instruments": [
        "Гитара",           # guitar
        "Мандолина",        # mandolin
        "Балалайка",        # balalaika
        "Гусли",            # gusli (Russian zither)
        "Домра",            # domra
        "Гармоника",        # accordion / harmonica
        "Цитра",            # zither
        "Тамбурин",         # tambourine
        "Кастаньеты",       # castanets
        "Волынка",          # bagpipe
        "Корнет",           # cornet
        "Туба",             # tuba
        "Серпент",          # serpent
        "Пикколо",          # piccolo
        "Ксилофон",         # xylophone
        "Цимбалы",          # cymbals
        "Виолончель",       # already have, skip OK
        "Мандора",          # mandore
        "Теорба",           # theorbo
        "Клавикорд",        # clavichord
        "Фисгармония",      # harmonium
        "Спинет",           # spinet
        "Рожок",            # horn (folk)
        "Свирель",          # pipe/fife (folk)
        "Гудок",            # gudok (Russian folk fiddle)
        "Колёсная лира",    # hurdy-gurdy
        "Варган",           # jaw harp
        "Тромпет",          # trumpet (alt form)
        "Флейта-пикколо",   # piccolo flute
        "Английский рожок", # cor anglais
    ],

    # ── PERFORMANCE CONTEXTS ──────────────────────────────────────────────────
    "performance": [
        "Концерт",              # concert
        "Камерная музыка",      # chamber music
        "Хор",                  # choir
        "Капелла",              # chapel / a cappella
        "Капельмейстер",        # Kapellmeister
        "Дирижёр",              # conductor
        "Виртуоз",              # virtuoso
        "Импровизация",         # improvisation
        "Каденция",             # cadenza
        "Речитатив",            # recitative
        "Квартет",              # quartet
        "Квинтет",              # quintet
        "Трио",                 # trio
        "Дуэт",                 # duet
        "Ансамбль",             # ensemble
        "Интермедия",           # interlude / intermezzo
        "Пастораль",            # pastoral
        "Серенада",             # serenade
        "Дивертисмент",         # divertimento
        "Консерватория",        # conservatory
        "Театр",                # theatre
        "Опера-буффа",          # opera buffa
        "Опера-сериа",          # opera seria
        "Опера-комик",          # opéra comique
        "Зингшпиль",            # Singspiel
        "Водевиль",             # vaudeville
        "Мистерия (театр)",     # mystery play
        "Регент (музыка)",      # choirmaster (church)
        "Солист",               # soloist
        "Аккомпанемент",        # accompaniment
    ],

    # ── VOICE / PERFORMERS ────────────────────────────────────────────────────
    "voice": [
        "Меццо-сопрано",    # mezzo-soprano
        "Кастрат",          # castrato
        "Примадонна",       # prima donna
        "Тенор-буффо",      # tenor buffo
        "Бас-баритон",      # bass-baritone
        "Хормейстер",       # choirmaster
        "Певица",           # female singer
        "Вокализ",          # vocalise
        "Колоратура",       # coloratura
        "Фальцет",          # falsetto
        "Вибрато",          # vibrato
        "Legato",           # legato
        "Стаккато",         # staccato
    ],

    # ── DANCE ──────────────────────────────────────────────────────────────────
    "dance": [
        "Полонез",          # polonaise
        "Кадриль",          # quadrille
        "Тарантелла",       # tarantella
        "Болеро",           # bolero
        "Жига",             # gigue
        "Сарабанда",        # sarabande
        "Аллеманда",        # allemande
        "Куранта",          # courante
        "Краковяк",         # krakowiak
        "Экосез",           # écossaise
        "Котильон",         # cotillion
        "Мазур",            # mazur
        "Чардаш",           # csárdás
        "Кекуок",           # cakewalk
        "Вальс-бостон",     # boston waltz
        "Пляска",           # folk dance (general)
        "Хоровод",          # round dance
        "Трепак",           # trepak (Russian dance)
        "Камаринская",      # kamarinskaya
        "Русская пляска",   # Russian dance
    ],

    # ── MUSICAL FORMS & THEORY ────────────────────────────────────────────────
    "forms_theory": [
        "Фуга",             # fugue
        "Увертюра",         # overture
        "Прелюдия",         # prelude
        "Этюд",             # etude
        "Ноктюрн",          # nocturne
        "Баллада",          # ballade
        "Марш",             # march
        "Скерцо",           # scherzo
        "Рапсодия",         # rhapsody
        "Сюита",            # suite
        "Вариации",         # variations
        "Интермеццо",       # intermezzo
        "Хорал",            # chorale
        "Инвенция",         # invention
        "Токката",          # toccata
        "Фантазия",         # fantasy / fantasia
        "Каприччо",         # capriccio
        "Концерт (форма)",  # concerto (musical form)
        "Ритурнель",        # ritornello
        "Речитатив",        # recitative (form)
        "Ария (форма)",     # aria (form)
        "Тема (музыка)",    # theme
        "Контрданс (форма)",# contredanse form
        "Мотив (музыка)",   # motif
        "Лейтмотив",        # leitmotif
        "Ритм",             # rhythm
        "Мелодия",          # melody
        "Тональность",      # tonality
        "Тембр",            # timbre
        "Аккорд",           # chord
        "Интервал (музыка)",# musical interval
        "Такт",             # measure / bar
        "Темп",             # tempo
        "Нотация",          # notation
        "Ноты",             # musical notes / score
        "Партитура",        # score
        "Клавир",           # keyboard score / clavier
    ],

    # ── SACRED / CHURCH MUSIC ─────────────────────────────────────────────────
    "sacred": [
        "Псалом",           # psalm
        "Антифон",          # antiphon
        "Реквием",          # requiem
        "Вечерня",          # vespers
        "Утреня",           # matins
        "Тропарь",          # troparion
        "Кондак",           # kontakion
        "Ирмос",            # heirmos
        "Стихира",          # sticheron
        "Акафист",          # akathist
        "Духовная музыка",  # sacred music
        "Знаменный распев", # znamenny chant
        "Партесное пение",  # partesnoe singing
        "Кант (музыка)",    # kant (Russian polyphonic song)
    ],

    # ── RUSSIAN BIOGRAPHICAL ──────────────────────────────────────────────────
    "biog_russian": [
        "Рубинштейн Антон Григорьевич",     # Anton Rubinstein
        "Бородин Александр Порфирьевич",    # Borodin
        "Балакирев Милий Алексеевич",       # Balakirev
        "Серов Александр Николаевич",       # Serov
        "Кюи Цезарь Антонович",             # Cui
        "Даргомыжский Александр Сергеевич", # Dargomyzhsky
        "Варламов Александр Егорович",      # Varlamov
        "Гурилёв Александр Львович",        # Gurilev
        "Стасов Владимир Васильевич",       # Stasov (critic)
        "Вьётан Анри",                       # Vieuxtemps
        "Рубинштейн Николай Григорьевич",   # Nikolai Rubinstein
        "Направник Эдуард Францевич",       # Napravnik
        "Аренский Антон Степанович",        # Arensky
        "Лядов Анатолий Константинович",    # Lyadov
        "Танеев Сергей Иванович",           # Taneyev
    ],

    # ── WESTERN BIOGRAPHICAL ──────────────────────────────────────────────────
    "biog_western": [
        "Гайдн Йозеф",          # Haydn
        "Гендель",              # Handel (alt)
        "Рамо Жан-Филипп",      # Rameau
        "Люлли Жан-Батист",     # Lully
        "Берлиоз Гектор",       # Berlioz
        "Мендельсон Феликс",    # Mendelssohn
        "Шуман Роберт",         # Schumann
        "Россини Джоакино",     # Rossini
        "Доницетти Гаэтано",    # Donizetti
        "Беллини Винченцо",     # Bellini
        "Мейербер Джакомо",     # Meyerbeer
        "Гуно Шарль",           # Gounod
        "Бизе Жорж",            # Bizet
        "Оффенбах Жак",         # Offenbach
        "Обер Даниэль",         # Auber
        "Глюк Кристоф Виллибальд", # Gluck
        "Монтеверди Клаудио",   # Monteverdi
        "Палестрина",           # Palestrina
        "Паганини Никколо",     # Paganini
        "Тартини Джузеппе",     # Tartini
        "Корелли Арканджело",   # Corelli
        "Вивальди Антонио",     # Vivaldi
        "Перголези Джованни Баттиста", # Pergolesi
        "Скарлатти Доменико",   # D. Scarlatti
        "Куперен Франсуа",      # Couperin
    ],

    # ── RUSSIAN-SPECIFIC CULTURE ──────────────────────────────────────────────
    "russian_culture": [
        "Гусляр",               # gusli player
        "Калики",               # wandering religious singers
        "Колядки",              # kolyadki (Christmas songs)
        "Частушка",             # chastushka
        "Городской романс",     # urban romance
        "Русский романс",       # Russian romance genre
        "Церковное пение",      # church singing
        "Крепостные театры",    # serf theatres
        "Русская опера",        # Russian opera
        "Императорские театры", # Imperial theatres
    ],
}


def clean_wikisource_text(html_text: str) -> str:
    """Extract and clean article body text from Wikisource HTML."""
    soup = BeautifulSoup(html_text, "html.parser")
    content = soup.find(id="mw-content-text")
    if not content:
        return ""

    # Remove navigation boxes, tables, references, edit links
    for tag in content.find_all(["table", "sup", "span", "div"],
                                  class_=re.compile(r"(navbox|reflist|mw-editsection|sister|noprint)")):
        tag.decompose()
    for tag in content.find_all("div", class_=re.compile(r"(thumbcaption|thumb|toc)")):
        tag.decompose()

    raw = content.get_text(separator="\n", strip=True)

    # Strip Wikisource navigation lines (← Prev Article → Next)
    lines = []
    nav_patterns = re.compile(
        r"^(←|→|Словник|Источник|скан|Даты|Энциклопедии|на других языках|"
        r"внешние ссылки|Википроекты|Эта страница|Категория|"
        r"MKL|Britannica|ЕЭБЕ|МСР|МЭСБЕ|ТСД|БСЭ|Den Store|"
        r"Visuotin|Store norske|Encyclop|Большая рос)"
    )
    for line in raw.split("\n"):
        line = line.strip()
        if not line or nav_patterns.match(line):
            continue
        # Skip very short navigation-looking lines
        if len(line) < 4 and line not in ("I", "II", "III"):
            continue
        lines.append(line)

    return "\n".join(lines)


def fetch_article(title: str, session: requests.Session) -> str:
    """Fetch one ESBE article; return cleaned text or '' if not found/too short."""
    url = BASE_URL + requests.utils.quote(title)
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 404:
            return ""
        if resp.status_code != 200:
            return ""
        text = clean_wikisource_text(resp.text)
        # Require at least 150 chars of actual content (filters redirects/stubs)
        if len(text) < 150:
            return ""
        return text
    except Exception as e:
        print(f"  ERROR fetching {title}: {e}")
        return ""


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": "LexiconC19-research/1.0 (academic; musicology)"})

    results = []
    skipped = 0
    not_found = 0
    fetched = 0

    all_targets = []
    for category, titles in TARGET_ARTICLES.items():
        for t in titles:
            all_targets.append((category, t))

    print(f"Fetching {len(all_targets)} candidate articles from ru.wikisource.org/ЭСБЕ …\n")

    for category, title in all_targets:
        if title in ALREADY_HAVE:
            skipped += 1
            continue

        print(f"  [{category}] {title} …", end=" ", flush=True)
        text = fetch_article(title, session)

        if text:
            results.append(f"=== {title} ===\n{text}\n")
            fetched += 1
            print(f"OK ({len(text)} chars)")
        else:
            not_found += 1
            print("not found / too short")

        time.sleep(0.4)  # polite rate

    print(f"\n─── Done: {fetched} fetched, {not_found} not found, {skipped} skipped ───")

    if results:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(results))
        print(f"Saved {fetched} articles → {OUTPUT_FILE}")
    else:
        print("No new articles retrieved.")


if __name__ == "__main__":
    main()
