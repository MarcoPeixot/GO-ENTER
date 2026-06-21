from app.normalization import normalize_text


def test_lowercases_and_collapses_whitespace():
    out = normalize_text("CONTRATO   de    Prestação\t\tDE Serviços")
    assert out == "contrato de prestação de serviços"


def test_normalizes_newlines_and_trims():
    out = normalize_text("  linha um  \r\n\r\n\r\n\r\nlinha dois  ")
    # 4 blank lines collapse to a single blank line (paragraph break preserved).
    assert out == "linha um\n\nlinha dois"


def test_empty_input():
    assert normalize_text("") == ""
    assert normalize_text(None) == ""


def test_preserves_legal_punctuation():
    out = normalize_text("Art. 5º, inciso II - direitos.")
    assert "art." in out
    assert "inciso ii" in out
