"""
Dirichlet / harmonic semi-supervised probe (the ML test).

Question: if you PIN known exploits as boundary and diffuse across the coupling
graph, do you localize the HELD-OUT exploits better than the baselines?

Honest, pre-registered win condition: a propagation method must beat BOTH
  (a) degree   — the unsup baseline that won 4x, AND
  (b) seed_adj — the TRIVIAL seed-aware baseline (decayed proximity to a known
                 seed): "just look at the neighbors of known bugs"
on held-out buggy-vs-clean AUC, by a real, consistent margin. If propagation only
ties seed_adj, the multi-hop DIFFUSION earned nothing over 1-hop neighborhood and
the "physics" is decorative. If it only ties degree, semi-supervision didn't help.

Methods scored (AUC on held-out fn nodes, seeds excluded; mean over K random splits):
  degree    unsupervised, no seeds
  eigcent   unsupervised, no seeds
  seed_adj  seed-aware TRIVIAL: max_s decay^dist(node, seed_buggy)         [the bar that matters]
  harmonic  Dirichlet two-class: pin buggy=1, clean=0, solve L-harmonic    [Zhu-Ghahramani-Lafferty]
  heat      personalized-PageRank / RWR diffusion from buggy seeds         [decayed heat]
State/modifier nodes are kept as RELAYS (functions coupled through shared storage
propagate through them) but only fn nodes are seeded/evaluated.
"""
import os, pickle, io, tarfile, urllib.request, shutil, json, random, statistics as st
import numpy as np, networkx as nx
import sol_graph as sg

CURATED = "corpus/scabench/curated.json"
CACHE = "runs/geom_graphs_cache.pkl"
TMP = "/tmp/geom_dir"
MIN_FN, MIN_BUG = 50, 6        # need >=6 buggy to split seed/eval
K_SPLITS, SEED_FRAC, DECAY, ALPHA = 10, 0.5, 0.5, 0.85
RNG = random.Random(42)

def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "geom"})
    data = urllib.request.urlopen(req, timeout=60).read()
    with tarfile.open(fileobj=io.BytesIO(data)) as t: t.extractall(dest)

def build_cache():
    projects = json.load(open(CURATED)); out = {}
    os.makedirs(TMP, exist_ok=True)
    for p in projects:
        pid = p["project_id"]; cb = p.get("codebases") or []
        url = cb[0].get("tarball_url") if cb else None
        if not url: continue
        vtext = " ".join((v.get("title","")+" "+v.get("description","")) for v in p.get("vulnerabilities",[])).lower()
        dest = os.path.join(TMP, pid)
        try:
            if os.path.isdir(dest): shutil.rmtree(dest)
            os.makedirs(dest, exist_ok=True); fetch(url, dest)
            files = sg.parse_dir(dest); fns = sg.collect_functions(files)
            if len(fns) < MIN_FN: continue
            G = sg.rich_graph(fns, files)
            if G.number_of_edges() == 0: continue
            cc = max(nx.connected_components(G), key=len); H = G.subgraph(cc).copy()
            fn_nodes = [n for n,d in H.nodes(data=True) if d.get("kind")=="fn"]
            import re
            def isbug(n):
                nm = str(n).split(".")[-1]
                return len(nm) >= 5 and re.search(r"\b"+re.escape(nm.lower())+r"\b", vtext) is not None
            buggy = set(n for n in fn_nodes if isbug(n))
            if len(buggy) < MIN_BUG: continue
            out[pid] = (H, fn_nodes, buggy)
            print(f"  cached {pid[:44]:44} fn={len(fn_nodes):4d} bug={len(buggy):3d}", flush=True)
        except Exception as e:
            print(f"  err {pid[:44]}: {str(e)[:34]}", flush=True)
        finally:
            if os.path.isdir(dest): shutil.rmtree(dest, ignore_errors=True)
    pickle.dump(out, open(CACHE, "wb")); return out

def auc(score, pos, neg):
    if not pos or not neg: return None
    w = sum((score[a]>score[b])+0.5*(score[a]==score[b]) for a in pos for b in neg)
    return w/(len(pos)*len(neg))

