"""Guards on the knowledge-base source files themselves.

Unfilled template text used to reach customers verbatim: the bot read
`prijzen_topproducten.txt` and answered "omdat de actuele prijslijst hier niet is
ingevuld" (sess_JDhaIfes, 2026-07-28). These tests fail the build instead.
"""
import glob
import os
import re

KB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "knowledge_base")

# Template markers a human was supposed to replace before shipping the file.
PLACEHOLDER_RE = re.compile(
    r'\[INVULLEN\]|\[[^\]]*invullen[^\]]*\]|\bTODO\b|\bTBD\b|XXX',
    re.IGNORECASE,
)


def _kb_files() -> list[str]:
    return sorted(glob.glob(os.path.join(KB_DIR, "*.txt")))


def test_knowledge_base_has_files():
    assert _kb_files(), f"No knowledge base .txt files found in {KB_DIR}"


def test_no_unfilled_placeholders():
    offenders = []
    for path in _kb_files():
        with open(path, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                if PLACEHOLDER_RE.search(line):
                    offenders.append(f"{os.path.basename(path)}:{lineno}: {line.strip()}")

    assert not offenders, (
        "Knowledge base contains unfilled template text, which the bot will read out "
        "to customers. Fill it in or remove the file:\n  " + "\n  ".join(offenders)
    )


def test_phone_number_is_consistent():
    """The pickup section carried 0324-784000; the real number is 0342 - 784 000."""
    wrong = []
    for path in _kb_files():
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        for match in re.finditer(r'\b03\d{2}\s*[–\-]?\s*784\s*000\b', content):
            digits = re.sub(r'\D', '', match.group(0))
            if not digits.startswith('0342'):
                wrong.append(f"{os.path.basename(path)}: {match.group(0)}")

    assert not wrong, (
        "Wrong customer service phone number in the knowledge base "
        "(expected 0342 – 784 000):\n  " + "\n  ".join(wrong)
    )


def test_support_hours_match_the_canned_phone_reply():
    """The hours live in two places and must agree.

    `openingstijden.txt` serves questions phrased without a phone word; the canned
    reply in `app.py` serves everything PHONE_CONTACT_RE catches, which never
    reaches the RAG at all. Editing one and not the other is how sess_jLgTn7 would
    come back as a *wrong* answer instead of a missing one.
    """
    import app

    path = os.path.join(KB_DIR, "openingstijden.txt")
    with open(path, "r", encoding="utf-8") as f:
        kb = f.read()

    for label, canned in (("NL", app.SUPPORT_HOURS_NL), ("EN", app.SUPPORT_HOURS_EN)):
        times = re.findall(r'\b\d{1,2}:\d{2}\b', canned)
        assert times, f"{label} support hours name no time: {canned!r}"
        for t in times:
            assert t in kb, (
                f"{label} canned phone reply says {t}, which openingstijden.txt "
                f"does not mention. Keep app.SUPPORT_HOURS_* and the KB file in sync."
            )


def test_douglas_premium_is_not_confused_with_the_discontinued_excellent():
    """Only "Douglas Excellent" (HSDE-2) is discontinued; "Douglas Premium" is not.

    The KB named only Excellent, so retrieval matched a customer asking about
    "Douglas Premium | Houtsnippers | Big Bag" against the discontinued-products
    file and told a buying customer we no longer sell it (sess_jLgTn7 replay,
    2026-08-25). Both files must keep naming Premium as available.
    """
    with open(os.path.join(KB_DIR, "Houtsnippers.txt"), "r", encoding="utf-8") as f:
        snippers = f.read()
    with open(os.path.join(KB_DIR, "niet_leverbare_producten.txt"), "r", encoding="utf-8") as f:
        unavailable = f.read()

    assert "Douglas Premium" in snippers, (
        "Houtsnippers.txt must name Douglas Premium, or the only KB hit for "
        "'Douglas' is the discontinued Excellent"
    )
    assert "Douglas Premium" in unavailable, (
        "niet_leverbare_producten.txt must say Douglas Premium is a different, "
        "still-available product next to the Excellent entry"
    )
