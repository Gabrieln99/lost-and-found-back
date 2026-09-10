import pytest

from app.messages_db import DuplicateMessageError, fetch_messages, init_db, insert_message


@pytest.fixture
async def conn():
    connection = await init_db(":memory:")
    yield connection
    await connection.close()


async def test_fetch_messages_is_empty_for_a_listing_with_none(conn):
    messages = await fetch_messages(conn, 1)
    assert messages == []


async def test_insert_then_fetch_round_trips(conn):
    record = await insert_message(
        conn, listing_id=1, sender="0xSender", body="Meet at noon", timestamp=1_700_000_000
    )

    assert record["id"] is not None
    assert record["listing_id"] == 1
    assert record["sender"] == "0xSender"
    assert record["body"] == "Meet at noon"
    assert record["timestamp"] == 1_700_000_000

    messages = await fetch_messages(conn, 1)
    assert messages == [record]


async def test_fetch_only_returns_messages_for_the_requested_listing(conn):
    await insert_message(conn, listing_id=1, sender="0xA", body="for listing 1", timestamp=100)
    await insert_message(conn, listing_id=2, sender="0xA", body="for listing 2", timestamp=200)

    messages = await fetch_messages(conn, 1)

    assert len(messages) == 1
    assert messages[0]["body"] == "for listing 1"


async def test_fetch_orders_chronologically(conn):
    await insert_message(conn, listing_id=1, sender="0xA", body="third", timestamp=300)
    await insert_message(conn, listing_id=1, sender="0xA", body="first", timestamp=100)
    await insert_message(conn, listing_id=1, sender="0xA", body="second", timestamp=200)

    messages = await fetch_messages(conn, 1)

    assert [m["body"] for m in messages] == ["first", "second", "third"]


async def test_duplicate_listing_sender_timestamp_is_rejected(conn):
    await insert_message(conn, listing_id=1, sender="0xA", body="original", timestamp=100)

    with pytest.raises(DuplicateMessageError):
        await insert_message(conn, listing_id=1, sender="0xA", body="replay attempt", timestamp=100)

    # The rejected duplicate must not have been recorded either.
    messages = await fetch_messages(conn, 1)
    assert len(messages) == 1
    assert messages[0]["body"] == "original"


async def test_same_sender_and_timestamp_but_different_listing_is_allowed(conn):
    await insert_message(conn, listing_id=1, sender="0xA", body="for listing 1", timestamp=100)
    # Same sender/timestamp, different listing -- not a replay, should succeed.
    await insert_message(conn, listing_id=2, sender="0xA", body="for listing 2", timestamp=100)

    assert len(await fetch_messages(conn, 1)) == 1
    assert len(await fetch_messages(conn, 2)) == 1
