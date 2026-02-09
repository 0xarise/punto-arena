# Punto Arena - Definition of Done (Agent Track)

Data stamp: `2026-02-07`

Use this checklist as the final go/no-go gate before hackathon submission.

## P0 Must-Have (No-Go if any unchecked)

- [ ] Security: no hardcoded secrets in repo; rotated keys; `.env.example` complete.
- [ ] LLM decisions: official submitted matches run in `STRICT_LLM` mode (no rule fallback in official evidence runs).
- [ ] On-chain lifecycle: every official match completes `createGame -> joinGame -> submitResult -> verify`.
- [ ] Minimum matches: at least 5 completed official matches.
- [ ] Public verification: full tx hashes + explorer links for all official matches.
- [ ] Performance proof: neutral or positive winrate shown on a multi-match series (recommended 10+).
- [ ] Evidence artifacts: generated `evidence/matches.jsonl` and `evidence/summary.csv`.
- [ ] Submission docs: `README.md` and `HACKATHON_SUBMISSION.md` are aligned with implementation and evidence.

## Quality Gate (Technical)

- [ ] `hackathon_matches.py` prints/saves full tx hashes (not truncated).
- [ ] Every logged move includes `model`, `decision_source`, `reasoning`, `timestamp`.
- [ ] Pre-submit sanity checks pass:
- [ ] `python3 -m py_compile hackathon_matches.py`
- [ ] `python3 -m py_compile ai_player.py`
- [ ] Required env vars are present for selected engines and wallets.

## Demo Gate (Judge-Friendly)

- [ ] 60-120s demo video: run start, gameplay, tx confirmation, payout verification.
- [ ] One screenshot or table with final scoreboard + explorer links.
- [ ] Repro steps in docs are short and executable (1-2 commands preferred).

## Optional Nice-to-Have

- [ ] Opponent adaptation enabled and documented.
- [ ] Bankroll/risk policy enabled and documented.
- [ ] Human-vs-AI web mode and AI-vs-AI mode both exposed from one unified UX.
- [ ] Frontend leaderboard with ELO score and last N match history.
- [ ] Leaderboard API includes proof fields (`match_id`, `winner`, `tx_hash`) for transparency.

## Hack Tests (Frontend / Realtime)

- [ ] Chaos suite passes on current build (`test_frontend_chaos.py` full run, not only fast mode).
- [ ] Refresh storm: no duplicated moves, no broken turn state.
- [ ] Reconnect race: rejoin restores correct role/cards/turn and does not fork game state.
- [ ] Click spam / duplicate events: server accepts at most one valid move per turn.
- [ ] Invalid payload fuzz: bad card/coords/role cannot crash server and returns controlled error.
- [ ] Stale room/session attempts are rejected safely.

## Contract Hardening Tests

- [ ] Unauthorized `submitResult` reverts (only oracle allowed).
- [ ] `joinGame` with wrong wager reverts.
- [ ] `submitResult` cannot be called twice for same game.
- [ ] Cancel/refund paths enforce correct state and timeout rules.
- [ ] Payout accounting invariant holds: `winner_payout + protocol_fee == total_pot`.
- [ ] Malicious receiver test (revert on receive) does not brick contract lifecycle.
- [ ] Oracle rotation/admin paths tested for access control.

## Evidence of Hardening

- [ ] `security/HARDENING_REPORT.md` with test matrix and pass/fail results.
- [ ] Include exact commands used to run tests and environment assumptions.
- [ ] Link hardening results in `HACKATHON_SUBMISSION.md`.

## Go / No-Go Rule

- [ ] GO: all P0 items checked.
- [ ] NO-GO: if any P0 item remains unchecked.

## Owner Split

- [ ] Developer owner: implementation, logging, docs consistency, evidence generation.
- [ ] Team owner: key rotation, funded wallets, final real on-chain run, final submission upload.
