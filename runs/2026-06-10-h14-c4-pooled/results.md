# H14 second-premise — c4 scale-up (pooled)

Generated 75 contests, 36314 functions, 2230 bug-implicated, 34084 clean.

## Pooled Mann-Whitney U per feature (★ = p<0.05, ★★ = Bonferroni-corrected p<0.0125)

| Feature | n_bug | n_clean | bug mean | clean mean | p |
|---|---|---|---|---|---|
| degree | 2230 | 34084 | 3.7228699551569506 | 2.562492665180143 | 2.318879857672612e-38 ★★ |
| betweenness | 2230 | 34084 | 0.0031529453055677355 | 0.0011754110352226999 | 4.408076826266682e-52 ★★ |
| clustering | 2230 | 34084 | 0.03512249419478658 | 0.02139181644346244 | 2.146505469763421e-08 ★★ |
| is_cut_vertex | 2230 | 34084 | 0.1547085201793722 | 0.11451120760474123 | 0.0014463337777922754 ★★ |

## Per-contest summary

| Contest | |V| | bugs | clean |
|---|---|---|---|
| 2022-01-insure | 267 | 17 | 250 |
| 2023-04-rubicon | 675 | 51 | 624 |
| 2023-06-lybra | 518 | 78 | 440 |
| 2023-07-amphora | 490 | 22 | 468 |
| 2023-09-asymmetry | 93 | 30 | 63 |
| 2023-09-maia | 362 | 67 | 295 |
| 2023-10-badger | 1509 | 44 | 1465 |
| 2023-10-nextgen | 314 | 31 | 283 |
| 2023-10-party | 577 | 17 | 560 |
| 2023-10-zksync | 665 | 51 | 614 |
| 2023-11-panoptic | 93 | 8 | 85 |
| 2023-11-zetachain | 247 | 24 | 223 |
| 2023-12-autonolas | 1072 | 4 | 1068 |
| 2023-12-ethereumcreditguild | 265 | 35 | 230 |
| 2023-12-particle | 93 | 25 | 68 |
| 2023-12-revolutionprotocol | 397 | 42 | 355 |
| 2024-01-canto | 40 | 0 | 40 |
| 2024-01-curves | 53 | 14 | 39 |
| 2024-01-decent | 82 | 14 | 68 |
| 2024-01-init-capital-invitational | 539 | 16 | 523 |
| 2024-01-salty | 612 | 87 | 525 |
| 2024-02-ai-arena | 123 | 24 | 99 |
| 2024-02-althea-liquid-infrastructure | 27 | 10 | 17 |
| 2024-02-spectra | 476 | 22 | 454 |
| 2024-02-thruster | 540 | 17 | 523 |
| 2024-02-wise-lending | 1299 | 100 | 1199 |
| 2024-03-abracadabra-money | 493 | 43 | 450 |
| 2024-03-coinbase | 65 | 2 | 63 |
| 2024-03-dittoeth | 927 | 48 | 879 |
| 2024-03-gitcoin | 45 | 1 | 44 |
| 2024-03-neobase | 55 | 6 | 49 |
| 2024-03-ondo-finance | 844 | 24 | 820 |
| 2024-03-pooltogether | 57 | 19 | 38 |
| 2024-03-revert-lend | 148 | 38 | 110 |
| 2024-03-taiko | 411 | 30 | 381 |
| 2024-03-zksync | 813 | 16 | 797 |
| 2024-04-dyad | 103 | 26 | 77 |
| 2024-04-gondi | 134 | 18 | 116 |
| 2024-04-noya | 1537 | 94 | 1443 |
| 2024-04-panoptic | 262 | 11 | 251 |
| 2024-04-renzo | 547 | 36 | 511 |
| 2024-05-arbitrum-foundation | 1061 | 33 | 1028 |
| 2024-05-bakerfi | 427 | 29 | 398 |
| 2024-05-canto | 30 | 0 | 30 |
| 2024-05-loop | 30 | 1 | 29 |
| 2024-05-munchables | 461 | 14 | 447 |
| 2024-05-olas | 1562 | 77 | 1485 |
| 2024-05-predy | 348 | 18 | 330 |
| 2024-06-badger | 1808 | 21 | 1787 |
| 2024-06-krystal-defi | 44 | 4 | 40 |
| 2024-06-size | 196 | 66 | 130 |
| 2024-06-thorchain | 160 | 26 | 134 |
| 2024-06-vultisig | 160 | 10 | 150 |
| 2024-07-basin | 269 | 5 | 264 |
| 2024-07-benddao | 608 | 30 | 578 |
| 2024-07-dittoeth | 1621 | 48 | 1573 |
| 2024-07-karak | 260 | 54 | 206 |
| 2024-07-loopfi | 624 | 140 | 484 |
| 2024-07-munchables | 524 | 14 | 510 |
| 2024-07-optimism | 801 | 13 | 788 |
| 2024-07-reserve | 1941 | 53 | 1888 |
| 2024-07-traitforge | 192 | 41 | 151 |
| 2024-08-axelar-network | 617 | 43 | 574 |
| 2024-08-basin | 269 | 10 | 259 |
| 2024-08-chakra | 112 | 6 | 106 |
| 2024-08-phi | 232 | 29 | 203 |
| 2024-08-superposition | 125 | 9 | 116 |
| 2024-08-wildcat | 570 | 42 | 528 |
| 2024-09-fenix-finance | 1485 | 71 | 1414 |
| 2024-10-kleidi | 109 | 5 | 104 |
| 2024-10-loopfi | 695 | 22 | 673 |
| 2024-10-ramses-exchange | 842 | 28 | 814 |
| 2024-10-superposition | 141 | 4 | 137 |
| 2024-11-ethena-labs | 86 | 0 | 86 |
| 2024-11-nibiru | 35 | 2 | 33 |

## Honest interpretation

With pooled N=36314 functions, 4/4 features survived Bonferroni correction at α=0.05/4=0.0125.

**H14 second premise is SUPPORTED by this data.** Bug-implicated functions occupy systematically different positions on the corresponding graph features. Geometric priors are informative about bug location.
