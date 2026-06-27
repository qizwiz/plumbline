"""
plumbline live-halmos — the "it's not canned" proof.

A Modal function with foundry + halmos baked in, plus MULTIPLE contest examples. On request it
runs the REAL symbolic-execution invariant for the requested target in the cloud and returns the
verbatim stdout + sha256 + wall time. The web demo calls this so a viewer can watch halmos actually
produce the counterexample on THAT page's own contract — and confirm its hash matches the recorded run.

Each page passes ?target=<name>&inv=<check_*>; both are whitelisted so the endpoint only ever runs a
known invariant against the matching contract (never the wrong contract's bytecode).

Test:   modal run deploy/live_halmos.py
Deploy: modal deploy deploy/live_halmos.py   -> public GET endpoint
"""
import modal
import re as _re

app = modal.App("plumbline-live")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("curl", "git")
    .run_commands(
        "curl -L https://foundry.paradigm.xyz | bash",
        "/root/.foundry/bin/foundryup",                 # latest forge installs cleanly
        "/root/.foundry/bin/forge --version",
    )
    .pip_install("halmos==0.3.3", "fastapi[standard]")  # pin halmos to the known-good version
    .env({"PATH": "/root/.foundry/bin:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"})
    # bake each target in its own dir so a page only ever runs ITS OWN contract
    .add_local_dir("examples/synthetic-dreusd", remote_path="/work/synthetic-dreusd", copy=True)
    .add_local_dir("examples/t-swap", remote_path="/work/t-swap", copy=True)
    .run_commands(
        "cd /work/synthetic-dreusd && /root/.foundry/bin/forge build",
        "cd /work/t-swap && /root/.foundry/bin/forge build",
    )
)

# target -> (workdir, whitelisted invariants). A request must name a known target AND a known
# invariant for it; anything else is rejected — the endpoint can never run the wrong contract.
TARGETS = {
    "synthetic-dreusd": ("/work/synthetic-dreusd", {"check_redeemReturnsDeposit", "check_supplyAtMostBacking"}),
    "t-swap":           ("/work/t-swap",           {"check_swapPreservesXYK"}),
}


_KEEP = _re.compile(r"Running \d+ test|Counterexample|\[FAIL\]|\[PASS\]|passed; \d+ failed|Symbolic test result|= 0x")
_LINT = _re.compile(r"forge-lint|unsafe-typecast|disable-next-line|safe because|block-timestamp|"
                    r"[─-╿]|^\s*\d+ │|help: https|note:|warning\[|"
                    r"Skipped .*parsing failure|Found unknown .*config|AST source not found|"
                    r"Compiler run successful|Warning \(\d|Unused (function parameter|local variable)")


def _clean(out: str) -> str:
    """Drop forge-lint warning blocks; keep only the halmos result lines."""
    return "\n".join(ln for ln in out.splitlines() if _KEEP.search(ln)).strip()


def _resolve(target: str, inv: str):
    """Return (workdir, None) if (target, inv) is a known-safe pair, else (None, error)."""
    t = TARGETS.get(target)
    if not t:
        return None, f"unknown target: {target}"
    workdir, allowed = t
    if inv not in allowed:
        return None, f"invariant not allowed for {target}: {inv}"
    return workdir, None


def _run(target: str, inv: str) -> dict:
    import subprocess, hashlib, time
    wd, err = _resolve(target, inv)
    if err:
        return {"error": err}
    t0 = time.monotonic()
    try:
        r = subprocess.run(["halmos", "--function", inv], cwd=wd,
                           capture_output=True, text=True, timeout=160)
        so = _re.sub(r"\x1b\[[0-9;]*m", "", r.stdout or "")
        se = _re.sub(r"\x1b\[[0-9;]*m", "", r.stderr or "")
        code = r.returncode
    except Exception as e:
        return {"error": str(e)[:300]}
    clean = _clean(so + "\n" + se)
    return {
        "target": target,
        "argv": f"halmos --function {inv}",
        "exit_code": code,
        "wall_s": round(time.monotonic() - t0, 2),
        "found_counterexample": "Counterexample" in (so + se),
        "stdout_sha256": hashlib.sha256((so + se).encode("utf-8", "replace")).hexdigest()[:16],
        "clean": clean,
        "stdout_tail": (so + se).strip()[-600:],
        "ran_in": "modal cloud container",
    }


@app.function(image=image, timeout=200)
def run_check(target: str = "synthetic-dreusd", inv: str = "check_redeemReturnsDeposit") -> dict:
    return _run(target, inv)


@app.function(image=image, timeout=200)
@modal.fastapi_endpoint(method="GET")
def web_run(target: str = "synthetic-dreusd", inv: str = "check_redeemReturnsDeposit"):
    from fastapi.responses import JSONResponse
    return JSONResponse(_run(target, inv), headers={"Access-Control-Allow-Origin": "*"})


@app.function(image=image, timeout=200)
@modal.fastapi_endpoint(method="GET")
def web_stream(target: str = "synthetic-dreusd", inv: str = "check_redeemReturnsDeposit"):
    """Stream the REAL work line-by-line as it happens — forge compiling, then halmos
    exploring paths — so a viewer watches it take real time. Nothing is canned."""
    from fastapi.responses import StreamingResponse, JSONResponse
    wd, err = _resolve(target, inv)
    if err:
        return JSONResponse({"error": err}, headers={"Access-Control-Allow-Origin": "*"})

    def gen():
        import subprocess, time
        t0 = time.monotonic()
        yield f"[modal] cloud container up · foundry + halmos 0.3.3 · target {target}\n"
        yield "[forge] compiling contracts …\n"
        subprocess.run(["forge", "build"], cwd=wd, capture_output=True, text=True, timeout=120)
        yield f"[forge] build complete · {round(time.monotonic() - t0, 2)}s\n\n"
        yield f"$ halmos --function {inv}\n"
        p = subprocess.Popen(["halmos", "--function", inv], cwd=wd,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for raw in iter(p.stdout.readline, ""):
            line = _re.sub(r"\x1b\[[0-9;]*m", "", raw)
            if _LINT.search(line) or not line.strip():
                continue
            yield line if line.endswith("\n") else line + "\n"
        p.wait()
        yield f"\n[done] exit {p.returncode} · {round(time.monotonic() - t0, 2)}s total — real symbolic execution, in the cloud, just now\n"

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8",
                             headers={"Access-Control-Allow-Origin": "*",
                                      "Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.local_entrypoint()
def main():
    import json
    for target, inv in [("synthetic-dreusd", "check_redeemReturnsDeposit"), ("t-swap", "check_swapPreservesXYK")]:
        res = run_check.remote(target, inv)
        print(f"=== {target} / {inv} ===")
        print(json.dumps({k: v for k, v in res.items() if k not in ("clean", "stdout_tail")}, indent=2))
        print(res.get("clean", res.get("error", "")))
