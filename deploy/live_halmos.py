"""
plumbline live-halmos — the "it's not canned" proof.

A Modal function with foundry + halmos baked in, plus the synthetic-dreusd example.
On request it runs the REAL symbolic-execution invariant in the cloud and returns the
verbatim stdout + sha256 + wall time. The web demo calls this so a viewer can watch
halmos actually produce the counterexample — and confirm its hash matches the recorded run.

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
    .add_local_dir("examples/synthetic-dreusd", remote_path="/work", copy=True)
    .run_commands("cd /work && /root/.foundry/bin/forge build")
)

ALLOWED = {"check_redeemReturnsDeposit", "check_supplyAtMostBacking"}


_KEEP = _re.compile(r"Running \d+ test|Counterexample|\[FAIL\]|\[PASS\]|passed; \d+ failed|Symbolic test result|= 0x")


def _clean(out: str) -> str:
    """Drop forge-lint warning blocks; keep only the halmos result lines."""
    return "\n".join(ln for ln in out.splitlines() if _KEEP.search(ln)).strip()


def _run(inv: str) -> dict:
    import subprocess, hashlib, time
    if inv not in ALLOWED:
        return {"error": f"invariant not in whitelist: {inv}"}
    t0 = time.monotonic()
    try:
        r = subprocess.run(["halmos", "--function", inv], cwd="/work",
                           capture_output=True, text=True, timeout=160)
        so = _re.sub(r"\x1b\[[0-9;]*m", "", r.stdout or "")
        se = _re.sub(r"\x1b\[[0-9;]*m", "", r.stderr or "")
        code = r.returncode
    except Exception as e:
        return {"error": str(e)[:300]}
    clean = _clean(so + "\n" + se)
    return {
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
def run_check(inv: str = "check_redeemReturnsDeposit") -> dict:
    return _run(inv)


@app.function(image=image, timeout=200)
@modal.fastapi_endpoint(method="GET")
def web_run(inv: str = "check_redeemReturnsDeposit"):
    from fastapi.responses import JSONResponse
    return JSONResponse(_run(inv), headers={"Access-Control-Allow-Origin": "*"})


@app.local_entrypoint()
def main():
    import json
    res = run_check.remote("check_redeemReturnsDeposit")
    print(json.dumps({k: v for k, v in res.items() if k not in ("clean", "stdout_tail")}, indent=2))
    print("--- CLEAN (what the demo would show) ---")
    print(res.get("clean", res.get("error", "")))
    print("--- raw tail ---")
    print(res.get("stdout_tail", ""))
