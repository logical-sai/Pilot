"""Deterministic reminder-risk logic for the single-schema memory recall pilot.

The reminder score remains intentionally separate from the experimental distraction
analysis. The score uses task structure stored by the assessment app and does not
reinterpret the scenario with another LLM. It is a heuristic score, not a calibrated
forgetting probability.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from pilot_schema import RULE_ENGINE_VERSION, validate_columns


def _yes(v) -> bool:
    return str(v).strip().upper() == "Y"


@dataclass(frozen=True)
class ReminderDecision:
    session_id: str
    session_number: int
    user: str
    role: str
    set_index: int
    scenario_family_id: str
    scenario_form: str
    scenario_id: str
    target_id: str
    target_family_id: str
    task: str
    remembered: bool
    out_of_order: bool
    serial_category: str
    high_demand: bool
    open_ended: bool
    instruction_interference_present: bool
    trigger_anchor: str
    instruction_complexity_index: float
    distractor_condition: str
    risk_score: float
    risk_level: str
    requires_reminder: bool
    reminder_logic: str


class UniversalReminderRuleEngine:
    """Transparent deterministic reminder heuristic.

    Base score by serial position:
      Primacy = 10.0
      Middle  = 42.5
      Recency = 20.0

    Add 25.0 when the next instruction is high-demand (within-list interference),
    add 18.0 when the task is open-ended / weakly cued, and add 10.0 when the
    task itself is high-demand. Cap at 95.

    The assessment's NONE/LOW/HIGH experimental distractor condition is recorded
    but is deliberately NOT folded into this rule yet. That effect should first be
    estimated from real pilot data instead of assigning another arbitrary penalty.
    """

    BASE_WEIGHTS = {"Primacy": 10.0, "Middle": 42.5, "Recency": 20.0}
    INTERFERENCE_PENALTY = 25.0
    OPEN_ENDED_PENALTY = 18.0
    HIGH_DEMAND_PENALTY = 10.0
    MAX_SCORE = 95.0

    @classmethod
    def calculate(
        cls,
        *,
        serial_category: str,
        instruction_interference_present: bool,
        open_ended: bool,
        high_demand: bool,
    ) -> tuple[float, str, bool, str]:
        if serial_category not in cls.BASE_WEIGHTS:
            raise ValueError(f"Unknown serial category: {serial_category!r}")

        score = cls.BASE_WEIGHTS[serial_category]
        reasons = [f"{serial_category.lower()} base={score:.1f}"]
        if instruction_interference_present:
            score += cls.INTERFERENCE_PENALTY
            reasons.append(f"instruction-interference=+{cls.INTERFERENCE_PENALTY:.1f}")
        if open_ended:
            score += cls.OPEN_ENDED_PENALTY
            reasons.append(f"open-ended=+{cls.OPEN_ENDED_PENALTY:.1f}")
        if high_demand:
            score += cls.HIGH_DEMAND_PENALTY
            reasons.append(f"high-demand=+{cls.HIGH_DEMAND_PENALTY:.1f}")

        score = round(min(score, cls.MAX_SCORE), 1)
        level = "HIGH" if score >= 50.0 else ("MEDIUM" if score >= 25.0 else "LOW")
        requires = level == "HIGH"
        rationale = "; ".join(reasons) + f"; capped score={score:.1f}; level={level}"
        return score, level, requires, rationale

    @classmethod
    def decision_from_row(cls, row: dict) -> ReminderDecision:
        score, level, requires, rationale = cls.calculate(
            serial_category=row["Serial_Category"],
            instruction_interference_present=_yes(row["Instruction_Interference_Present"]),
            open_ended=_yes(row["Open_Ended"]),
            high_demand=_yes(row["High_Demand"]),
        )
        return ReminderDecision(
            session_id=row["Session_ID"],
            session_number=int(row["Session_Number"]),
            user=row["User"],
            role=row["Role"],
            set_index=int(row["Set_Index"]),
            scenario_family_id=row["Scenario_Family_ID"],
            scenario_form=row["Scenario_Form"],
            scenario_id=row["Scenario_ID"],
            target_id=row["Target_ID"],
            target_family_id=row["Target_Family_ID"],
            task=row["Target_Instruction"],
            remembered=_yes(row["Remembered"]),
            out_of_order=_yes(row["Out_of_Order"]),
            serial_category=row["Serial_Category"],
            high_demand=_yes(row["High_Demand"]),
            open_ended=_yes(row["Open_Ended"]),
            instruction_interference_present=_yes(row["Instruction_Interference_Present"]),
            trigger_anchor=row.get("Trigger_Anchor", ""),
            instruction_complexity_index=float(row.get("Instruction_Complexity_Index") or 0),
            distractor_condition=row.get("Distractor_Condition", ""),
            risk_score=score,
            risk_level=level,
            requires_reminder=requires,
            reminder_logic=rationale,
        )

    @classmethod
    def process_results_csv(
        cls,
        input_csv: str | Path,
        output_csv: str | Path,
        active_only: bool = False,
    ) -> list[ReminderDecision]:
        input_csv = Path(input_csv)
        output_csv = Path(output_csv)
        with input_csv.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            validate_columns(reader.fieldnames or [])
            rows = list(reader)

        decisions = []
        for row in rows:
            if row.get("Record_Type") != "Target":
                continue
            d = cls.decision_from_row(row)
            if not active_only or d.requires_reminder:
                decisions.append(d)

        output_csv.parent.mkdir(parents=True, exist_ok=True)
        fields = [
            "Session_ID", "Session_Number", "User", "Role", "Set_Index",
            "Scenario_Family_ID", "Scenario_Form", "Scenario_ID",
            "Target_ID", "Target_Family_ID", "Task", "Remembered", "Out_of_Order",
            "Serial_Category", "High_Demand", "Open_Ended",
            "Instruction_Interference_Present", "Trigger_Anchor",
            "Instruction_Complexity_Index", "Distractor_Condition",
            "Risk_Score", "Risk_Level", "Requires_Reminder", "Observed_Memory_Flag",
            "Reminder_Logic", "Rule_Engine_Version",
        ]
        with output_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for d in decisions:
                observed_flag = "Forgotten" if not d.remembered else ("Out_of_Order" if d.out_of_order else "Recalled")
                writer.writerow({
                    "Session_ID": d.session_id,
                    "Session_Number": d.session_number,
                    "User": d.user,
                    "Role": d.role,
                    "Set_Index": d.set_index,
                    "Scenario_Family_ID": d.scenario_family_id,
                    "Scenario_Form": d.scenario_form,
                    "Scenario_ID": d.scenario_id,
                    "Target_ID": d.target_id,
                    "Target_Family_ID": d.target_family_id,
                    "Task": d.task,
                    "Remembered": "Y" if d.remembered else "N",
                    "Out_of_Order": "Y" if d.out_of_order else "N",
                    "Serial_Category": d.serial_category,
                    "High_Demand": "Y" if d.high_demand else "N",
                    "Open_Ended": "Y" if d.open_ended else "N",
                    "Instruction_Interference_Present": "Y" if d.instruction_interference_present else "N",
                    "Trigger_Anchor": d.trigger_anchor,
                    "Instruction_Complexity_Index": d.instruction_complexity_index,
                    "Distractor_Condition": d.distractor_condition,
                    "Risk_Score": d.risk_score,
                    "Risk_Level": d.risk_level,
                    "Requires_Reminder": "Y" if d.requires_reminder else "N",
                    "Observed_Memory_Flag": observed_flag,
                    "Reminder_Logic": d.reminder_logic,
                    "Rule_Engine_Version": RULE_ENGINE_VERSION,
                })
        return decisions


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv")
    parser.add_argument("--output", default="outputs/reminder_candidates.csv")
    parser.add_argument("--active-only", action="store_true")
    args = parser.parse_args()

    results = UniversalReminderRuleEngine.process_results_csv(
        args.input_csv, args.output, active_only=args.active_only
    )
    print(f"Wrote {len(results)} reminder decisions to {args.output}")
