"""Plot measured graph latencies and wave-aligned launch evidence."""
import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

p=argparse.ArgumentParser()
p.add_argument("report",type=Path)
report=p.parse_args().report


def read(name):
    with (report/"data"/(name+".csv")).open() as f:
        return list(csv.DictReader(f))


def export(fig,name):
    fig.savefig(report/"figures"/(name+".png"),dpi=160)
    plt.close(fig)


names={"mobile":"Mobile bottleneck","attention":"Scaled dot-product attention"}
rows=read("schedule_oracle")
methods=("A_Base","B_Dedup","C_Both","D_Safe","E_Partial","F_Static")
labels=("Base","Dedup","Both","D","E","F")
palette=("#747d89","#3d69a7","#238174","#b67342","#8456a1","#bd585e")
fig,axes=plt.subplots(2,2,figsize=(11,7.1),layout="constrained")
for col,graph in enumerate(names):
    subset=[r for r in rows if r["Graph"]==graph]
    for panel,delta in enumerate((False,True)):
        ax=axes[panel,col]
        for i,(key,label,color) in enumerate(zip(methods,labels,palette,strict=True)):
            values=[int(r[key])-(int(r["B_Dedup"]) if delta else 0) for r in subset]
            ax.bar([j+(i-2.5)*.13 for j in range(len(subset))],values,.123,color=color,label=label)
        if delta:
            ax.axhline(0,color="#53616d",linewidth=.8)
        ax.set(title=names[graph] if not delta else "Difference from Dedup",
               ylabel=("Cycle difference" if delta else "Graph cycles"),xticks=range(len(subset)),
               xticklabels=[f"Seed {r['Seed']}" for r in subset])
        ax.set_axisbelow(True)
        ax.grid(axis="y",alpha=.17)
fig.legend(*axes[0,0].get_legend_handles_labels(),loc="outside lower center",ncol=6,frameon=False)
export(fig,"end_to_end")

grid=read("layout_grid")
fig,axes=plt.subplots(1,2,figsize=(10,3.8),layout="constrained",sharey=True)
for ax,(graph,title) in zip(axes,names.items(),strict=True):
    for i,seed in enumerate(("11","37")):
        y=[int(r["Saving_vs_Safe"]) for r in grid if r["Graph"]==graph and r["Seed"]==seed]
        ax.plot(range(8),y,marker="o",linewidth=1.6,label=f"Seed {seed}",color=(palette[0],palette[2])[i])
    ax.set(title=title,xlabel="Pointer fields moved before await",xticks=range(8),
           xticklabels=["None","A","B","AB","C","AC","BC","ABC"],ylim=(-.35,3.65))
    ax.set_yticks([0,1,2,3])
    ax.grid(axis="y",alpha=.2)
axes[0].set_ylabel("Cycles saved vs D (same ELF layout)")
axes[1].legend(frameon=False)
export(fig,"layout_oracle")

events=read("hardware_windows")
fig,axes=plt.subplots(2,2,figsize=(10.5,6.1),layout="constrained",sharex=True)
pulse="#2d859c"
for row,graph in enumerate(names):
    for col,seed in enumerate(("11","37")):
        ax=axes[row,col]
        for y,method in enumerate(("M0","C")):
            o=next(r for r in events if (r["Graph"],r["Method"],r["Seed"])==(graph,method,seed))
            baseline=float(o["First_Streamer_Capture"])
            start=float(o["First_Busy_Start"])-baseline
            width=float(o["GEMM_Busy_Window"])
            ax.broken_barh([(start,width)],(y-.19,.38),facecolors=pulse,alpha=.58)
            for letter,marker,colour,sh in zip("ABC",("v","o","^"),
                                                (palette[3],palette[4],palette[5]),(-.14,0,.14),strict=True):
                t=float(o["Stage_"+letter])-baseline
                ax.scatter(t,y+sh,marker=marker,c=colour,s=37)
            ax.scatter(float(o["First_Await"])-baseline,y-.32,marker="|",s=65,color="#3a4651")
        ax.set(title=f"{names[graph]}, seed {seed}",yticks=(0,1),yticklabels=("D","Both"),
               ylim=(-.55,1.40),xlim=(-.4,13.5),xlabel="Cycles since streamer capture")
        ax.axvline(0,color="#56606b",linewidth=.8,linestyle="--")
        ax.grid(axis="x",alpha=.15)
legend=[Line2D([],[],color=pulse,linewidth=5,label="GEMM busy"),
        Line2D([],[],color="#3a4651",marker="|",linestyle="",label="First await")]
legend.extend(Line2D([],[],color=colour,marker=marker,linestyle="",label=letter+" write")
              for letter,colour,marker in zip("ABC",(palette[3],palette[4],palette[5]),("v","o","^"),strict=True))
fig.legend(handles=legend,loc="outside lower center",ncol=5,frameon=False)
export(fig,"hardware_window")
