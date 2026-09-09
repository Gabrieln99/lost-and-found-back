from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider

# Just enough of LostAndFound's ABI to read a listing's owner/finder and
# the total listing count -- mirrors scripts/check-listing.js's read-only
# usage of the same public getters, adapted to web3.py's async API (rather
# than ethers/Hardhat) so a chain read never blocks aiohttp's event loop.
# Field order matches the Listing struct in contracts/LostAndFound.sol.
LISTINGS_ABI = [
    {
        "inputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "name": "listings",
        "outputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "address", "name": "finder", "type": "address"},
            {"internalType": "uint256", "name": "reward", "type": "uint256"},
            {"internalType": "string", "name": "itemCID", "type": "string"},
            {"internalType": "uint8", "name": "status", "type": "uint8"},
            {"internalType": "uint256", "name": "createdAt", "type": "uint256"},
            {"internalType": "uint256", "name": "expirationTimestamp", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "listingCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class ContractReadError(Exception):
    """Raised on any RPC/network failure reading from the chain."""


class ListingNotFoundError(Exception):
    """Raised when listing_id >= the on-chain listing count."""


class ContractReader:
    """Thin, read-only async wrapper around the deployed LostAndFound
    contract -- just enough to look up a listing's owner/finder for
    message authorization. Holds one AsyncWeb3 instance (and its
    connection-pooled HTTP session) for the app's lifetime; see
    close()."""

    def __init__(self, rpc_url: str, contract_address: str):
        self._provider = AsyncHTTPProvider(rpc_url)
        self._web3 = AsyncWeb3(self._provider)
        self._contract = self._web3.eth.contract(
            address=AsyncWeb3.to_checksum_address(contract_address),
            abi=LISTINGS_ABI,
        )

    async def get_listing_parties(self, listing_id: int) -> tuple[str, str]:
        """Returns (owner, finder) addresses for listing_id.
        Raises ListingNotFoundError if it doesn't exist on-chain, or
        ContractReadError on any RPC/network failure."""
        try:
            count = await self._contract.functions.listingCount().call()
            if listing_id >= count:
                raise ListingNotFoundError(f"Listing {listing_id} does not exist")

            owner, finder, *_rest = await self._contract.functions.listings(listing_id).call()
        except ListingNotFoundError:
            raise
        except Exception as exc:
            raise ContractReadError(
                f"Failed to read listing {listing_id} from chain: {exc}"
            ) from exc

        return owner, finder

    async def close(self) -> None:
        await self._provider.disconnect()
