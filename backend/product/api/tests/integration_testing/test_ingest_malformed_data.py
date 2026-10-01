def test_ingest_malformed_data(client, monkeypatch, caplog):
    """Test ingesting malformed data returns an error."""