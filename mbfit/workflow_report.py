"""What a workflow run hands the reader. FR-091, FR-092.

Three tables and one page. The tables are for a reader who will open them in
their own tools; the page is for a reader who will not.

Every human-facing word on the page arrives in `text`, built by the caller from
`mbfit/messages.py`. This module stays ASCII (Article IV), so a label can be
improved without touching the code that lays it out, and the layout can be
tested without reading Korean.

The page fetches nothing. It is written to be sent by email to someone behind a
firewall and opened with no connection, so every script and style is inline and
no font is named that the machine may not have.
"""

from __future__ import annotations

import csv
import json
import math
import pathlib
from typing import Any

import numpy as np

SUMMARY = "workflow_summary.csv"
CARRIERS = "workflow_carriers.csv"
CANDIDATES = "workflow_candidates.csv"
PAGE = "report.html"

# One point in this many is drawn. 361 records per sweep make a page that is
# slow to scroll with twelve temperatures and no clearer for it.
CURVE_STEP = 3


def _cell(value: Any) -> Any:
    """A table cell: NaN and infinity as empty, never as a number that is not."""
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    return value


def _number(value: Any) -> Any:
    """A JSON value: JSON has no NaN, and a plotting line reads null as a gap."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def write_tables(result, out: pathlib.Path) -> list[pathlib.Path]:
    """FR-091. Three tables, each self-contained."""
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)

    summary = out / SUMMARY
    with summary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "T(K)", "count_rule", "combination", "beyond_bound", "grade",
            "residual_over_noise_rhoxx", "residual_over_noise_rhoxy",
            "runs_z_rhoxx", "runs_z_rhoxy", "noise_rhoxx(microohm_cm)", "noise_rhoxy(microohm_cm)",
            "R2_rhoxx", "R2_rhoxy",
            "RMSE_rhoxx(microohm_cm)", "RMSE_rhoxy(microohm_cm)",
            "condition_number", "spread", "gates_failed", "outside_window",
            "undetermined_better", "undetermined_ratio",
            "island_neighbours", "island_price",
            "iterations", "loop_stop", "seconds",
        ])
        for item in result.outcomes:
            writer.writerow([
                item.T_K, item.mode, item.label, bool(getattr(item, "beyond_bound", False)),
                item.grade,
                _cell(getattr(item, "residual_over_noise_xx", float("nan"))),
                _cell(getattr(item, "residual_over_noise_xy", float("nan"))),
                _cell(getattr(item, "runs_z_xx", float("nan"))),
                _cell(getattr(item, "runs_z_xy", float("nan"))),
                _cell(getattr(item, "noise_rhoxx", float("nan"))),
                _cell(getattr(item, "noise_rhoxy", float("nan"))),
                _cell(item.r2_rhoxx), _cell(item.r2_rhoxy),
                _cell(item.rmse_rhoxx), _cell(item.rmse_rhoxy),
                _cell(item.condition_number), _cell(item.spread),
                ";".join(item.failed_gates), ";".join(item.escaped_window),
                getattr(item, "undetermined_better", ""),
                _cell(getattr(item, "undetermined_ratio", float("nan"))),
                getattr(item, "island_label", ""),
                _cell(getattr(item, "island_price", float("nan"))),
                item.iterations, getattr(item, "stop_reason", ""),
                round(item.seconds, 1),
            ])

    carriers = out / CARRIERS
    with carriers.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "T(K)", "name", "kind", "density(cm^-3)", "mobility(cm^2_Vs)",
            "conduction_share", "mu_B_at_9T",
        ])
        for item in result.outcomes:
            for carrier in item.carriers:
                writer.writerow([
                    item.T_K, carrier["name"], carrier["kind"],
                    _cell(carrier["density_cm3"]), _cell(carrier["mobility_cm2Vs"]),
                    _cell(carrier["conduction_share"]), _cell(carrier["mu_B_at_9T"]),
                ])

    candidates = out / CANDIDATES
    with candidates.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "T(K)", "holes", "electrons", "RMSE_rhoxx(microohm_cm)",
            "RMSE_rhoxy(microohm_cm)", "condition_number", "spread",
            "weakest_share", "on_bound", "out_of_budget", "starts_finished", "seconds",
        ])
        for item in result.outcomes:
            for c in item.candidates:
                writer.writerow([
                    item.T_K, c.n_hole, c.n_electron,
                    _cell(c.rmse_rhoxx), _cell(c.rmse_rhoxy),
                    _cell(c.condition_number), _cell(c.spread),
                    _cell(c.weakest_share), c.at_bound, c.expired, c.n_starts,
                    round(c.seconds, 1),
                ])

    return [summary, carriers, candidates]


def payload(result) -> dict[str, Any]:
    """Everything the page draws, as plain JSON values."""
    from .workflow import _model_of, roughness_of

    groups = {}
    if getattr(result, "dataset", None) is not None:
        groups = {float(g.T_K): g for g in result.dataset.groups}
    polarity = float(getattr(result, "hall_polarity", 1.0))

    temperatures = []
    for item in result.outcomes:
        entry = {
            "T": item.T_K, "mode": item.mode, "label": item.label,
            "grade": item.grade,
            "beyond": bool(getattr(item, "beyond_bound", False)),
            "ratio_xx": _number(getattr(item, "residual_over_noise_xx", None)),
            "ratio_xy": _number(getattr(item, "residual_over_noise_xy", None)),
            "runs_xx": _number(getattr(item, "runs_z_xx", None)),
            "r2xx": _number(item.r2_rhoxx), "r2xy": _number(item.r2_rhoxy),
            "rmsexx": _number(item.rmse_rhoxx), "rmsexy": _number(item.rmse_rhoxy),
            "condition": _number(item.condition_number),
            "spread": _number(item.spread),
            "failed": list(item.failed_gates),
            "escaped": list(item.escaped_window),
            "undetermined": getattr(item, "undetermined_better", ""),
            "undetermined_ratio": _number(getattr(item, "undetermined_ratio", None)),
            # FR-090. The count both neighbours share, where this sweep carries
            # more, and what holding it to theirs costs in residual.
            "island": getattr(item, "island_label", ""),
            "island_price": _number(getattr(item, "island_price", None)),
            # FR-081. The spectrum that bounded this sweep, and the window its
            # peaks were turned into, so the page can show what the count and
            # the range were read from.
            "spectrum": getattr(item, "spectrum", {}) or None,
            "window": {kind: [_number(edge) for edge in edges]
                       for kind, edges in (item.bounds or {}).get("window", {}).items()},
            "iterations": item.iterations,
            "stop": getattr(item, "stop_reason", ""),
            "seconds": round(item.seconds, 1),
            "carriers": [
                {"name": c["name"], "kind": c["kind"],
                 "n": _number(c["density_cm3"]), "mu": _number(c["mobility_cm2Vs"]),
                 "share": _number(c["conduction_share"])}
                for c in item.carriers
            ],
            "candidates": [
                {"h": c.n_hole, "e": c.n_electron,
                 "rmsexx": _number(c.rmse_rhoxx), "condition": _number(c.condition_number),
                 "spread": _number(c.spread), "share": _number(c.weakest_share),
                 "bound": bool(c.at_bound), "expired": bool(c.expired),
                 "starts": int(c.n_starts),
                 "seconds": round(c.seconds, 1)}
                for c in item.candidates
            ],
            "curve": None,
        }
        group = groups.get(float(item.T_K))
        if group is not None and item.carriers:
            fit_xx, fit_xy = _model_of(group, list(item.carriers), polarity)
            step = slice(None, None, CURVE_STEP)
            entry["curve"] = {
                "B": [_number(v) for v in np.asarray(group.B_T)[step]],
                "xx": [_number(v) for v in np.asarray(group.rhoxx_uohmcm)[step]],
                "xy": [_number(v) for v in np.asarray(group.rhoxy_uohmcm)[step]],
                "fxx": [_number(v) for v in np.asarray(fit_xx)[step]],
                "fxy": [_number(v) for v in np.asarray(fit_xy)[step]],
            }
        temperatures.append(entry)
    return {"mode": result.mode, "seconds": round(result.seconds, 1),
            # FR-107, FR-109. The measure the coupling penalty acts on, for the
            # run as a whole. The page of feature 005 shows it for a band the
            # reader picks; a reader of the command line gets it for the band
            # they ran, and `nan` where the question does not apply.
            "roughness": _number(roughness_of(result.outcomes)),
            "temperatures": temperatures}


def _embed(value: Any) -> str:
    """JSON for a script tag. `</` would close the tag early, so it is split."""
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).replace("</", "<\\/")


def write_page(result, out: pathlib.Path, text: dict[str, str]) -> pathlib.Path:
    """FR-092. One file, no network, the verdict before the numbers."""
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    page = out / PAGE
    html = (_TEMPLATE
            .replace("__DATA__", _embed(payload(result)))
            .replace("__TEXT__", _embed(dict(text))))
    page.write_text(html, encoding="utf-8")
    return page


_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>report</title>
<style>
:root{--ground:#f3f5f6;--surface:#fff;--sunk:#e8ecef;--ink:#16212b;--soft:#4a5c69;
--faint:#798894;--rule:#d2dae0;--strong:#a9b6c0;--hole:#b4571c;--holefill:#d98a48;
--elec:#1d6c87;--elecfill:#4e9cb8;--spine:#2b3a5c;--warn:#8a5a00;}
@media (prefers-color-scheme:dark){:root{--ground:#0e161d;--surface:#16222c;--sunk:#0a1116;
--ink:#e4ecf1;--soft:#a0b1be;--faint:#6d8190;--rule:#273742;--strong:#3d5261;
--hole:#e4924e;--holefill:#c0702f;--elec:#63b6d6;--elecfill:#3a8cab;--spine:#93a9d0;--warn:#e0b050;}}
*{box-sizing:border-box}
body{margin:0;padding:0 18px;background:var(--ground);color:var(--ink);
font:15px/1.6 system-ui,-apple-system,"Segoe UI","Malgun Gothic",sans-serif}
.page{max-width:1000px;margin:0 auto;padding:36px 0 80px}
h1{font-size:28px;margin:0 0 6px;line-height:1.2}
h2{font-size:20px;margin:40px 0 4px}
.sub{color:var(--soft);margin:0 0 14px;max-width:70ch}
.notice{border-left:3px solid var(--spine);background:var(--surface);padding:10px 14px;margin:14px 0;max-width:80ch}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;min-width:560px;font-variant-numeric:tabular-nums;font-size:13.5px}
th,td{padding:6px 9px;border-bottom:1px solid var(--rule);text-align:right;white-space:nowrap}
th{color:var(--faint);font-weight:600;font-size:11.5px;text-transform:uppercase;letter-spacing:.04em}
th:first-child,td:first-child{text-align:left}
tr.pick{cursor:pointer} tr.pick:hover td{background:var(--sunk)}
tr.on td{background:var(--sunk)}
.grade{display:inline-block;min-width:1.8em;text-align:center;font-weight:700;border:1px solid currentColor;padding:0 5px}
.gA{color:var(--spine)} .gB{color:var(--hole)} .gC,.gD{color:var(--faint)}
.bad{color:var(--warn)} .dim{color:var(--faint)} .h{color:var(--hole)} .e{color:var(--elec)}
.temps{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}
.temps button{font:inherit;padding:4px 11px;border:1px solid var(--strong);background:var(--surface);color:var(--ink);cursor:pointer}
.temps button[aria-pressed=true]{background:var(--ink);color:var(--ground);border-color:var(--ink)}
.temps button:focus-visible{outline:2px solid var(--spine);outline-offset:2px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media (max-width:760px){.pair{grid-template-columns:1fr}}
.plot{background:var(--surface);border:1px solid var(--rule);padding:10px}
.plot svg{display:block;width:100%;height:auto}
.legend{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:12.5px;color:var(--soft);margin-top:6px}
.fold{margin-top:14px;border-top:1px solid var(--rule);padding-top:8px}
.fold>summary{cursor:pointer;color:var(--soft);font-size:13.5px;padding:3px 0}
.fold>summary:focus-visible{outline:2px solid var(--spine);outline-offset:2px}
.sw{display:inline-block;width:14px;height:3px;vertical-align:middle;margin-right:5px}
footer{margin-top:50px;border-top:1px solid var(--rule);padding-top:14px;color:var(--faint);font-size:13px;max-width:80ch}
</style>
</head>
<body>
<div class="page">
<h1 id="title"></h1>
<p class="sub" id="lede"></p>
<div class="notice" id="modenotice"></div>

<h2 id="h-verdict"></h2>
<p class="sub" id="p-verdict"></p>
<div class="scroll"><table><thead id="verdict-head"></thead><tbody id="verdict-body"></tbody></table></div>

<h2 id="h-curves"></h2>
<p class="sub" id="p-curves"></p>
<div class="temps" id="temps"></div>
<div class="pair"><div class="plot" id="plot-xx"></div><div class="plot" id="plot-xy"></div></div>
<div class="legend" id="curve-legend"></div>
<div class="scroll"><table><thead id="carrier-head"></thead><tbody id="carrier-body"></tbody></table></div>

<details class="fold"><summary id="s-spectrum"></summary>
<p class="sub" id="p-spectrum"></p>
<div class="pair"><div class="plot" id="plot-sh"></div><div class="plot" id="plot-se"></div></div>
<div class="legend" id="spectrum-legend"></div>
</details>

<h2 id="h-params"></h2>
<p class="sub" id="p-params"></p>
<p class="sub" id="roughness"></p>
<div class="pair"><div class="plot" id="plot-n"></div><div class="plot" id="plot-mu"></div></div>

<h2 id="h-cands"></h2>
<p class="sub" id="p-cands"></p>
<div class="scroll"><table><thead id="cand-head"></thead><tbody id="cand-body"></tbody></table></div>

<footer><p id="f-interval"></p><p id="f-mobility"></p></footer>
</div>
<script>
var D = __DATA__;
var T = __TEXT__;
var NS = "http://www.w3.org/2000/svg";
function $(id){return document.getElementById(id);}
function say(id,key){var n=$(id); if(n) n.textContent = T[key] || "";}
function el(name, attrs, text){var n=document.createElementNS(NS,name);
  for (var k in attrs) n.setAttribute(k, attrs[k]); if (text!==undefined) n.textContent=text; return n;}
function fmt(v,d){return (v===null||v===undefined)? "" : Number(v).toFixed(d);}
function sci(v){ if (v===null||v===undefined) return ""; if (v===0) return "0";
  var e=Math.floor(Math.log10(Math.abs(v))); return (v/Math.pow(10,e)).toFixed(2)+"e"+e;}
function cell(tr,text,cls){var td=document.createElement("td"); td.textContent=text; if(cls) td.className=cls; tr.appendChild(td); return td;}
function head(id, keys){var tr=document.createElement("tr");
  keys.forEach(function(k){var th=document.createElement("th"); th.textContent=T[k]||k; tr.appendChild(th);});
  $(id).replaceChildren(tr);}

say("title","title"); say("lede","lede");
$("modenotice").textContent = D.mode==="peaks" ? T.count_notice_peaks : T.count_notice_data;
["verdict","curves","params","cands"].forEach(function(s){say("h-"+s, s+"_heading"); say("p-"+s, s+"_intro");});
say("f-interval","interval_notice"); say("f-mobility","effective_mobility");
say("s-spectrum","spectrum_show"); say("p-spectrum","spectrum_note");
$("roughness").textContent = (D.roughness===null || D.roughness===undefined)
  ? T.roughness_none
  : T.roughness_label + ": " + fmt(D.roughness,3) + ". " + T.roughness_note;

var gateName = {fits:T.gate_fits, reproducible:T.gate_reproducible, earns:T.gate_earns, free:T.gate_free};
var current = D.temperatures.length ? D.temperatures[0].T : null;

function verdict(){
  head("verdict-head", ["col_T","col_combo","col_fit_ratio","col_grade","col_r2xx","col_r2xy","col_cond","col_failed","col_escaped","col_undetermined","col_island","col_stop"]);
  var body=$("verdict-body"); body.replaceChildren();
  D.temperatures.forEach(function(t){
    var tr=document.createElement("tr"); tr.className="pick"+(t.T===current?" on":"");
    tr.addEventListener("click", function(){ show(t.T); });
    cell(tr, t.T);
    cell(tr, t.label + (t.beyond ? " " + T.beyond_mark : ""), t.beyond ? "bad" : "");
    cell(tr, t.ratio_xx === null ? "" : fmt(t.ratio_xx,1) + " / " + fmt(t.ratio_xy,1));
    var g=cell(tr,""); var span=document.createElement("span");
    span.className="grade g"+(t.grade==="-"?"D":t.grade); span.textContent=t.grade;
    span.title = T["grade_"+(t.grade==="-"?"dash":t.grade)] || ""; g.appendChild(span);
    cell(tr, fmt(t.r2xx,5)); cell(tr, fmt(t.r2xy,5)); cell(tr, sci(t.condition));
    var failed = !t.carriers.length ? T.no_answer : (t.failed.length ? t.failed.map(function(k){return gateName[k]||k;}).join(", ") : T.none);
    cell(tr, failed, t.failed.length ? "bad" : "dim");
    cell(tr, t.escaped.length ? t.escaped.join(", ") : T.none, t.escaped.length ? "bad" : "dim");
    cell(tr, t.undetermined ? t.undetermined + ", " + fmt(t.undetermined_ratio,2) + T.undetermined_times : T.none, t.undetermined ? "bad" : "dim");
    cell(tr, t.island ? t.island + ", " + fmt(t.island_price,2) + T.island_times : T.none, t.island ? "bad" : "dim");
    cell(tr, t.stop ? (T["stop_"+t.stop] || t.stop) + " (" + t.iterations + ")" : "", t.stop && t.stop!=="converged" ? "bad" : "dim");
    body.appendChild(tr);
  });
}

function drawCurve(id, t, key, label){
  var box=$(id); box.replaceChildren();
  if (!t.curve){ box.textContent = T.no_curve; return; }
  var B=t.curve.B, d=t.curve[key], f=t.curve["f"+key];
  var W=460,H=300,L=58,R=12,TOP=14,BOT=40;
  var lo=Infinity,hi=-Infinity;
  d.concat(f).forEach(function(v){ if(v!==null){lo=Math.min(lo,v);hi=Math.max(hi,v);} });
  if (!isFinite(lo)) { box.textContent = T.no_curve; return; }
  var pad=(hi-lo)*0.06||1; lo-=pad; hi+=pad;
  var bmin=Math.min.apply(null,B), bmax=Math.max.apply(null,B);
  function x(b){return L+(b-bmin)/(bmax-bmin||1)*(W-L-R);}
  function y(v){return H-BOT-(v-lo)/(hi-lo)*(H-TOP-BOT);}
  var s=el("svg",{viewBox:"0 0 "+W+" "+H,role:"img","aria-label":label});
  for (var k=0;k<=4;k++){ var v=lo+(hi-lo)*k/4;
    s.appendChild(el("line",{x1:L,x2:W-R,y1:y(v),y2:y(v),stroke:"var(--rule)"}));
    s.appendChild(el("text",{x:L-6,y:y(v)+4,"text-anchor":"end","font-size":"10.5",fill:"var(--faint)"}, Math.abs(v)>=100? v.toFixed(0): v.toFixed(2)));
  }
  [bmin,0,bmax].forEach(function(b){ s.appendChild(el("text",{x:x(b),y:H-BOT+16,"text-anchor":"middle","font-size":"10.5",fill:"var(--faint)"}, b.toFixed(0))); });
  s.appendChild(el("text",{x:(L+W-R)/2,y:H-6,"text-anchor":"middle","font-size":"11.5",fill:"var(--soft)"}, T.field));
  s.appendChild(el("text",{x:6,y:12,"font-size":"11.5",fill:"var(--soft)"}, label));
  B.forEach(function(b,i){ if(d[i]!==null) s.appendChild(el("circle",{cx:x(b),cy:y(d[i]),r:"1.8",fill:"var(--faint)"})); });
  var path=""; B.forEach(function(b,i){ if(f[i]!==null) path+=(path?"L":"M")+x(b).toFixed(1)+" "+y(f[i]).toFixed(1); });
  s.appendChild(el("path",{d:path,fill:"none",stroke:"var(--spine)","stroke-width":"2"}));
  box.appendChild(s);
}

function drawSpectrum(id, t, kind, label){
  // FR-110. What bounded the search, so that the count and the range the
  // reader is being asked to accept can be looked at rather than taken. The
  // vertical axis is the normalised weight the spectrum solves for; a reader
  // who takes it for a density reads a peak height as a carrier count.
  var box=$(id); box.replaceChildren();
  var branch = t.spectrum && t.spectrum[kind];
  var mu = branch && branch.mobility_cm2Vs;
  if (!mu || mu.length < 2){ box.textContent = T.no_spectrum; return; }
  var w = branch.weight || [], peaks = branch.peaks_cm2Vs || [];
  var win = (t.window || {})[kind] || [];
  var W=460,H=260,L=52,R=14,TOP=18,BOT=40;
  var lo=Math.log10(mu[0]), hi=Math.log10(mu[mu.length-1]);
  if (!isFinite(lo) || !isFinite(hi) || hi<=lo){ box.textContent = T.no_spectrum; return; }
  var wmax=0; w.forEach(function(v){ if(v!==null && v>wmax) wmax=v; });
  if (!(wmax>0)) wmax=1;
  function x(v){return L+(Math.log10(v)-lo)/(hi-lo)*(W-L-R);}
  function y(v){return H-BOT-(v/wmax)*(H-TOP-BOT);}
  var s=el("svg",{viewBox:"0 0 "+W+" "+H,role:"img","aria-label":label});
  if (win.length===2 && win[0]!==null && win[1]!==null){
    var a=x(Math.max(win[0],mu[0])), b=x(Math.min(win[1],mu[mu.length-1]));
    if (b>a) s.appendChild(el("rect",{x:a,y:TOP,width:b-a,height:H-TOP-BOT,fill:"var(--sunk)"}));
  }
  for (var d=Math.ceil(lo); d<=Math.floor(hi); d++){
    var gx=x(Math.pow(10,d));
    s.appendChild(el("line",{x1:gx,x2:gx,y1:TOP,y2:H-BOT,stroke:"var(--rule)"}));
    s.appendChild(el("text",{x:gx,y:H-BOT+16,"text-anchor":"middle","font-size":"10.5",fill:"var(--faint)"},"1e"+d));
  }
  s.appendChild(el("line",{x1:L,x2:W-R,y1:H-BOT,y2:H-BOT,stroke:"var(--strong)"}));
  var col = kind==="hole" ? "var(--hole)" : "var(--elec)";
  var path="";
  mu.forEach(function(v,i){ if(w[i]!==null && v>0) path+=(path?"L":"M")+x(v).toFixed(1)+" "+y(w[i]).toFixed(1); });
  s.appendChild(el("path",{d:path,fill:"none",stroke:col,"stroke-width":"1.8"}));
  peaks.forEach(function(v){ if(v===null || v<=0) return;
    s.appendChild(el("line",{x1:x(v),x2:x(v),y1:TOP,y2:H-BOT,stroke:col,"stroke-dasharray":"3 3"}));
    s.appendChild(el("text",{x:x(v),y:TOP-5,"text-anchor":"middle","font-size":"10",fill:col},
                   Math.round(v).toLocaleString("en-US"))); });
  s.appendChild(el("text",{x:(L+W-R)/2,y:H-6,"text-anchor":"middle","font-size":"11.5",fill:"var(--soft)"},T.mobility));
  s.appendChild(el("text",{x:6,y:12,"font-size":"11.5",fill:"var(--soft)"},label+" - "+T.spectrum_weight));
  box.appendChild(s);
}

function carriers(t){
  head("carrier-head", ["col_name","col_kind","col_density","col_mobility","col_share"]);
  var body=$("carrier-body"); body.replaceChildren();
  t.carriers.forEach(function(c){
    var tr=document.createElement("tr"); var cls = c.kind==="hole" ? "h" : "e";
    cell(tr,c.name,cls); cell(tr, c.kind==="hole"?T.hole:T.electron, cls);
    cell(tr, sci(c.n)); cell(tr, c.mu===null?"":Math.round(c.mu).toLocaleString("en-US"));
    cell(tr, c.share===null?"":(c.share*100).toFixed(2)+" %");
    body.appendChild(tr);
  });
}

function candidates(t){
  head("cand-head", ["col_holes","col_electrons","col_rmse","col_cond","col_spread","col_share","col_bound","col_expired","col_starts","col_seconds"]);
  var body=$("cand-body"); body.replaceChildren();
  if (!t.candidates.length){ var tr=document.createElement("tr"); var td=cell(tr, T.no_candidates, "dim"); td.colSpan=9; body.appendChild(tr); return; }
  t.candidates.forEach(function(c){
    var tr=document.createElement("tr"); var chosen = (c.h+"h+"+c.e+"e")===t.label;
    if (chosen) tr.className="on";
    cell(tr,c.h); cell(tr,c.e); cell(tr, c.rmsexx===null? T.out_of_budget : c.rmsexx.toFixed(5));
    cell(tr, sci(c.condition)); cell(tr, sci(c.spread));
    cell(tr, c.share===null?"":(c.share*100).toFixed(3)+" %");
    cell(tr, c.bound?T.yes:T.no, c.bound?"bad":"dim"); cell(tr, c.expired?T.yes:T.no, "dim"); cell(tr, c.starts);
    cell(tr, c.seconds);
    body.appendChild(tr);
  });
}

function versusT(id, pick, label){
  var box=$(id); box.replaceChildren();
  var series={};
  D.temperatures.forEach(function(t){ t.carriers.forEach(function(c){
    var v=pick(c); if (v===null||v<=0) return;
    (series[c.name]=series[c.name]||{kind:c.kind,pts:[]}).pts.push([t.T,v]); }); });
  var names=Object.keys(series); if(!names.length){ box.textContent=T.no_curve; return; }
  var lo=Infinity,hi=-Infinity,tmin=Infinity,tmax=-Infinity;
  names.forEach(function(n){ series[n].pts.forEach(function(p){ lo=Math.min(lo,p[1]);hi=Math.max(hi,p[1]);tmin=Math.min(tmin,p[0]);tmax=Math.max(tmax,p[0]); }); });
  lo=Math.floor(Math.log10(lo)); hi=Math.ceil(Math.log10(hi)); if(hi===lo) hi=lo+1;
  var W=460,H=300,L=52,R=60,TOP=14,BOT=40;
  function x(v){return L+(v-tmin)/((tmax-tmin)||1)*(W-L-R);}
  function y(v){return H-BOT-(Math.log10(v)-lo)/(hi-lo)*(H-TOP-BOT);}
  var s=el("svg",{viewBox:"0 0 "+W+" "+H,role:"img","aria-label":label});
  for (var d=lo; d<=hi; d++){ s.appendChild(el("line",{x1:L,x2:W-R,y1:y(Math.pow(10,d)),y2:y(Math.pow(10,d)),stroke:"var(--rule)"}));
    s.appendChild(el("text",{x:L-6,y:y(Math.pow(10,d))+4,"text-anchor":"end","font-size":"10.5",fill:"var(--faint)"},"1e"+d)); }
  s.appendChild(el("text",{x:(L+W-R)/2,y:H-6,"text-anchor":"middle","font-size":"11.5",fill:"var(--soft)"},T.temperature));
  s.appendChild(el("text",{x:6,y:12,"font-size":"11.5",fill:"var(--soft)"},label));
  names.forEach(function(n){ var ser=series[n]; var col = ser.kind==="hole"?"var(--hole)":"var(--elec)";
    var path=""; ser.pts.forEach(function(p){ path+=(path?"L":"M")+x(p[0]).toFixed(1)+" "+y(p[1]).toFixed(1); });
    s.appendChild(el("path",{d:path,fill:"none",stroke:col,"stroke-width":"1.8"}));
    ser.pts.forEach(function(p){ s.appendChild(el("circle",{cx:x(p[0]),cy:y(p[1]),r:"2.6",fill:col})); });
    var last=ser.pts[ser.pts.length-1];
    s.appendChild(el("text",{x:x(last[0])+5,y:y(last[1])+4,"font-size":"10.5",fill:col},n)); });
  box.appendChild(s);
}

function show(T0){
  current=T0;
  var t=D.temperatures.filter(function(u){return u.T===T0;})[0]; if(!t) return;
  Array.prototype.forEach.call($("temps").children, function(b){ b.setAttribute("aria-pressed", String(Number(b.dataset.t)===T0)); });
  verdict();
  drawCurve("plot-xx", t, "xx", T.rhoxx);
  drawCurve("plot-xy", t, "xy", T.rhoxy);
  drawSpectrum("plot-sh", t, "hole", T.hole);
  drawSpectrum("plot-se", t, "electron", T.electron);
  carriers(t); candidates(t);
}

D.temperatures.forEach(function(t){ var b=document.createElement("button"); b.type="button";
  b.textContent=t.T; b.dataset.t=t.T; b.setAttribute("aria-pressed","false");
  b.addEventListener("click", function(){ show(t.T); }); $("temps").appendChild(b); });
$("curve-legend").innerHTML = "";
[["var(--faint)", T.measured],["var(--spine)", T.fitted]].forEach(function(p){
  var span=document.createElement("span"); var sw=document.createElement("i"); sw.className="sw"; sw.style.background=p[0];
  span.appendChild(sw); span.appendChild(document.createTextNode(p[1])); $("curve-legend").appendChild(span); });
[["var(--sunk)", T.spectrum_window],["var(--strong)", T.spectrum_peak]].forEach(function(p){
  var span=document.createElement("span"); var sw=document.createElement("i"); sw.className="sw"; sw.style.background=p[0];
  span.appendChild(sw); span.appendChild(document.createTextNode(p[1])); $("spectrum-legend").appendChild(span); });
versusT("plot-n", function(c){return c.n;}, T.density);
versusT("plot-mu", function(c){return c.mu;}, T.mobility);
verdict();
if (current!==null) show(current);
</script>
</body>
</html>
"""
