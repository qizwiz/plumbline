"""
spec_mutator — SVM for CA/NCA grammar-driven evolution kernel.

For each own-corpus TLA+ FailureMode, applies single-step grammar-respecting
mutations and classifies the result: broken | fixed | equivalent | novel.

Usage: python tools/spec_mutator.py --runs 5
Writes ca_svm_report.json + survivors to docs/tla/mutations/.
"""
from __future__ import annotations
import hashlib, json, os, random, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TLA_DIR = os.path.join(HERE, "docs", "tla")
MUTATIONS_DIR = os.path.join(TLA_DIR, "mutations")
TLA_JAR = os.path.join(TLA_DIR, "tla2tools.jar")
GRAMMAR_VALIDATE = os.path.join(HERE, "tools", "validate_tla_grammar.py")

OWN_SPECS = ["Create2NonIdempotent", "CrossWalletSigReplay",
             "ERC4337StaticSigDoS", "FlagBypassesValidationChain",
             "PartialSignatureReplay", "ReentrancyDrain",
             "SignatureReplay", "Uint64FeeOverflow"]

BINOP_SWAPS = [("=", "/="), ("/=", "="), ("+", "-"), ("-", "+"),
               ("\\in", "\\notin"), ("\\notin", "\\in"),
               ("<", ">"), (">", "<")]


def mutate_swap_binop(src, rng):
    cands = []
    for old, new in BINOP_SWAPS:
        for m in re.finditer(rf"(?<![\w\\]){re.escape(old)}(?!\w)", src):
            ls = src.rfind("\n", 0, m.start()) + 1
            line_prefix = src[ls:m.start()]
            if "\\*" in line_prefix or line_prefix.lstrip().startswith("(*"):
                continue
            cands.append((m.start(), m.end(), old, new))
    if not cands: return None
    s, e, old, new = rng.choice(cands)
    return src[:s] + new + src[e:], f"swap_binop({old}->{new})"


def mutate_swap_bool(src, rng):
    cands = [(m.start(), m.end(), tok)
             for tok in ("TRUE", "FALSE")
             for m in re.finditer(rf"\b{tok}\b", src)]
    if not cands: return None
    s, e, tok = rng.choice(cands)
    new = "FALSE" if tok == "TRUE" else "TRUE"
    return src[:s] + new + src[e:], f"swap_bool({tok}->{new})"


def mutate_swap_vars(src, rng):
    m = re.search(r"VARIABLES\s*\n((?:\s+\w+,?\s*\n)+)", src)
    if not m: return None
    decls = [x.strip().rstrip(",") for x in m.group(1).split("\n") if x.strip()]
    if len(decls) < 2: return None
    a, b = rng.sample(decls, 2)
    body = src[m.end():]
    occs = list(re.finditer(rf"\b{a}\b", body))
    if not occs: return None
    occ = rng.choice(occs)
    return (src[:m.end()] + body[:occ.start()] + b + body[occ.end():],
            f"swap_vars({a}<->{b})")


def mutate_replace_const(src, rng):
    cands = []
    for m in re.finditer(r"(?<![\w\.])(\d+)(?!\w)", src):
        v = int(m.group(1))
        if 0 <= v <= 9999:
            cands.append((m.start(), m.end(), v))
    if not cands: return None
    s, e, v = rng.choice(cands)
    new_v = v + rng.choice([-1, 1, 2])
    if new_v < 0: new_v = v + 1
    return src[:s] + str(new_v) + src[e:], f"replace_const({v}->{new_v})"


MUTATIONS = [mutate_swap_binop, mutate_swap_bool,
             mutate_swap_vars, mutate_replace_const]


def trace_hash(stdout):
    states = []
    for m in re.finditer(r"State \d+:.*?\n(.*?)(?=\nState \d+:|\nError|\Z)",
                         stdout, re.S):
        pairs = re.findall(r"/\\\s*(\w+)\s*=\s*([^/\n]+?)(?=\s*/\\|\n|$)",
                           m.group(1))
        states.append(tuple(sorted((k.strip(), v.strip()) for k, v in pairs)))
    return hashlib.sha256(json.dumps(states, default=str).encode()).hexdigest()[:16]


