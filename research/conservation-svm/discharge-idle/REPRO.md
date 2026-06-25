# Real-external-contract discharge — idle StakingRewards (deps resolved, halmos PASS)
Proves the dependency blocker is breakable + halmos discharges on real external bytecode.
src/StakingRewards.sol + src/utils/ are the real idle contract (from runs/glm-bet/src/idle).
lib/ and out/ were removed to save disk; regenerate:
  curl -sL https://github.com/OpenZeppelin/openzeppelin-contracts/archive/refs/tags/v4.5.0.tar.gz | tar xz -C lib
  mv lib/openzeppelin-contracts-4.5.0 lib/openzeppelin-contracts
  ../../../.venv/bin/halmos --function check_idleConservation --contract IdleConservation
Result: [PASS] 0.20s — idiom #2 conservation (Δ_totalSupply==Δ_balances) cleared (conservation is sound here).
Frictions handled: OZ 3.4 vendored vs 4.x needed (fetch right era); solc 0.8.10 pin vs forge-std >=0.8.13 (drop forge-std).
