import pytest

from app.contract_reader import ContractReader, ContractReadError, ListingNotFoundError

TEST_ADDRESS = "0x1945e05F857505C4282168d7Fa2974b36353B8d1"


class _FakeCall:
    def __init__(self, result=None, exception=None):
        self._result = result
        self._exception = exception

    async def call(self):
        if self._exception is not None:
            raise self._exception
        return self._result


class _FakeFunctions:
    def __init__(
        self,
        listing_count=0,
        listing_count_exception=None,
        listing_result=None,
        listings_exception=None,
    ):
        self._listing_count = listing_count
        self._listing_count_exception = listing_count_exception
        self._listing_result = listing_result
        self._listings_exception = listings_exception

    def listingCount(self):
        return _FakeCall(result=self._listing_count, exception=self._listing_count_exception)

    def listings(self, _listing_id):
        return _FakeCall(result=self._listing_result, exception=self._listings_exception)


class _FakeContract:
    def __init__(self, **kwargs):
        self.functions = _FakeFunctions(**kwargs)


def make_reader(**fake_functions_kwargs):
    # Construction does no network I/O (verified: AsyncHTTPProvider/
    # AsyncWeb3 build lazily), so a real ContractReader can be built here
    # and just have its internal contract swapped for a fake.
    reader = ContractReader("http://rpc.example", TEST_ADDRESS)
    reader._contract = _FakeContract(**fake_functions_kwargs)
    return reader


async def test_returns_owner_and_finder_for_an_existing_listing():
    owner = "0xOwner0000000000000000000000000000000001"
    finder = "0xFinder000000000000000000000000000000002"
    reader = make_reader(
        listing_count=5,
        listing_result=(owner, finder, 0, "bafycid", 1, 0, 0),
    )

    result_owner, result_finder = await reader.get_listing_parties(2)

    assert result_owner == owner
    assert result_finder == finder


async def test_raises_listing_not_found_when_id_is_at_or_past_the_count():
    reader = make_reader(listing_count=3)

    with pytest.raises(ListingNotFoundError):
        await reader.get_listing_parties(3)


async def test_raises_listing_not_found_without_ever_calling_listings(monkeypatch):
    reader = make_reader(listing_count=3)
    called = False

    async def fail_if_called():
        nonlocal called
        called = True
        raise AssertionError("listings() should not be called for an out-of-range id")

    reader._contract.functions.listings = lambda _id: type(
        "_", (), {"call": staticmethod(fail_if_called)}
    )()

    with pytest.raises(ListingNotFoundError):
        await reader.get_listing_parties(10)
    assert called is False


async def test_wraps_a_listing_count_rpc_failure_as_contract_read_error():
    reader = make_reader(listing_count_exception=RuntimeError("RPC unavailable"))

    with pytest.raises(ContractReadError):
        await reader.get_listing_parties(0)


async def test_wraps_a_listings_rpc_failure_as_contract_read_error():
    reader = make_reader(listing_count=5, listings_exception=RuntimeError("RPC unavailable"))

    with pytest.raises(ContractReadError):
        await reader.get_listing_parties(1)
