from display.core.db import quote_ident


def test_quote_ident_quotes_simple_identifier():
    assert quote_ident("name") == '"name"'


def test_quote_ident_preserves_mixed_case():
    assert quote_ident("MixedCase") == '"MixedCase"'


def test_quote_ident_quotes_reserved_word():
    assert quote_ident("select") == '"select"'


def test_quote_ident_quotes_invalid_looking_identifier_safely():
    assert quote_ident("bad;name") == '"bad;name"'


def test_quote_ident_escapes_embedded_quote():
    assert quote_ident('has"quote') == '"has""quote"'
