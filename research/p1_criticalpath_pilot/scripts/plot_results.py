"""Render static scientific figures exclusively from the pilot CSVs."""
import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument("report", type=Path)
args = parser.parse_args()
data = args.report / "data"
out = args.report / "figures"

C = {
    "A": "#727c8a", "B": "#3566a8", "C": "#ba7133", "D": "#156b70",
    "E": "#8e5c9c", "F": "#c15755", "G": "#15816b", "S": "#50688c", "W": "#9d8799",
}


def load(name):
    with (data / (name + ".csv")).open() as f:
        return list(csv.DictReader(f))


def save(fig, name):
    fig.savefig(out / (name + ".png"), dpi=160, bbox_inches="tight")
    plt.close(fig)


def spans(wave, method, signal, end):
    ordered = [(float(r["Relative_Cycle"]), int(r["Value"], 16)) for r in wave
               if r["Method"] == method and r["Signal"] == signal]
    return [(a, b - a) for (a, v), (b, _) in zip(ordered, ordered[1:] + [(end, 0)]) if v == 1]


wave = load("wave_hardware_events")
gaps = load("barrier_gap_breakdown")
windows = load("critical_path_intervals")
fig, ax = plt.subplots(figsize=(11, 3.65), layout="constrained")
for i, (method, summary) in enumerate(zip("DEF", windows, strict=True)):
    variant = summary["Variant"]
    y = 2 - i
    end = int(summary["Window_Cycles"])
    span = [(int(r["Start_Offset"]), int(r["Gap_Cycles"])) for r in gaps if r["Variant"] == variant]
    ax.broken_barh(span, (y-.36,.72), facecolors="#dfe8f3",
                   label="Long hart0 barrier-adjacent interval" if i==0 else None)
    ax.broken_barh(spans(wave, method, "hart1_dma_busy", end), (y-.13,.26), facecolors="#2461a2",
                   label="hart1 DMA busy (VCD)" if i==0 else None)
    starts = [float(r["Relative_Cycle"]) for r in wave if r["Method"]==method and r["Signal"]=="gemm_busy" and r["Value"]=="0x1"]
    ax.scatter(starts, [y+.22]*len(starts), color="#922b37", marker="v", s=18,
               label="GEMM busy rising edge" if i==0 else None)
ax.set_yticks([2,1,0], ["D  Both","E  Guard","F  Omit"])
ax.set(title="OpenGeMM 16³ checked: synchronized execution timeline", xlabel="Cycles since the timed window began", ylim=(-.55,2.65))
ax.legend(ncol=2, loc="upper center", bbox_to_anchor=(.5,-.20), frameon=False)
save(fig,"event_timeline")

parts = load("wave_dma_breakdown")
fig, ax = plt.subplots(figsize=(8.6, 3.3), layout="constrained")
for i, (m, r) in enumerate(zip("DEF", windows, strict=True)):
    value = [sum(float(x["DMA_Busy_Cycles"]) for x in parts if x["Method"] == m),
             sum(float(x["Non_DMA_Busy_In_Gap"]) for x in parts if x["Method"] == m),
             float(r["Outside_Gaps"])]
    left=0
    for v, col, title in zip(value, ["#2461a2","#b6c9e1","#dc9a4b"],
        ["DMA busy in long gaps","DMA not busy in long gaps","Outside long gaps"],strict=True):
        ax.barh(2-i,v,left=left, height=.54,color=col,label=title if i==0 else None)
        ax.text(left+v/2,2-i,f"{v:.0f}",ha="center",va="center",
                color="white" if col=="#2461a2" else "#182b40")
        left+=v
    ax.text(left+12,2-i,f"{left:.0f}",va="center")
ax.set(title="Observed cycle decomposition: same workload and timing boundary",xlabel="Cycles",xlim=(0,1820))
ax.set_yticks([2,1,0],["D  Both","E  Guard","F  Omit"])
ax.legend(ncol=2, loc="upper center", bbox_to_anchor=(.5,-.16), frameon=False)
save(fig,"critical_path_comparison")

