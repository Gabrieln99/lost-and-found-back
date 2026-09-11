# Lost and Found aplikacija — projekt README

Lost & Found je decentralizirana aplikacija za oglašavanje i pronalazak izgubljenih stvari. Vlasnik objavi što je izgubio i zaključa nagradu u pametnom ugovoru na blockchainu; novac automatski ode nalazniku tek kad vlasnik potvrdi da je stvar stvarno vratio, bez ikakvog posrednika koji uzima proviziju.
Sustav je podijeljen na više neovisnih mikroservisa: frontend, storage servis (to je ovaj repozitorij koji upravlja slikama i porukama), i sam pametni ugovor — komunikacija između korisnika i tih dijelova ide preko MetaMask walleta.

Projekt je izrađen u sklopu kolegija Raspodijeljeni sustavi i Blockchain aplikacije.

## Live

- Storage service: https://lost-and-found-storage.onrender.com
- Contract (Sepolia): [`0x1945e05F857505C4282168d7Fa2974b36353B8d1`](https://sepolia.etherscan.io/address/0x1945e05F857505C4282168d7Fa2974b36353B8d1)
- Frontend repository: https://github.com/Gabrieln99/lost-and-found-front
- Shared project docs: https://github.com/Gabrieln99/lost-and-found-project (sadrži dokumentaciju ovog projekta)

## Tech stack

(ovo su tehnologije koje sam koristio)
- Solidity, Hardhat, OpenZeppelin `ReentrancyGuard`, Solhint, `solidity-coverage`
- aiohttp, Pydantic, SQLite
- Pinata (IPFS pinning)

## Smart contract

`contracts/LostAndFound.sol` čuva nagradu (ETH) u depozitu dok vlasnik ne potvrdi pronalazak.

Stanja oglasa: `Open → Reported → Resolved`, plus `Reported → Open` (vlasnik odbija lažnu prijavu) i `Open → Cancelled` (vlasnik otkazuje oglas i vraća sebi nagradu prije nego itko prijavi pronalazak).

Deployano na Sepoliju: [`0x1945e05F857505C4282168d7Fa2974b36353B8d1`](https://sepolia.etherscan.io/address/0x1945e05F857505C4282168d7Fa2974b36353B8d1).

### Komande

```bash
npm install
npm run compile
npm run test
npm run lint
npm run coverage
```

Deploy ide isključivo preko GitHub Actions (`workflow_dispatch`) za pravi Sepolia deploy. Za lokalno testiranje:

```bash
npx hardhat run scripts/deploy.js
```

(cilja na Hardhatovu lokalnu in-memory mrežu, ne Sepoliju)

Provjera stanja bilo koje `createListing` transakcije na blockchainu (status, owner, itemCID, reward, timestamps) — po defaultu čita deployanu adresu iz `deployments/sepolia.json`:

```bash
TX_HASH=0x... npx hardhat run scripts/check-listing.js --network sepolia
```

Zahtijeva `SEPOLIA_RPC_URL` u `.env` (root ovog repozitorija, ne `storage-service/.env`) — samo za čitanje, privatni ključ nije potreban.

## Storage service

`storage-service/` je aiohttp REST API — sprema slike i podatke o oglasu na IPFS (Pinata), i čuva poruke između vlasnika i nalaznika u SQLite bazi. Bez sustava za prijavu: poruke se autentificiraju potpisom walleta, ne lozinkom — točan format je u nastavku.

Deployano na: https://lost-and-found-storage.onrender.com

- `POST /upload` — sprema sliku, vraća njen CID.
- `POST /listing-metadata` — sprema sliku + naslov/opis/lokaciju kao jedan JSON dokument, vraća njegov CID.
- `POST` / `GET /listings/{id}/messages` — chat između vlasnika i nalaznika.

### Format potpisa za poruke

Za slanje poruke potpisuje se (EIP-191 `personal_sign`) točno ovaj string:

```
lost-and-found:message:v1:{listingId}:{timestamp}:{body}
```

`timestamp` je Unix vrijeme u sekundama i mora biti unutar 5 minuta od vremena na serveru; `body` se šalje točno onakav kakav je potpisan, bez izmjena. Server iz potpisa izvuče adresu potpisnika i provjeri na blockchainu da je vlasnik ili nalaznik tog oglasa.

Za čitanje poruka (`GET`) potpisuje se drugačiji string — tako se potpis za čitanje ne može iskoristiti za slanje poruke, i obrnuto:

```
lost-and-found:read-messages:v1:{listingId}:{timestamp}
```

### Komande

```bash
cd storage-service
pip install -r requirements-dev.txt
cp .env.example .env
pytest
ruff check .
python run.py
```
