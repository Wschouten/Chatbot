"""Fase 5 — the deterministic volume helper.

Cases are the real customer sentences from CHATLOG-ANALYSE-2026-07-29.md, including
the one the model got wrong (sess_O7LCO1: 3,84 instead of 3,07).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from volume_calc import compute_volume  # noqa: E402


def test_sess_o7lco1_the_calculation_the_model_got_wrong():
    out = compute_volume("Ik denk ik heb 48 m lang op 80 cm breed 8 cm diep, hoeveel kuub?")
    assert "3,072 m3" in out
    assert "3,84" not in out


def test_sess_o7lco1_sloppy_units_second_attempt():
    """"Wat denk je 48 mt op 0.8 breed 0.06 diep" — units on the first number only.
    The model happened to get this one right; the helper must too."""
    out = compute_volume("Wat denk je 48 mt op 0.8 breed 0.06 diep, hoeveel kuub")
    assert "2,304 m3" in out


def test_sess_og881c_area_times_depth():
    """The bot refused this one outright: "in de context staat daar geen exacte
    richtlijn voor" — while it is pure arithmetic."""
    out = compute_volume("Hoeveel zakken heb ik nodig voor 5 m2 met een laag van 5 cm?")
    assert "0,25 m3" in out
    assert "250 liter" in out


def test_litres_are_included_so_bag_counts_are_a_division():
    """sess_9lIjUY: 5 m2 at 5 cm was answered with "3 tot 4 zakken" (it is ~5 bags
    of 50 L). Giving litres turns the bag count into a trivial division."""
    out = compute_volume("hoeveel bigbags voor 20 m2 bij 6 cm?")
    assert "1,2 m3" in out
    assert "1200 liter" in out


def test_dutch_and_english_decimals_both_parse():
    assert "3,072 m3" in compute_volume("48 m x 0,8 m x 0,08 m hoeveel kuub")
    assert "3,072 m3" in compute_volume("48 m x 0.8 m x 0.08 m how much cubic")


@pytest.mark.parametrize("message", [
    "Hebben jullie Franse boomschors?",                  # no dimensions at all
    "Wat kost een bigbag?",                              # no dimensions
    "Mijn bestelnummer is 6700 en ik wacht al 3 dagen",  # numbers, but not dimensions
    "3 x 4,5 x 4,5 hoeveel kuub",                        # no unit anywhere: ambiguous
    "Is 10 cm te veel?",                                 # one dimension only
])
def test_returns_none_when_it_cannot_be_sure(message):
    """A wrong computed line is worse than none: the model would report it verbatim."""
    assert compute_volume(message) is None


def test_implausible_results_are_rejected():
    assert compute_volume("100 m x 100 m x 100 m hoeveel kuub") is None
