"""Deterministic volume arithmetic for ground-cover questions.

The model does this arithmetic well most of the time and then quietly gets one
wrong: "48 m x 0,80 m x 0,08 m = 3,84 m3" (sess_O7LCO1 — it is 3,07). Rather than
hoping a prompt rule fixes that, the numbers are computed here and injected into the
context as a fact, so the model only has to report them.

Kept deliberately narrow: it computes only when the dimensions can be read with
confidence, and returns None otherwise. A wrong computed line would be worse than
none at all.
"""
from __future__ import annotations

import re

# Numbers written the Dutch way (0,08) and the English way (0.08).
_NUMBER = r'\d+(?:[.,]\d+)?'
_TO_METRES = {
    'mm': 0.001, 'millimeter': 0.001,
    'cm': 0.01, 'centimeter': 0.01,
    'dm': 0.1,
    'm': 1.0, 'mt': 1.0, 'meter': 1.0,
}
_UNIT = '|'.join(sorted(_TO_METRES, key=len, reverse=True))

# A number with an optional unit: "80 cm", "0.8", "48 mt".
_DIM_RE = re.compile(rf'({_NUMBER})\s*({_UNIT})?\b', re.IGNORECASE)
# An area: "5 m2", "60,75 m²", "20 vierkante meter".
_AREA_RE = re.compile(
    rf'({_NUMBER})\s*(?:m2|m²|vierkante\s+meter|square\s+met(?:er|re)s?)\b',
    re.IGNORECASE,
)
# Depth words, so "5 m2 met een laag van 5 cm" can be told apart from a stray number.
_DEPTH_RE = re.compile(
    rf'({_NUMBER})\s*({_UNIT})\b\s*(?:dik|diep|hoog|laag|laagdikte)?',
    re.IGNORECASE,
)
_ASKS_VOLUME_RE = re.compile(
    r'\b(kuub|m3|m³|kubieke?|volume|hoeveel\s+(heb|hebben|moet|zakken|bigbags?|big\s?bags?)'
    r'|hoeveel\s+\w+\s+(nodig|heb)|dik|diep|laagdikte|laag\s+van'
    r'|how\s+much|cubic|litres?|liters?)\b',
    re.IGNORECASE,
)


def _to_float(raw: str) -> float:
    return float(raw.replace(',', '.'))


def _fmt(value: float) -> str:
    """Dutch number formatting, without trailing zeros."""
    text = f"{value:.3f}".rstrip('0').rstrip('.')
    return text.replace('.', ',') or '0'


def compute_volume(message: str) -> str | None:
    """Return a one-line calculation for the dimensions in `message`, or None.

    Handles the two shapes customers actually use:
      "48 meter lang, 80 cm breed en 8 cm dik"  -> length x width x depth
      "5 m2 met een laag van 5 cm"              -> area x depth

    Returns None when the message has no dimensions, when units are missing
    entirely ("3 x 4,5 x 4,5" is just as likely an area), or when the result is
    implausible.
    """
    if not _ASKS_VOLUME_RE.search(message):
        return None

    area_match = _AREA_RE.search(message)
    if area_match:
        area = _to_float(area_match.group(1))
        # The depth is the first dimensioned number that is not the area itself.
        for match in _DEPTH_RE.finditer(message):
            if match.start() == area_match.start():
                continue
            depth = _to_float(match.group(1)) * _TO_METRES[match.group(2).lower()]
            if not 0 < depth <= 1:  # a layer thicker than a metre is a parse error
                continue
            volume = area * depth
            if not 0 < volume < 10_000:
                return None
            return (
                f"{_fmt(area)} m2 x {_fmt(depth)} m = {_fmt(volume)} m3 "
                f"({_fmt(volume * 1000)} liter)"
            )
        return None

    dims: list[tuple[float, bool]] = []
    for match in _DIM_RE.finditer(message):
        unit = match.group(2)
        if unit:
            dims.append((_to_float(match.group(1)) * _TO_METRES[unit.lower()], True))
        else:
            dims.append((_to_float(match.group(1)), False))

    if len(dims) != 3:
        return None
    if not any(explicit for _, explicit in dims):
        # No unit anywhere: "3 x 4,5 x 4,5" is as likely an area as a volume.
        return None

    values = [value for value, _ in dims]
    if any(value <= 0 for value in values):
        return None
    volume = values[0] * values[1] * values[2]
    if not 0 < volume < 10_000:
        return None
    shown = " x ".join(f"{_fmt(value)} m" for value in values)
    return f"{shown} = {_fmt(volume)} m3 ({_fmt(volume * 1000)} liter)"
