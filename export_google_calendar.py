"""Export reminder candidates into a Google Calendar-compatible CSV.

Calendar events require concrete dates and times. This exporter therefore expects a
planning CSV where each active reminder has Start_Date, Start_Time, End_Date, End_Time.
It intentionally does NOT invent dates from natural-language anchors.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

REQUIRED = {
    "User", "Task", "Risk_Score", "Risk_Level", "Requires_Reminder",
    "Trigger_Anchor", "Reminder_Logic", "Start_Date", "Start_Time",
    "End_Date", "End_Time",
}


def export(input_csv: Path, output_csv: Path) -> None:
    with input_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                "Calendar planning file is missing: " + ", ".join(sorted(missing))
            )
        rows = list(reader)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "Subject", "Start Date", "Start Time", "End Date", "End Time",
        "All Day Event", "Description", "Location", "Private",
    ]
    count = 0
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            if str(r["Requires_Reminder"]).upper() != "Y":
                continue
            if not all(r.get(k, "").strip() for k in ["Start_Date", "Start_Time", "End_Date", "End_Time"]):
                raise ValueError(
                    f"Reminder for {r.get('Task','[unknown]')} lacks a concrete calendar time."
                )
            writer.writerow({
                "Subject": f"Memory reminder — {r['Task']}",
                "Start Date": r["Start_Date"],
                "Start Time": r["Start_Time"],
                "End Date": r["End_Date"],
                "End Time": r["End_Time"],
                "All Day Event": "False",
                "Description": (
                    f"User: {r['User']} | Session: {r.get('Session_Number', '')} | Heuristic risk: {r['Risk_Score']} "
                    f"({r['Risk_Level']}) | Anchor: {r['Trigger_Anchor']} | "
                    f"Logic: {r['Reminder_Logic']}"
                ),
                "Location": "",
                "Private": "True",
            })
            count += 1
    print(f"Wrote {count} calendar event(s) to {output_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv")
    parser.add_argument("--output", default="outputs/google_calendar_reminders.csv")
    args = parser.parse_args()
    export(Path(args.input_csv), Path(args.output))
