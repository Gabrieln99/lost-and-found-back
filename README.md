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

`storage-service/` is an aiohttp REST API. Owner/finder contact storage
(SQLite) isn't built yet. Two endpoints so far:

- `POST /upload` (multipart/form-data, field `file`) — pins a raw image to
  Pinata, returns its IPFS CID. Generic utility.
- `POST /listing-metadata` (multipart/form-data, fields `file`, `title`,
  `description`, `location`) — pins the image, bundles it with the text
  fields into a JSON document (`{title, description, location, image:
  "ipfs://<image CID>"}`), pins that JSON too, and returns the JSON's CID.
  This is the CID the frontend passes on-chain as `createListing`'s
  `itemCID`.

### Commands

```bash
cd storage-service
python -m venv .venv
.venv/Scripts/activate       # .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
cp .env.example .env         # fill in PINATA_JWT
pytest
ruff check .
docker build -t lost-and-found-back .
```

Run locally: `python run.py` (serves on port 8080).
