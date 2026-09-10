# lost-and-found-back

Smart contract, storage service, and background listener for the Lost &
Found dApp. See the root project's `CLAUDE.md` / `AGENTS.md` for full
architecture and conventions.

## Smart contract

`contracts/LostAndFound.sol` escrows a reward (ETH) for a lost item until
the owner confirms recovery.

Listing lifecycle: `Open → Reported → Resolved`, plus `Reported → Open`
(owner rejects a false find) and `Open → Cancelled` (owner self-refunds
before anyone reports).

### Commands

```bash
npm install
npm run compile   # npx hardhat compile
npm run test      # npx hardhat test
npm run lint      # npx solhint 'contracts/**/*.sol'
npm run coverage  # npx hardhat coverage
```

Deploy locally:

```bash
npx hardhat run scripts/deploy.js
```

Deployed to Sepolia — see `deployments/sepolia.json` for the address,
transaction hash, and block explorer link.

Independently verify any `createListing` transaction's on-chain state
(status, owner, itemCID, reward, timestamps) — reads the deployed address
from `deployments/sepolia.json` by default:

```bash
TX_HASH=0x... npx hardhat run scripts/check-listing.js --network sepolia
```

Requires `SEPOLIA_RPC_URL` in `.env` (root of this repo, not
`storage-service/.env`) — read-only, no private key needed.

## Storage service

`storage-service/` is an aiohttp REST API.

- `POST /upload` (multipart/form-data, field `file`) — pins a raw image to
  Pinata, returns its IPFS CID. Generic utility.
- `POST /listing-metadata` (multipart/form-data, fields `file`, `title`,
  `description`, `location`) — pins the image, bundles it with the text
  fields into a JSON document (`{title, description, location, image:
  "ipfs://<image CID>"}`), pins that JSON too, and returns the JSON's CID.
  This is the CID the frontend passes on-chain as `createListing`'s
  `itemCID`.
- `POST /listings/{listingId}/messages` and
  `GET /listings/{listingId}/messages` — owner↔finder handover chat,
  SQLite-backed. No login system: a wallet signature over a canonical
  message IS the authentication. See "Messaging signature format" below
  for the exact format the frontend must replicate byte-for-byte, and the
  root `CLAUDE.md`'s storage-service section for the full design
  rationale (why reads also require a signature, replay-resistance
  tradeoffs, etc.).

### Messaging signature format

To **send** a message, sign (EIP-191 `personal_sign` — e.g. ethers.js
`signer.signMessage(...)`, or MetaMask's `personal_sign`) this exact
string, then `POST` it as JSON:

```
lost-and-found:message:v1:{listingId}:{timestamp}:{body}
```

```json
POST /listings/{listingId}/messages
{ "timestamp": 1700000000, "body": "Meet at the fountain at noon", "signature": "0x..." }
```

- `listingId` and `timestamp` in the signed string are plain decimal
  integers (no separators/padding); `timestamp` is Unix epoch **seconds**
  (not milliseconds).
- `body` is signed and sent **exactly as-is** — do not trim or otherwise
  modify it between signing and sending; the server reconstructs the same
  string from the request and will fail to match the signature otherwise.
- `timestamp` must be within 5 minutes of the server's clock.
- The server recovers the signer from the signature and independently
  checks (on-chain) that they're the listing's owner or finder — nothing
  about identity is trusted from the request itself.

To **read** a thread, sign a *different* string (so a read signature can
never be replayed as a message send, or vice versa) and pass it as query
params:

```
lost-and-found:read-messages:v1:{listingId}:{timestamp}
```

```
GET /listings/{listingId}/messages?timestamp=1700000000&signature=0x...
```

Response: `{ "messages": [{ "id", "listingId", "sender", "body",
"timestamp" }, ...] }`, chronological order.

### Commands

```bash
cd storage-service
python -m venv .venv
.venv/Scripts/activate       # .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
cp .env.example .env         # fill in PINATA_JWT, SEPOLIA_RPC_URL
pytest
ruff check .
docker build -t lost-and-found-back .
```

Run locally: `python run.py` (serves on port 8080).
