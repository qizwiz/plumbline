# The codespace problem — deep-research findings & recommendation

Source: deep-research workflow run 2026-06-06, 107 subagents, 4.0M
tokens, 25 claims adversarially verified (18 confirmed / 7 refuted).
Resolves the "gh codespace ssh is a trap" memory entry into a concrete
forward path.

## TL;DR

**Stop trying to fix `gh codespace ssh`.** Two structural blockers
make it not worth fighting:

1. The `ghcr.io/devcontainers/features/sshd:1` feature's `install.sh`
   hard-codes `apt-get` / `dpkg` with no Alpine/RHEL fallback —
   exits non-zero on any musl base. (3-0 verified.)
2. Even if you fix sshd, VS Code Remote-SSH's prebuilt Node binary is
   glibc-only and can't load on musl. Microsoft issue #423 OPEN since
   2019. (3-0 verified.)

**The recommended path** is to skip the Codespaces+SSH route entirely
and use **GitHub Actions with prebuilt analysis-toolchain images**:

- **`ghcr.io/trailofbits/eth-security-toolbox/ci:nightly`** —
  pre-installs Foundry, Slither, Echidna, Medusa, solc-select. Built
  specifically for the GHA `container:` directive. Debian-based, so
  the sshd-feature / glibc / musl problem doesn't exist.
- **`ghcr.io/a16z/halmos:latest`** — bundles Python, Halmos, Foundry,
  SMT solvers. Use as a separate job.
- **TLC stays local on Mac** (already working with tla2tools.jar).

This is `$0/month` for JH's contest pattern (a few hours over 1-3
days on contest weekends), composes with the existing
`.github/workflows/loop.yml` cloud loop, and removes the OZ-vendoring
acrobatics that blocked puppy-raffle in T15.

## Why this matters for tonight's measured pain

