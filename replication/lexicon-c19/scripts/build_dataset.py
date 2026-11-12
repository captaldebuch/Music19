"""
build_dataset.py — Improved extraction pipeline for the Lexicon of Performance project.

Generates:
  datasets/master_performance_dataset_v3_2.csv — version 3.2 release output
  datasets/multilingual_lexicon.csv            — cross-language concept alignments
  datasets/semantic_relations.csv             — headword co-occurrence / relation network
  datasets/quality_report_v3_2.md   — build quality statistics
"""

import os
import re
import csv
import json
import hashlib
from collections import defaultdict, Counter

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)

def _is_noise(text: str) -> bool:
    """Return True if text looks like OCR noise."""
    if re.fullmatch(r"\s*\d+\s*", text):
        return True
    if re.fullmatch(r"[A-Z\s]{1,3}", text):
        return True
    # camel-noise: alternating lower/upper like 'aBcDeF'
    if re.search(r"(?:[a-z][A-Z]){3,}", text):
        return True
    return False

NOISE_PATTERNS = None  # kept for compatibility

GEO_KEYWORDS = re.compile(
    r"""
    \b(
        France|French|Paris|Germany|German|Berlin|Italy|Italian|Rome|Venice|Florence|
        Spain|Spanish|Madrid|England|English|London|Russia|Russian|Moscow|
        Netherlands|Dutch|Amsterdam|Austria|Vienna|Portugal|Lisbon|Poland|Warsaw|
        Bohemia|Prague|Hungary|Budapest|Flanders|Bruges|Ghent|Bavaria|
        Iberia|Byzantine|Ottoman|Arabic|Persian|Oriental|Eastern|Northern|
        Southern|Western|European|Mediterranean|Moorish|Mooré|
        # French-language geo terms
        Italie|Allemagne|Espagne|Angleterre|Russie|Autriche|Vienne|
        Venise|Florence|Naples|Lyon|Versailles|Bordeaux|Strasbourg|
        # Spanish-language geo terms
        Francia|Alemania|Inglaterra|Rusia|Italia|Venecia|Florencia|Nápoles|
        Sevilla|Barcelona|Lisboa|Oporto|
        # Portuguese-language geo terms
        Itália|Alemanha|Espanha|Inglaterra|França|Rússia|
        # German-language geo terms (Meyers)
        Frankreich|Deutschland|Italien|England|Russland|Österreich|
        Wien|Venedig|Florenz|Neapel|Mailand|München|Leipzig|Dresden|
        Hamburg|Köln|Frankfurt|Stuttgart|Prag|Budapest|Warschau|
        # Russian geo terms (transliterated in text)
        Франция|Германия|Италия|Англия|Австрия|Вена|Венеция|
        Москва|Петербург|Санкт-Петербург
    )\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

PERIOD_KEYWORDS = re.compile(
    r"""
    \b(
        medieval|middle\s+ages?|ancient|classical|renaissance|baroque|
        \d{3,4}th\s+century|\d{3,4}s|\b1[0-9]{3}\b|\b[5-9][0-9]{2}\b|
        # French period terms
        moyen[-\s]?âge|antiquité|siècle|époque|classique|romantique|
        # Spanish period terms
        edad\s+media|antigüedad|siglo|época|clásico|romántico|
        # Russian period terms
        средневековье|античность|век|эпоха
    )\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

ETYMOLOGY_PATTERN = re.compile(
    r"""
    \b(
        from\s+(?:the\s+)?(?:Latin|Greek|French|Italian|German|Arabic|Spanish|
                            Old\s+\w+|Middle\s+\w+)\b[^.;]{0,80}
        | (?:Lat\.|Gr\.|Fr\.|It\.|Ger\.) [A-Z][a-zA-Z\s]{3,40}
        | derived?\s+from\s+\w[^.;]{0,60}
        | origin\w*\s+(?:from|in)\s+[^.;]{0,60}
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

CROSS_REF_PATTERN = re.compile(r"\bsee\b[^.;]{0,60}", re.IGNORECASE)

# Performance ontology keywords → (category, subcategory)
ONTOLOGY = {
    # Instruments
    "organ": ("INSTRUMENTS", "KEYBOARD"),
    "piano": ("INSTRUMENTS", "KEYBOARD"),
    "harpsichord": ("INSTRUMENTS", "KEYBOARD"),
    "clavichord": ("INSTRUMENTS", "KEYBOARD"),
    "cembalo": ("INSTRUMENTS", "KEYBOARD"),
    "virginal": ("INSTRUMENTS", "KEYBOARD"),
    "viol": ("INSTRUMENTS", "STRINGS"),
    "violin": ("INSTRUMENTS", "STRINGS"),
    "viola": ("INSTRUMENTS", "STRINGS"),
    "cello": ("INSTRUMENTS", "STRINGS"),
    "violoncello": ("INSTRUMENTS", "STRINGS"),
    "bass viol": ("INSTRUMENTS", "STRINGS"),
    "rebec": ("INSTRUMENTS", "STRINGS"),
    "rebab": ("INSTRUMENTS", "STRINGS"),
    "lute": ("INSTRUMENTS", "STRINGS"),
    "gittern": ("INSTRUMENTS", "STRINGS"),
    "cittern": ("INSTRUMENTS", "STRINGS"),
    "citole": ("INSTRUMENTS", "STRINGS"),
    "theorbo": ("INSTRUMENTS", "STRINGS"),
    "guitar": ("INSTRUMENTS", "STRINGS"),
    "harp": ("INSTRUMENTS", "STRINGS"),
    "psaltery": ("INSTRUMENTS", "STRINGS"),
    "dulcimer": ("INSTRUMENTS", "STRINGS"),
    "hurdy-gurdy": ("INSTRUMENTS", "STRINGS"),
    "vielle": ("INSTRUMENTS", "STRINGS"),
    "fiddle": ("INSTRUMENTS", "STRINGS"),
    "flute": ("INSTRUMENTS", "WINDS"),
    "oboe": ("INSTRUMENTS", "WINDS"),
    "clarinet": ("INSTRUMENTS", "WINDS"),
    "bassoon": ("INSTRUMENTS", "WINDS"),
    "trumpet": ("INSTRUMENTS", "WINDS"),
    "horn": ("INSTRUMENTS", "WINDS"),
    "trombone": ("INSTRUMENTS", "WINDS"),
    "bagpipe": ("INSTRUMENTS", "WINDS"),
    "chalumeau": ("INSTRUMENTS", "WINDS"),
    "cornet": ("INSTRUMENTS", "WINDS"),
    "flageolet": ("INSTRUMENTS", "WINDS"),
    "recorder": ("INSTRUMENTS", "WINDS"),
    "drum": ("INSTRUMENTS", "PERCUSSION"),
    "tabor": ("INSTRUMENTS", "PERCUSSION"),
    "tambourine": ("INSTRUMENTS", "PERCUSSION"),
    "bells": ("INSTRUMENTS", "PERCUSSION"),
    "cymbal": ("INSTRUMENTS", "PERCUSSION"),
    "kettledrum": ("INSTRUMENTS", "PERCUSSION"),
    "tympani": ("INSTRUMENTS", "PERCUSSION"),
    # Vocal/Voice
    "singer": ("VOICE", "PERFORMER"),
    "soprano": ("VOICE", "VOICE_TYPE"),
    "alto": ("VOICE", "VOICE_TYPE"),
    "tenor": ("VOICE", "VOICE_TYPE"),
    "bass": ("VOICE", "VOICE_TYPE"),
    "contralto": ("VOICE", "VOICE_TYPE"),
    "mezzo": ("VOICE", "VOICE_TYPE"),
    "baritone": ("VOICE", "VOICE_TYPE"),
    "castrato": ("VOICE", "PERFORMER"),
    "prima donna": ("VOICE", "PERFORMER"),
    "cantor": ("VOICE", "PERFORMER"),
    "chantre": ("VOICE", "PERFORMER"),
    "troubadour": ("VOICE", "PERFORMER"),
    "trouvere": ("VOICE", "PERFORMER"),
    "minstrel": ("VOICE", "PERFORMER"),
    "bard": ("VOICE", "PERFORMER"),
    "minnesinger": ("VOICE", "PERFORMER"),
    "meistersinger": ("VOICE", "PERFORMER"),
    "jongleur": ("VOICE", "PERFORMER"),
    "choir": ("VOICE", "ENSEMBLE"),
    "chorus": ("VOICE", "ENSEMBLE"),
    "chant": ("VOICE", "GENRE"),
    "plainsong": ("VOICE", "GENRE"),
    "aria": ("VOICE", "GENRE"),
    "song": ("VOICE", "GENRE"),
    "motet": ("VOICE", "GENRE"),
    "madrigal": ("VOICE", "GENRE"),
    "lied": ("VOICE", "GENRE"),
    "cantata": ("VOICE", "GENRE"),
    # Music concepts
    "harmony": ("MUSIC_CONCEPTS", "THEORY"),
    "counterpoint": ("MUSIC_CONCEPTS", "THEORY"),
    "melody": ("MUSIC_CONCEPTS", "THEORY"),
    "rhythm": ("MUSIC_CONCEPTS", "THEORY"),
    "interval": ("MUSIC_CONCEPTS", "THEORY"),
    "scale": ("MUSIC_CONCEPTS", "THEORY"),
    "mode": ("MUSIC_CONCEPTS", "THEORY"),
    "tonality": ("MUSIC_CONCEPTS", "THEORY"),
    "polyphony": ("MUSIC_CONCEPTS", "THEORY"),
    "fugue": ("MUSIC_CONCEPTS", "FORM"),
    "sonata": ("MUSIC_CONCEPTS", "FORM"),
    "concerto": ("MUSIC_CONCEPTS", "FORM"),
    "symphony": ("MUSIC_CONCEPTS", "FORM"),
    "overture": ("MUSIC_CONCEPTS", "FORM"),
    "composition": ("MUSIC_CONCEPTS", "PRACTICE"),
    "expression": ("MUSIC_CONCEPTS", "PRACTICE"),
    "tempo": ("MUSIC_CONCEPTS", "PERFORMANCE_DIRECTION"),
    "dynamics": ("MUSIC_CONCEPTS", "PERFORMANCE_DIRECTION"),
    "notation": ("MUSIC_CONCEPTS", "NOTATION"),
    # Dance
    "ballet": ("DANCE", "THEATRICAL"),
    "gavotte": ("DANCE", "COURTLY"),
    "minuet": ("DANCE", "COURTLY"),
    "sarabande": ("DANCE", "COURTLY"),
    "bourrée": ("DANCE", "COURTLY"),
    "waltz": ("DANCE", "POPULAR"),
    "polka": ("DANCE", "POPULAR"),
    "quadrille": ("DANCE", "POPULAR"),
    "rondo": ("DANCE", "POPULAR"),
    "rondeau": ("DANCE", "POPULAR"),
    "saltarello": ("DANCE", "FOLK"),
    "tarantella": ("DANCE", "FOLK"),
    "branle": ("DANCE", "FOLK"),
    "estampie": ("DANCE", "MEDIEVAL"),
    "carole": ("DANCE", "MEDIEVAL"),
    # Performance contexts
    "opera": ("PERFORMANCE", "THEATRICAL"),
    "theatre": ("PERFORMANCE", "THEATRICAL"),
    "theater": ("PERFORMANCE", "THEATRICAL"),
    "drama": ("PERFORMANCE", "THEATRICAL"),
    "concert": ("PERFORMANCE", "CONCERT"),
    "recital": ("PERFORMANCE", "CONCERT"),
    "chapel": ("PERFORMANCE", "SACRED"),
    "liturgy": ("PERFORMANCE", "SACRED"),
    "mass": ("PERFORMANCE", "SACRED"),
    "vespers": ("PERFORMANCE", "SACRED"),
    "court": ("PERFORMANCE", "COURTLY"),
    "festival": ("PERFORMANCE", "PUBLIC"),
    "procession": ("PERFORMANCE", "PUBLIC"),
    "ceremony": ("PERFORMANCE", "RITUAL"),
    "ritual": ("PERFORMANCE", "RITUAL"),
    # Acoustics / Sound
    "acoustics": ("SOUND", "PHYSICS"),
    "resonance": ("SOUND", "PHYSICS"),
    "echo": ("SOUND", "PHENOMENON"),
    "timbre": ("SOUND", "QUALITY"),
    "pitch": ("SOUND", "QUALITY"),
    "tone": ("SOUND", "QUALITY"),

    # ── French terms (Fétis, Desrat, Castil-Blaze) ────────────────────────────
    # Instruments
    "orgue": ("INSTRUMENTS", "KEYBOARD"),
    "clavecin": ("INSTRUMENTS", "KEYBOARD"),
    "clavicorde": ("INSTRUMENTS", "KEYBOARD"),
    "pianoforte": ("INSTRUMENTS", "KEYBOARD"),
    "violon": ("INSTRUMENTS", "STRINGS"),
    "viole": ("INSTRUMENTS", "STRINGS"),
    "violoncelle": ("INSTRUMENTS", "STRINGS"),
    "contrebasse": ("INSTRUMENTS", "STRINGS"),
    "luth": ("INSTRUMENTS", "STRINGS"),
    "harpe": ("INSTRUMENTS", "STRINGS"),
    "guitare": ("INSTRUMENTS", "STRINGS"),
    "flûte": ("INSTRUMENTS", "WINDS"),
    "hautbois": ("INSTRUMENTS", "WINDS"),
    "clarinette": ("INSTRUMENTS", "WINDS"),
    "basson": ("INSTRUMENTS", "WINDS"),
    "cor": ("INSTRUMENTS", "WINDS"),
    "trompette": ("INSTRUMENTS", "WINDS"),
    "trombone": ("INSTRUMENTS", "WINDS"),
    "cornemuse": ("INSTRUMENTS", "WINDS"),
    "tambour": ("INSTRUMENTS", "PERCUSSION"),
    "timbale": ("INSTRUMENTS", "PERCUSSION"),
    "cloche": ("INSTRUMENTS", "PERCUSSION"),
    "cymbale": ("INSTRUMENTS", "PERCUSSION"),
    # Voice / Performers
    "chanteur": ("VOICE", "PERFORMER"),
    "chanteuse": ("VOICE", "PERFORMER"),
    "soprano": ("VOICE", "VOICE_TYPE"),
    "ténor": ("VOICE", "VOICE_TYPE"),
    "basse": ("VOICE", "VOICE_TYPE"),
    "contralto": ("VOICE", "VOICE_TYPE"),
    "mezzo-soprano": ("VOICE", "VOICE_TYPE"),
    "troubadour": ("VOICE", "PERFORMER"),
    "trouvère": ("VOICE", "PERFORMER"),
    "ménestrel": ("VOICE", "PERFORMER"),
    "chantre": ("VOICE", "PERFORMER"),
    "choeur": ("VOICE", "ENSEMBLE"),
    "chœur": ("VOICE", "ENSEMBLE"),
    "chorale": ("VOICE", "ENSEMBLE"),
    "chant": ("VOICE", "GENRE"),
    "chanson": ("VOICE", "GENRE"),
    "mélodie": ("VOICE", "GENRE"),
    "romance": ("VOICE", "GENRE"),
    "cantate": ("VOICE", "GENRE"),
    "motet": ("VOICE", "GENRE"),
    "madrigal": ("VOICE", "GENRE"),
    # Dance (Desrat vocabulary)
    "ballet": ("DANCE", "THEATRICAL"),
    "danse": ("DANCE", "POPULAR"),
    "ballerine": ("DANCE", "THEATRICAL"),
    "chorégraphie": ("DANCE", "THEATRICAL"),
    "quadrille": ("DANCE", "POPULAR"),
    "contredanse": ("DANCE", "POPULAR"),
    "valse": ("DANCE", "POPULAR"),
    "polka": ("DANCE", "POPULAR"),
    "mazurka": ("DANCE", "POPULAR"),
    "gavotte": ("DANCE", "COURTLY"),
    "menuet": ("DANCE", "COURTLY"),
    "sarabande": ("DANCE", "COURTLY"),
    "bourrée": ("DANCE", "COURTLY"),
    "branle": ("DANCE", "FOLK"),
    "farandole": ("DANCE", "FOLK"),
    "gigue": ("DANCE", "FOLK"),
    "tarentelle": ("DANCE", "FOLK"),
    # Performance contexts
    "opéra": ("PERFORMANCE", "THEATRICAL"),
    "théâtre": ("PERFORMANCE", "THEATRICAL"),
    "concert": ("PERFORMANCE", "CONCERT"),
    "récital": ("PERFORMANCE", "CONCERT"),
    "chapelle": ("PERFORMANCE", "SACRED"),
    "liturgie": ("PERFORMANCE", "SACRED"),
    "messe": ("PERFORMANCE", "SACRED"),
    "vêpres": ("PERFORMANCE", "SACRED"),
    "cour": ("PERFORMANCE", "COURTLY"),
    "fête": ("PERFORMANCE", "PUBLIC"),
    "procession": ("PERFORMANCE", "PUBLIC"),
    # Music theory
    "harmonie": ("MUSIC_CONCEPTS", "THEORY"),
    "contrepoint": ("MUSIC_CONCEPTS", "THEORY"),
    "mélodie": ("MUSIC_CONCEPTS", "THEORY"),
    "rythme": ("MUSIC_CONCEPTS", "THEORY"),
    "gamme": ("MUSIC_CONCEPTS", "THEORY"),
    "mode": ("MUSIC_CONCEPTS", "THEORY"),
    "tonalité": ("MUSIC_CONCEPTS", "THEORY"),
    "polyphonie": ("MUSIC_CONCEPTS", "THEORY"),
    "fugue": ("MUSIC_CONCEPTS", "FORM"),
    "sonate": ("MUSIC_CONCEPTS", "FORM"),
    "symphonie": ("MUSIC_CONCEPTS", "FORM"),
    "concerto": ("MUSIC_CONCEPTS", "FORM"),
    "ouverture": ("MUSIC_CONCEPTS", "FORM"),
    "tempo": ("MUSIC_CONCEPTS", "PERFORMANCE_DIRECTION"),
    "nuance": ("MUSIC_CONCEPTS", "PERFORMANCE_DIRECTION"),

    # ── Spanish terms (Pedrell) ───────────────────────────────────────────────
    "órgano": ("INSTRUMENTS", "KEYBOARD"),
    "clavicémbalo": ("INSTRUMENTS", "KEYBOARD"),
    "violín": ("INSTRUMENTS", "STRINGS"),
    "viola": ("INSTRUMENTS", "STRINGS"),
    "violonchelo": ("INSTRUMENTS", "STRINGS"),
    "contrabajo": ("INSTRUMENTS", "STRINGS"),
    "arpa": ("INSTRUMENTS", "STRINGS"),
    "guitarra": ("INSTRUMENTS", "STRINGS"),
    "laúd": ("INSTRUMENTS", "STRINGS"),
    "flauta": ("INSTRUMENTS", "WINDS"),
    "oboe": ("INSTRUMENTS", "WINDS"),
    "clarinete": ("INSTRUMENTS", "WINDS"),
    "fagot": ("INSTRUMENTS", "WINDS"),
    "trompa": ("INSTRUMENTS", "WINDS"),
    "trompeta": ("INSTRUMENTS", "WINDS"),
    "gaita": ("INSTRUMENTS", "WINDS"),
    "tambor": ("INSTRUMENTS", "PERCUSSION"),
    "timbal": ("INSTRUMENTS", "PERCUSSION"),
    "campana": ("INSTRUMENTS", "PERCUSSION"),
    "cantante": ("VOICE", "PERFORMER"),
    "soprano": ("VOICE", "VOICE_TYPE"),
    "tenor": ("VOICE", "VOICE_TYPE"),
    "bajo": ("VOICE", "VOICE_TYPE"),
    "barítono": ("VOICE", "VOICE_TYPE"),
    "juglar": ("VOICE", "PERFORMER"),
    "trovador": ("VOICE", "PERFORMER"),
    "coro": ("VOICE", "ENSEMBLE"),
    "canto": ("VOICE", "GENRE"),
    "canción": ("VOICE", "GENRE"),
    "zarzuela": ("PERFORMANCE", "THEATRICAL"),
    "ópera": ("PERFORMANCE", "THEATRICAL"),
    "baile": ("DANCE", "POPULAR"),
    "danza": ("DANCE", "POPULAR"),
    "jota": ("DANCE", "FOLK"),
    "fandango": ("DANCE", "FOLK"),
    "seguidilla": ("DANCE", "FOLK"),
    "bolero": ("DANCE", "FOLK"),
    "armonia": ("MUSIC_CONCEPTS", "THEORY"),
    "contrapunto": ("MUSIC_CONCEPTS", "THEORY"),
    "sinfonía": ("MUSIC_CONCEPTS", "FORM"),

    # ── Portuguese terms (Vieira) ─────────────────────────────────────────────
    "órgão": ("INSTRUMENTS", "KEYBOARD"),
    "cravo": ("INSTRUMENTS", "KEYBOARD"),
    "violino": ("INSTRUMENTS", "STRINGS"),
    "violeta": ("INSTRUMENTS", "STRINGS"),
    "violoncelo": ("INSTRUMENTS", "STRINGS"),
    "contrabaixo": ("INSTRUMENTS", "STRINGS"),
    "harpa": ("INSTRUMENTS", "STRINGS"),
    "guitarra": ("INSTRUMENTS", "STRINGS"),
    "alaúde": ("INSTRUMENTS", "STRINGS"),
    "flauta": ("INSTRUMENTS", "WINDS"),
    "oboé": ("INSTRUMENTS", "WINDS"),
    "clarinete": ("INSTRUMENTS", "WINDS"),
    "fagote": ("INSTRUMENTS", "WINDS"),
    "trompa": ("INSTRUMENTS", "WINDS"),
    "trompeta": ("INSTRUMENTS", "WINDS"),
    "cantor": ("VOICE", "PERFORMER"),
    "cantora": ("VOICE", "PERFORMER"),
    "coro": ("VOICE", "ENSEMBLE"),
    "cantata": ("VOICE", "GENRE"),
    "ópera": ("PERFORMANCE", "THEATRICAL"),
    "teatro": ("PERFORMANCE", "THEATRICAL"),
    "dança": ("DANCE", "POPULAR"),
    "fado": ("DANCE", "FOLK"),

    # ── German terms (Meyers Konversations-Lexikon) ──────────────────────────
    "orgel": ("INSTRUMENTS", "KEYBOARD"),
    "klavier": ("INSTRUMENTS", "KEYBOARD"),
    "pianoforte": ("INSTRUMENTS", "KEYBOARD"),
    "klavichord": ("INSTRUMENTS", "KEYBOARD"),
    "cembalo": ("INSTRUMENTS", "KEYBOARD"),
    "spinett": ("INSTRUMENTS", "KEYBOARD"),
    "harmonium": ("INSTRUMENTS", "KEYBOARD"),
    "violine": ("INSTRUMENTS", "STRINGS"),
    "geige": ("INSTRUMENTS", "STRINGS"),
    "bratsche": ("INSTRUMENTS", "STRINGS"),
    "violoncell": ("INSTRUMENTS", "STRINGS"),
    "kontrabass": ("INSTRUMENTS", "STRINGS"),
    "laute": ("INSTRUMENTS", "STRINGS"),
    "theorbe": ("INSTRUMENTS", "STRINGS"),
    "gitarre": ("INSTRUMENTS", "STRINGS"),
    "harfe": ("INSTRUMENTS", "STRINGS"),
    "zither": ("INSTRUMENTS", "STRINGS"),
    "hackbrett": ("INSTRUMENTS", "STRINGS"),
    "flöte": ("INSTRUMENTS", "WINDS"),
    "oboe": ("INSTRUMENTS", "WINDS"),
    "klarinette": ("INSTRUMENTS", "WINDS"),
    "fagott": ("INSTRUMENTS", "WINDS"),
    "trompete": ("INSTRUMENTS", "WINDS"),
    "posaune": ("INSTRUMENTS", "WINDS"),
    "waldhorn": ("INSTRUMENTS", "WINDS"),
    "tuba": ("INSTRUMENTS", "WINDS"),
    "kornett": ("INSTRUMENTS", "WINDS"),
    "sackpfeife": ("INSTRUMENTS", "WINDS"),
    "dudelsack": ("INSTRUMENTS", "WINDS"),
    "flageolet": ("INSTRUMENTS", "WINDS"),
    "trommel": ("INSTRUMENTS", "PERCUSSION"),
    "pauke": ("INSTRUMENTS", "PERCUSSION"),
    "glocke": ("INSTRUMENTS", "PERCUSSION"),
    "becken": ("INSTRUMENTS", "PERCUSSION"),
    "tamburin": ("INSTRUMENTS", "PERCUSSION"),
    "sänger": ("VOICE", "PERFORMER"),
    "sängerin": ("VOICE", "PERFORMER"),
    "kapellmeister": ("VOICE", "PERFORMER"),
    "minnesänger": ("VOICE", "PERFORMER"),
    "meistersinger": ("VOICE", "PERFORMER"),
    "spielmann": ("VOICE", "PERFORMER"),
    "barde": ("VOICE", "PERFORMER"),
    "kantor": ("VOICE", "PERFORMER"),
    "sopran": ("VOICE", "VOICE_TYPE"),
    "bariton": ("VOICE", "VOICE_TYPE"),
    "kastrat": ("VOICE", "PERFORMER"),
    "chor": ("VOICE", "ENSEMBLE"),
    "orchester": ("VOICE", "ENSEMBLE"),
    "lied": ("VOICE", "GENRE"),
    "arie": ("VOICE", "GENRE"),
    "choral": ("VOICE", "GENRE"),
    "ballade": ("VOICE", "GENRE"),
    "volkslied": ("VOICE", "GENRE"),
    "oper": ("PERFORMANCE", "THEATRICAL"),
    "theater": ("PERFORMANCE", "THEATRICAL"),
    "oratorium": ("PERFORMANCE", "THEATRICAL"),
    "festspiel": ("PERFORMANCE", "PUBLIC"),
    "kirchenmusik": ("PERFORMANCE", "SACRED"),
    "messe": ("PERFORMANCE", "SACRED"),
    "motette": ("VOICE", "GENRE"),
    "ballett": ("DANCE", "THEATRICAL"),
    "walzer": ("DANCE", "POPULAR"),
    "polka": ("DANCE", "POPULAR"),
    "mazurka": ("DANCE", "POPULAR"),
    "menuett": ("DANCE", "COURTLY"),
    "gavotte": ("DANCE", "COURTLY"),
    "sarabande": ("DANCE", "COURTLY"),
    "gigue": ("DANCE", "FOLK"),
    "bourrée": ("DANCE", "FOLK"),
    "ländler": ("DANCE", "FOLK"),
    "tanz": ("DANCE", "POPULAR"),
    "harmonie": ("MUSIC_CONCEPTS", "THEORY"),
    "kontrapunkt": ("MUSIC_CONCEPTS", "THEORY"),
    "melodie": ("MUSIC_CONCEPTS", "THEORY"),
    "rhythmus": ("MUSIC_CONCEPTS", "THEORY"),
    "polyphonie": ("MUSIC_CONCEPTS", "THEORY"),
    "tonleiter": ("MUSIC_CONCEPTS", "THEORY"),
    "intervall": ("MUSIC_CONCEPTS", "THEORY"),
    "akkord": ("MUSIC_CONCEPTS", "THEORY"),
    "kadenz": ("MUSIC_CONCEPTS", "THEORY"),
    "notation": ("MUSIC_CONCEPTS", "NOTATION"),
    "sonate": ("MUSIC_CONCEPTS", "FORM"),
    "symphonie": ("MUSIC_CONCEPTS", "FORM"),
    "konzert": ("MUSIC_CONCEPTS", "FORM"),
    "ouvertüre": ("MUSIC_CONCEPTS", "FORM"),
    "fuge": ("MUSIC_CONCEPTS", "FORM"),
    "rondo": ("MUSIC_CONCEPTS", "FORM"),
    "variation": ("MUSIC_CONCEPTS", "FORM"),

    # ── Russian terms (Brockhaus — Cyrillic) ─────────────────────────────────
    "орган": ("INSTRUMENTS", "KEYBOARD"),
    "клавесин": ("INSTRUMENTS", "KEYBOARD"),
    "фортепиано": ("INSTRUMENTS", "KEYBOARD"),
    "скрипка": ("INSTRUMENTS", "STRINGS"),
    "альт": ("INSTRUMENTS", "STRINGS"),
    "виолончель": ("INSTRUMENTS", "STRINGS"),
    "контрабас": ("INSTRUMENTS", "STRINGS"),
    "арфа": ("INSTRUMENTS", "STRINGS"),
    "лютня": ("INSTRUMENTS", "STRINGS"),
    "гитара": ("INSTRUMENTS", "STRINGS"),
    "флейта": ("INSTRUMENTS", "WINDS"),
    "гобой": ("INSTRUMENTS", "WINDS"),
    "кларнет": ("INSTRUMENTS", "WINDS"),
    "фагот": ("INSTRUMENTS", "WINDS"),
    "валторна": ("INSTRUMENTS", "WINDS"),
    "труба": ("INSTRUMENTS", "WINDS"),
    "тромбон": ("INSTRUMENTS", "WINDS"),
    "барабан": ("INSTRUMENTS", "PERCUSSION"),
    "литавры": ("INSTRUMENTS", "PERCUSSION"),
    "колокол": ("INSTRUMENTS", "PERCUSSION"),
    "певец": ("VOICE", "PERFORMER"),
    "певица": ("VOICE", "PERFORMER"),
    "сопрано": ("VOICE", "VOICE_TYPE"),
    "тенор": ("VOICE", "VOICE_TYPE"),
    "бас": ("VOICE", "VOICE_TYPE"),
    "баритон": ("VOICE", "VOICE_TYPE"),
    "контральто": ("VOICE", "VOICE_TYPE"),
    "хор": ("VOICE", "ENSEMBLE"),
    "ария": ("VOICE", "GENRE"),
    "романс": ("VOICE", "GENRE"),
    "песня": ("VOICE", "GENRE"),
    "трубадур": ("VOICE", "PERFORMER"),
    "менестрель": ("VOICE", "PERFORMER"),
    "скоморох": ("VOICE", "PERFORMER"),
    "опера": ("PERFORMANCE", "THEATRICAL"),
    "театр": ("PERFORMANCE", "THEATRICAL"),
    "концерт": ("PERFORMANCE", "CONCERT"),
    "литургия": ("PERFORMANCE", "SACRED"),
    "хоровое пение": ("PERFORMANCE", "SACRED"),
    "балет": ("DANCE", "THEATRICAL"),
    "вальс": ("DANCE", "POPULAR"),
    "полька": ("DANCE", "POPULAR"),
    "мазурка": ("DANCE", "POPULAR"),
    "гармония": ("MUSIC_CONCEPTS", "THEORY"),
    "контрапункт": ("MUSIC_CONCEPTS", "THEORY"),
    "мелодия": ("MUSIC_CONCEPTS", "THEORY"),
    "ритм": ("MUSIC_CONCEPTS", "THEORY"),
    "полифония": ("MUSIC_CONCEPTS", "THEORY"),
    "соната": ("MUSIC_CONCEPTS", "FORM"),
    "симфония": ("MUSIC_CONCEPTS", "FORM"),
    "концерт": ("MUSIC_CONCEPTS", "FORM"),
}

SEMANTIC_TAGS_MAP = {
    "Sacred":       ["church", "mass", "god", "liturgy", "sacred", "holy", "divine",
                     "prayer", "chapel", "monastery", "plainchant", "chant", "vespers",
                     "benedictine", "gregorian", "canticle",
                     # French
                     "église", "messe", "liturgie", "chapelle", "grégorien", "prière",
                     # Spanish
                     "iglesia", "misa", "liturgia", "capilla", "gregoriano",
                     # Portuguese
                     "igreja", "missa", "liturgia", "capela",
                     # German
                     "kirche", "kirchenmusik", "gottesdienst", "gregorianisch",
                     "kloster", "mönch", "geistlich", "sakral", "choral",
                     # Russian
                     "церковь", "литургия", "молитва", "монастырь", "хоровое"],
    "Mournful":     ["sad", "mourn", "dirge", "funeral", "elegy", "weep", "sorrow",
                     "lament", "grief", "tragic",
                     "triste", "deuil", "funèbre", "élégie",       # French
                     "triste", "funeral", "elegía",                 # Spanish
                     "trauermarsch", "traurig", "elegie", "klage",  # German
                     "траурный", "похоронный", "элегия"],           # Russian
    "Folk/Peasant": ["peasant", "folk", "village", "rustic", "rural", "country",
                     "popular", "common", "tavern", "street",
                     "populaire", "paysan", "villageois", "rustique",  # French
                     "popular", "campesino", "aldeano", "rústico",     # Spanish
                     "volkslied", "volksmusik", "volkstanz", "bäuerlich", "dörflich",  # German
                     "народный", "крестьянский", "деревенский"],       # Russian
    "Courtly/Elite":["court", "king", "royal", "noble", "elite", "aristocrat",
                     "palace", "princely", "courtier", "chamber",
                     "cour", "roi", "royal", "noble", "aristocrate", "palais",  # French
                     "corte", "rey", "real", "noble", "aristócrata", "palacio", # Spanish
                     "hof", "hofmusik", "fürstlich", "königlich", "adel",       # German
                     "двор", "царский", "королевский", "аристократ"],           # Russian
    "Festive":      ["festival", "feast", "celebration", "joy", "dance", "merry",
                     "carnival", "procession",
                     "fête", "carnaval", "célébration", "réjouissance",  # French
                     "fiesta", "carnaval", "celebración", "festivo",     # Spanish
                     "fest", "festspiel", "feier", "festlich", "karneval",  # German
                     "праздник", "карнавал", "торжество"],               # Russian
    "Italian":      ["italian", "italy", "venice", "florence", "naples", "rome",
                     "milan", "sicilian", "neapolitan",
                     "italien", "italie", "venise", "florence", "naples",  # French
                     "italiano", "italia", "venecia", "florencia",         # Spanish
                     "italienisch", "venedig", "florenz", "neapel", "rom"],  # German
    "French":       ["french", "france", "paris", "parisian", "versailles",
                     "français", "france", "parisien",                   # French self-ref
                     "francés", "francia",                               # Spanish
                     "französisch", "frankreich", "paris",               # German
                     "французский", "париж"],                            # Russian
    "German":       ["german", "germany", "berlin", "vienna", "austrian",
                     "allemand", "allemagne", "vienne", "autrichien",    # French
                     "alemán", "alemania", "berlín", "viena",            # Spanish
                     "deutsch", "deutschland", "wien", "österreichisch",  # German self-ref
                     "немецкий", "германия", "берлин", "вена"],          # Russian
    "Spanish":      ["spanish", "spain", "madrid", "seville", "castilian",
                     "espagnol", "espagne", "madrid",                    # French
                     "español", "españa",                                # Spanish
                     "spanisch", "spanien", "madrid",                    # German
                     "испанский", "испания"],                            # Russian
    "Russian":      ["russian", "russia", "moscow", "slavic", "orthodox",
                     "russe", "russie", "moscou",                        # French
                     "ruso", "rusia", "moscú",                           # Spanish
                     "russisch", "russland", "moskau", "slawisch",       # German
                     "русский", "россия", "москва", "православный"],    # Russian
    "Ancient/Medieval": ["ancient", "medieval", "middle ages", "greek", "latin",
                         "roman", "byzantin", "troubadour", "minstrel", "bard",
                         "moyen âge", "antique", "grec", "latin",            # French
                         "edad media", "antiguo", "griego", "latino",        # Spanish
                         "mittelalter", "antike", "griechisch", "lateinisch",  # German
                         "средневековый", "античный", "греческий"],          # Russian
}


def ocr_confidence(text: str) -> float:
    """Heuristic OCR confidence (0-1). Lower = noisier."""
    if not text:
        return 0.0
    total = len(text)
    noise = 0
    # Repeated spaces
    noise += len(re.findall(r"  +", text)) * 2
    # Non-Latin/Cyrillic characters that look like OCR artefacts
    noise += len(re.findall(r"[^\x00-\x7FÀ-ɏЀ-ӿ\s]", text))
    # Single capital letter entries
    if re.fullmatch(r"[A-Z\.\s]{1,4}", text.strip()):
        return 0.1
    score = max(0.0, 1.0 - (noise / max(total, 1)) * 3)
    return round(score, 3)


def extract_geography(text: str) -> str:
    matches = GEO_KEYWORDS.findall(text)
    return "; ".join(sorted(set(m.title() for m in matches))) if matches else ""


def extract_periods(text: str) -> str:
    matches = PERIOD_KEYWORDS.findall(text)
    clean = [m.strip() for m in matches if len(m.strip()) > 2]
    return "; ".join(sorted(set(clean[:6]))) if clean else ""


def extract_etymology(text: str) -> str:
    m = ETYMOLOGY_PATTERN.search(text)
    return m.group(0).strip()[:200] if m else ""


def extract_cross_refs(text: str) -> str:
    matches = CROSS_REF_PATTERN.findall(text)
    return "; ".join(m.strip()[:60] for m in matches[:3]) if matches else ""


def semantic_tags(text: str) -> str:
    tl = text.lower()
    tags = [tag for tag, kws in SEMANTIC_TAGS_MAP.items() if any(kw in tl for kw in kws)]
    return "; ".join(tags) if tags else "Neutral"


def categorize(headword: str, definition: str):
    """Return (category, subcategory) from the ontology."""
    text = (headword + " " + definition).lower()
    for term, (cat, sub) in ONTOLOGY.items():
        if re.search(r"\b" + re.escape(term) + r"\b", text):
            return cat, sub
    return "GENERAL", "OTHER"


# ── Per-dictionary parsers ────────────────────────────────────────────────────

GROVE_ENTRY = re.compile(
    r"^([A-Z][A-Z\s\-\'\(\),\.]{1,55})\.\s{2,}(.+)$", re.MULTILINE
)
MOORE_ENTRY = re.compile(
    r"^([A-Z][A-Z\s\-\'\(\),\.]{1,55})[\.,]\s+(.+)$", re.MULTILINE
)
# Riemann is English-translated, mixed case: "Accompaniment (Fr. ...). In pieces..."
RIEMANN_ENTRY = re.compile(
    r"^([A-Z][A-Za-z\s\-\']{2,55})(?:\s*\([^)]{0,80}\))?,\s+(.+)$", re.MULTILINE
)

# Fétis: "NOM (Prénom), dates. Biographical text..." — caps surname, mixed first name
FETIS_ENTRY = re.compile(
    r"^([A-ZÁÀÂÉÈÊÎÔÙÛÜÇŒÆ][A-ZÁÀÂÉÈÊÎÔÙÛÜÇŒÆ\s\-\'\(\),\.]{1,60})[\.,]\s+(.+)$",
    re.MULTILINE,
)

# Desrat: "TERME. Définition..." — all-caps headword + period + 2 spaces or single space
DESRAT_ENTRY = re.compile(
    r"^([A-ZÁÀÂÉÈÊÎÔÙÛÜÇŒÆ][A-ZÁÀÂÉÈÊÎÔÙÛÜÇŒÆ\s\-]{1,50})\.\s+(.+)$",
    re.MULTILINE,
)

# Pedrell (ES): "TÉRMINO. Definición..." — similar to Desrat
PEDRELL_ENTRY = re.compile(
    r"^([A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ\s\-\(\),\.]{1,55})[\.,]\s+(.+)$",
    re.MULTILINE,
)

# Vieira (PT): "SOBRENOME (Firstname), dates. Text..." or "TERMO. Definição..."
VIEIRA_ENTRY = re.compile(
    r"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ\s\-\'\(\),\.]{1,60})[\.,]\s+(.+)$",
    re.MULTILINE,
)

# Meyers Konversations-Lexikon (DE): entries formatted as "=== TITLE ===" by the
# German Wikisource scraper, identical to the Brockhaus article format.
# Inline fallback for raw Archive.org OCR:
#   "Orgel (lat. organum; fr. Orgue), ein Tasteninstrument..."
MEYERS_ARTICLE = re.compile(
    r"===\s*(.+?)\s*===\s*\n([\s\S]+?)(?====|\Z)", re.MULTILINE
)
MEYERS_ENTRY = re.compile(
    r"^([A-ZÁÄÖÜ][A-ZÄÖÜa-zäöüß\s\-\']{2,55})"
    r"(?:\s*\([^)]{0,120}\))?"
    r"[,\.]\s+(.+)$",
    re.MULTILINE,
)

# Russian Brockhaus: articles are already split by "=== TITLE ===" from scraper.
# Each article becomes one entry; we also try to split on capitalised Cyrillic headwords.
BROCKHAUS_ARTICLE = re.compile(
    r"===\s*(.+?)\s*===\s*\n([\s\S]+?)(?====|\Z)", re.MULTILINE
)
# Fallback for inline Cyrillic headwords: "СЛОВО. Определение..."
BROCKHAUS_INLINE = re.compile(
    r"^([А-ЯЁ][А-ЯЁ\s\-]{2,50})\.\s+(.+)$", re.MULTILINE
)

FALLBACK_ENTRY = re.compile(
    r"^([A-Z][A-Z\s\-\'\(\),\.]{2,55})[\.,]\s+(.+)$", re.MULTILINE
)

# Larousse Grand dictionnaire universel du XIXe siècle (FR):
# Articles scraped from fr.wikisource.org via larousse_scraper.py.
# Format: "=== TITRE ===" + article text (same as Meyers/Brockhaus scraper output).
# Inline fallback uses the DESRAT pattern (ALL-CAPS headword + period + definition).
LAROUSSE_ARTICLE = re.compile(
    r"===\s*(.+?)\s*===\s*\n([\s\S]+?)(?====|\Z)", re.MULTILINE
)
LAROUSSE_ENTRY = re.compile(
    r"^([A-ZÁÀÂÉÈÊÎÔÙÛÜÇŒÆ][A-ZÁÀÂÉÈÊÎÔÙÛÜÇŒÆ\s\-]{1,60})\.\s+(.+)$",
    re.MULTILINE,
)

DICT_PARSERS = {
    "EN-GROVE-1879":     GROVE_ENTRY,
    "EN-GROVE-1879-V2":  GROVE_ENTRY,
    "EN-GROVE-1879-V3":  GROVE_ENTRY,
    "EN-GROVE-1879-V4":  GROVE_ENTRY,
    "EN-MOORE-1854":     MOORE_ENTRY,
    "DE-RIEMANN-1882":   RIEMANN_ENTRY,
    "FR-FETIS-1860":     FETIS_ENTRY,
    "FR-DESRAT-1895":    DESRAT_ENTRY,
    "FR-LAROUSSE-1866":  LAROUSSE_ARTICLE,
    "ES-PEDRELL-1894":   PEDRELL_ENTRY,
    "PT-VIEIRA-1900":    VIEIRA_ENTRY,
    "RU-BROCKHAUS":      BROCKHAUS_ARTICLE,
    "DE-MEYERS-1885":    MEYERS_ARTICLE,
}

SKIP_HEADS = {
    "THE", "OF", "AND", "TO", "A", "IN", "THAT", "IS", "WITH", "FOR", "ON",
    "AT", "BY", "FROM", "THIS", "THESE", "THOSE", "ARE", "WAS", "WERE",
    "PREFACE", "APPENDIX", "INDEX", "CONTENTS", "VOLUME", "EDITION", "PAGE",
    "CHAPTER", "PART", "INTRODUCTION",
}


def parse_file(text: str, dict_id: str, inv: dict) -> list:
    inv_item = inv[dict_id]
    entries = []
    seen = set()

    # Meyers Konversations-Lexikon: articles segmented by the Wikisource scraper.
    # Falls back to MEYERS_ENTRY inline regex if no === markers found.
    if dict_id == "DE-MEYERS-1885":
        matches = list(MEYERS_ARTICLE.finditer(text))
        if not matches:
            matches = list(MEYERS_ENTRY.finditer(text))
        for m in matches:
            hw = m.group(1).strip()
            defn = m.group(2).strip()[:800]
            key = (hw.lower(), dict_id)
            if key in seen or len(hw) < 2:
                continue
            seen.add(key)
            conf = ocr_confidence(hw + " " + defn)
            cat, sub = categorize(hw, defn)
            entries.append({
                "id": f"{dict_id}-{len(entries)+1:05d}",
                "language": inv_item["language"],
                "headword": hw,
                "normalized_headword": hw.lower().strip(),
                "category": cat,
                "subcategory": sub,
                "definition": defn,
                "example": "",
                "etymology": extract_etymology(defn),
                "source_dictionary": inv_item["title"],
                "author": inv_item["author"],
                "publication_year": inv_item["year"],
                "volume": inv_item.get("volumes", ""),
                "page": "",
                "source_text": m.group(0)[:300],
                "semantic_tags": semantic_tags(defn),
                "geographic_refs": extract_geography(defn),
                "historical_refs": extract_periods(defn),
                "cross_refs": extract_cross_refs(defn),
                "confidence_score": conf,
                "multilingual_alignment": "",
                "article_type": inv_item.get("article_type", ""),
                "notes": "",
            })
        return entries

    # Russian Brockhaus: articles already segmented by scraper as "=== TITLE ==="
    if dict_id == "RU-BROCKHAUS":
        matches = list(BROCKHAUS_ARTICLE.finditer(text))
        if not matches:
            # Fallback: treat whole file as one article per Cyrillic inline pattern
            matches = list(BROCKHAUS_INLINE.finditer(text))
        for m in matches:
            hw = m.group(1).strip()
            defn = m.group(2).strip()[:800]
            key = (hw.lower(), dict_id)
            if key in seen or len(hw) < 2:
                continue
            seen.add(key)
            conf = ocr_confidence(hw + " " + defn)
            cat, sub = categorize(hw, defn)
            entries.append({
                "id": f"{dict_id}-{len(entries)+1:05d}",
                "language": inv_item["language"],
                "headword": hw,
                "normalized_headword": hw.lower().strip(),
                "category": cat,
                "subcategory": sub,
                "definition": defn,
                "example": "",
                "etymology": extract_etymology(defn),
                "source_dictionary": inv_item["title"],
                "author": inv_item["author"],
                "publication_year": inv_item["year"],
                "volume": inv_item.get("volumes", ""),
                "page": "",
                "source_text": m.group(0)[:300],
                "semantic_tags": semantic_tags(defn),
                "geographic_refs": extract_geography(defn),
                "historical_refs": extract_periods(defn),
                "cross_refs": extract_cross_refs(defn),
                "confidence_score": conf,
                "multilingual_alignment": "",
                "article_type": inv_item.get("article_type", ""),
                "notes": "",
            })
        return entries

    # Larousse: same article-per-=== structure as Meyers/Brockhaus
    if dict_id == "FR-LAROUSSE-1866":
        matches = list(LAROUSSE_ARTICLE.finditer(text))
        if not matches:
            matches = list(LAROUSSE_ENTRY.finditer(text))
        for m in matches:
            hw = m.group(1).strip()
            defn = m.group(2).strip()[:800]
            key = (hw.lower(), dict_id)
            if key in seen or len(hw) < 2:
                continue
            seen.add(key)
            conf = ocr_confidence(hw + " " + defn)
            cat, sub = categorize(hw, defn)
            entries.append({
                "id": f"{dict_id}-{len(entries)+1:05d}",
                "language": inv_item["language"],
                "headword": hw,
                "normalized_headword": hw.lower().strip(),
                "category": cat,
                "subcategory": sub,
                "definition": defn,
                "example": "",
                "etymology": extract_etymology(defn),
                "source_dictionary": inv_item["title"],
                "author": inv_item["author"],
                "publication_year": inv_item["year"],
                "volume": inv_item.get("volumes", ""),
                "page": "",
                "source_text": m.group(0)[:300],
                "semantic_tags": semantic_tags(defn),
                "geographic_refs": extract_geography(defn),
                "historical_refs": extract_periods(defn),
                "cross_refs": extract_cross_refs(defn),
                "confidence_score": conf,
                "multilingual_alignment": "",
                "article_type": inv_item.get("article_type", ""),
                "notes": "",
            })
        return entries

    pattern = DICT_PARSERS.get(dict_id, FALLBACK_ENTRY)

    for m in pattern.finditer(text):
        hw = m.group(1).strip()
        defn = m.group(2).strip()[:800]

        hw = re.sub(r"[\.,]$", "", hw).strip()
        if hw.upper() in SKIP_HEADS:
            continue
        if len(hw) < 2 or len(hw) > 60:
            continue
        if re.search(r"\d{4}", hw):
            continue
        if "\n" in hw:
            continue
        if _is_noise(hw):
            continue
        if not re.search(r"[A-Za-zÀ-ɏЀ-ӿ]", hw):
            continue

        key = (hw.lower().strip(), dict_id)
        if key in seen:
            continue
        seen.add(key)

        conf = ocr_confidence(hw + " " + defn)
        cat, sub = categorize(hw, defn)

        entries.append({
            "id": f"{dict_id}-{len(entries)+1:05d}",
            "language": inv_item["language"],
            "headword": hw,
            "normalized_headword": hw.lower().strip(),
            "category": cat,
            "subcategory": sub,
            "definition": defn,
            "example": "",
            "etymology": extract_etymology(defn),
            "source_dictionary": inv_item["title"],
            "author": inv_item["author"],
            "publication_year": inv_item["year"],
            "volume": inv_item.get("volumes", ""),
            "page": "",
            "source_text": m.group(0)[:300],
            "semantic_tags": semantic_tags(defn),
            "geographic_refs": extract_geography(defn),
            "historical_refs": extract_periods(defn),
            "cross_refs": extract_cross_refs(defn),
            "confidence_score": conf,
            "multilingual_alignment": "",
            "article_type": inv_item.get("article_type", ""),
            "notes": "",
        })

    return entries


# ── Multilingual lexicon builder ──────────────────────────────────────────────

def build_multilingual_lexicon(taxonomy: dict) -> list:
    rows = []
    alignments = taxonomy.get("multilingual_alignment_targets", {})
    for concept, langs in alignments.items():
        row = {"concept": concept}
        row.update(langs)
        rows.append(row)

    # Add extra known alignments from the ontology
    EXTRA = [
        {"concept": "chant", "en": "chant", "fr": "chant", "de": "Gesang",
         "it": "canto", "es": "canto", "la": "cantus", "ru": "пение"},
        {"concept": "organ", "en": "organ", "fr": "orgue", "de": "Orgel",
         "it": "organo", "es": "órgano", "la": "organum", "ru": "орган"},
        {"concept": "harp", "en": "harp", "fr": "harpe", "de": "Harfe",
         "it": "arpa", "es": "arpa", "la": "harpa", "ru": "арфа"},
        {"concept": "lute", "en": "lute", "fr": "luth", "de": "Laute",
         "it": "liuto", "es": "laúd", "la": "testudo", "ru": "лютня"},
        {"concept": "flute", "en": "flute", "fr": "flûte", "de": "Flöte",
         "it": "flauto", "es": "flauta", "la": "tibia", "ru": "флейта"},
        {"concept": "drum", "en": "drum", "fr": "tambour", "de": "Trommel",
         "it": "tamburo", "es": "tambor", "la": "tympanum", "ru": "барабан"},
        {"concept": "choir", "en": "choir", "fr": "choeur", "de": "Chor",
         "it": "coro", "es": "coro", "la": "chorus", "ru": "хор"},
        {"concept": "song", "en": "song", "fr": "chanson", "de": "Lied",
         "it": "canzone", "es": "canción", "la": "carmen", "ru": "песня"},
        {"concept": "melody", "en": "melody", "fr": "mélodie", "de": "Melodie",
         "it": "melodia", "es": "melodía", "la": "melodia", "ru": "мелодия"},
        {"concept": "rhythm", "en": "rhythm", "fr": "rythme", "de": "Rhythmus",
         "it": "ritmo", "es": "ritmo", "la": "rhythmus", "ru": "ритм"},
        {"concept": "dance", "en": "dance", "fr": "danse", "de": "Tanz",
         "it": "danza", "es": "danza", "la": "saltatio", "ru": "танец"},
        {"concept": "singer", "en": "singer", "fr": "chanteur", "de": "Sänger",
         "it": "cantore", "es": "cantante", "la": "cantor", "ru": "певец"},
        {"concept": "minstrel", "en": "minstrel", "fr": "ménestrel", "de": "Spielmann",
         "it": "menestrello", "es": "juglar", "la": "ioculator", "ru": "менестрель"},
        {"concept": "harmony", "en": "harmony", "fr": "harmonie", "de": "Harmonie",
         "it": "armonia", "es": "armonía", "la": "harmonia", "ru": "гармония"},
        {"concept": "counterpoint", "en": "counterpoint", "fr": "contrepoint",
         "de": "Kontrapunkt", "it": "contrappunto", "es": "contrapunto",
         "la": "contrapunctus", "ru": "контрапункт"},
        {"concept": "polyphony", "en": "polyphony", "fr": "polyphonie",
         "de": "Polyphonie", "it": "polifonia", "es": "polifonía",
         "la": "discantus", "ru": "полифония"},
        {"concept": "bell", "en": "bell", "fr": "cloche", "de": "Glocke",
         "it": "campana", "es": "campana", "la": "campana", "ru": "колокол"},
        {"concept": "festival", "en": "festival", "fr": "fête", "de": "Fest",
         "it": "festa", "es": "fiesta", "la": "festum", "ru": "праздник"},
        {"concept": "ritual", "en": "ritual", "fr": "rituel", "de": "Ritus",
         "it": "rito", "es": "rito", "la": "ritus", "ru": "обряд"},
        {"concept": "procession", "en": "procession", "fr": "procession",
         "de": "Prozession", "it": "processione", "es": "procesión",
         "la": "processio", "ru": "процессия"},
        {"concept": "liturgy", "en": "liturgy", "fr": "liturgie", "de": "Liturgie",
         "it": "liturgia", "es": "liturgia", "la": "liturgia", "ru": "литургия"},
        {"concept": "opera", "en": "opera", "fr": "opéra", "de": "Oper",
         "it": "opera", "es": "ópera", "la": "opus", "ru": "опера"},
        {"concept": "violin", "en": "violin", "fr": "violon", "de": "Violine",
         "it": "violino", "es": "violín", "la": "vitula", "ru": "скрипка"},
        {"concept": "trumpet", "en": "trumpet", "fr": "trompette", "de": "Trompete",
         "it": "tromba", "es": "trompeta", "la": "tuba", "ru": "труба"},
    ]
    # Deduplicate
    existing_concepts = {r["concept"] for r in rows}
    for r in EXTRA:
        if r["concept"] not in existing_concepts:
            rows.append(r)
    return rows


# ── Semantic relations builder ────────────────────────────────────────────────

SEMANTIC_GROUPS = {
    "INSTRUMENT_FAMILY_STRINGS": [
        "violin", "viola", "cello", "viol", "rebec", "lute", "guitar", "harp",
        "psaltery", "cittern", "gittern", "hurdy-gurdy", "fiddle", "vielle",
    ],
    "INSTRUMENT_FAMILY_WINDS": [
        "flute", "oboe", "clarinet", "bassoon", "trumpet", "horn", "trombone",
        "bagpipe", "cornet", "recorder", "chalumeau",
    ],
    "INSTRUMENT_FAMILY_KEYBOARD": [
        "organ", "piano", "harpsichord", "clavichord", "virginal", "spinet",
    ],
    "INSTRUMENT_FAMILY_PERCUSSION": [
        "drum", "tabor", "tambourine", "bells", "cymbal", "kettledrum",
    ],
    "SACRED_PERFORMANCE": [
        "chant", "plainchant", "mass", "liturgy", "vespers", "motet", "choir",
        "cantor", "chapel", "organ", "bells", "gregorian", "hymn",
    ],
    "COURTLY_PERFORMANCE": [
        "troubadour", "trouvere", "minstrel", "lute", "harp", "chanson",
        "ballad", "court", "ballet", "gavotte", "minuet",
    ],
    "THEATRICAL_PERFORMANCE": [
        "opera", "drama", "theatre", "ballet", "overture", "aria",
        "prima donna", "soprano", "tenor", "bass",
    ],
    "FOLK_DANCE": [
        "saltarello", "tarantella", "branle", "estampie", "polka", "waltz",
        "bagpipe", "drum", "tabor", "fiddle",
    ],
    "VOICE_TYPES": [
        "soprano", "alto", "tenor", "bass", "baritone", "contralto",
        "mezzo", "castrato",
    ],
    "MUSIC_THEORY": [
        "harmony", "counterpoint", "melody", "rhythm", "interval", "scale",
        "mode", "tonality", "polyphony", "fugue", "notation",
    ],
    "PERFORMER_ROLES": [
        "singer", "troubadour", "minstrel", "bard", "cantor", "jongleur",
        "organist", "violinist", "pianist", "conductor",
    ],
}


def build_semantic_relations() -> list:
    rows = []
    rel_id = 1
    for group, members in SEMANTIC_GROUPS.items():
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                rows.append({
                    "id": f"REL-{rel_id:04d}",
                    "source": a,
                    "target": b,
                    "relation_type": "SAME_FAMILY",
                    "group": group,
                    "weight": 1.0,
                    "notes": f"Co-member of {group}",
                })
                rel_id += 1

    # Cross-domain relations
    CROSS = [
        ("organ", "sacred", "ASSOCIATED_WITH", "Dominant instrument of church music"),
        ("troubadour", "courtly", "ASSOCIATED_WITH", "Performer of courtly love poetry"),
        ("bells", "ritual", "ASSOCIATED_WITH", "Used in liturgical processions"),
        ("ballet", "opera", "RELATED_TO", "Both theatrical performance genres"),
        ("chant", "polyphony", "PRECEDES", "Gregorian chant preceded polyphonic development"),
        ("lute", "troubadour", "USED_BY", "Troubadours often accompanied with lute"),
        ("drum", "procession", "USED_IN", "Drums central to processional music"),
        ("harp", "bard", "USED_BY", "Traditional bardic instrument"),
        ("castrato", "opera", "ASSOCIATED_WITH", "Central role in Baroque opera"),
        ("prima donna", "opera", "ASSOCIATED_WITH", "Lead soprano in opera"),
        ("rebec", "fiddle", "RELATED_TO", "Both bowed string instruments"),
        ("harmony", "counterpoint", "RELATED_TO", "Complementary music theory concepts"),
    ]
    for src, tgt, rel, note in CROSS:
        rows.append({
            "id": f"REL-{rel_id:04d}",
            "source": src,
            "target": tgt,
            "relation_type": rel,
            "group": "CROSS_DOMAIN",
            "weight": 0.8,
            "notes": note,
        })
        rel_id += 1

    return rows


# ── Build provenance ──────────────────────────────────────────────────────────

def infer_print_volume(dict_id: str, filename: str) -> int | str:
    """Return the printed volume represented by an OCR file where known."""
    if dict_id.startswith("EN-GROVE-1879"):
        return {
            "EN-GROVE-1879": 1,
            "EN-GROVE-1879-V2": 2,
            "EN-GROVE-1879-V3": 3,
            "EN-GROVE-1879-V4": 4,
        }[dict_id]
    if dict_id == "FR-FETIS-1860":
        m = re.search(r"vol(\d+)", filename.lower())
        if m:
            return int(m.group(1))
        # The locally named "vol1" file is Pougin's Supplement, tome I,
        # not main-series volume I.
        if "biographiemusyork01ftuoft" in filename.lower():
            return "Supplement 1"
        return "Unknown"
    if dict_id == "PT-VIEIRA-1900":
        return 1
    return 1


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")

    taxonomy = load_json("metadata/performance_taxonomy.json")
    raw_inventory = load_json("metadata/dictionary_inventory.json")
    inventory = {item["id"]: item for item in raw_inventory}

    # Also load the 19th-century sources we actually have
    extra_inventory = {
        "EN-GROVE-1879": {
            "id": "EN-GROVE-1879",
            "title": "A Dictionary of Music and Musicians (A.D. 1450-1889)",
            "author": "George Grove (ed.)",
            "year": 1879,
            "language": "English",
            "country": "United Kingdom",
            "domain": "Music / Encyclopedia",
            "volumes": 4,
            "ocr_quality": "High",
            "machine_readable": True,
            "license": "Public Domain",
            "article_type": "scholarly_treatise",
        },
        "EN-GROVE-1879-V2": {
            "id": "EN-GROVE-1879-V2",
            "title": "A Dictionary of Music and Musicians (A.D. 1450-1889)",
            "author": "George Grove (ed.)",
            "year": 1880,
            "language": "English",
            "country": "United Kingdom",
            "domain": "Music / Encyclopedia",
            "volumes": 4,
            "ocr_quality": "High",
            "machine_readable": True,
            "license": "Public Domain",
            "article_type": "scholarly_treatise",
        },
        "EN-GROVE-1879-V3": {
            "id": "EN-GROVE-1879-V3",
            "title": "A Dictionary of Music and Musicians (A.D. 1450-1889)",
            "author": "George Grove (ed.)",
            "year": 1883,
            "language": "English",
            "country": "United Kingdom",
            "domain": "Music / Encyclopedia",
            "volumes": 4,
            "ocr_quality": "High",
            "machine_readable": True,
            "license": "Public Domain",
            "article_type": "scholarly_treatise",
        },
        "EN-GROVE-1879-V4": {
            "id": "EN-GROVE-1879-V4",
            "title": "A Dictionary of Music and Musicians (A.D. 1450-1889)",
            "author": "George Grove (ed.)",
            "year": 1889,
            "language": "English",
            "country": "United Kingdom",
            "domain": "Music / Encyclopedia",
            "volumes": 4,
            "ocr_quality": "High",
            "machine_readable": True,
            "license": "Public Domain",
            "article_type": "scholarly_treatise",
        },
        "EN-MOORE-1854": {
            "id": "EN-MOORE-1854",
            "title": "Complete Encyclopaedia of Music",
            "author": "John Weeks Moore",
            "year": 1854,
            "language": "English",
            "country": "United States",
            "domain": "Music / Encyclopedia",
            "volumes": 1,
            "ocr_quality": "Medium-High",
            "machine_readable": True,
            "license": "Public Domain",
            "article_type": "specialized_music",
        },
        "DE-RIEMANN-1882": {
            "id": "DE-RIEMANN-1882",
            "title": "Musik-Lexikon",
            "author": "Hugo Riemann",
            "year": 1908,
            "language": "English",
            "country": "Germany",
            "domain": "Music / Lexicography",
            "volumes": 1,
            "ocr_quality": "Medium (OCR of the Shedlock English translation)",
            "machine_readable": True,
            "license": "Public Domain",
            "article_type": "specialized_music",
        },
        "FR-FETIS-1860": {
            "id": "FR-FETIS-1860",
            "title": "Biographie universelle des musiciens",
            "author": "François-Joseph Fétis",
            "year": 1860,
            "language": "French",
            "country": "France/Belgium",
            "domain": "Music / Biography",
            "volumes": 8,
            "ocr_quality": "Medium",
            "machine_readable": True,
            "license": "Public Domain",
            "article_type": "personal_polemical",
            "note": "Local coverage is main-series volumes 2-8 plus Pougin's Supplement, tome I; main-series volume 1 is not present.",
        },
        "FR-DESRAT-1895": {
            "id": "FR-DESRAT-1895",
            "title": "Dictionnaire de la danse",
            "author": "G. Desrat",
            "year": 1895,
            "language": "French",
            "country": "France",
            "domain": "Dance",
            "volumes": 1,
            "ocr_quality": "Medium",
            "machine_readable": True,
            "license": "Public Domain",
            "article_type": "specialized_dance",
        },
        "ES-PEDRELL-1894": {
            "id": "ES-PEDRELL-1894",
            "title": "Diccionario técnico de la música",
            "author": "Felipe Pedrell",
            "year": 1894,
            "language": "Spanish",
            "country": "Spain",
            "domain": "Music / Terminology",
            "volumes": 1,
            "ocr_quality": "Medium",
            "machine_readable": True,
            "license": "Public Domain",
            "article_type": "specialized_music",
        },
        "PT-VIEIRA-1900": {
            "id": "PT-VIEIRA-1900",
            "title": "Diccionario biographico de musicos portuguezes",
            "author": "Ernesto Vieira",
            "year": 1900,
            "language": "Portuguese",
            "country": "Portugal",
            "domain": "Music / Biography",
            "volumes": 2,
            "ocr_quality": "Medium",
            "machine_readable": True,
            "license": "Public Domain",
            "article_type": "specialized_biographical",
        },
        "DE-MEYERS-1885": {
            "id": "DE-MEYERS-1885",
            "title": "Meyers Konversations-Lexikon (Music Articles)",
            "author": "Various (ed. Bibliographisches Institut Leipzig)",
            "year": 1885,
            "language": "German",
            "country": "Germany",
            "domain": "Music / Encyclopedia",
            "volumes": 16,
            "ocr_quality": "High (German Wikisource transcription)",
            "machine_readable": True,
            "license": "Public Domain",
            "article_type": "konversations_lexikon",
            "note": "Scraped from the MKL1888 namespace on German Wikisource, "
                    "which identifies the text as the 4th edition (1885-1890, supplements to 1892).",
        },
        "RU-BROCKHAUS": {
            "id": "RU-BROCKHAUS",
            "title": "Brockhaus-Efron Encyclopaedia (Music Articles)",
            "author": "Various (ed. F. A. Brockhaus & I. A. Efron)",
            "year": 1896,
            "language": "Russian",
            "country": "Russia",
            "domain": "Music / Encyclopedia",
            "volumes": 86,
            "ocr_quality": "High",
            "machine_readable": True,
            "license": "Public Domain",
            "article_type": "konversations_lexikon",
        },
        "FR-LAROUSSE-1866": {
            "id": "FR-LAROUSSE-1866",
            "title": "Grand dictionnaire universel du XIXe siècle",
            "author": "Pierre Larousse",
            "year": 1866,
            "language": "French",
            "country": "France",
            "domain": "Encyclopedia (Universal)",
            "volumes": 17,
            "ocr_quality": "Medium-High (fr.wikisource.org)",
            "machine_readable": True,
            "license": "Public Domain",
            "article_type": "personal_polemical",
        },
    }
    inventory.update(extra_inventory)

    dir_map = {
        "completeencyclop00moor":         "EN-MOORE-1854",
        "dictionaryofmusi00riem":          "DE-RIEMANN-1882",
        "dictionaryofmusi01grovuoft":      "EN-GROVE-1879",
        "grove_vol2":                      "EN-GROVE-1879-V2",
        "grove_vol3":                      "EN-GROVE-1879-V3",
        "grove_vol4":                      "EN-GROVE-1879-V4",
        "fetis_biographie_vol1":           "FR-FETIS-1860",
        "desrat_danse":                    "FR-DESRAT-1895",
        "pedrell_diccionario":             "ES-PEDRELL-1894",
        "vieira_musicos_portuguezes":      "PT-VIEIRA-1900",
        "RU_BROCKHAUS":                    "RU-BROCKHAUS",
        "meyers_konversations_lexikon":    "DE-MEYERS-1885",
        "larousse_grand_dictionnaire":     "FR-LAROUSSE-1866",
    }

    all_entries = []
    per_dict_counts = Counter()
    source_sequence = Counter()
    noise_count = 0

    for dir_name, dict_id in sorted(dir_map.items()):
        dir_path = os.path.join("data_ocr", dir_name)
        if not os.path.exists(dir_path):
            print(f"[SKIP] {dir_path} not found")
            continue

        for fname in sorted(os.listdir(dir_path)):
            if not fname.endswith(".txt"):
                continue
            fpath = os.path.join(dir_path, fname)
            print(f"[PARSE] {fpath}")
            with open(fpath, encoding="utf-8", errors="replace") as fh:
                text = fh.read()

            entries = parse_file(text, dict_id, inventory)
            search_cursor = 0
            for entry in entries:
                source_sequence[dict_id] += 1
                entry["id"] = f"{dict_id}-{source_sequence[dict_id]:05d}"
                entry["volume"] = infer_print_volume(dict_id, fname)
                entry["source_file"] = os.path.relpath(fpath)
                entry["source_text_language"] = entry["language"]
                entry["original_publication_year"] = 1882 if dict_id == "DE-RIEMANN-1882" else entry["publication_year"]

                snippet = entry.get("source_text", "")
                char_start = text.find(snippet, search_cursor) if snippet else -1
                if char_start < 0 and snippet:
                    char_start = text.find(snippet)
                if char_start >= 0:
                    entry["source_line_start"] = text.count("\n", 0, char_start) + 1
                    search_cursor = char_start + len(snippet)
                else:
                    entry["source_line_start"] = ""

            low_conf = sum(1 for e in entries if e["confidence_score"] < 0.4)
            noise_count += low_conf
            print(f"  → {len(entries)} entries ({low_conf} low-confidence)")
            per_dict_counts[dict_id] += len(entries)
            all_entries.extend(entries)

    print(f"\nTotal entries: {len(all_entries)}")

    # ── Performance-filtered subset ──
    perf_entries = [e for e in all_entries if e["category"] != "GENERAL"]
    print(f"Performance entries: {len(perf_entries)}")

    # ── Save a non-destructive v3.2 candidate ──
    fieldnames = [
        "id", "language", "headword", "normalized_headword", "category", "subcategory",
        "definition", "example", "etymology", "source_dictionary", "author",
        "publication_year", "original_publication_year", "source_text_language",
        "volume", "page", "source_file", "source_line_start",
        "source_text", "semantic_tags",
        "geographic_refs", "historical_refs", "cross_refs", "confidence_score",
        "multilingual_alignment", "article_type", "notes",
    ]
    out_path = "datasets/master_performance_dataset_v3_2.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(perf_entries)
    print(f"Saved: {out_path} ({len(perf_entries)} rows)")

    # The complete parsed-candidate pool is required for relevance-recall sampling.
    os.makedirs("validation", exist_ok=True)
    audit_path = "validation/all_extracted_entries_v3_2.jsonl"
    with open(audit_path, "w", encoding="utf-8") as fh:
        for entry in all_entries:
            audit_entry = dict(entry)
            audit_entry["predicted_relevant"] = entry["category"] != "GENERAL"
            fh.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
    print(f"Saved: {audit_path} ({len(all_entries)} rows)")

    # ── Multilingual lexicon ──
    lexicon_rows = build_multilingual_lexicon(taxonomy)
    lex_path = "datasets/multilingual_lexicon.csv"
    lex_fields = ["concept", "la", "fr", "en", "de", "it", "es", "pt", "ru"]
    with open(lex_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=lex_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(lexicon_rows)
    print(f"Saved: {lex_path} ({len(lexicon_rows)} concepts)")

    # ── Semantic relations ──
    rel_rows = build_semantic_relations()
    rel_path = "datasets/semantic_relations.csv"
    with open(rel_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id","source","target","relation_type","group","weight","notes"])
        w.writeheader()
        w.writerows(rel_rows)
    print(f"Saved: {rel_path} ({len(rel_rows)} relations)")

    # ── Category breakdown ──
    cat_counts = Counter(e["category"] for e in perf_entries)
    sub_counts = Counter(e["subcategory"] for e in perf_entries)
    sem_all = []
    for e in perf_entries:
        sem_all.extend(e["semantic_tags"].split("; "))
    sem_counts = Counter(t for t in sem_all if t and t != "Neutral")

    geo_all = []
    for e in perf_entries:
        if e["geographic_refs"]:
            geo_all.extend(e["geographic_refs"].split("; "))
    geo_counts = Counter(geo_all)

    # ── Quality report ──
    qr_path = "datasets/quality_report_v3_2.md"
    with open(qr_path, "w", encoding="utf-8") as fh:
        fh.write("# Dataset Quality Report\n\n")
        fh.write(f"**Generated:** 2026-08-27  \n**Pipeline:** `scripts/build_dataset.py`\n\n")
        fh.write("## Corpus Overview\n\n")
        fh.write(f"| Metric | Value |\n|--------|-------|\n")
        fh.write(f"| Total extracted entries | {len(all_entries):,} |\n")
        fh.write(f"| Performance-relevant entries | {len(perf_entries):,} |\n")
        fh.write(f"| Low-confidence entries (< 0.4) | {noise_count:,} |\n")
        fh.write(f"| Multilingual lexicon concepts | {len(lexicon_rows)} |\n")
        fh.write(f"| Semantic relation pairs | {len(rel_rows)} |\n\n")

        fh.write("## Entries per Dictionary\n\n")
        fh.write("| Dictionary ID | Count |\n|---------------|-------|\n")
        for did, cnt in sorted(per_dict_counts.items()):
            fh.write(f"| {did} | {cnt:,} |\n")

        fh.write("\n## Category Distribution (Performance Entries)\n\n")
        fh.write("| Category | Count | % |\n|----------|-------|---|\n")
        total_p = len(perf_entries)
        for cat, cnt in cat_counts.most_common():
            fh.write(f"| {cat} | {cnt} | {cnt/total_p*100:.1f}% |\n")

        fh.write("\n## Top Subcategories\n\n")
        fh.write("| Subcategory | Count |\n|-------------|-------|\n")
        for sub, cnt in sub_counts.most_common(20):
            fh.write(f"| {sub} | {cnt} |\n")

        fh.write("\n## Semantic Tag Distribution\n\n")
        fh.write("| Tag | Count |\n|-----|-------|\n")
        for tag, cnt in sem_counts.most_common():
            fh.write(f"| {tag} | {cnt} |\n")

        fh.write("\n## Geographic References\n\n")
        fh.write("| Place/Region | Mentions |\n|--------------|----------|\n")
        for geo, cnt in geo_counts.most_common(20):
            fh.write(f"| {geo} | {cnt} |\n")

        fh.write("\n## Known Limitations\n\n")
        fh.write("1. **OCR noise**: the processed Riemann/Shedlock English translation contains substantial OCR artefacts.\n")
        fh.write("2. **Entry boundary detection**: Regex heuristics miss multi-paragraph entries.\n")
        fh.write("3. **Russian corpus**: Brockhaus articles are scraped from Wikisource as discrete entries; article length varies.\n")
        fh.write("4. **French corpus**: local Fétis coverage is main-series volumes 2-8 plus Pougin's Supplement, tome I; main-series volume 1 is missing and segmentation recall remains unvalidated.\n")
        fh.write("5. **Temporal skew**: Coverage biased toward 17th–19th century despite 1450–1889 range.\n")
        fh.write("6. **Definition truncation**: Definitions capped at 800 characters; long entries lose tail context.\n")
        fh.write("7. **Cross-language ontology**: Keyword matching for FR/ES/PT/RU may miss inflected forms.\n")

    print(f"Saved: {qr_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
