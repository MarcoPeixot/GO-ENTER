from app.normalization import mask_variable_data, normalize_text


def _mask(text):
    return mask_variable_data(normalize_text(text))


def test_masks_money_and_date():
    out = _mask("João da Silva pagará R$ 10.000,00 em 10/03/2026")
    assert "VALOR_MONETARIO" in out
    assert "DATA" in out
    assert "10.000,00" not in out
    assert "10/03/2026" not in out


def test_masks_cpf_and_cnpj():
    out = _mask("CPF 123.456.789-09 e CNPJ 12.345.678/0001-95")
    assert "CPF" in out
    assert "CNPJ" in out
    assert "123.456.789-09" not in out
    assert "12.345.678/0001-95" not in out


def test_masks_process_number():
    out = _mask("Processo nº 0001234-56.2026.8.26.0100 distribuído")
    assert "NUMERO_PROCESSO" in out
    assert "0001234-56.2026.8.26.0100" not in out


def test_masks_written_date():
    out = _mask("assinado em 10 de março de 2026 nesta cidade")
    assert "DATA" in out
    assert "março de 2026" not in out


def test_stable_across_value_changes():
    # Same template, different variable values -> identical masked text.
    a = _mask("pagamento de R$ 1.000,00 em 01/01/2026")
    b = _mask("pagamento de R$ 9.999,99 em 31/12/2030")
    assert a == b
