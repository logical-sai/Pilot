"""Descriptive repeated-measures analysis for the single active pilot schema.

The script accepts one or many canonical result CSVs. It produces participant,
session, serial-position, instruction-complexity, and distractor-condition summaries.
The distraction analysis uses SETS as the main descriptive unit because the four
instruction rows within a set share the same distractor exposure.
"""
from __future__ import annotations

import argparse
import csv
import glob
import math
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

from pilot_schema import SCHEMA_VERSION, validate_columns


def yes(v) -> bool:
    return str(v).strip().upper() == "Y"


def fnum(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def pct(num: float, den: float) -> float:
    return round(100.0 * num / den, 1) if den else float("nan")


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def resolve_inputs(items: list[str]) -> list[Path]:
    paths: list[Path] = []
    for item in items:
        p = Path(item)
        if p.is_dir():
            paths.extend(sorted(p.glob("memory_recall_results_*.csv")))
        elif any(ch in item for ch in "*?[]"):
            paths.extend(Path(x) for x in sorted(glob.glob(item)))
        elif p.exists():
            paths.append(p)
        else:
            raise FileNotFoundError(item)
    unique = []
    seen = set()
    for p in paths:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            unique.append(p)
    if not unique:
        raise ValueError("No canonical result CSV files found.")
    return unique


def load_rows(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    seen_target_keys = set()
    seen_intrusion_keys = set()
    for path in paths:
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            validate_columns(reader.fieldnames or [])
            for row in reader:
                if row.get("Schema_Version") != SCHEMA_VERSION:
                    raise ValueError(
                        f"{path.name} uses schema {row.get('Schema_Version')!r}; "
                        f"this build accepts only {SCHEMA_VERSION!r}."
                    )
                if row.get("Record_Type") == "Target":
                    key = (row["Session_ID"], row["Target_ID"])
                    if key in seen_target_keys:
                        continue
                    seen_target_keys.add(key)
                else:
                    key = (row.get("Session_ID", ""), row.get("Set_Index", ""), row.get("User_Recall_Text", ""))
                    if key in seen_intrusion_keys:
                        continue
                    seen_intrusion_keys.add(key)
                rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def complexity_band(ici: float) -> str:
    if ici < 3.5:
        return "LOW"
    if ici < 6.5:
        return "MEDIUM"
    return "HIGH"


def build_set_level(targets: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for r in targets:
        grouped[(r["Session_ID"], r["Set_Index"])].append(r)

    out = []
    for (_, _), rs in sorted(grouped.items(), key=lambda kv: (kv[1][0]["User"], int(kv[1][0]["Session_Number"]), int(kv[1][0]["Set_Index"]))):
        first = rs[0]
        remembered = sum(yes(r["Remembered"]) for r in rs)
        out.append({
            "User": first["User"],
            "Session_ID": first["Session_ID"],
            "Session_Number": int(first["Session_Number"]),
            "Set_Index": int(first["Set_Index"]),
            "Scenario_Family_ID": first["Scenario_Family_ID"],
            "Scenario_Form": first["Scenario_Form"],
            "Scenario_ID": first["Scenario_ID"],
            "Instruction_Complexity_Index": round(fnum(first["Instruction_Complexity_Index"]), 3),
            "Complexity_Band": complexity_band(fnum(first["Instruction_Complexity_Index"])),
            "Distractor_Condition": first["Distractor_Condition"],
            "Distractor_Difficulty_Score": fnum(first["Distractor_Difficulty_Score"]),
            "Distractor_Items_Presented": first.get("Distractor_Items_Presented", ""),
            "Distractor_Items_Answered": first.get("Distractor_Items_Answered", ""),
            "Distractor_Items_Correct": first.get("Distractor_Items_Correct", ""),
            "Distractor_Accuracy_Pct": first.get("Distractor_Accuracy_Pct", ""),
            "Distractor_Mean_Response_Time_Sec": first.get("Distractor_Mean_Response_Time_Sec", ""),
            "Target_Count": len(rs),
            "Remembered_Count": remembered,
            "Set_Recall_pct": pct(remembered, len(rs)),
            "Reading_Time_Sec": fnum(first["Reading_Time_Sec"]),
            "Distractor_Time_Sec": fnum(first["Distractor_Time_Sec"]),
            "Recall_Time_Sec": fnum(first["Recall_Time_Sec"]),
        })
    return out


def analyze(input_items: list[str], output_dir: Path) -> None:
    paths = resolve_inputs(input_items)
    all_rows = load_rows(paths)
    targets = [r for r in all_rows if r.get("Record_Type") == "Target"]
    intrusions = [r for r in all_rows if r.get("Record_Type") == "Intrusion"]
    if not targets:
        raise ValueError("No target rows found.")

    output_dir.mkdir(parents=True, exist_ok=True)
    set_level = build_set_level(targets)
    write_csv(output_dir / "pilot_set_level.csv", set_level)

    # ------------------------------------------------------------------
    # Session-level summary
    # ------------------------------------------------------------------
    by_session = defaultdict(list)
    for r in targets:
        by_session[r["Session_ID"]].append(r)

    session_summary = []
    for session_id, rs in sorted(by_session.items(), key=lambda kv: (kv[1][0]["User"], int(kv[1][0]["Session_Number"]))):
        remembered = sum(yes(r["Remembered"]) for r in rs)
        in_order = sum(yes(r["Remembered"]) and not yes(r["Out_of_Order"]) for r in rs)
        session_intrusions = sum(r.get("Session_ID") == session_id for r in intrusions)
        session_sets = [s for s in set_level if s["Session_ID"] == session_id]
        session_summary.append({
            "User": rs[0]["User"],
            "Session_ID": session_id,
            "Session_Number": int(rs[0]["Session_Number"]),
            "Scenario_Form": rs[0]["Scenario_Form"],
            "N_Sets": len(session_sets),
            "Target_Count": len(rs),
            "Remembered_Count": remembered,
            "Recall_Rate_pct": pct(remembered, len(rs)),
            "In_Order_Count": in_order,
            "In_Order_pct": pct(in_order, len(rs)),
            "Intrusion_Count": session_intrusions,
            "Mean_Set_Complexity": round(mean([s["Instruction_Complexity_Index"] for s in session_sets]), 3),
        })
    write_csv(output_dir / "pilot_session_summary.csv", session_summary)

    # ------------------------------------------------------------------
    # Longitudinal participant summary
    # ------------------------------------------------------------------
    by_user_sessions = defaultdict(list)
    for s in session_summary:
        by_user_sessions[s["User"]].append(s)

    longitudinal = []
    for user, sessions in sorted(by_user_sessions.items()):
        sessions = sorted(sessions, key=lambda x: x["Session_Number"])
        first, last = sessions[0], sessions[-1]
        total_targets = sum(s["Target_Count"] for s in sessions)
        total_remembered = sum(s["Remembered_Count"] for s in sessions)
        longitudinal.append({
            "User": user,
            "Completed_Sessions": len(sessions),
            "First_Session_Number": first["Session_Number"],
            "Last_Session_Number": last["Session_Number"],
            "First_Session_Recall_pct": first["Recall_Rate_pct"],
            "Last_Session_Recall_pct": last["Recall_Rate_pct"],
            "Change_First_to_Last_pp": round(last["Recall_Rate_pct"] - first["Recall_Rate_pct"], 1),
            "All_Sessions_Target_Count": total_targets,
            "All_Sessions_Recall_pct": pct(total_remembered, total_targets),
        })
    write_csv(output_dir / "pilot_user_longitudinal_summary.csv", longitudinal)

    # ------------------------------------------------------------------
    # Serial position and within-list instruction interference
    # ------------------------------------------------------------------
    serial_summary = []
    for cat in ("Primacy", "Middle", "Recency"):
        rs = [r for r in targets if r["Serial_Category"] == cat]
        remembered = sum(yes(r["Remembered"]) for r in rs)
        serial_summary.append({
            "Serial_Category": cat,
            "N_Targets": len(rs),
            "Recall_Rate_pct": pct(remembered, len(rs)),
            "Forgetting_Rate_pct": pct(len(rs) - remembered, len(rs)),
        })
    write_csv(output_dir / "pilot_serial_position_summary.csv", serial_summary)

    instruction_interference_summary = []
    for flag in ("N", "Y"):
        rs = [r for r in targets if r["Instruction_Interference_Present"] == flag]
        remembered = sum(yes(r["Remembered"]) for r in rs)
        instruction_interference_summary.append({
            "Instruction_Interference_Present": flag,
            "N_Targets": len(rs),
            "Recall_Rate_pct": pct(remembered, len(rs)),
            "Forgetting_Rate_pct": pct(len(rs) - remembered, len(rs)),
        })
    write_csv(output_dir / "pilot_instruction_interference_summary.csv", instruction_interference_summary)

    # ------------------------------------------------------------------
    # Experimental distractor effect - primarily SET level
    # ------------------------------------------------------------------
    distraction_summary = []
    baseline_sets = [s for s in set_level if s["Distractor_Condition"] == "NONE"]
    baseline_mean = mean([s["Set_Recall_pct"] for s in baseline_sets])
    for condition in ("NONE", "LOW", "HIGH"):
        sets = [s for s in set_level if s["Distractor_Condition"] == condition]
        trs = [r for r in targets if r["Distractor_Condition"] == condition]
        scored_sets = [s for s in sets if str(s.get("Distractor_Accuracy_Pct", "")).strip()]
        distractor_accuracy_values = [fnum(s["Distractor_Accuracy_Pct"]) for s in scored_sets]
        mean_set_recall = mean([s["Set_Recall_pct"] for s in sets])
        target_remembered = sum(yes(r["Remembered"]) for r in trs)
        distraction_summary.append({
            "Distractor_Condition": condition,
            "N_Sets": len(sets),
            "N_Participants": len({s["User"] for s in sets}),
            "Mean_Set_Recall_pct": round(mean_set_recall, 1) if sets else float("nan"),
            "Target_Level_Recall_pct": pct(target_remembered, len(trs)),
            "Observed_Difference_vs_NONE_pp": (
                round(mean_set_recall - baseline_mean, 1)
                if sets and baseline_sets and not math.isnan(mean_set_recall) else float("nan")
            ),
            "Distractor_Accuracy_pct": (round(mean(distractor_accuracy_values), 1) if distractor_accuracy_values else ""),
            "Mean_Distractor_Response_Time_Sec": (
                round(mean([fnum(s["Distractor_Mean_Response_Time_Sec"]) for s in scored_sets if str(s["Distractor_Mean_Response_Time_Sec"]).strip()]), 2)
                if any(str(s.get("Distractor_Mean_Response_Time_Sec", "")).strip() for s in scored_sets) else ""
            ),
            "Mean_Instruction_Complexity_Index": round(mean([s["Instruction_Complexity_Index"] for s in sets]), 3) if sets else "",
        })
    write_csv(output_dir / "pilot_distraction_condition_summary.csv", distraction_summary)

    # Per-user condition performance, useful once a participant has repeated sessions.
    distraction_by_user = []
    for user in sorted({s["User"] for s in set_level}):
        user_sets = [s for s in set_level if s["User"] == user]
        none_sets = [s for s in user_sets if s["Distractor_Condition"] == "NONE"]
        user_baseline = mean([s["Set_Recall_pct"] for s in none_sets])
        for condition in ("NONE", "LOW", "HIGH"):
            sets = [s for s in user_sets if s["Distractor_Condition"] == condition]
            if not sets:
                continue
            m = mean([s["Set_Recall_pct"] for s in sets])
            distraction_by_user.append({
                "User": user,
                "Distractor_Condition": condition,
                "N_Sets": len(sets),
                "Mean_Set_Recall_pct": round(m, 1),
                "Difference_vs_User_NONE_pp": (
                    round(m - user_baseline, 1) if none_sets else ""
                ),
            })
    write_csv(output_dir / "pilot_distraction_by_user.csv", distraction_by_user)

    # ------------------------------------------------------------------
    # Instruction complexity
    # ------------------------------------------------------------------
    complexity_summary = []
    for band in ("LOW", "MEDIUM", "HIGH"):
        sets = [s for s in set_level if s["Complexity_Band"] == band]
        if not sets:
            continue
        complexity_summary.append({
            "Complexity_Band": band,
            "N_Sets": len(sets),
            "Mean_Instruction_Complexity_Index": round(mean([s["Instruction_Complexity_Index"] for s in sets]), 3),
            "Mean_Set_Recall_pct": round(mean([s["Set_Recall_pct"] for s in sets]), 1),
        })
    write_csv(output_dir / "pilot_instruction_complexity_summary.csv", complexity_summary)

    form_summary = []
    for family in sorted({s["Scenario_Family_ID"] for s in set_level}):
        for form in sorted({s["Scenario_Form"] for s in set_level if s["Scenario_Family_ID"] == family}):
            sets = [s for s in set_level if s["Scenario_Family_ID"] == family and s["Scenario_Form"] == form]
            form_summary.append({
                "Scenario_Family_ID": family,
                "Scenario_Form": form,
                "N_Sets": len(sets),
                "Mean_Instruction_Complexity_Index": round(mean([s["Instruction_Complexity_Index"] for s in sets]), 3),
                "Mean_Set_Recall_pct": round(mean([s["Set_Recall_pct"] for s in sets]), 1),
            })
    write_csv(output_dir / "pilot_equivalent_form_summary.csv", form_summary)

    # ------------------------------------------------------------------
    # Risk heuristic calibration - target level, descriptive only
    # ------------------------------------------------------------------
    by_score = defaultdict(list)
    for r in targets:
        if str(r.get("Risk_Score", "")).strip():
            by_score[fnum(r["Risk_Score"])].append(r)
    calibration = []
    for score in sorted(by_score):
        rs = by_score[score]
        forgotten = sum(not yes(r["Remembered"]) for r in rs)
        observed = pct(forgotten, len(rs))
        calibration.append({
            "Risk_Score": score,
            "N_Targets": len(rs),
            "Observed_Forgetting_pct": observed,
            "Difference_pp": round(observed - score, 1),
        })
    write_csv(output_dir / "pilot_risk_calibration.csv", calibration)

    # ------------------------------------------------------------------
    # Charts - descriptive only
    # ------------------------------------------------------------------
    plt.figure(figsize=(7, 4.5))
    plt.bar([r["Serial_Category"] for r in serial_summary], [r["Recall_Rate_pct"] for r in serial_summary])
    plt.ylim(0, 100)
    plt.xlabel("Serial position")
    plt.ylabel("Observed recall (%)")
    plt.title("Pilot Recall by Serial Position")
    plt.tight_layout()
    plt.savefig(output_dir / "pilot_recall_by_serial_position.png", dpi=180)
    plt.close()

    plt.figure(figsize=(7, 4.5))
    plt.bar(
        [r["Distractor_Condition"] for r in distraction_summary],
        [r["Mean_Set_Recall_pct"] for r in distraction_summary],
    )
    plt.ylim(0, 100)
    plt.xlabel("Distractor condition")
    plt.ylabel("Mean set recall (%)")
    plt.title("Pilot Recall by Distractor Condition")
    plt.tight_layout()
    plt.savefig(output_dir / "pilot_distraction_effect.png", dpi=180)
    plt.close()

    plt.figure(figsize=(7, 4.5))
    plt.scatter(
        [s["Instruction_Complexity_Index"] for s in set_level],
        [s["Set_Recall_pct"] for s in set_level],
    )
    plt.ylim(0, 100)
    plt.xlabel("Instruction Complexity Index")
    plt.ylabel("Set recall (%)")
    plt.title("Set Recall vs. Instruction Complexity")
    plt.tight_layout()
    plt.savefig(output_dir / "pilot_complexity_vs_recall.png", dpi=180)
    plt.close()

    if calibration:
        plt.figure(figsize=(7, 4.5))
        plt.plot([r["Risk_Score"] for r in calibration], [r["Observed_Forgetting_pct"] for r in calibration], marker="o")
        plt.plot([0, 100], [0, 100], linestyle="--")
        plt.xlim(0, 100); plt.ylim(0, 100)
        plt.xlabel("Heuristic risk score")
        plt.ylabel("Observed forgetting (%)")
        plt.title("Pilot Risk Calibration Check")
        plt.tight_layout()
        plt.savefig(output_dir / "pilot_risk_calibration.png", dpi=180)
        plt.close()

    print(f"Loaded {len(paths)} canonical result file(s).")
    print(f"Participants: {len({r['User'] for r in targets})}")
    print(f"Sessions: {len(by_session)}")
    print(f"Target rows: {len(targets)}; set-level observations: {len(set_level)}")
    print(f"Outputs: {output_dir}")
    print("Interpret distractor and complexity summaries descriptively until sufficient controlled data exist.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "inputs",
        nargs="+",
        help="One or more canonical CSVs, glob patterns, or directories containing result CSVs.",
    )
    parser.add_argument("--output-dir", default="outputs/analysis")
    args = parser.parse_args()
    analyze(args.inputs, Path(args.output_dir))
