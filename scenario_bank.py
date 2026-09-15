"""Versioned scenario bank for the memory-recall pilot.

There is one active bank format. Each scenario family has three equivalent forms
(A/B/C) so the same participant can repeat the assessment without seeing the
identical wording every time. Forms are intentionally similar in task count and
structure, but equivalence must ultimately be checked with real pilot data.
"""
from __future__ import annotations

FORM_IDS = ("A", "B", "C")

# Each target uses the same structural metadata keys:
# - high_demand: task itself requires appreciable cognitive effort
# - open_ended: future action is weakly cued / flexible
# - trigger_anchor: natural event/time cue
# - dependency_depth: 0 = independent, 1 = depends on one preceding action,
#                     2 = nested/multistep dependency
SCENARIO_FAMILIES = {
    "pilot_s01": {
        "title": "Preparation sequence",
        "forms": {
            "A": {
                "scenario_text": (
                    "After dinner, place the lunch container in the sink. Then finish the math worksheet. "
                    "The weather report says tomorrow will be cooler. Put the signed form inside the backpack. "
                    "Before going to bed, set an alarm for 6:45 AM. A blue car is parked across the street."
                ),
                "non_instruction_distractor_count": 2,
                "tasks": [
                    {"text": "Place the lunch container in the sink", "high_demand": False, "open_ended": False, "trigger_anchor": "after dinner", "dependency_depth": 0},
                    {"text": "Finish the math worksheet", "high_demand": True, "open_ended": False, "trigger_anchor": "after putting away the lunch container", "dependency_depth": 1},
                    {"text": "Put the signed form inside the backpack", "high_demand": False, "open_ended": True, "trigger_anchor": "before preparing for tomorrow", "dependency_depth": 1},
                    {"text": "Set an alarm for 6:45 AM", "high_demand": False, "open_ended": False, "trigger_anchor": "before going to bed", "dependency_depth": 0},
                ],
            },
            "B": {
                "scenario_text": (
                    "After breakfast, place the cereal bowl in the dishwasher. Then finish the science worksheet. "
                    "The kitchen window is slightly open. Put the signed library slip inside the school folder. "
                    "Before leaving, set a reminder for 7:15 AM. A red bicycle is beside the fence."
                ),
                "non_instruction_distractor_count": 2,
                "tasks": [
                    {"text": "Place the cereal bowl in the dishwasher", "high_demand": False, "open_ended": False, "trigger_anchor": "after breakfast", "dependency_depth": 0},
                    {"text": "Finish the science worksheet", "high_demand": True, "open_ended": False, "trigger_anchor": "after putting away the cereal bowl", "dependency_depth": 1},
                    {"text": "Put the signed library slip inside the school folder", "high_demand": False, "open_ended": True, "trigger_anchor": "before preparing to leave", "dependency_depth": 1},
                    {"text": "Set a reminder for 7:15 AM", "high_demand": False, "open_ended": False, "trigger_anchor": "before leaving", "dependency_depth": 0},
                ],
            },
            "C": {
                "scenario_text": (
                    "After arriving home, hang the jacket on the hallway hook. Then complete the vocabulary review. "
                    "A delivery van is parked near the corner. Put the permission slip inside the blue folder. "
                    "Before dinner, set a timer reminder for 6:30 PM. The porch light is already on."
                ),
                "non_instruction_distractor_count": 2,
                "tasks": [
                    {"text": "Hang the jacket on the hallway hook", "high_demand": False, "open_ended": False, "trigger_anchor": "after arriving home", "dependency_depth": 0},
                    {"text": "Complete the vocabulary review", "high_demand": True, "open_ended": False, "trigger_anchor": "after hanging the jacket", "dependency_depth": 1},
                    {"text": "Put the permission slip inside the blue folder", "high_demand": False, "open_ended": True, "trigger_anchor": "before getting ready for dinner", "dependency_depth": 1},
                    {"text": "Set a timer reminder for 6:30 PM", "high_demand": False, "open_ended": False, "trigger_anchor": "before dinner", "dependency_depth": 0},
                ],
            },
        },
    },
    "pilot_s02": {
        "title": "Morning work sequence",
        "forms": {
            "A": {
                "scenario_text": (
                    "Before starting the main work period, refill the water bottle. Review the two-page instruction sheet carefully. "
                    "The hallway clock is five minutes fast. Send the completed permission form to the front desk. "
                    "After that, place the spare key in the labeled drawer. Someone outside is talking about a baseball game."
                ),
                "non_instruction_distractor_count": 2,
                "tasks": [
                    {"text": "Refill the water bottle", "high_demand": False, "open_ended": False, "trigger_anchor": "before starting the main work period", "dependency_depth": 0},
                    {"text": "Review the two-page instruction sheet", "high_demand": True, "open_ended": False, "trigger_anchor": "after refilling the water bottle", "dependency_depth": 1},
                    {"text": "Send the completed permission form to the front desk", "high_demand": False, "open_ended": True, "trigger_anchor": "after reviewing the instruction sheet", "dependency_depth": 1},
                    {"text": "Place the spare key in the labeled drawer", "high_demand": False, "open_ended": False, "trigger_anchor": "after sending the permission form", "dependency_depth": 0},
                ],
            },
            "B": {
                "scenario_text": (
                    "Before beginning the morning session, fill the travel mug with water. Review the two-page safety note carefully. "
                    "The wall calendar is still showing last month. Send the completed request form to the reception desk. "
                    "After that, place the backup badge in the marked tray. Someone nearby is discussing a basketball game."
                ),
                "non_instruction_distractor_count": 2,
                "tasks": [
                    {"text": "Fill the travel mug with water", "high_demand": False, "open_ended": False, "trigger_anchor": "before beginning the morning session", "dependency_depth": 0},
                    {"text": "Review the two-page safety note", "high_demand": True, "open_ended": False, "trigger_anchor": "after filling the travel mug", "dependency_depth": 1},
                    {"text": "Send the completed request form to the reception desk", "high_demand": False, "open_ended": True, "trigger_anchor": "after reviewing the safety note", "dependency_depth": 1},
                    {"text": "Place the backup badge in the marked tray", "high_demand": False, "open_ended": False, "trigger_anchor": "after sending the request form", "dependency_depth": 0},
                ],
            },
            "C": {
                "scenario_text": (
                    "Before beginning focused work, refill the thermos at the sink. Review the two-page project brief carefully. "
                    "The printer beside the door is making a quiet noise. Send the completed approval sheet to the service counter. "
                    "After that, place the spare access card in the labeled box. Two people nearby are discussing a tennis match."
                ),
                "non_instruction_distractor_count": 2,
                "tasks": [
                    {"text": "Refill the thermos at the sink", "high_demand": False, "open_ended": False, "trigger_anchor": "before beginning focused work", "dependency_depth": 0},
                    {"text": "Review the two-page project brief", "high_demand": True, "open_ended": False, "trigger_anchor": "after refilling the thermos", "dependency_depth": 1},
                    {"text": "Send the completed approval sheet to the service counter", "high_demand": False, "open_ended": True, "trigger_anchor": "after reviewing the project brief", "dependency_depth": 1},
                    {"text": "Place the spare access card in the labeled box", "high_demand": False, "open_ended": False, "trigger_anchor": "after sending the approval sheet", "dependency_depth": 0},
                ],
            },
        },
    },
    "pilot_s03": {
        "title": "Afternoon organization",
        "forms": {
            "A": {
                "scenario_text": (
                    "When the afternoon session begins, charge the tablet at the side outlet. Complete the short planning worksheet. "
                    "A delivery truck is stopped near the entrance. Move the folder marked REVIEW onto the top shelf. "
                    "Later, email the attendance note to the coordinator. The room has four windows."
                ),
                "non_instruction_distractor_count": 2,
                "tasks": [
                    {"text": "Charge the tablet at the side outlet", "high_demand": False, "open_ended": False, "trigger_anchor": "when the afternoon session begins", "dependency_depth": 0},
                    {"text": "Complete the short planning worksheet", "high_demand": True, "open_ended": False, "trigger_anchor": "after plugging in the tablet", "dependency_depth": 1},
                    {"text": "Move the folder marked REVIEW onto the top shelf", "high_demand": False, "open_ended": False, "trigger_anchor": "after the planning worksheet", "dependency_depth": 1},
                    {"text": "Email the attendance note to the coordinator", "high_demand": False, "open_ended": True, "trigger_anchor": "later in the afternoon", "dependency_depth": 0},
                ],
            },
            "B": {
                "scenario_text": (
                    "When the afternoon block begins, connect the laptop to the desk charger. Complete the short scheduling worksheet. "
                    "A maintenance cart is parked near the elevator. Move the folder marked CHECK onto the upper shelf. "
                    "Later, email the participation note to the supervisor. The room has three ceiling lights."
                ),
                "non_instruction_distractor_count": 2,
                "tasks": [
                    {"text": "Connect the laptop to the desk charger", "high_demand": False, "open_ended": False, "trigger_anchor": "when the afternoon block begins", "dependency_depth": 0},
                    {"text": "Complete the short scheduling worksheet", "high_demand": True, "open_ended": False, "trigger_anchor": "after connecting the laptop", "dependency_depth": 1},
                    {"text": "Move the folder marked CHECK onto the upper shelf", "high_demand": False, "open_ended": False, "trigger_anchor": "after the scheduling worksheet", "dependency_depth": 1},
                    {"text": "Email the participation note to the supervisor", "high_demand": False, "open_ended": True, "trigger_anchor": "later in the afternoon", "dependency_depth": 0},
                ],
            },
            "C": {
                "scenario_text": (
                    "When the afternoon work period starts, plug the phone into the charging dock. Complete the short priority worksheet. "
                    "A courier is standing near the front entrance. Move the folder marked ACTION onto the high shelf. "
                    "Later, email the check-in note to the manager. The room has two large clocks."
                ),
                "non_instruction_distractor_count": 2,
                "tasks": [
                    {"text": "Plug the phone into the charging dock", "high_demand": False, "open_ended": False, "trigger_anchor": "when the afternoon work period starts", "dependency_depth": 0},
                    {"text": "Complete the short priority worksheet", "high_demand": True, "open_ended": False, "trigger_anchor": "after plugging in the phone", "dependency_depth": 1},
                    {"text": "Move the folder marked ACTION onto the high shelf", "high_demand": False, "open_ended": False, "trigger_anchor": "after the priority worksheet", "dependency_depth": 1},
                    {"text": "Email the check-in note to the manager", "high_demand": False, "open_ended": True, "trigger_anchor": "later in the afternoon", "dependency_depth": 0},
                ],
            },
        },
    },
    "pilot_s04": {
        "title": "Departure checklist",
        "forms": {
            "A": {
                "scenario_text": (
                    "Before leaving the building, return the borrowed charger to the cabinet. Check the schedule for tomorrow's first appointment. "
                    "The lobby television is showing a travel program. Put the outgoing envelope in the mail tray. "
                    "Finally, turn off the desk lamp. A plant beside the doorway has yellow flowers."
                ),
                "non_instruction_distractor_count": 2,
                "tasks": [
                    {"text": "Return the borrowed charger to the cabinet", "high_demand": False, "open_ended": False, "trigger_anchor": "before leaving the building", "dependency_depth": 0},
                    {"text": "Check the schedule for tomorrow's first appointment", "high_demand": True, "open_ended": False, "trigger_anchor": "after returning the charger", "dependency_depth": 1},
                    {"text": "Put the outgoing envelope in the mail tray", "high_demand": False, "open_ended": True, "trigger_anchor": "before departure", "dependency_depth": 1},
                    {"text": "Turn off the desk lamp", "high_demand": False, "open_ended": False, "trigger_anchor": "immediately before leaving", "dependency_depth": 0},
                ],
            },
            "B": {
                "scenario_text": (
                    "Before leaving the office, return the borrowed adapter to the supply drawer. Check the schedule for tomorrow's first meeting. "
                    "The lobby screen is showing a cooking program. Put the outgoing package in the collection bin. "
                    "Finally, turn off the reading light. A plant near the doorway has broad leaves."
                ),
                "non_instruction_distractor_count": 2,
                "tasks": [
                    {"text": "Return the borrowed adapter to the supply drawer", "high_demand": False, "open_ended": False, "trigger_anchor": "before leaving the office", "dependency_depth": 0},
                    {"text": "Check the schedule for tomorrow's first meeting", "high_demand": True, "open_ended": False, "trigger_anchor": "after returning the adapter", "dependency_depth": 1},
                    {"text": "Put the outgoing package in the collection bin", "high_demand": False, "open_ended": True, "trigger_anchor": "before departure", "dependency_depth": 1},
                    {"text": "Turn off the reading light", "high_demand": False, "open_ended": False, "trigger_anchor": "immediately before leaving", "dependency_depth": 0},
                ],
            },
            "C": {
                "scenario_text": (
                    "Before leaving the workspace, return the borrowed headset to the storage cabinet. Check the schedule for tomorrow's first call. "
                    "The lobby display is showing a nature program. Put the outgoing document in the pickup tray. "
                    "Finally, turn off the task light. A small plant by the entrance has white flowers."
                ),
                "non_instruction_distractor_count": 2,
                "tasks": [
                    {"text": "Return the borrowed headset to the storage cabinet", "high_demand": False, "open_ended": False, "trigger_anchor": "before leaving the workspace", "dependency_depth": 0},
                    {"text": "Check the schedule for tomorrow's first call", "high_demand": True, "open_ended": False, "trigger_anchor": "after returning the headset", "dependency_depth": 1},
                    {"text": "Put the outgoing document in the pickup tray", "high_demand": False, "open_ended": True, "trigger_anchor": "before departure", "dependency_depth": 1},
                    {"text": "Turn off the task light", "high_demand": False, "open_ended": False, "trigger_anchor": "immediately before leaving", "dependency_depth": 0},
                ],
            },
        },
    },
    "pilot_s05": {
        "title": "End-of-day follow-up",
        "forms": {
            "A": {
                "scenario_text": (
                    "At the end of the day, place the completed checklist in the green folder. Review the summary page for errors. "
                    "A radio in the next room is playing softly. Send the final status message to the coordinator. "
                    "Before leaving, bring the reusable bottle home. The elevator doors are silver."
                ),
                "non_instruction_distractor_count": 2,
                "tasks": [
                    {"text": "Place the completed checklist in the green folder", "high_demand": False, "open_ended": False, "trigger_anchor": "at the end of the day", "dependency_depth": 0},
                    {"text": "Review the summary page for errors", "high_demand": True, "open_ended": False, "trigger_anchor": "after filing the checklist", "dependency_depth": 1},
                    {"text": "Send the final status message to the coordinator", "high_demand": False, "open_ended": True, "trigger_anchor": "after the review", "dependency_depth": 1},
                    {"text": "Bring the reusable bottle home", "high_demand": False, "open_ended": False, "trigger_anchor": "before leaving", "dependency_depth": 0},
                ],
            },
            "B": {
                "scenario_text": (
                    "At the end of the shift, place the completed log sheet in the orange folder. Review the summary note for errors. "
                    "Music from the hallway is playing quietly. Send the final progress message to the supervisor. "
                    "Before leaving, bring the travel mug home. The stairwell doors are gray."
                ),
                "non_instruction_distractor_count": 2,
                "tasks": [
                    {"text": "Place the completed log sheet in the orange folder", "high_demand": False, "open_ended": False, "trigger_anchor": "at the end of the shift", "dependency_depth": 0},
                    {"text": "Review the summary note for errors", "high_demand": True, "open_ended": False, "trigger_anchor": "after filing the log sheet", "dependency_depth": 1},
                    {"text": "Send the final progress message to the supervisor", "high_demand": False, "open_ended": True, "trigger_anchor": "after the review", "dependency_depth": 1},
                    {"text": "Bring the travel mug home", "high_demand": False, "open_ended": False, "trigger_anchor": "before leaving", "dependency_depth": 0},
                ],
            },
            "C": {
                "scenario_text": (
                    "At the end of the work period, place the completed review sheet in the purple folder. Review the summary memo for errors. "
                    "A podcast in the next room is playing softly. Send the final update message to the manager. "
                    "Before leaving, bring the insulated cup home. The elevator panel is black."
                ),
                "non_instruction_distractor_count": 2,
                "tasks": [
                    {"text": "Place the completed review sheet in the purple folder", "high_demand": False, "open_ended": False, "trigger_anchor": "at the end of the work period", "dependency_depth": 0},
                    {"text": "Review the summary memo for errors", "high_demand": True, "open_ended": False, "trigger_anchor": "after filing the review sheet", "dependency_depth": 1},
                    {"text": "Send the final update message to the manager", "high_demand": False, "open_ended": True, "trigger_anchor": "after the review", "dependency_depth": 1},
                    {"text": "Bring the insulated cup home", "high_demand": False, "open_ended": False, "trigger_anchor": "before leaving", "dependency_depth": 0},
                ],
            },
        },
    },
}

