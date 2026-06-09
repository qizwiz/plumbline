# My cold-read findings on synthetic-dreusd

## decimals mismatch in redeem
`dreUSD.redeem` does not scale 18-decimal dreUSD back down to 6-decimal USDC; redemption pays out 1e12× the deposited USDC value, draining backing.

## yield sniping via instant distribution
`distributeYield` adds an instant lump to totalAssets with no vesting or withdrawal cooldown, so a depositor can JIT-sandwich the keeper and capture yield earned by time-committed stakers.
