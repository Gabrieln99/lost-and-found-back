# Lost and Found aplikacija — projekt README

Lost & Found je decentralizirana aplikacija za oglašavanje i pronalazak izgubljenih stvari. Vlasnik objavi što je izgubio i zaključa nagradu u pametnom ugovoru na blockchainu; novac automatski ode nalazniku tek kad vlasnik potvrdi da je stvar stvarno vratio, bez ikakvog posrednika koji uzima proviziju. Sustav je podijeljen na više neovisnih mikroservisa: frontend (zaseban repozitorij), storage servis koji ovaj repozitorij sadrži (upravlja slikama i porukama), i sam pametni ugovor — komunikacija između korisnika i tih dijelova ide preko MetaMask walleta.

Projekt je izrađen u sklopu kolegija Raspodijeljeni sustavi i Blockchain aplikacije.

## Live

- Storage service: https://lost-and-found-storage.onrender.com
- Contract (Sepolia): [`0x1945e05F857505C4282168d7Fa2974b36353B8d1`](https://sepolia.etherscan.io/address/0x1945e05F857505C4282168d7Fa2974b36353B8d1)
- Frontend repository: https://github.com/Gabrieln99/lost-and-found-front
- Shared project docs: https://github.com/Gabrieln99/lost-and-found-project

## Tech stack

- Solidity, Hardhat, OpenZeppelin `ReentrancyGuard`, Solhint, `solidity-coverage`
- aiohttp, Pydantic, SQLite
- Pinata (IPFS pinning)

## Smart contract

`contracts/LostAndFound.sol` escrows a reward (ETH) for a lost item until the owner confirms recovery.

Listing lifecycle: `Open -> Reported -> Resolved`, plus `Reported -> Open` (owner rejects a false find) and `Open -> Cancelled` (owner self-refunds before anyone reports).

Deployed to Sepolia at [`0x1945e05F857505C4282168d7Fa2974b36353B8d1`](https://sepolia.etherscan.io/address/0x1945e05F857505C4282168d7Fa2974b36353B8d1) (see `deployments/sepolia.json` for the deployer address and transaction hash).

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

This targets Hardhat's default local network (an ephemeral in-memory chain, reset on every run) — it's for local testing only. The real Sepolia deploy happens exclusively via the `workflow_dispatch` GitHub Action (`.github/workflows/deploy-sepolia.yml`), never via this command directly.

Verify any `createListing` transaction's on-chain state (status, owner, itemCID, reward, timestamps) — reads the deployed address from `deployments/sepolia.json` by default:

```bash
TX_HASH=0x... npx hardhat run scripts/check-listing.js --network sepolia
```

Requires `SEPOLIA_RPC_URL` in `.env` (root of this repo, not `storage-service/.env`) — read-only, no private key needed.

## Storage service

`storage-service/` is an aiohttp REST API. It pins images and listing metadata to IPFS via Pinata, and stores owner-finder handover messages in SQLite.

Deployed at https://lost-and-found-storage.onrender.com.

- `POST /upload` (multipart/form-data, field `file`) — pins a raw image to Pinata, returns its IPFS CID.
- `POST /listing-metadata` (multipart/form-data, fields `file`, `title`, `description`, `location`) — pins the image, bundles it with the text fields into a JSON document (`{title, description, location, image: "ipfs://<image CID>"}`), pins that JSON too, and returns the JSON's CID — the CID the frontend passes on-chain as `createListing`'s `itemCID`.
- `POST /listings/{listingId}/messages` and `GET /listings/{listingId}/messages` — owner-finder handover chat, SQLite-backed. No login system: a wallet signature over a canonical message IS the authentication. See "Messaging signature format" below.

### Messaging signature format

To send a message, sign (EIP-191 `personal_sign` — e.g. ethers.js `signer.signMessage(...)`, or MetaMask's `personal_sign`) this exact string, then `POST` it as JSON:

```
lost-and-found:message:v1:{listingId}:{timestamp}:{body}
```

```json
POST /listings/{listingId}/messages
{ "timestamp": 1700000000, "body": "Meet at the fountain at noon", "signature": "0x..." }
```

- `listingId` and `timestamp` in the signed string are plain decimal integers (no separators/padding); `timestamp` is Unix epoch seconds (not milliseconds).
- `body` is signed and sent exactly as-is — do not trim or otherwise modify it between signing and sending; the server reconstructs the same string from the request and will fail to match the signature otherwise.
- `timestamp` must be within 5 minutes of the server's clock.
- The server recovers the signer from the signature and independently checks (on-chain) that they're the listing's owner or finder — nothing about identity is trusted from the request itself.

To read a thread, sign a different string (so a read signature can never be replayed as a message send, or vice versa) and pass it as query params:

```
lost-and-found:read-messages:v1:{listingId}:{timestamp}
```

```
GET /listings/{listingId}/messages?timestamp=1700000000&signature=0x...
```

Response: `{ "messages": [{ "id", "listingId", "sender", "body", "timestamp" }, ...] }`, chronological order.

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
