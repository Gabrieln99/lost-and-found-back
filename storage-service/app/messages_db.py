import aiosqlite

# Minimal by design -- see CLAUDE.md's storage-service section: this is
# "temporary" owner<->finder contact storage, not a permanent record. The
# UNIQUE constraint rejects an exact replay of a previously accepted
# signed message (same listing, sender, and timestamp) outright.
SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL,
    sender TEXT NOT NULL,
    body TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    UNIQUE (listing_id, sender, timestamp)
);
CREATE INDEX IF NOT EXISTS idx_messages_listing_id ON messages (listing_id);
"""


class DuplicateMessageError(Exception):
    """Raised when a message with the same (listing_id, sender, timestamp)
    has already been recorded -- an exact replay of a previously accepted
    signed message, not a new one."""


async def init_db(db_path: str) -> aiosqlite.Connection:
    """Opens (creating if needed) the messages database and ensures its
    schema exists. Callers own the returned connection's lifetime -- keep
    it open for the app's lifetime (see __init__.py's cleanup_ctx) rather
    than reopening per request, since ":memory:" databases (used by tests)
    only persist for as long as their one connection stays open."""
    conn = await aiosqlite.connect(db_path)
    await conn.executescript(SCHEMA)
    await conn.commit()
    return conn


async def insert_message(
    conn: aiosqlite.Connection, *, listing_id: int, sender: str, body: str, timestamp: int
) -> dict:
    try:
        cursor = await conn.execute(
            "INSERT INTO messages (listing_id, sender, body, timestamp) VALUES (?, ?, ?, ?)",
            (listing_id, sender, body, timestamp),
        )
        await conn.commit()
    except aiosqlite.IntegrityError as exc:
        raise DuplicateMessageError(str(exc)) from exc

    return {
        "id": cursor.lastrowid,
        "listing_id": listing_id,
        "sender": sender,
        "body": body,
        "timestamp": timestamp,
    }


async def fetch_messages(conn: aiosqlite.Connection, listing_id: int) -> list[dict]:
    cursor = await conn.execute(
        "SELECT id, listing_id, sender, body, timestamp FROM messages "
        "WHERE listing_id = ? ORDER BY timestamp ASC, id ASC",
        (listing_id,),
    )
    rows = await cursor.fetchall()
    return [
        {"id": row[0], "listing_id": row[1], "sender": row[2], "body": row[3], "timestamp": row[4]}
        for row in rows
    ]
