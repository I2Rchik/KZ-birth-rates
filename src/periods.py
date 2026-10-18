"""Parse period labels found in Taldau / stat.gov.kz exports.

Returns (kind, year, index) with kind in {"M", "Q", "A", "CUM"}:
  M   month 1-12
  Q   quarter 1-4
  A   year
  CUM cumulative January..month (index = last month), e.g. "январь-март 2025"
"""
import datetime as _dt
import re

_MONTHS = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "ма": 5, "июн": 6,
    "июл": 7, "август": 8, "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4}


def _month(word):
    w = word.lower()
    # check longest stems first so "март" is not taken for "ма(й)"
    for stem in sorted(_MONTHS, key=len, reverse=True):
        if w.startswith(stem):
            if stem == "ма" and not (w.startswith("май") or w.startswith("мая")):
                continue
            return _MONTHS[stem]
    return None


def parse_period(label):
    if label is None:
        return None
    if isinstance(label, (_dt.date, _dt.datetime)):
        return ("M", label.year, label.month)
    if isinstance(label, (int, float)) and not isinstance(label, bool):
        if label != label:  # NaN
            return None
        y = int(label)
        return ("A", y, 1) if 1950 <= y <= 2100 and float(label) == y else None
    s = str(label).strip().lower().replace("ё", "е")
    if not s:
        return None
    ym = re.search(r"(19|20)\d{2}", s)
    if not ym:
        return None
    year = int(ym.group(0))
    rest = (s[: ym.start()] + " " + s[ym.end():]).strip()

    # 2010-01 / 2010.01 / 01.2010
    m = re.fullmatch(r"(19|20)\d{2}[-./](\d{1,2})(?:[-./]\d{1,2})?", s)
    if m:
        return ("M", year, int(m.group(2)))
    m = re.fullmatch(r"(?:\d{1,2}[-./])?(\d{1,2})[-./](19|20)\d{2}", s)
    if m:
        return ("M", year, int(m.group(1)))

    # quarters: 2010Q1, Q1 2010, 1 квартал 2010, I квартал, 1-й квартал
    m = re.search(r"q\s*([1-4])|([1-4])\s*q\b", s)
    if m:
        return ("Q", year, int(m.group(1) or m.group(2)))
    if "квартал" in rest or "тоқсан" in rest:
        m = re.search(r"\b([1-4])\b|\b([1-4])\s*-?\s*(?:й|ый|ой)\b|\b(iv|iii|ii|i)\b", rest)
        if m:
            q = m.group(1) or m.group(2) or _ROMAN[m.group(3)]
            return ("Q", year, int(q))

    # cumulative "январь-март"
    words = re.findall(r"[a-zа-я]+", rest)
    months = [mm for mm in (_month(w) for w in words) if mm]
    if len(months) >= 2 and ("-" in rest or "–" in rest) and months[0] == 1:
        return ("CUM", year, months[-1])
    if len(months) == 1:
        return ("M", year, months[0])
    if not rest or re.fullmatch(r"[\sгодаy.]*", rest):
        return ("A", year, 1)
    return None


def quarter_of(kind, year, idx):
    if kind == "M":
        return year, (idx - 1) // 3 + 1
    if kind == "Q":
        return year, idx
    raise ValueError(kind)
