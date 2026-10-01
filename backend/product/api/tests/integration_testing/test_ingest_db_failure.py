def test_ingest_db_failure(client, monkeypatch):
    """Test ingesting data when the database is down returns an error."""