def run():
    cache = pickle.load(open(CACHE,"rb")) if os.path.exists(CACHE) else build_cache()
    print(f"\n{'protocol':44} {'#fn':>4}{'#bug':>4} | {'degr':>5}{'eigc':>5}{'sadj':>5}{'harm':>5}{'heat':>5}")
    print("-"*86)
    pooled = {k:[] for k in ("degree","eigcent","seed_adj","harmonic","heat")}
    rows = []
    for pid,(H,fn_nodes,buggy) in cache.items():
        nodes = list(H.nodes()); idx = {n:i for i,n in enumerate(nodes)}; N=len(nodes)
        A = nx.to_numpy_array(H, nodelist=nodes)
        deg = A.sum(1); D = np.diag(deg); L = D - A
        Pmat = A / np.where(deg[:,None]==0,1,deg[:,None])      # row-stochastic
        degree = {n: H.degree(n) for n in fn_nodes}
        try: eig = nx.eigenvector_centrality(H, max_iter=5000, tol=1e-6)
        except Exception: eig = nx.degree_centrality(H)
        fn_idx = [idx[n] for n in fn_nodes]
        bug_list = [n for n in fn_nodes if n in buggy]; clean_list = [n for n in fn_nodes if n not in buggy]
        per = {k:[] for k in pooled}
        for s in range(K_SPLITS):
            RNG.shuffle(bug_list); RNG.shuffle(clean_list)
            nb = max(1,int(len(bug_list)*SEED_FRAC))
            seed_bug, eval_bug = bug_list[:nb], bug_list[nb:]
            seed_cln, eval_cln = clean_list[:nb], clean_list[nb:]
            if not eval_bug or not eval_cln: continue
            # --- harmonic (Dirichlet two-class): pin seeds, solve L-harmonic for rest ---
            lab = {idx[n]:1.0 for n in seed_bug}; lab.update({idx[n]:0.0 for n in seed_cln})
            lidx = sorted(lab); uidx = [i for i in range(N) if i not in lab]
            uset = {i:j for j,i in enumerate(uidx)}
            Luu = L[np.ix_(uidx,uidx)]; Lul = L[np.ix_(uidx,lidx)]
            fl = np.array([lab[i] for i in lidx])
            try: fu = np.linalg.solve(Luu, -Lul@fl)
            except np.linalg.LinAlgError: fu = np.zeros(len(uidx))
            harm = {}
            for n in fn_nodes:
                i=idx[n]; harm[n]= lab[i] if i in lab else fu[uset[i]]
            # --- heat / RWR personalized PageRank from buggy seeds ---
            s_vec = np.zeros(N)
            for n in seed_bug: s_vec[idx[n]] = 1.0
            if s_vec.sum()>0: s_vec/=s_vec.sum()
            heatf = (1-ALPHA)*np.linalg.solve(np.eye(N)-ALPHA*Pmat.T, s_vec)
            heat = {n: heatf[idx[n]] for n in fn_nodes}
            # --- seed_adj TRIVIAL: decayed BFS proximity to nearest seed-buggy ---
            sadj = {n:0.0 for n in fn_nodes}
            for sb in seed_bug:
                dist = nx.single_source_shortest_path_length(H, sb, cutoff=4)
                for n,dd in dist.items():
                    if n in sadj: sadj[n]=max(sadj[n], DECAY**dd)
            # score eval set (held out, seeds excluded)
            for k,sc in (("degree",degree),("eigcent",eig),("seed_adj",sadj),("harmonic",harm),("heat",heat)):
                a = auc(sc, eval_bug, eval_cln)
                if a is not None: per[k].append(a)
                # pooled rank-norm within this split's eval pool
                pool = eval_bug+eval_cln
                order = sorted(pool, key=lambda n: sc[n])
                rk = {n:(i/(len(order)-1) if len(order)>1 else .5) for i,n in enumerate(order)}
                for n in pool: pooled[k].append((rk[n], n in buggy))
        m = {k:(st.mean(v) if v else float('nan')) for k,v in per.items()}
        rows.append((pid,len(fn_nodes),len(buggy),m))
        print(f"{pid[:44]:44} {len(fn_nodes):4d}{len(buggy):4d} | "
              f"{m['degree']:5.2f}{m['eigcent']:5.2f}{m['seed_adj']:5.2f}{m['harmonic']:5.2f}{m['heat']:5.2f}")
    print("-"*86)
    for k in ("degree","eigcent","seed_adj","harmonic","heat"):
        vals=[r[3][k] for r in rows if r[3][k]==r[3][k]]
        print(f"  mean per-protocol AUC  {k:9}= {st.mean(vals):.3f}   (n={len(vals)})")
    print()
    for k in ("degree","eigcent","seed_adj","harmonic","heat"):
        B=[s for s,b in pooled[k] if b]; C=[s for s,b in pooled[k] if not b]
        a=sum((x>y)+0.5*(x==y) for x in B for y in C)/(len(B)*len(C))
        print(f"  pooled AUC             {k:9}= {a:.3f}   ({len(B)} held-out buggy / {len(C)} clean)")
    json.dump([(r[0],r[1],r[2],r[3]) for r in rows], open("runs/geom_dirichlet_probe.json","w"), indent=1)
    print(f"\nwrote runs/geom_dirichlet_probe.json ({len(rows)} protocols)")

if __name__ == "__main__":
    run()