def run_tlc(tla, cfg, timeout=30):
    work = os.path.dirname(tla); mod = os.path.basename(tla).removesuffix(".tla")
    try:
        p = subprocess.run(["java", "-XX:+UseParallelGC", "-cp", TLA_JAR,
                            "tlc2.TLC", "-config", os.path.basename(cfg),
                            "-deadlock", mod],
                           cwd=work, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"violated": False, "trace_hash": "", "error": "timeout"}
    out = p.stdout + p.stderr
    if "Invariant" in out and "is violated" in out:
        return {"violated": True, "trace_hash": trace_hash(out), "error": None}
    if p.returncode != 0 or "Error" in out:
        return {"violated": False, "trace_hash": "", "error": "tlc-error"}
    return {"violated": False, "trace_hash": "", "error": None}


def lark_ok(tla):
    p = subprocess.run([sys.executable, GRAMMAR_VALIDATE, tla],
                       capture_output=True, text=True, timeout=30)
    return "PASS" in p.stdout and "FAIL" not in p.stdout


def main():
    runs = int(sys.argv[sys.argv.index("--runs") + 1]) if "--runs" in sys.argv else 5
    rng = random.Random(42)
    report, novel_archive = [], []
    originals = {}
    for spec in OWN_SPECS:
        r = run_tlc(os.path.join(TLA_DIR, spec + ".tla"),
                    os.path.join(TLA_DIR, spec + ".cfg"))
        originals[spec] = r["trace_hash"]
        print(f"[baseline] {spec}: hash={r['trace_hash']}")
    tmp = tempfile.mkdtemp(prefix="ca_svm_")
    try:
        for spec in OWN_SPECS:
            src = open(os.path.join(TLA_DIR, spec + ".tla")).read()
            cfg_src = open(os.path.join(TLA_DIR, spec + ".cfg")).read()
            for run in range(runs):
                fn = rng.choice(MUTATIONS); result = fn(src, rng)
                if result is None:
                    kind = fn.__name__.removeprefix("mutate_") + "(no-target)"
                    report.append({"spec": spec, "mutation_kind": kind,
                                   "bucket": "broken", "orig_hash": originals[spec],
                                   "new_hash": ""})
                    print(f"  [{spec} #{run+1}] {kind} -> broken"); continue
                new_src, kind = result
                d = os.path.join(tmp, f"{spec}_{run}"); os.makedirs(d, exist_ok=True)
                tla_t = os.path.join(d, spec + ".tla")
                cfg_t = os.path.join(d, spec + ".cfg")
                jl = os.path.join(d, "tla2tools.jar")
                if not os.path.exists(jl): os.symlink(TLA_JAR, jl)
                open(tla_t, "w").write(new_src); open(cfg_t, "w").write(cfg_src)
                if not lark_ok(tla_t):
                    bucket, new_hash = "broken", ""
                else:
                    r = run_tlc(tla_t, cfg_t); new_hash = r["trace_hash"]
                    if r["error"]: bucket = "broken"
                    elif not r["violated"]: bucket = "fixed"
                    elif new_hash == originals[spec]: bucket = "equivalent"
                    else:
                        bucket = "novel"
                        if len(novel_archive) < 5:
                            os.makedirs(MUTATIONS_DIR, exist_ok=True)
                            a = os.path.join(MUTATIONS_DIR, f"{spec}_mut_{run}.tla")
                            open(a, "w").write(
                                f"\\* MUTATION: {kind}\n\\* original hash: "
                                f"{originals[spec]}\n\\* new hash: {new_hash}\n\n{new_src}")
                            novel_archive.append(a)
                report.append({"spec": spec, "mutation_kind": kind,
                               "bucket": bucket, "orig_hash": originals[spec],
                               "new_hash": new_hash})
                print(f"  [{spec} #{run+1}] {kind} -> {bucket}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    counts = {"broken": 0, "fixed": 0, "equivalent": 0, "novel": 0}
    for r in report: counts[r["bucket"]] += 1
    print(f"\nbroken={counts['broken']} fixed={counts['fixed']} "
          f"equivalent={counts['equivalent']} novel={counts['novel']}")
    print(f"total={len(report)}")
    json.dump({"counts": counts, "attempts": report},
              open(os.path.join(HERE, "ca_svm_report.json"), "w"), indent=2)
    print(f"novel archives: {len(novel_archive)}")


if __name__ == "__main__":
    main()
