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
    """The pickup section once carried 0324-784000, and since the rebrand to
    Boomschors.nl the number is 0516 - 715 000; the old 0342 - 784 000 must not linger."""
    wrong = []
    for path in _kb_files():
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        for match in re.finditer(r'(\b0\d{3}|\+31\s*\d{3}|\b0031\s*\d{3})\s*[–\-]?\s*(784|715)\s*000\b', content):
            digits = re.sub(r'\D', '', match.group(0))
            if not digits.endswith('516715000'):
                wrong.append(f"{os.path.basename(path)}: {match.group(0)}")

    assert not wrong, (
        "Wrong customer service phone number in the knowledge base "
        "(expected 0516 – 715 000):\n  " + "\n  ".join(wrong)
    )


# Ground Cover Group no longer exists: the shop is Boomschors.nl, a webshop of
# EUROstyle BV. Only oude_naam_ground_cover_group.txt may name the old brand, so the bot can
# tell a customer who still uses it that it is the same shop.
OLD_BRAND_RE = re.compile(r'ground\s*cover\s*group|groundcovergroup', re.IGNORECASE)
OLD_BRAND_ALLOWED_KB = {"oude_naam_ground_cover_group.txt"}
CUSTOMER_FACING_CODE = [
    "app.py", "rag_engine.py", "brand_config.py", "email_client.py",
    os.path.join("..", "frontend", "static", "widget.js"),
    os.path.join("..", "frontend", "templates", "portal.html"),
]


def test_old_brand_name_is_gone():
    offenders = []
    for path in _kb_files():
        if os.path.basename(path) in OLD_BRAND_ALLOWED_KB:
            continue
        with open(path, "r", encoding="utf-8") as f:
            if OLD_BRAND_RE.search(f.read()):
                offenders.append(os.path.basename(path))
    for rel in CUSTOMER_FACING_CODE:
        with open(rel, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                # ponytail: the Chroma collection name stays; renaming it re-embeds the whole KB.
                if OLD_BRAND_RE.search(line) and "groundcovergroup_docs" not in line:
                    offenders.append(f"{rel}:{lineno}: {line.strip()}")

    assert not offenders, (
        "The old brand name Ground Cover Group is still customer-facing:\n  "
        + "\n  ".join(offenders)
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
