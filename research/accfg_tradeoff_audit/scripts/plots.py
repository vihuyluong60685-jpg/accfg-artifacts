"""Scientific plots from CSV tables. Each panel labels its own measured scope."""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from collect import read

p=argparse.ArgumentParser()
p.add_argument("report",type=Path)
args=p.parse_args()
r=args.report
def load(n):
    return read(r/"data"/(n+".csv"))
def save(fig,n):
    fig.savefig(r/"figures"/(n+".png"),dpi=160)
    plt.close(fig)

colors=dict(A="#687580",B="#3a6db0",C="#bf6546",D="#218472")
oc=load("opengemm_cases")
paper=[i for i in oc if i["Scope"]=="paper_no_copy"]
fig,axes=plt.subplots(1,2,figsize=(10,4),layout="constrained")
for method,color in colors.items():
    data=[i for i in paper if i["Mode"]==method]
    dims=[int(i["Shape"].split("x")[0]) for i in data]
    elapsed=[int(i["Cycles"]) for i in data]
    relative=[int(next(j["Cycles"] for j in paper if j["Shape"]==i["Shape"] and j["Mode"]=="A"))/int(i["Cycles"]) for i in data]
    axes[0].plot(dims,elapsed,marker="o",color=color,label=method)
    axes[1].plot(dims,relative,marker="o",color=color,label=method)
axes[0].set(yscale="log",ylabel="Target cycles (log scale)",title="Published no-copy cycle window")
axes[1].axhline(1,color=".5",linestyle="--",linewidth=.8)
axes[1].set(ylabel="Speedup vs matched Base",title="Speedup across six original shapes")
for ax in axes:
    ax.set(xscale="log",xlabel="Matrix dimension",xticks=dims,xticklabels=dims)
    ax.legend(frameon=False)
save(fig,"performance")

pairs=load("multi_metric_comparison")
fig,axes=plt.subplots(1,2,figsize=(12,4),layout="constrained")
for ax,key,title in zip(axes,("no_copy","checked"),("No-copy tiling","Checked with scratchpad copy"),strict=True):
    scopes=["paper_no_copy","extras_no_copy"] if key=="no_copy" else ["prior_checked","extras_checked"]
    ac=[i for i in pairs if i["Measurement_Scope"] in scopes and i["Metric"]=="Cycles"
        and i["Mode"]=="C" and i["Baseline_Mode"]=="A" and int(i["Matrix_Size"].split("x")[0])<=64]
    bd=[i for i in pairs if i["Measurement_Scope"] in scopes and i["Metric"]=="Cycles"
        and i["Mode"]=="D" and i["Baseline_Mode"]=="B" and int(i["Matrix_Size"].split("x")[0])<=64]
    for j,(ss,label,c) in enumerate(((ac,"C vs A",colors["C"]),(bd,"D vs B",colors["D"]))):
        ax.bar([i+(j-.5)*.35 for i in range(len(ss))],[float(k["Relative_Change_Percent"]) for k in ss],
               .33,label=label,color=c)
    ax.axhline(0,color=".35",linewidth=.7)
    ax.set(title=title,ylabel="Cycle change (%)",xticks=range(len(ac)),
           xticklabels=[i["Matrix_Size"].split("x")[0] if len(set(i["Matrix_Size"].split("x")))==1 else i["Matrix_Size"] for i in ac])
    ax.legend(frameon=False)
save(fig,"small_regressions")

fig,axes=plt.subplots(1,2,figsize=(10,4),layout="constrained")
for ax,key,title in zip(axes,("Text_Bytes","Timed_Kernel_Symbol_Bytes"),(".text size","Timed function symbol size"),strict=True):
    for mode in "BCD":
        val=[]; dim=[]
        for k in paper:
            if k["Mode"]!=mode: continue
            a=next(i for i in paper if i["Shape"]==k["Shape"] and i["Mode"]=="A")
            val.append(int(k[key])-int(a[key]))
            dim.append(int(k["Shape"].split("x")[0]))
        ax.plot(dim,val,marker="o",label=mode,color=colors[mode])
    ax.set(xscale="log",xticks=dim,xticklabels=dim,xlabel="Square size",ylabel="Difference from Base (bytes)",title=title)
    ax.axhline(0,linewidth=.65,color=".5"); ax.legend(frameon=False)
