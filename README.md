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
