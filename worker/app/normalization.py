"""Text normalization and masking of variable elements.

Normalization reduces noise (whitespace, casing) so hashes/shingles are stable.
Masking replaces values that legitimately change between versions of the same
document (dates, money, process numbers, CPF/CNPJ) with placeholders, so two
near-identical drafts are not pushed apart by those edits.
"""
import re
import unicodedata

# --- masking patterns (order matters: most specific first) ---

# CNPJ: 00.000.000/0000-00  (also bare 14 digits)
_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
# CPF: 000.000.000-00 (also bare 11 digits)
_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
# Brazilian process number (CNJ): 0000000-00.0000.0.00.0000
_PROCESS = re.compile(r"\b\d{7}-?\d{2}\.?\d{4}\.?\d\.?\d{2}\.?\d{4}\b")
# Monetary values: R$ 1.234,56 / R$1234 / 1.234,56
_MONEY = re.compile(r"(r\$\s*)?\d{1,3}(\.\d{3})*(,\d{2})\b", re.IGNORECASE)
_MONEY_PREFIX = re.compile(r"r\$\s*\d[\d\.\,]*", re.IGNORECASE)
# Dates: 10/03/2026, 10-03-2026, 2026-03-10
_DATE_NUMERIC = re.compile(r"\b\d{1,4}[/\-]\d{1,2}[/\-]\d{1,4}\b")
# Dates written out: 10 de março de 2026
_MONTHS = (
    "janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|"
    "setembro|outubro|novembro|dezembro"
)
_DATE_TEXT = re.compile(rf"\b\d{{1,2}}\s+de\s+(?:{_MONTHS})\s+de\s+\d{{4}}\b", re.IGNORECASE)


def normalize_text(text: str) -> str:
    """Lowercase, collapse whitespace/newlines, strip control chars.

    Keeps letters, digits, common Portuguese punctuation relevant to legal text.
    """
    if not text:
        return ""
    # Normalize unicode (NFKC) so visually-equal chars compare equal.
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    # Remove control characters except newline/tab.
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or not unicodedata.category(ch).startswith("C"))
    # Normalize newlines and collapse 3+ blank lines.
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Trim trailing spaces per line.
    text = "\n".join(line.strip() for line in text.split("\n"))
    return text.strip()


def mask_variable_data(text: str) -> str:
    """Replace dates, money, process numbers and CPF/CNPJ with placeholders.

    Applied on already-normalized (lowercased) text.
    """
    if not text:
        return ""
    text = _DATE_TEXT.sub(" DATA ", text)
    text = _PROCESS.sub(" NUMERO_PROCESSO ", text)
    text = _CNPJ.sub(" CNPJ ", text)
    text = _CPF.sub(" CPF ", text)
    text = _MONEY_PREFIX.sub(" VALOR_MONETARIO ", text)
    text = _MONEY.sub(" VALOR_MONETARIO ", text)
    text = _DATE_NUMERIC.sub(" DATA ", text)
    # Collapse spaces produced by substitutions.
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()
