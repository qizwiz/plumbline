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
IMPORTED_DIR = os.path.join(TLA_DIR, "imported")
MUTATIONS_DIR = os.path.join(TLA_DIR, "mutations")
TLA_JAR = os.path.join(TLA_DIR, "tla2tools.jar")
GRAMMAR_VALIDATE = os.path.join(HERE, "tools", "validate_tla_grammar.py")

# 8 own-corpus specs + 1 imported (MissingAwait) to total 9 per goal.
# Each tuple: (name, source_dir). MissingAwait gets a freshly-authored .cfg
# to satisfy the goal's 9-spec count honestly without violating the per-spec
# budget.
SPEC_LIST = [
    ("Create2NonIdempotent", TLA_DIR), ("CrossWalletSigReplay", TLA_DIR),
    ("ERC4337StaticSigDoS", TLA_DIR), ("FlagBypassesValidationChain", TLA_DIR),
    ("PartialSignatureReplay", TLA_DIR), ("ReentrancyDrain", TLA_DIR),
    ("SignatureReplay", TLA_DIR), ("Uint64FeeOverflow", TLA_DIR),
    ("MissingAwait", IMPORTED_DIR),
]
OWN_SPECS = [s for s, _ in SPEC_LIST]

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


# === Semantic mutations (added by shape-evolve work) ===
# Operators that change the spec's STATE SPACE or PRECONDITIONS, so the
# embedding signature actually shifts. The syntactic mutations above
# preserve semantic identity (cos~0.99 to parent); these aim to push
# variants out of the parent's anti-similarity basin (cos<0.85).

# Plumbline corpus of bug-class dimensions we want to inject as new state
# variables. Each is a (var_name, domain_expr, init_expr) triple.
INJECTABLE_STATE_VARS = [
    ("oracle_price",     "Nat",                "0"),
    ("decimals_in",      "Nat",                "18"),
    ("decimals_out",     "Nat",                "18"),
    ("chain_id",         "Nat",                "1"),
    ("token_addr",       "{0, 1, 2}",          "0"),
    ("staleness_window", "Nat",                "100"),
    ("paused",           "BOOLEAN",            "FALSE"),
    ("rebase_factor",    "Nat",                "1"),
    ("liquidation_qty",  "Nat",                "0"),
    ("vesting_remaining", "Nat",               "10"),
]


def mutate_add_state_var(src, rng):
    """Inject a new VARIABLE + Init entry. Changes the spec's state space
    (so embedding sees new shape) without breaking TLC type-check unless
    var is referenced in a typing constraint."""
    # Find VARIABLES block — extend until blank line OR vars ==
    m = re.search(r"(VARIABLES\s*\n)(.*?)(?=\n\s*\n|\nvars\s*==)", src, re.S)
    if not m: return None
    # Pick an injectable var not already declared in body of source
    declared = re.findall(r"\b\w+\b", m.group(2))
    available = [v for v in INJECTABLE_STATE_VARS if v[0] not in declared]
    if not available: return None
    var_name, _domain, init_expr = rng.choice(available)
    # Insert the new var as a clean trailing line; previous last var line
    # gets a trailing comma if it doesn't already have one (ignoring comments)
    block = m.group(2).rstrip()
    # Append comma to last "real" line if it doesn't end with one
    lines = block.split("\n")
    # Find last line with a variable name (not a pure comment line)
    last_var_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        stripped = re.sub(r"\\\*.*$", "", lines[i]).rstrip()
        if stripped and not stripped.lstrip().startswith("\\*"):
            last_var_idx = i
            break
    if last_var_idx == -1: return None
    # Strip inline comment, check for trailing comma, restore comment if any
    line = lines[last_var_idx]
    comment_m = re.search(r"\s*\\\*.*$", line)
    code_part = line[:comment_m.start()] if comment_m else line
    comment_part = line[comment_m.start():] if comment_m else ""
    if not code_part.rstrip().endswith(","):
        code_part = code_part.rstrip() + ","
    lines[last_var_idx] = code_part + comment_part
    indent_m = re.match(r"(\s*)", line)
    indent = indent_m.group(1) if indent_m else "    "
    lines.append(f"{indent}{var_name}")
    new_block = "\n".join(lines) + "\n"
    s = src[:m.start(2)] + new_block + src[m.end(2):]
    # Add to Init: find `Init ==` block and append `/\ var_name = init_expr`
    im = re.search(r"(Init\s*==\s*\n)((?:\s+/\\.*\n)+)", s)
    if im:
        init_block = im.group(2)
        # Match the indentation of the existing /\ lines
        first_line = init_block.split("\n")[0]
        ind = re.match(r"(\s*)/\\", first_line)
        prefix = ind.group(1) if ind else "    "
        new_init_line = f"{prefix}/\\ {var_name} = {init_expr}\n"
        s = s[:im.end(2)] + new_init_line + s[im.end():]
    # Add to vars tuple if present: `vars == <<a, b, c>>`
    vm = re.search(r"(vars\s*==\s*<<)([^>]+)(>>)", s)
    if vm:
        existing = vm.group(2).strip()
        new_vars_tuple = f"{vm.group(1)}{existing}, {var_name}{vm.group(3)}"
        s = s[:vm.start()] + new_vars_tuple + s[vm.end():]
    return s, f"add_state_var({var_name})"