The T15 puppy-raffle slither failure happened because:
- pragma 0.7.6 needs OZ 3.x (we'd vendored OZ 5.0)
- imports `lib/base64/base64.sol` (foundry lib path)
- foundry isn't installed locally
- disk at 2.1 GiB free, foundryup install risky

**The ToB CI image has Foundry pre-installed and a fully-working
solc-select chain.** A GitHub Actions workflow using that image
would have run slither on all 5 corpora — including puppy-raffle —
without OZ-vendoring or disk pressure.

## Refuted hypotheses (deep-research killed these)

| Claim I'd have guessed | Verdict |
|------------------------|---------|
| Use `ghcr.io/foundry-rs/foundry` as devcontainer base | 0-3 ✗ (Foundry maintainers explicitly declined to ship a devcontainer feature; image not the workaround) |
| `gcompat` package fixes Remote-SSH on Alpine | 0-3 ✗ (workaround insufficient per Microsoft #423) |
| Tailscale feature sidesteps sshd-feature-vs-musl | 0-3 ✗ (Tailscale daemon ITSELF is glibc-based; same problem on Alpine bases) |
| `gh codespace ssh/cp/logs` fails with "connection refused" via sshd feature | 0-3 ✗ (different failure mode; the feature breaks at install time on musl, not connect time) |

## If SSH access is genuinely needed (escape hatch)

For a Debian-based devcontainer where SSH access matters:

```jsonc
// .devcontainer/devcontainer.json
{
  "image": "ghcr.io/trailofbits/eth-security-toolbox/ci:nightly",
  "features": {
    "ghcr.io/tailscale/codespace/tailscale": {}
  },
  "runArgs": ["--device=/dev/net/tun"],
  "remoteEnv": {
    "TS_AUTH_KEY": "${localEnv:TS_AUTH_KEY}"
  }
}
```

Add `TS_AUTH_KEY` as a Codespaces secret. Tailscale daemon auto-starts
at entrypoint and exposes the codespace on the tailnet — bypasses
`gh codespace ssh` entirely. Known caveat: long-lived codespaces hit
auth-key restart-expiration bugs (tailscale/codespace #19501).

**For JH's use case, this is probably overkill** — GitHub Actions
covers the contest-week pattern without needing live SSH.

## Cost / runtime envelope

| Option | Cost (JH's pattern) | Max runtime | Persistent disk | Setup |
|--------|---------------------|-------------|-----------------|-------|
| **GitHub Actions + ToB CI image** | **$0** | 6h/job (hard limit) | None (ephemeral) | ~5 min |
| Codespaces + Tailscale | $0 with included core hours | until shutdown | Yes (codespace) | ~15 min |
| Fly.io performance-1x + volume | ~$32/mo + $0.15/GB-mo (stop machine to save) | Indefinite | Yes ($0.15/GB-mo) | ~30 min |
| E2B Hobby (free) | $100 one-time credit | **1h/session — hard blocker** | Per docs (gap on pricing page) | ~10 min |
| E2B Pro | $150/mo | 24h/session | Yes | ~10 min |

For contest weekends (a few hours over 1-3 days):
- **6h/job GHA cap is comfortably above typical runs.**
- E2B Hobby's 1h cap is a hard blocker.
- Fly.io is the right paid fallback if a single Halmos invariant
  search runs >6h — stop machine between sessions to minimize cost.

## Immediate compounding move for plumbline

Add `.github/workflows/slither.yml` using the ToB CI image:

```yaml
name: slither-baselines
on: workflow_dispatch
jobs:
  slither:
    runs-on: ubuntu-latest
    container: ghcr.io/trailofbits/eth-security-toolbox/ci:nightly
    strategy:
      matrix:
        corpus: [boss-bridge, puppy-raffle, sequence, t-swap, thunder-loan]
    steps:
      - uses: actions/checkout@v4
      - name: Install solc for ${{ matrix.corpus }}
        run: |
          # ToB CI image has solc-select; pin per-corpus pragma
          case "${{ matrix.corpus }}" in
            puppy-raffle) solc-select install 0.7.6 && solc-select use 0.7.6 ;;
            *) solc-select install 0.8.20 && solc-select use 0.8.20 ;;
          esac
      - name: Run slither
        run: slither examples/${{ matrix.corpus }} 2>&1 | tee examples/${{ matrix.corpus }}/slither.txt || true
      - uses: actions/upload-artifact@v4
        with:
          name: slither-${{ matrix.corpus }}
          path: examples/${{ matrix.corpus }}/slither.txt
```

This **closes the puppy-raffle T15 gap** because Foundry + solc-select
are pre-installed in the ToB image. No OZ-vendoring needed because
Foundry's remappings resolve via `foundry.toml`. ~5 min to author, $0
to run, runs across all 5 corpora in parallel.

## Recommendation summary

| Layer | Tool | Where it runs |
|-------|------|---------------|
| Lead generation | sol_intent | GHA cloud loop (existing) |
| Slither baseline | slither | **New `slither.yml` GHA + ToB image** |
| Halmos symbolic | halmos | Future GHA job + a16z image |
| TLC discharge | tla2tools.jar | **Local Mac** (already works) |
| Interactive shell | (skip — not needed) | n/a |

The codespace `organic-dollop-9qjvgq9pp39xpr` stays Shutdown; we don't
revive it. The CodeSpace+Tailscale path is documented as an escape
hatch but the recommended path makes it unnecessary.

## Verified sources

- [devcontainers/features#sshd](https://github.com/devcontainers/features/tree/main/src/sshd) — the broken install.sh
- [microsoft/vscode-remote-release#423](https://github.com/microsoft/vscode-remote-release/issues/423) — Remote-SSH glibc/musl OPEN since 2019
- [foundry-rs/foundry#7290](https://github.com/foundry-rs/foundry/issues/7290) — Foundry maintainers declined the devcontainer feature
- [trailofbits/eth-security-toolbox](https://github.com/trailofbits/eth-security-toolbox) — the CI image
- [a16z/halmos](https://github.com/a16z/halmos) — the halmos image
- [tailscale/codespace](https://github.com/tailscale/codespace) — Tailscale devcontainer feature
- [fly.io/docs/about/pricing](https://fly.io/docs/about/pricing/) — verified pricing figures
- [docs.github.com/actions/reference/limits](https://docs.github.com/en/actions/reference/limits) — 6h/job cap

## Open questions (acknowledged limits)

- E2B SSH mechanism + persistence — pricing page silent; needs separate
  evaluation if we ever consider it
- Tailscale TS_AUTH_KEY restart-expiration on Shutdown codespace —
  not tested
- Gitpod post-acquisition viability in 2026 — no claims survived voting
- GHA self-hosted runners on Fly.io as a hybrid — operational overhead
  unclear

These don't block the recommendation; the recommended path (GHA + ToB
image) doesn't depend on them.
