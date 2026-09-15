"""Audit equivalent-form complexity and repeated-session counterbalancing."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from complexity_metrics import measure_scenario
from protocol_design import prepare_session_scenarios
from scenario_bank import FORM_IDS, SCENARIO_FAMILIES


def write_complexity_report(output: Path) -> None:
    rows = []
    for family_id in sorted(SCENARIO_FAMILIES):
        family = SCENARIO_FAMILIES[family_id]
        for form_id in FORM_IDS:
            form = family["forms"][form_id]
            m = measure_scenario(form["tasks"])
            rows.append({
                "Scenario_Family_ID": family_id,
                "Scenario_Form": form_id,
                "Target_Count": m["target_count"],
                "Mean_Target_Words": m["mean_target_words"],
                "Mean_Dependency_Depth": m["mean_dependency_depth"],
                "Scenario_Semantic_Overlap": m["scenario_semantic_overlap"],
                "Instruction_Complexity_Index": m["instruction_complexity_index"],
            })
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    print("Equivalent-form structural complexity:")
    by_family = {}
    for r in rows:
        by_family.setdefault(r["Scenario_Family_ID"], []).append(r)
    for family_id, rs in by_family.items():
        vals = [float(r["Instruction_Complexity_Index"]) for r in rs]
        print(
            f"  {family_id}: "
            + ", ".join(f"{r['Scenario_Form']}={r['Instruction_Complexity_Index']:.3f}" for r in rs)
            + f" | range={max(vals)-min(vals):.3f}"
        )
    print(f"Wrote {output}")


def show_counterbalancing(user: str, sessions: int) -> None:
    user = "".join(ch if (ch.isalnum() or ch in "_-") else "_" for ch in user.strip())[:64] or "participant"
    print(f"\nCounterbalancing example for {user}:")
    for session_number in range(1, sessions + 1):
        form, scenarios = prepare_session_scenarios(user, session_number)
        print(f"\nSession {session_number} — form {form}")
        for s in scenarios:
            print(
                f"  set {s['set_index']}: {s['scenario_family_id']} / {s['scenario_form']} "
                f"/ distractor={s['distractor_condition']} / ICI={s['complexity']['instruction_complexity_index']:.3f}"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="P001")
    parser.add_argument("--sessions", type=int, default=3)
    parser.add_argument("--output", default="outputs/protocol_complexity_report.csv")
    args = parser.parse_args()
    write_complexity_report(Path(args.output))
    show_counterbalancing(args.user, args.sessions)
