"""Region names -> harmonised region codes (pre-2018 borders).

Harmonisation (documented in the indicator card):
  * Abai (split off 8 June 2022)    -> East Kazakhstan (EKO)
  * Zhetisu (split off 8 June 2022) -> Almaty oblast (ALM)
  * Ulytau (split off 8 June 2022)  -> Karaganda (KAR)
  * Shymkent (city status 2018)     -> Turkestan / South Kazakhstan (TUR)
"""
import re

REGIONS = {
    "AKM": "Akmola",
    "AKT": "Aktobe",
    "ALM": "Almaty oblast (incl. Zhetisu)",
    "ATY": "Atyrau",
    "WKO": "West Kazakhstan",
    "ZHA": "Zhambyl",
    "KAR": "Karaganda (incl. Ulytau)",
    "KOS": "Kostanay",
    "KZY": "Kyzylorda",
    "MAN": "Mangystau",
    "TUR": "Turkestan + Shymkent",
    "PAV": "Pavlodar",
    "NKO": "North Kazakhstan",
    "EKO": "East Kazakhstan (incl. Abai)",
    "AST": "Astana",
    "ALA": "Almaty city",
}

# Order matters: more specific patterns first ("алматинск" before "алматы",
# "west kazakhstan" before the national total "kazakhstan").
_PATTERNS = [
    ("акмолин", "AKM"), ("akmola", "AKM"), ("ақмола", "AKM"),
    ("shygys kazakhstan", "EKO"), ("soltustik kazakhstan", "NKO"), ("batys-kazakhstan", "WKO"),
    ("batys kazakhstan", "WKO"), ("karagandy", "KAR"), ("turkistan", "TUR"),
    ("актюбин", "AKT"), ("актобе", "AKT"), ("aktobe", "AKT"), ("ақтөбе", "AKT"),
    ("жетісу", "ALM"), ("жетысу", "ALM"), ("жетису", "ALM"), ("zhetisu", "ALM"), ("zhetysu", "ALM"),
    ("алматинск", "ALM"), ("almaty region", "ALM"), ("almaty oblast", "ALM"), ("алматы облысы", "ALM"),
    ("атырау", "ATY"), ("atyrau", "ATY"),
    ("западно-казахстан", "WKO"), ("западно казахстан", "WKO"), ("west kazakhstan", "WKO"), ("батыс қазақстан", "WKO"),
    ("жамбыл", "ZHA"), ("zhambyl", "ZHA"), ("jambyl", "ZHA"),
    ("улытау", "KAR"), ("ulytau", "KAR"), ("ұлытау", "KAR"),
    ("карагандин", "KAR"), ("караганд", "KAR"), ("karaganda", "KAR"), ("қарағанды", "KAR"),
    ("костанай", "KOS"), ("kostanay", "KOS"), ("қостанай", "KOS"),
    ("кызылорд", "KZY"), ("kyzylorda", "KZY"), ("қызылорда", "KZY"),
    ("мангист", "MAN"), ("мангыстау", "MAN"), ("mangystau", "MAN"), ("mangistau", "MAN"), ("маңғыстау", "MAN"),
    ("south-kazakhstan", "TUR"), ("южно-казахстан", "TUR"), ("южно казахстан", "TUR"), ("south kazakhstan", "TUR"),
    ("туркестан", "TUR"), ("turkestan", "TUR"), ("түркістан", "TUR"),
    ("шымкент", "TUR"), ("shymkent", "TUR"),
    ("павлодар", "PAV"), ("pavlodar", "PAV"),
    ("северо-казахстан", "NKO"), ("северо казахстан", "NKO"), ("north kazakhstan", "NKO"), ("солтүстік қазақстан", "NKO"),
    ("восточно-казахстан", "EKO"), ("восточно казахстан", "EKO"), ("east kazakhstan", "EKO"), ("шығыс қазақстан", "EKO"),
    ("абай", "EKO"), ("abai", "EKO"), ("abay", "EKO"),
    ("нур-султан", "AST"), ("nur-sultan", "AST"), ("астана", "AST"), ("astana", "AST"),
    ("алматы", "ALA"), ("almaty", "ALA"),
]

_TOTAL = ("республика казахстан", "republic of kazakhstan", "казахстан", "kazakhstan", "қазақстан", "всего", "total")


def normalise(name):
    s = str(name).strip().lower().replace("ё", "е")
    s = re.sub(r"\s+", " ", s)
    return s


_SPLIT_COMPONENT = {
    # South Kazakhstan = Turkestan + Shymkent on the pre-2018 borders: a full unit
    "южно-казахстан": "SKO_FULL", "южно казахстан": "SKO_FULL", "south kazakhstan": "SKO_FULL",
    "south-kazakhstan": "SKO_FULL",
    "жетісу": "ZHETISU", "жетысу": "ZHETISU", "жетису": "ZHETISU", "zhetisu": "ZHETISU", "zhetysu": "ZHETISU",
    "улытау": "ULYTAU", "ulytau": "ULYTAU", "ұлытау": "ULYTAU",
    "шымкент": "SHYMKENT", "shymkent": "SHYMKENT",
    "абай": "ABAI", "abai": "ABAI", "abay": "ABAI",
}


def region_code(name):
    """Return (code, component) for a raw region label, or (None, None).

    `component` names the current region inside a harmonised unit (e.g.
    "ABAI" inside EKO). It is used to weight rate series by population
    when two current regions are merged into one harmonised unit."""
    s = normalise(name)
    if not s or s == "nan":
        return None, None
    for pat, code in _PATTERNS:
        if pat in s:
            return code, _SPLIT_COMPONENT.get(pat, code)
    return None, None


_REPUBLICAN_CITIES = ("алматы", "астана", "шымкент", "нур-султан", "almaty", "astana", "shymkent", "nur-sultan")


def is_top_level(name):
    """True for an oblast or a city of republican significance; False for
    districts (район), towns inside an oblast (Г.АКТОБЕ, АКСУ Г.А.,
    Г.А.АЛАТАУ) and the national total. Taldau lists all of these together,
    and keeping a town would count its people twice."""
    s = normalise(name)
    if not s or "район" in s or "district" in s or "ауданы" in s or "г.а." in s or s.endswith(" г.а") or is_total(s):
        return False
    if region_code(s)[0] is None:
        return False
    # an oblast is always named as one; anything else must be a republican city
    if any(w in s for w in ("област", "облысы", "oblast", "region")):
        return True
    return any(c in s for c in _REPUBLICAN_CITIES) and not s.startswith(("с.", "п.", "пос."))


def is_total(name):
    s = normalise(name)
    return any(t == s or s.startswith(t) for t in _TOTAL)
