import pytest


@pytest.fixture(autouse=True)
def _default_messages_db_path(monkeypatch):
    """Every app built via create_app() now also opens the messages
    database (app/messages_db.py's cleanup_ctx). Default it to an
    in-memory database for every test, so tests that don't care about
    messaging at all (upload, CORS, rate-limit, etc.) never create a
    stray messages.db file on disk. Tests that do care can still override
    this with their own monkeypatch.setenv("MESSAGES_DB_PATH", ...)."""
    monkeypatch.setenv("MESSAGES_DB_PATH", ":memory:")
