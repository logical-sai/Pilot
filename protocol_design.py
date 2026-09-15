"""Counterbalancing and session-design helpers for the pilot."""
from __future__ import annotations

import hashlib

from complexity_metrics import measure_scenario
from pilot_schema import serial_category
from scenario_bank import DISTRACTOR_LIBRARY, FORM_IDS, SCENARIO_FAMILIES

DISTRACTOR_CONDITIONS = ("NONE", "LOW", "HIGH")


def stable_int(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def prepare_session_scenarios(user: str, session_number: int) -> tuple[str, list[dict]]:
    """Build the five sets for one repeated-measures session.

    Equivalent form, scenario order, and experimental distractor condition are all
    deterministic for a participant/session so a run is reproducible.
    """
    form_offset = stable_int(user + ":form") % len(FORM_IDS)
    form_id = FORM_IDS[(form_offset + session_number - 1) % len(FORM_IDS)]

    canonical_families = sorted(SCENARIO_FAMILIES)
    order_shift = (stable_int(user + ":order") + session_number - 1) % len(canonical_families)
    ordered_families = canonical_families[order_shift:] + canonical_families[:order_shift]

    condition_offset = (stable_int(user + ":condition") + session_number - 1) % len(DISTRACTOR_CONDITIONS)

    prepared = []
    for order_position, family_id in enumerate(ordered_families, start=1):
        family = SCENARIO_FAMILIES[family_id]
        form = family["forms"][form_id]
        family_index = canonical_families.index(family_id)
        condition = DISTRACTOR_CONDITIONS[(family_index + condition_offset) % len(DISTRACTOR_CONDITIONS)]
        library = DISTRACTOR_LIBRARY[condition]
        distractor = dict(library[family_index % len(library)])

        raw_tasks = [dict(t) for t in form["tasks"]]
        complexity = measure_scenario(raw_tasks)
        total = len(raw_tasks)
        tasks = []
        for i, raw in enumerate(raw_tasks, start=1):
            tm = complexity["target_metrics"][i - 1]
            task = dict(raw)
            task.update({
                "target_id": f"{family_id}_{form_id}_t{i:02d}",
                "target_family_id": f"{family_id}_t{i:02d}",
                "target_index": i,
                "serial_category": serial_category(i, total),
                "instruction_interference_present": (
                    i < total and bool(raw_tasks[i].get("high_demand", False))
                ),
                "word_count": tm["word_count"],
                "semantic_overlap": tm["semantic_overlap"],
                "structural_complexity": tm["structural_complexity"],
            })
            tasks.append(task)

        prepared.append({
            "set_index": order_position,
            "scenario_order_position": order_position,
            "scenario_family_id": family_id,
            "scenario_form": form_id,
            "scenario_id": f"{family_id}_{form_id}",
            "title": family["title"],
            "scenario_text": form["scenario_text"],
            "non_instruction_distractor_count": int(form.get("non_instruction_distractor_count", 0)),
            "tasks": tasks,
            "complexity": complexity,
            "distractor_condition": condition,
            "distractor": distractor,
        })

    return form_id, prepared