squares=load("new_square_replays")
fig, axes=plt.subplots(1,2,figsize=(10,3.7),layout="constrained")
for ax, scope in zip(axes,["no_copy","checked"],strict=True):
    subset=[r for r in squares if r["Scope"]==scope and r["Matrix_Size"]=="16x16x16"]
    ax.bar([r["Method"] for r in subset],[int(r["Cycles"]) for r in subset],color=[C[r["Method"]] for r in subset])
    ax.set(title=("No-copy microbenchmark" if scope=="no_copy" else "Checked, scratchpad copies enabled"),
           xlabel="Method",ylabel="Cycles")
    for r in subset:
        ax.annotate(r["Cycles"],(r["Method"],int(r["Cycles"])),xytext=(0,3),textcoords="offset points",ha="center",fontsize=8)
    ax.margins(y=.15)
fig.suptitle("16³ square replay: methods A–F in separate measurement scopes")
save(fig,"square_scope_comparison")

fig,axes=plt.subplots(1,2,figsize=(9.6,3.7),layout="constrained")
for ax,scope in zip(axes,["no_copy","checked"],strict=True):
    subset=[r for r in squares if r["Scope"]==scope and r["Matrix_Size"]=="16x16x16"]
    for r in subset:
        m=r["Method"]
        x,y=int(r["CSR_Writes"]),int(r["Cycles"])
        ax.scatter(x,y,color=C[m],s=36)
        # B and E share a point in the no-copy experiment.
        if m=="E" and scope=="no_copy":
            continue
        ax.annotate("B / E" if m=="B" and scope=="no_copy" else m,(x,y),
                    xytext=(4,4),textcoords="offset points",fontsize=8)
    ax.set(title=scope.replace("_"," "),xlabel="Configuration CSR writes",ylabel="Cycles")
    ax.grid(alpha=.19)
save(fig,"csr_writes_vs_cycles")

holdout=[r for r in load("partial_comparison") if r["Trial_Class"]=="heldout"]
fig,axes=plt.subplots(1,2,figsize=(9.8,3.7),layout="constrained")
for ax, scope in zip(axes,["direct_checked","metadata_dma_checked"],strict=True):
    for index, method in enumerate("SWG"):
        rows=sorted((r for r in holdout if r["Scope"]==scope and r["Method"]==method),key=lambda r:int(r["K"]))
        ax.bar([n+(index-1)*.24 for n in range(len(rows))],[int(r["Cycles"]) for r in rows],
               color=C[method],width=.23,label=method)
    ax.set_xticks([0,1,2],["16","32","64"])
    ax.set(xlabel="Reduction K (8 × K × 8)",ylabel="Cycles / three trips",title=scope.replace("_"," "))
    ax.legend(frameon=False)
fig.suptitle("Held-out partial scheduling fixture; same checks and workload per group")
save(fig,"partial_cycles")

pred=load("model_predictions")
fig,ax=plt.subplots(figsize=(6,4.4),layout="constrained")
lim=max(max(float(r["Predicted"]),float(r["Actual"])) for r in pred)*1.03
ax.plot([200,lim],[200,lim],"--",color="#8a8b90",label="Perfect prediction")
for m in "SWG":
    sub=[r for r in pred if r["Method"]==m]
    ax.scatter([float(r["Actual"]) for r in sub],[float(r["Predicted"]) for r in sub],
               marker="x" if m=="W" else "o",color=C[m],label=m)
ax.set(title="Explanatory model vs. actual Verilator cycles",xlabel="Measured cycles",ylabel="Predicted cycles")
ax.legend(frameon=False)
save(fig,"model_vs_actual")

policy={r["Strategy"]:r for r in load("policy_summary")}
groups=[("Always Both","always_both"),("K threshold","fixed_threshold"),
        ("Dependency model","dependency_model"),("Always partial","always_partial"),
        ("Offline oracle","offline_oracle")]
fig,ax=plt.subplots(figsize=(8.5,3.6),layout="constrained")
ax.bar([label for label,_ in groups],[100*float(policy[k]["Mean_Regret"]) for _,k in groups],color="#4268a3")
for i,(_,key) in enumerate(groups):
    value=100*float(policy[key]["Mean_Regret"])
    ax.text(i,value+.25,f"{value:.2f}%",ha="center")
ax.set(title="Mean regret in six legal matched cells",ylabel="Regret vs. same-cell oracle (%)",ylim=(0,12))
save(fig,"policy_regret")