save(fig,"code_size")

build=load("build_samples")
fig,axes=plt.subplots(2,3,figsize=(10,6.8),layout="constrained")
for j,n in enumerate(("16","128","512")):
    for k,key,unit in ((0,"Elapsed_Seconds","Build wall time (s)"),(1,"Max_Child_RSS_KiB","Max child RSS (MiB)")):
        ax=axes[k,j]
        for i,m in enumerate("ABCD"):
            rows=[q for q in build if q["Size"]==n and q["Mode"]==m]
            y=[float(q[key])/(1024 if k else 1) for q in rows]
            ax.scatter([i+(.05*(t-1.5)) for t in range(len(y))],y,color=colors[m],s=28)
        ax.set(title=f"N={n}",ylabel=unit,xticks=range(4),xticklabels=list("ABCD"))
        ax.grid(axis="y",alpha=.17)
save(fig,"build_cost")

fig,ax=plt.subplots(figsize=(7.4,4.7),layout="constrained")
for mode in "BCD":
    points=[]
    for k in paper:
        if k["Mode"]!=mode: continue
        a=next(i for i in paper if i["Mode"]=="A" and i["Shape"]==k["Shape"])
        points.append((int(k["Config_CSR_Writes"])/int(a["Config_CSR_Writes"]),int(k["Cycles"])/int(a["Cycles"])))
    ax.scatter(*zip(*points),s=37,label=mode,color=colors[mode])
ax.axhline(1,color=".6",linestyle="--"); ax.axvline(1,color=".6",linestyle="--")
ax.set(xlabel="Configuration-only CSR writes / matched Base",ylabel="Cycles / matched Base",title="Writes and cycles, six original no-copy shapes")
ax.legend(frameon=False)
save(fig,"configuration_vs_cycles")

events=load("dma_events")
gaps=load("dma_windows")
fig,axes=plt.subplots(2,1,figsize=(11,4.4),layout="constrained",sharex=True)
for ax,m in zip(axes,"BD",strict=True):
    for item in gaps:
        if item["Mode"]==m:
            x=float(item["Offset"]); z=float(item["Cycles"])
            ax.axvspan(x,x+z,color="#dae6ee")
    for y,signal,col in ((0,"hart1_dma_busy","#376fa0"),(1,"gemm_busy","#b86344")):
        series=[(float(i["Offset"]),int(i["Value"],16)) for i in events if i["Mode"]==m and i["Signal"]==signal]
        for (a,v),(b,_) in zip(series,series[1:]):
            if v: ax.broken_barh([(a,b-a)],(y-.20,.40),facecolors=col)
    ax.set(yticks=[0,1],yticklabels=["DMA busy","GEMM busy"],ylim=(-.5,1.5),title=f"Mode {m}, 16³ checked inner window")
axes[-1].set_xlabel("Cycles since inner marker")
fig.legend(handles=[Line2D([0],[0],color="#dae6ee",lw=7,label="Long barrier-associated interval")],
           loc="outside lower center",frameon=False)
save(fig,"dma_timeline")

pareto=load("pareto_comparison")
fig,axes=plt.subplots(2,2,figsize=(10,7),layout="constrained")
groups=sorted({(i["Scope"],i["Shape"]) for i in pareto})
for ax,(scope,shape) in zip(axes.flat,groups,strict=True):
    for q in pareto:
        if (q["Scope"],q["Shape"])!=(scope,shape): continue
        x,y=int(q["Text_Bytes"]),int(q["Cycles"])
        ax.scatter(x,y,color=colors[q["Mode"]],marker="o" if q["Pareto"]=="FRONTIER" else "x",s=45+int(q["Config_CSR_Writes"])*.14)
        ax.annotate(q["Mode"],(x,y),xytext=(5,4),textcoords="offset points")
    ax.set(title=f"{shape} ({'new marker' if scope.startswith('envelope') else 'checked'})",xlabel=".text bytes",ylabel="Target cycles")
fig.legend(handles=[Line2D((),(),marker=m,color="#626c75",linestyle="",label=name) for m,name in (("o","3-metric frontier"),("x","Dominated"))],
           frameon=False,loc="outside lower center",ncol=2)
save(fig,"pareto")
