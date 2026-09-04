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

## Storage service

`storage-service/` is an aiohttp REST API. This first pass only handles
image upload: `POST /upload` (multipart/form-data, field name `file`)
uploads an image to Pinata and returns its IPFS CID. Owner/finder
contact storage (SQLite) isn't built yet.

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
