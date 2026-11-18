"""Render timing and grouped cycle comparisons from validated hardware evidence."""
import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

parser=argparse.ArgumentParser()
parser.add_argument("report",type=Path)
r=parser.parse_args().report


def read(name):
    with (r/"data"/(name+".csv")).open() as f:
        return list(csv.DictReader(f))


def save(fig,name):
    fig.savefig(r/"figures"/(name+".png"),dpi=160)
    plt.close(fig)


rows=read("causal_p1")
fig,ax=plt.subplots(figsize=(11.4,4.5),layout="constrained")
colors=["#59677a","#987449","#4c73ae","#a75a61","#207c74"]
method_keys=("S","S_Reg","S_Compact","G_Late","G")
for index,(key,color) in enumerate(zip(method_keys,colors,strict=True)):
    label=key.replace("_","-").replace("Reg","reg").replace("Compact","compact").replace("Late","late")
    ax.bar([i+(index-2)*.155 for i in range(len(rows))],[int(row[key]) for row in rows],.145,label=label,color=color)
ax.set_xticks(range(len(rows)),[f"K={row['K']}\n"+("direct" if row["DMA_Bytes"]=="0" else "4 B DMA") for row in rows])
ax.set(ylabel="Verilator cycles / three trips",title="Metadata-selection workload: same-scope schedule and instruction controls")
ax.legend(ncol=5,loc="lower center",bbox_to_anchor=(.5,-.24),frameon=False)
ax.grid(axis="y",alpha=.18)
ax.set_axisbelow(True)
save(fig,"p1_grouped_cycles")

chain=[row for row in read("negative_and_cross_family") if row["Scenario"]=="tensor-chain" and int(row["Trips"])>0]
fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout="constrained",width_ratios=[1.4,1])
labels=[f"K={row['K']}, {row['Trips']} trip(s)\n"+("direct" if row["DMA_Bytes"]=="0" else f"{row['DMA_Bytes']} B DMA") for row in chain]
for index,(key,color) in enumerate(zip(("S","L","G"),[colors[0],colors[3],colors[4]],strict=True)):
    axes[0].bar([i+(index-1)*.25 for i in range(len(chain))],[int(row[key]) for row in chain],.24,label=key,color=color)
axes[0].set(ylabel="Verilator cycles",title="Tensor-chain total")
axes[0].legend(frameon=False)
axes[0].set_xticks(range(len(chain)),labels,fontsize=8)
axes[1].bar(range(len(chain)),[int(row["Strict_Early_Saving"]) for row in chain],color=colors[4])
axes[1].axhline(0,color=".45",linewidth=.7)
axes[1].set(ylabel="Cycles saved (L − G)",title="Same-layout intervention")
axes[1].set_xticks(range(len(chain)),labels,fontsize=8)
for ax in axes:
    ax.grid(axis="y",alpha=.18)
    ax.set_axisbelow(True)
save(fig,"tensor_chain_grouped_cycles")

vcd=read("vcd_events")
trace=read("timeline")
shown=(
    ("g_k16_t3_d1_s11","Metadata select • G"),
    ("g-late_k16_t3_d1_s11","Metadata select • G-late"),
    ("c0_g_k32_t3_b4096_s11","Tensor chain, 4096 B • G"),
    ("c0_l_k32_t3_b4096_s11","Tensor chain, 4096 B • L"),
)
fig,axes=plt.subplots(2,2,figsize=(13,5.1),layout="constrained")
first_by_run={row["Run_ID"]:row for row in trace if row["Slot"]=="0" and row["Mode"]=="wave"}
for index,(ax,(run,title)) in enumerate(zip(axes.flat,shown,strict=True)):
    first=first_by_run[run]
    pair=[first_by_run[key] for key,_ in shown[2*(index//2):2*(index//2)+2]]
    width=max(int(row["Second_GEMM"])-int(row["First_GEMM"]) for row in pair)
    start,end=int(first["First_GEMM"]),int(first["Second_GEMM"])
    for y,signal,color in ((2,"gemm_busy","#2483a0"),(1,"hart1_dma_busy","#e6a74b")):
        samples=[(float(row["Cycle"]),int(row["Value"],16)) for row in vcd if row["Run_ID"]==run and row["Signal"]==signal]
        for (a,v),(b,_) in zip(samples,samples[1:]):
            span=max(0,min(b,end)-max(a,start))
            if v and span:
                ax.broken_barh([(max(a,start)-start,span)],(y-.22,.44),facecolors=color)
    window=[row for row in vcd if row["Run_ID"]==run and row["Signal"].startswith("stage_")]
    for field,marker,color,level in zip("ABC",("v","o","^"),("#7f5290","#cd5857","#2c8065"),(-.16,0,.16),strict=True):
        expected=int(first[field+"_Write"])
        observed=min((row for row in window if row["Signal"]=="stage_"+field and row["Value"]==first["Next_"+field]),
                     key=lambda row:abs(float(row["Cycle"])-expected))
        ax.scatter(float(observed["Cycle"])-start,level,marker=marker,s=37,color=color,zorder=3)
    ax.axvspan(int(first["Load_First"])-start,int(first["Load_Last"])-start+.6,color="#9fadc2",alpha=.36)
    ax.set_yticks([0,1,2],["CSR","DMA","GEMM"])
    ax.set(title=title,xlabel="Cycles since first GEMM launch",xlim=(-2,width+4),ylim=(-.55,2.55))
handles=[Patch(color="#2483a0",label="GEMM busy"),Patch(color="#e6a74b",label="DMA busy"),
         Patch(color="#9fadc2",alpha=.36,label="Dependent load span")]
handles.extend(Line2D([],[],marker=m,color=c,linestyle="",label=label)
               for m,c,label in zip(("v","o","^"),("#7f5290","#cd5857","#2c8065"),("A stage","B stage","C stage"),strict=True))
fig.legend(handles=handles,loc="outside lower center",ncol=6,frameon=False)
save(fig,"core_timeline")