# All conditions use the same 30-second retention interval. NONE is the baseline
# (quiet wait), LOW uses simple arithmetic, and HIGH uses multistep working-memory
# arithmetic. The numeric difficulty score is protocol metadata, not a validated scale.
DISTRACTOR_LIBRARY = {
    "NONE": [
        {
            "distractor_id": "none_fixation_01",
            "task": "Keep your eyes on the fixation mark below until the interval ends.\n\n# +",
            "answer": "",
            "answers": [],
            "difficulty_score": 0.0,
            "requires_answer": False,
        },
    ],
    "LOW": [
        {"distractor_id":"low_pack_01","task":"Solve as many as you can in order. Enter answers separated by commas.\n\n1. 27 + 18 - 9\n2. 14 × 3 - 7\n3. 64 ÷ 8 + 17\n4. 51 - 19 + 6\n5. 9 × 5 - 13\n6. 33 + 16 - 12","answers":["36","35","25","38","32","37"],"answer":"36,35,25,38,32,37","difficulty_score":3.0,"requires_answer":True},
        {"distractor_id":"low_pack_02","task":"Solve as many as you can in order. Enter answers separated by commas.\n\n1. 45 - 17 + 8\n2. 8 × 4 + 5\n3. 81 ÷ 9 + 14\n4. 26 + 19 - 11\n5. 7 × 6 - 15\n6. 58 - 29 + 9","answers":["36","37","23","34","27","38"],"answer":"36,37,23,34,27,38","difficulty_score":3.0,"requires_answer":True},
        {"distractor_id":"low_pack_03","task":"Solve as many as you can in order. Enter answers separated by commas.\n\n1. 63 ÷ 7 + 12\n2. 34 + 28 - 17\n3. 6 × 7 - 8\n4. 71 - 26 + 4\n5. 9 × 4 + 3\n6. 52 - 18 - 7","answers":["21","45","34","49","39","27"],"answer":"21,45,34,49,39,27","difficulty_score":3.0,"requires_answer":True},
        {"distractor_id":"low_pack_04","task":"Solve as many as you can in order. Enter answers separated by commas.\n\n1. 39 + 24 - 13\n2. 72 ÷ 8 + 15\n3. 11 × 3 - 9\n4. 67 - 31 + 8\n5. 5 × 9 - 14\n6. 28 + 17 + 6","answers":["50","24","24","44","31","51"],"answer":"50,24,24,44,31,51","difficulty_score":3.0,"requires_answer":True},
        {"distractor_id":"low_pack_05","task":"Solve as many as you can in order. Enter answers separated by commas.\n\n1. 84 ÷ 12 + 19\n2. 43 - 16 + 12\n3. 7 × 5 + 4\n4. 62 - 28 - 9\n5. 24 + 33 - 18\n6. 8 × 6 - 11","answers":["26","39","39","25","39","37"],"answer":"26,39,39,25,39,37","difficulty_score":3.0,"requires_answer":True},
    ],
    "HIGH": [
        {"distractor_id":"high_pack_01","task":"Work through the multi-step problems in order. Enter final answers separated by commas.\n\n1. Start 18 → +7 → ×2 → -11\n2. Start 36 → -8 → +14 → ÷2\n3. Start 12 → ×3 → -5 → +17\n4. Start 50 → ÷2 → +9 → -13","answers":["39","21","48","21"],"answer":"39,21,48,21","difficulty_score":7.0,"requires_answer":True},
        {"distractor_id":"high_pack_02","task":"Work through the multi-step problems in order. Enter final answers separated by commas.\n\n1. Start 42 → -15 → +9 → ÷3\n2. Start 20 → +6 → ×2 → -17\n3. Start 64 → ÷2 → -7 → +19\n4. Start 15 → ×3 → +8 → -21","answers":["12","35","44","32"],"answer":"12,35,44,32","difficulty_score":7.0,"requires_answer":True},
        {"distractor_id":"high_pack_03","task":"Work through the multi-step problems in order. Enter final answers separated by commas.\n\n1. Start 16 → ×3 → -14 → +8\n2. Start 25 → +11 → ÷2 → +16\n3. Start 54 → -18 → ÷3 → +23\n4. Start 13 → +7 → ×2 → -9","answers":["42","34","35","31"],"answer":"42,34,35,31","difficulty_score":7.0,"requires_answer":True},
        {"distractor_id":"high_pack_04","task":"Work through the multi-step problems in order. Enter final answers separated by commas.\n\n1. Start 55 → -17 → ×2 → -20\n2. Start 30 → +12 → -6 → ÷3\n3. Start 72 → ÷3 → +15 → -11\n4. Start 19 → ×2 → -9 → +14","answers":["56","12","28","43"],"answer":"56,12,28,43","difficulty_score":7.0,"requires_answer":True},
        {"distractor_id":"high_pack_05","task":"Work through the multi-step problems in order. Enter final answers separated by commas.\n\n1. Start 24 → +12 → ÷2 → +19\n2. Start 48 → -18 → +6 → ÷2\n3. Start 14 → +9 → ×2 → -15\n4. Start 60 → ÷3 → +17 → -8","answers":["37","18","31","29"],"answer":"37,18,31,29","difficulty_score":7.0,"requires_answer":True},
    ],
}


def validate_bank() -> None:
    family_ids = sorted(SCENARIO_FAMILIES)
    if not family_ids:
        raise ValueError("Scenario bank is empty.")
    for family_id, family in SCENARIO_FAMILIES.items():
        forms = family.get("forms", {})
        if set(forms) != set(FORM_IDS):
            raise ValueError(f"{family_id} must contain forms {FORM_IDS}.")
        counts = []
        for form_id in FORM_IDS:
            form = forms[form_id]
            tasks = form.get("tasks", [])
            if not tasks:
                raise ValueError(f"{family_id}/{form_id} has no tasks.")
            counts.append(len(tasks))
            for task in tasks:
                for key in ("text", "high_demand", "open_ended", "trigger_anchor", "dependency_depth"):
                    if key not in task:
                        raise ValueError(f"{family_id}/{form_id} task missing {key}.")
        if len(set(counts)) != 1:
            raise ValueError(f"Equivalent forms for {family_id} do not have the same task count.")

    for condition in ("NONE", "LOW", "HIGH"):
        if condition not in DISTRACTOR_LIBRARY or not DISTRACTOR_LIBRARY[condition]:
            raise ValueError(f"Missing distractor condition {condition}.")


validate_bank()
