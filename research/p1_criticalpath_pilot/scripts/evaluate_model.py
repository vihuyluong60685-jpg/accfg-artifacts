"""Execute the frozen explanatory policy and evaluate only after making predictions."""
import argparse
import csv
import math
from pathlib import Path
import re
import time

from compare_square import save


def inputs(path):
    return list(csv.DictReader(path.open()))


def static_step_instructions(path):
    text = path.read_text()
    body = re.search(r"<pilot_step>:\n(.*?)(?=\n[0-9a-f]+ <|\Z)", text, flags=re.S)
    assert body is not None
    return len(re.findall(r"^\s*[0-9a-f]+:", body[1], re.M))


def predict(k, trips, calibration, static_delta):
    estimate = trips*(calibration["serial_cycles"] + 2*(k//8-2))
    headroom = min(2, calibration["first_launch_to_await"])
    return {"S": estimate, "W": estimate, "G": estimate - trips*headroom + trips*static_delta}


def evaluate(local, report):
    complete = inputs(report/"data/partial_comparison.csv")
    cells = sorted({(r["Scope"],int(r["K"])) for r in complete if r["Trial_Class"]=="heldout"})
    control = inputs(report/"data/baseline_comparison.csv")
    numeric = lambda row,key: int(row[key])
    policy = []
    predictions = []
    full_table = inputs(report/"data/new_square_replays.csv")
    historial = {(r["Matrix_Size"],r["Scope"],r["Method"]):r for r in control}
    for row in full_table:
        ref = historial[row["Matrix_Size"],row["Scope"],row["Method"]]
        for k in ("Speedup_vs_Base","Speedup_vs_Both","Regret"):
            row[k]=ref[k]
    for row in control:
        if row["Cycles"]=="N/A":
            full_table.append(row)

    for scope,k in cells:
        matched = {r["Method"]:r for r in complete if r["Trial_Class"]=="heldout" and r["Scope"]==scope and numeric(r,"K")==k}
        assert set(matched)=={"S","W","G"}
        s = next(r for r in complete if r["Trial_Class"]=="calibration" and r["Scope"]==scope and r["Method"]=="S")
        cal = {"serial_cycles": numeric(s,"Cycles"), "first_launch_to_await": numeric(s,"First_Launch_To_Last_Await")}
        static = {m: static_step_instructions(local/"partial"/r["Run_ID"]/"disassembly.txt") for m,r in matched.items()}

        begin = time.perf_counter_ns()
        model = predict(k, 3, cal, static["G"]-static["S"])
        pick = min(model, key=model.get)
        runtime_ns = time.perf_counter_ns() - begin
        # Measured holdout outcomes enter only for scoring below.
        actual = {m:int(r["Cycles"]) for m,r in matched.items()}
        best = min(actual,key=actual.get)
        for method, guess in model.items():
            predictions.append(dict(Scope=scope,K=k,Method=method,Actual=actual[method],
                                    Predicted=guess,Absolute_Pct_Error=abs(guess/actual[method]-1),
                                    Calibration_Run=s["Run_ID"],Static_Insts=static[method],Evidence="MODEL"))
        choices={"original_whole":"W","always_dedup":"S","always_both":"S",
                 "fixed_threshold":"G" if k>=32 else "S","fewest_csrs_tie_S":"S",
                 "dependency_model":pick,"offline_oracle":best,"always_partial":"G"}
        for strategy, method in choices.items():
            cycles = actual[method]
            policy.append(dict(Scope=scope,K=k,Strategy=strategy,Selected=method,
                               Cycles=cycles,Best_Legal=actual[best],
                               Regret=(cycles-actual[best])/actual[best],
                               Speedup_vs_Matched_S=actual["S"]/cycles,
                               Correct_Pick=int(cycles==actual[best]),
                               Selection_NS=runtime_ns if strategy=="dependency_model" else "N/A"))
        for row in matched.values():
            full_table.append({**row, "Speedup_vs_Base":actual["S"]/int(row["Cycles"]),
                               "Speedup_vs_Both":actual["W"]/int(row["Cycles"]),
                               "Comparison_Group":"paired fixture; Both-equivalent via identical lowering"})

    totals = []
    for strategy in dict.fromkeys(r["Strategy"] for r in policy):
        sample=[r for r in policy if r["Strategy"]==strategy]
        totals.append(dict(Strategy=strategy,Cells=len(sample),
                           Correct_Picks=sum(r["Correct_Pick"] for r in sample),
                           Mean_Regret=sum(r["Regret"] for r in sample)/len(sample),
                           Worst_Regret=max(r["Regret"] for r in sample),
                           Worst_Slowdown_vs_Matched_S=max(0,max(1/r["Speedup_vs_Matched_S"]-1 for r in sample)),
                           Geomean_vs_Matched_S=math.exp(sum(math.log(r["Speedup_vs_Matched_S"]) for r in sample)/len(sample))))
    strongest = max((r for r in totals if r["Strategy"] in {"always_dedup","always_both","always_partial"}),
                    key=lambda r:r["Geomean_vs_Matched_S"])
    for total in totals:
        total["Geomean_vs_Strongest_Fixed"] = total["Geomean_vs_Matched_S"]/strongest["Geomean_vs_Matched_S"]

    save(report/"data/model_predictions.csv",predictions)
    save(report/"data/policy_regret.csv",policy)
    save(report/"data/policy_summary.csv",totals)
    save(report/"data/performance_comparison.csv",full_table)
    print("MAPE",sum(r["Absolute_Pct_Error"] for r in predictions)/len(predictions))
    for r in totals:
        print(r["Strategy"], r["Correct_Picks"], r["Mean_Regret"],r["Geomean_vs_Matched_S"])


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("local",type=Path)
    ap.add_argument("report",type=Path)
    args=ap.parse_args()
    evaluate(args.local,args.report)
