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
