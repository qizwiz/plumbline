# ScaBench baseline sweep — 2026-06-20

**GPT-5 confidence-ordered baseline through `gpt-4o-mini` judge on `scorer_v2.py`.**

- Projects: 31
- Macro F1: **0.2537**
- Median F1: 0.2400
- Macro precision: 0.2566
- Macro recall: 0.3737
- Stdev F1: 0.1247

This is the missing baseline-anchor flagged in `scorecard.md` ("did not run baseline GPT-5-confidence-ordered through same judge"). It is the comparator for any plumbline re-rank or filter intervention.

## Per-project

| F1 | Project | Expected | Found | TP | FP | FN |
|---:|---|---:|---:|---:|---:|---:|
| 0.600 | `code4rena_forte-float128-solidity-library_2025_04` | 12 | 8 | 6 | 2 | 6 |
| 0.483 | `sherlock_cork-protocol_2025_01` | 18 | 40 | 14 | 26 | 4 |
| 0.467 | `code4rena_pump-science_2025_02` | 17 | 13 | 7 | 6 | 10 |
| 0.400 | `sherlock_oku_2024_12` | 19 | 26 | 9 | 17 | 10 |
| 0.353 | `sherlock_tally_2024_12` | 11 | 6 | 3 | 3 | 8 |
| 0.326 | `sherlock_20240920---final---boost-core-incentive-protocol-audit-report_2024_09` | 7 | 36 | 7 | 29 | 0 |
| 0.318 | `code4rena_coded-estate-invitational_2024_12` | 33 | 11 | 7 | 4 | 26 |
| 0.308 | `code4rena_liquid-ron_2025_03` | 5 | 8 | 2 | 6 | 3 |
| 0.304 | `code4rena_kinetiq_2025_07` | 25 | 21 | 7 | 14 | 18 |
| 0.304 | `code4rena_blackhole_2025_07` | 37 | 121 | 24 | 97 | 13 |
| 0.296 | `code4rena_lambowin_2025_02` | 14 | 13 | 4 | 9 | 10 |
| 0.294 | `code4rena_bakerfi-invitational_2025_02` | 32 | 70 | 15 | 55 | 17 |
| 0.279 | `code4rena_virtuals-protocol_2025_08` | 43 | 86 | 18 | 68 | 25 |
| 0.273 | `code4rena_cabal-liquid-staking-token_2025_05` | 8 | 36 | 6 | 30 | 2 |
| 0.270 | `sherlock_crestal-network_2025_03` | 7 | 30 | 5 | 25 | 2 |
| 0.240 | `code4rena_next-generation_2025_05` | 14 | 11 | 3 | 8 | 11 |
| 0.222 | `cantina_minimal-delegation_2025_04` | 17 | 10 | 3 | 7 | 14 |
| 0.222 | `code4rena_iq-ai_2025_03` | 9 | 18 | 3 | 15 | 6 |
| 0.217 | `code4rena_secondswap_2025_02` | 30 | 16 | 5 | 11 | 25 |
| 0.211 | `cantina_smart-contract-audit-of-tn-contracts_2025_08` | 23 | 15 | 4 | 11 | 19 |
| 0.200 | `sherlock_symmio_2025_03` | 6 | 14 | 2 | 12 | 4 |
| 0.195 | `code4rena_initia-move_2025_04` | 18 | 23 | 4 | 19 | 14 |
| 0.187 | `code4rena_starknet-perpetual_2025_06` | 13 | 19 | 3 | 16 | 10 |
| 0.169 | `code4rena_loopfi_2025_02` | 7 | 52 | 5 | 47 | 2 |
| 0.165 | `code4rena_mantra-dex_2025_03` | 55 | 78 | 11 | 67 | 44 |
| 0.154 | `sherlock_20240913---final---perennial-v2-update-3-audit-report_2024_09` | 21 | 5 | 2 | 3 | 19 |
| 0.118 | `sherlock_axion_2025_01` | 10 | 7 | 1 | 6 | 9 |
| 0.105 | `code4rena_fenix-finance-invitational_2024_10` | 15 | 80 | 5 | 75 | 10 |
| 0.100 | `code4rena_superposition_2025_01` | 11 | 9 | 1 | 8 | 10 |
| 0.042 | `sherlock_morph-l-2_2024_09` | 13 | 225 | 5 | 220 | 8 |
| 0.041 | `sherlock_idle-finance_2024_12` | 5 | 44 | 1 | 43 | 4 |