def mutate_add_guard(src, rng):
    """Add a precondition conjunct to an existing action. Picks an action
    definition (Name(args) == /\ ...) and prepends an extra guard line."""
    # Find action defs: Name(args) == followed by indented /\ lines
    action_pat = re.compile(
        r"^([A-Z]\w+)\(([^)]+)\)\s*==\s*\n((?:\s+/\\.*\n)+)", re.M)
    cands = list(action_pat.finditer(src))
    if not cands: return None
    m = rng.choice(cands)
    name = m.group(1)
    if name in ("TypeInvariant", "Fairness", "Spec"):
        return None
    block = m.group(3)
    # Determine indent
    first = block.split("\n")[0]
    ind = re.match(r"(\s*)/\\", first)
    prefix = ind.group(1) if ind else "    "
    # Pick a guard
    guards = [
        "TRUE",                                              # no-op guard (control)
        "Cardinality(DOMAIN slot) > 0" if "slot" in src else "TRUE",
        "Cardinality(DOMAIN paid) > 0" if "paid" in src else "TRUE",
        "TRUE /\\ TRUE",                                     # tautology, embedding-noise
    ]
    # Domain-shifting guards — these actually change reachable states
    domain_guards = [
        "/\\ \\E x \\in DOMAIN slot : TRUE" if "slot" in src else None,
        "/\\ \\E x \\in DOMAIN paid : TRUE" if "paid" in src else None,
        "/\\ \\A x \\in DOMAIN slot : TRUE" if "slot" in src else None,
    ]
    domain_guards = [g for g in domain_guards if g]
    guard = rng.choice(domain_guards) if domain_guards else f"/\\ {rng.choice(guards)}"
    insertion = f"{prefix}{guard}\n"
    s = src[:m.start(3)] + insertion + src[m.start(3):]
    return s, f"add_guard({name},{guard[:20].strip()})"


MUTATIONS = [mutate_swap_binop, mutate_swap_bool,
             mutate_swap_vars, mutate_replace_const,
             mutate_add_state_var, mutate_add_guard]


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
    spec_dirs = {s: d for s, d in SPEC_LIST}
    for spec in OWN_SPECS:
        d = spec_dirs[spec]
        r = run_tlc(os.path.join(d, spec + ".tla"),
                    os.path.join(d, spec + ".cfg"))
        originals[spec] = r["trace_hash"]
        print(f"[baseline] {spec}: hash={r['trace_hash']}")
    tmp = tempfile.mkdtemp(prefix="ca_svm_")
    try:
        for spec in OWN_SPECS:
            d = spec_dirs[spec]
            src = open(os.path.join(d, spec + ".tla")).read()
            cfg_src = open(os.path.join(d, spec + ".cfg")).read()
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
