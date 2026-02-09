# Punto Arena - Security Hardening Report

**Date:** 2026-02-09
**Contract:** `0xF057f5bc20533eeBD669A6fDb9792620F9e2C240` (v2.0)
**Chain:** Monad Mainnet (Chain ID: 143)

---

## 1. Smart Contract Security Tests

All tests executed on-chain against the deployed v2.0 contract.

| # | Test | Expected | Result |
|---|------|----------|--------|
| 1 | Unauthorized `submitResult` (non-oracle) | Revert "Only oracle" | PASS |
| 2 | `joinGame` with wrong wager amount | Revert "Wrong wager amount" | PASS |
| 3 | Double `submitResult` on same game | Revert "Game not active" | PASS |
| 4 | `claimRefund` before 30min timeout | Revert "Refund not available yet" | PASS |
| 5 | Payout accounting: `payout + fee == totalPot` | True, fee = 5% | PASS |

**Result: 5/5 PASS**

### Contract Architecture Notes
- Oracle-only result submission prevents unauthorized payouts
- State machine guards prevent double-spend and re-entrancy on results
- Time-locked refund mechanism protects players in stuck games
- 5% protocol fee (500 bps) with max cap of 10% (enforced by `setProtocolFee`)
- Minimum wager of 0.001 MON prevents spam attacks

---

## 2. Server-Side Security (app_wagering.py)

### Fixes Applied

| Issue | Before | After | Status |
|-------|--------|-------|--------|
| CORS wildcard | `cors_allowed_origins="*"` | Whitelist: localhost:8000 | FIXED |
| Turn enforcement | No server-side check | `current_turn == player_role` check before move | FIXED |
| Move rate limiting | None | 500ms cooldown per player | FIXED |

### Turn Enforcement Detail
- Server validates `room['current_turn'] == player_role` before accepting any move
- Rejects out-of-turn moves with `"Not your turn"` error
- Prevents race conditions in rapid-fire move scenarios

### Rate Limiting Detail
- Per-session 500ms cooldown between moves
- Prevents click-spam attacks
- Returns `"Too fast, wait a moment"` error to client

---

## 3. Frontend Chaos Tests (test_frontend_chaos.py)

10-test suite covering edge cases:

| # | Test | Description |
|---|------|-------------|
| 1 | Refresh Storm | 5 rapid F5 reconnects during game |
| 2 | WebSocket Chaos | Random disconnect/reconnect mid-turn |
| 3 | Double Tab | Same wallet on 2 connections |
| 4 | Click Spam | 10x rapid same-move submissions |
| 5 | Reconnect Race | Both players disconnect, reconnect randomly |
| 6 | Mid-Move Disconnect | Send move then immediately disconnect |
| 7 | Stale Session | Rejoin after game ends / nonexistent room |
| 8 | Concurrent Joins | 3 players join 2-player room simultaneously |
| 9 | Rapid Room Creation | 10 rooms created rapidly |
| 10 | Invalid Moves | 7 types of malformed payloads |

**Note:** These tests require a running server instance. Run with:
```bash
python app_wagering.py &  # Start server
python test_frontend_chaos.py  # Run all tests
```

---

## 4. Credential Security

### Issues Found & Fixed

| Issue | Severity | Status |
|-------|----------|--------|
| Plaintext private keys in SUBMISSION_CHECKLIST.md | CRITICAL | FIXED - Replaced with `<REDACTED>` |
| Plaintext API keys in SUBMISSION_CHECKLIST.md | HIGH | FIXED - Replaced with `<REDACTED>` |
| Keys stored in `.env` (gitignored) | LOW | OK - Standard practice |

### Recommendations
- Rotate all exposed keys before production deployment
- Use environment variable injection (not files) in production
- Add `.env` to `.gitignore` (verify)

---

## 5. Architecture Security Summary

### Strengths
- Oracle-controlled result submission (single point of trust)
- On-chain escrow (funds locked until game resolution)
- Time-locked refund prevents permanent fund lockup
- Server-side move validation prevents client-side manipulation
- Rate limiting prevents DoS via move spam

### Known Limitations (Acceptable for Hackathon)
- Single oracle (centralization risk) - noted in contract comments as "upgradeable to multi-sig"
- No replay protection on WebSocket events (mitigated by turn enforcement)
- No IP-based rate limiting (only per-session)

---

## 6. Test Reproduction

```bash
# Contract hardening tests
python test_contract_hardening.py

# Frontend chaos tests (requires running server)
python app_wagering.py &
python test_frontend_chaos.py

# ELO verification
python elo.py
```

---

*Generated: 2026-02-09 | Punto Arena v2.0*
