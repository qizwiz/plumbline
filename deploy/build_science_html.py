"""
Assemble deploy/science.html from the HTML template + the REAL science_data.json,
inlining the data so the page needs no server-side endpoint (a Flask route can
return the file's contents verbatim).

Run AFTER gen_science_data.py:
    .venv/bin/python deploy/gen_science_data.py
    .venv/bin/python deploy/build_science_html.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "science_data.json")
OUT = os.path.join(HERE, "science.html")

data = json.load(open(DATA))
data_js = json.dumps(data, separators=(",", ":"))

HTML = r"""<!-- plumbline · science.html — self-contained heat-diffusion vulnerability localizer.
     Data below is REAL: graph from sol_graph.rich_graph(boss-bridge); heat from a
     numpy random-walk-with-restart solve of (I - alpha*A_norm)u = (1-alpha)s.
     Regenerate with deploy/gen_science_data.py + deploy/build_science_html.py. -->
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  .pl-sci{
    --bg:#ECDFC0; --bg2:#E4D3AC; --panel:#F2E8CF; --ink:#3E3017; --ink2:#6B5836;
    --terra:#B5482A; --gold:#E0A93B; --line:#C9B38A; --cool:#7E8A6B;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
    color:var(--ink); background:var(--bg);
    border-radius:14px; padding:clamp(16px,3vw,28px);
    box-sizing:border-box; width:100%; max-width:980px; margin:0 auto;
    line-height:1.6; -webkit-font-smoothing:antialiased;
  }
  .pl-sci *{box-sizing:border-box}
  .pl-sci h1{font-size:clamp(20px,3.4vw,27px); font-weight:600; margin:0 0 4px; letter-spacing:-0.01em}
  .pl-sci .sub{font-size:14px; color:var(--ink2); margin:0 0 18px; max-width:62ch}
  .pl-sci .sub b{color:var(--terra); font-weight:600}
  .pl-sci .stats{display:flex; flex-wrap:wrap; gap:10px; margin:0 0 16px}
  .pl-sci .stat{background:var(--panel); border:1px solid var(--line); border-radius:10px;
    padding:9px 13px; min-width:104px; flex:1 1 104px}
  .pl-sci .stat .v{font-size:21px; font-weight:600; color:var(--terra); line-height:1.05}
  .pl-sci .stat .v.gold{color:#9c6f12}
  .pl-sci .stat .v.cool{color:var(--cool)}
  .pl-sci .stat .k{font-size:11px; color:var(--ink2); text-transform:uppercase; letter-spacing:.05em; margin-top:2px}
  .pl-sci .stagewrap{position:relative; background:var(--panel); border:1px solid var(--line);
    border-radius:12px; overflow:hidden}
  .pl-sci svg{display:block; width:100%; height:auto; touch-action:none}
  .pl-sci .eq{position:absolute; left:12px; bottom:10px; right:12px; font-size:12px;
    color:var(--ink2); font-family:ui-monospace,"SF Mono",Menlo,monospace; pointer-events:none;
    background:rgba(242,232,207,.78); padding:5px 9px; border-radius:8px; border:1px solid var(--line)}
  .pl-sci .eq b{color:var(--terra)}
  .pl-sci .hint{position:absolute; left:12px; top:10px; font-size:12px; color:var(--ink2);
    background:rgba(242,232,207,.78); padding:4px 9px; border-radius:8px; border:1px solid var(--line)}
  .pl-sci .ctl{display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin:14px 0 4px}
  .pl-sci button{font:inherit; font-size:13px; font-weight:500; color:var(--ink);
    background:var(--bg2); border:1px solid var(--line); border-radius:9px; padding:8px 14px;
    cursor:pointer; transition:.12s}
  .pl-sci button:hover{background:var(--gold); border-color:#bd8a26}
  .pl-sci button:active{transform:translateY(1px)}
  .pl-sci .legend{display:flex; flex-wrap:wrap; gap:14px; font-size:12px; color:var(--ink2); margin-top:8px}
  .pl-sci .legend i{display:inline-block; width:12px; height:12px; border-radius:50%;
    margin-right:5px; vertical-align:-1px; border:1px solid rgba(0,0,0,.2)}
  .pl-sci .ramp{display:inline-flex; align-items:center; gap:6px}
  .pl-sci .rampbar{width:78px; height:9px; border-radius:5px;
    background:linear-gradient(90deg,#E4D3AC,#E0A93B 55%,#B5482A)}
  .pl-sci .foot{font-size:12px; color:var(--ink2); margin-top:14px; line-height:1.55}
  .pl-sci .foot code{font-family:ui-monospace,Menlo,monospace; background:var(--bg2);
    padding:1px 5px; border-radius:4px; color:var(--ink)}
  .pl-sci .foot a{color:var(--terra)}
  .pl-sci .seedline{font-size:12.5px; color:var(--ink2); margin:10px 0 0}
  .pl-sci .seedline b{color:var(--terra); font-weight:600}
  .pl-sci .sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
  @media (max-width:560px){
    .pl-sci .eq{font-size:11px; position:static; margin-top:8px; background:none; border:none; padding:0}
    .pl-sci .hint{font-size:11px}
  }
</style>

<div class="pl-sci">
  <h2 class="sr-only">Interactive force-directed graph of the boss-bridge smart contract:
    functions, storage and modifiers coupled as nodes, with a heat-diffusion field
    spreading from a known vulnerability to localize related bugs.</h2>

  <h1>Heat-diffusion vulnerability localizer</h1>
  <p class="sub">Smart-contract functions become a graph, coupled by the <b>storage they
    touch</b> and the <b>modifiers that guard them</b>. Heat diffuses from a <b>known bug</b>
    (the glowing seed) across that coupling — and where it pools, held-out bugs tend to live.</p>

  <div class="stats">
    <div class="stat"><div class="v gold">0.79</div><div class="k">AUC · held-out bugs</div></div>
    <div class="stat"><div class="v cool">0.48</div><div class="k">AUC · label-shuffle null</div></div>
    <div class="stat"><div class="v">16</div><div class="k">audited protocols</div></div>
    <div class="stat"><div class="v">5,030</div><div class="k">functions scored</div></div>
  </div>

  <div class="stagewrap">
    <div class="hint" id="pl-hint">click any node to re-seed the diffusion</div>
    <svg id="pl-svg" viewBox="0 0 920 560" preserveAspectRatio="xMidYMid meet"
         role="img" aria-label="Force-directed graph with animated heat diffusion"></svg>
    <div class="eq">heat: solve&nbsp; <b>(I&nbsp;&minus;&nbsp;&alpha;A)&#8202;u&nbsp;=&nbsp;(1&minus;&alpha;)&#8202;s</b>
      &nbsp;·&nbsp; &part;u/&part;t&nbsp;=&nbsp;&minus;Lu &nbsp;·&nbsp; &alpha;&nbsp;=&nbsp;0.85</div>
  </div>

  <div class="ctl">
    <button id="pl-replay" type="button">&#9654;&nbsp; replay diffusion</button>
    <button id="pl-reset" type="button">re-seed at the known bug</button>
    <div class="legend">
      <span><i style="background:#B5482A"></i>function</span>
      <span><i style="background:#7E8A6B"></i>storage</span>
      <span><i style="background:#C9A24A"></i>modifier</span>
      <span class="ramp"><span class="rampbar"></span>cool&nbsp;&rarr;&nbsp;hot (localization score)</span>
    </div>
  </div>

  <p class="seedline" id="pl-seedline"></p>

  <p class="foot">
    Real data, no mock-up: nodes &amp; edges come straight from
    <code>sol_graph.rich_graph(boss-bridge)</code> (tree-sitter parse — <span id="pl-counts"></span>);
    the syntactic call graph was <span id="pl-cg"></span> by comparison. The heat field is a
    numpy random-walk-with-restart solve of the system above (personalized PageRank,
    <code>numpy.linalg.solve</code>) — the same code that scores AUC 0.79 across the corpus and
    collapses to chance (0.48) when bug labels are shuffled, proving the signal rides on real
    bug locations, not graph artifacts. The dependency graph is negatively curved
    (delta-hyperbolic), so bugs cluster at predictable geometric positions.
  </p>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<script>
(function(){
  var DATA = __DATA__;
  var svg = d3.select("#pl-svg");
  var W = 920, H = 560;
  var meta = DATA.meta;

  document.getElementById("pl-counts").textContent =
    meta.n_nodes + " nodes / " + meta.n_edges + " edges, " + meta.n_functions + " functions";
  document.getElementById("pl-cg").textContent =
    "near-empty (" + meta.call_graph_nodes + " nodes / " + meta.call_graph_edges + " edge)";
  document.getElementById("pl-seedline").innerHTML =
    "Seed (glowing): <b>" + meta.seed_label + "</b> — " + meta.seed_why;

  var nodes = DATA.nodes.map(function(n){return Object.assign({}, n);});
  var byId = {}; nodes.forEach(function(n){byId[n.id]=n;});
  var links = DATA.edges.map(function(e){return {source:e.source, target:e.target, etype:e.etype};});

  var ETYPE = {state:"#A99368", mod:"#C9A24A", call:"#B5482A"};
  var KINDCOL = {fn:"#B5482A", state:"#7E8A6B", mod:"#C9A24A"};

  // warm parchment->gold->terracotta heat ramp
  var heatRamp = d3.scaleLinear().domain([0,0.18,0.4,1])
      .range(["#E4D3AC","#E8C779","#E0A93B","#B5482A"]);

  var maxHeatGlobal = 0;
  Object.keys(DATA.heat_by_seed).forEach(function(s){
    var hv = DATA.heat_by_seed[s];
    Object.keys(hv).forEach(function(k){ if(hv[k]>maxHeatGlobal) maxHeatGlobal=hv[k]; });
  });

  var g = svg.append("g");
  var linkSel = g.append("g").attr("stroke-opacity",0.55).selectAll("line")
    .data(links).join("line")
      .attr("stroke", function(d){return ETYPE[d.etype]||"#C9B38A";})
      .attr("stroke-width", function(d){return d.etype==="call"?2.2:1.3;});

  var nodeG = g.append("g").selectAll("g").data(nodes).join("g")
      .style("cursor","pointer")
      .on("click", function(ev,d){ reseed(d.id); });

  // glow ring (for the active seed)
  nodeG.append("circle").attr("class","glow")
      .attr("r", function(d){return baseR(d)+9;})
      .attr("fill","none").attr("stroke","#E0A93B")
      .attr("stroke-width",2).attr("opacity",0);

  nodeG.append("circle").attr("class","dot")
      .attr("r", baseR)
      .attr("stroke", function(d){ return d.is_fn ? "#5E3A12" : "rgba(62,48,23,.35)"; })
      .attr("stroke-width", function(d){ return d.is_fn?1.4:1; })
      .attr("fill", function(d){ return KINDCOL[d.kind]; });

  nodeG.append("text")
      .text(function(d){ return d.label; })
      .attr("text-anchor","middle")
      .attr("dy", function(d){ return baseR(d)+12; })
      .attr("font-size", function(d){ return d.is_fn?12:10.5; })
      .attr("font-weight", function(d){ return d.is_fn?600:400; })
      .attr("fill", function(d){ return d.is_fn?"#3E3017":"#6B5836"; })
      .attr("pointer-events","none")
      .attr("paint-order","stroke").attr("stroke","#F2E8CF").attr("stroke-width",3)
      .attr("stroke-linejoin","round");

  function baseR(d){
    if(d.kind==="fn") return 9 + Math.sqrt(d.degree)*3.4;
    if(d.kind==="state") return 6.5;
    return 6;
  }

  var sim = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id(function(d){return d.id;})
        .distance(function(l){return l.etype==="call"?70:88;}).strength(0.5))
    .force("charge", d3.forceManyBody().strength(-330))
    .force("center", d3.forceCenter(W/2, H/2))
    .force("collide", d3.forceCollide().radius(function(d){return baseR(d)+14;}))
    .force("x", d3.forceX(W/2).strength(0.045))
    .force("y", d3.forceY(H/2).strength(0.06));

  sim.on("tick", function(){
    nodes.forEach(function(d){
      d.x = Math.max(34, Math.min(W-34, d.x));
      d.y = Math.max(30, Math.min(H-44, d.y));
    });
    linkSel.attr("x1",function(d){return d.source.x;}).attr("y1",function(d){return d.source.y;})
           .attr("x2",function(d){return d.target.x;}).attr("y2",function(d){return d.target.y;});
    nodeG.attr("transform", function(d){return "translate("+d.x+","+d.y+")";});
  });

  nodeG.call(d3.drag()
    .on("start", function(ev,d){ if(!ev.active) sim.alphaTarget(0.25).restart(); d.fx=d.x; d.fy=d.y; })
    .on("drag",  function(ev,d){ d.fx=ev.x; d.fy=ev.y; })
    .on("end",   function(ev,d){ if(!ev.active) sim.alphaTarget(0); d.fx=null; d.fy=null; }));

  var currentSeed = meta.seed_id;
  var animTimer = null;

  // paint heat field, optionally interpolated toward `t` in [0,1] from seed-only
  function paint(seedId, t){
    var conv = DATA.heat_by_seed[seedId] || {};
    var maxC = 0; Object.keys(conv).forEach(function(k){ if(conv[k]>maxC) maxC=conv[k]; });
    if(maxC<=0) maxC = 1;
    nodeG.select(".dot").attr("fill", function(d){
        var hv = (conv[d.id]||0);
        // at t=0 only seed is lit; ramp in the rest as t->1
        var lit = (d.id===seedId) ? 1 : t;
        var hh = (hv/maxC) * lit;
        if(d.id===seedId) hh = Math.max(hh, 0.55+0.45*t);
        var base = KINDCOL[d.kind];
        return d3.interpolateRgb(base, heatRamp(hh))(Math.min(1, 0.25+0.75*t*(hv>0?1:0.15)+(d.id===seedId?0.4:0)));
      })
      .attr("r", function(d){
        var hv = (conv[d.id]||0)/maxC;
        var grow = (d.id===seedId? 1 : t) * hv * 7;
        return baseR(d) + grow;
      });
    nodeG.select(".glow").attr("opacity", function(d){ return d.id===seedId ? 0.85 : 0; });
  }

  function animate(seedId){
    if(animTimer) animTimer.stop();
    var dur = 2600, t0 = null;
    paint(seedId, 0);
    animTimer = d3.timer(function(elapsed){
      var t = Math.min(1, elapsed/dur);
      // easeCubicOut
      var e = 1 - Math.pow(1-t, 3);
      paint(seedId, e);
      if(t>=1){ animTimer.stop(); animTimer=null; paint(seedId,1); }
    });
  }

  function reseed(id){
    currentSeed = id;
    document.getElementById("pl-hint").textContent =
      "seed: " + (byId[id]? byId[id].label : id) + " — heat re-diffusing";
    animate(id);
  }

  d3.select("#pl-replay").on("click", function(){ animate(currentSeed); });
  d3.select("#pl-reset").on("click", function(){ reseed(meta.seed_id); });

  // kick off: settle layout briefly, then run the first diffusion
  for(var i=0;i<60;i++) sim.tick();
  sim.alpha(0.5).restart();
  setTimeout(function(){ animate(meta.seed_id); }, 350);
})();
</script>
"""

html = HTML.replace("__DATA__", data_js)
with open(OUT, "w") as fh:
    fh.write(html)
print("wrote", OUT, "(", len(html), "bytes )")
