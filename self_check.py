"""Regression self-check for Memory Recall Pilot v8.3.

This check deliberately exercises more than syntax: protocol structure, stimulus
rendering, registry behavior, and a complete five-set state-machine session are
validated without contacting Ollama.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import participant_registry as registry
from pilot_schema import APP_VERSION, SCHEMA_VERSION, CANONICAL_COLUMNS
from protocol_design import prepare_session_scenarios
from scenario_bank import SCENARIO_FAMILIES, DISTRACTOR_LIBRARY
import memory_recall_app as app


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    require(APP_VERSION == "pilot-8.3", f"Unexpected app version: {APP_VERSION}")
    require(SCHEMA_VERSION == "pilot-8.3", f"Unexpected schema version: {SCHEMA_VERSION}")
    require(len(CANONICAL_COLUMNS) == len(set(CANONICAL_COLUMNS)), "Canonical schema has duplicate columns.")
    require(len(SCENARIO_FAMILIES) == 5, "Pilot must contain exactly five scenario families.")

    # Protocol structure and counterbalancing.
    user = "PSELFCHK"
    family_conditions: dict[str, list[str]] = {}
    forms = []
    for session in (1, 2, 3):
        form, scenarios = prepare_session_scenarios(user, session)
        forms.append(form)
        require(len(scenarios) == 5, f"Session {session} did not prepare five sets.")
        require([s["set_index"] for s in scenarios] == [1, 2, 3, 4, 5], "Set indices must be exactly 1..5.")
        require(all(len(s["tasks"]) == 4 for s in scenarios), "Each set must contain four target instructions.")
        require(all(str(s.get("scenario_text", "")).strip() for s in scenarios), "Every set must have non-empty instruction text.")
        for scenario in scenarios:
            family_conditions.setdefault(scenario["scenario_family_id"], []).append(
                scenario["distractor_condition"]
            )

    require(len(set(forms)) == 3, "Three repeated sessions should rotate through all three equivalent forms.")
    for family, conditions in family_conditions.items():
        require(set(conditions) == {"NONE", "LOW", "HIGH"}, f"{family} is not counterbalanced across distraction conditions.")

    require(len(DISTRACTOR_LIBRARY["NONE"]) >= 1, "Missing NONE distractor baseline.")
    require(all(len(x.get("answers", [])) == 6 for x in DISTRACTOR_LIBRARY["LOW"]), "LOW distractor packs must have six items.")
    require(all(len(x.get("answers", [])) == 4 for x in DISTRACTOR_LIBRARY["HIGH"]), "HIGH distractor packs must have four items.")

    # Actual stimulus renderer (this specifically catches missing io/base64 imports).
    html = app.render_protected_stimulus_html(
        "After dinner, place the lunch container in the sink.",
        "PSELFCHK",
        "Student",
        1,
    )
    require("data:image/png;base64," in html, "Protected stimulus did not contain an inline PNG.")
    require("protected-stimulus-image" in html, "Protected stimulus HTML is malformed.")

    # Registry + complete five-set state-machine smoke test in isolated storage.
    original_registry = registry.REGISTRY_PATH
    original_output_dir = app.OUTPUT_DIR
    original_llm_matches = app.llm_candidate_matches
    try:
        with tempfile.TemporaryDirectory(prefix="pilot_v83_regression_") as td:
            td = Path(td)
            registry.REGISTRY_PATH = td / "registry.sqlite3"
            app.OUTPUT_DIR = td / "outputs"
            app.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            # Keep this self-check offline and deterministic.
            app.llm_candidate_matches = lambda tasks, recall_lines: []

            pid1, code1 = registry.create_auto_participant()
            pid2, _ = registry.create_auto_participant()
            require(pid1 != pid2, "Automatically generated Participant IDs collided.")

            token = pid1 + "_selfcheck"
            require(registry.authenticate_and_acquire_session(pid1, code1, token) == pid1, "Valid credentials failed.")
            try:
                registry.authenticate_and_acquire_session(pid1, code1, pid1 + "_duplicate")
                raise AssertionError("Concurrent reuse of the same Participant ID was not blocked.")
            except registry.ActiveSessionError:
                pass

            state = app.make_state(pid1, "Student", app.utc_now(), token)
            require(state.get("stimuli_preflight_ok") is True, "Stimulus preflight flag was not set.")
            require(len(state["scenarios"]) == 5, "Preflight state does not contain five scenarios.")
            for scenario in state["scenarios"]:
                require("data:image/png;base64," in scenario.get("stimulus_html", ""),
                        f"Set {scenario['set_index']} has no cached stimulus.")

            # Complete all five sets with exact target text. This exercises scoring,
            # set advancement, save invariants, filename generation, and summary rows.
            for set_number in range(1, 6):
                scenario = state["scenario"]
                require(scenario["set_index"] == set_number, "State-machine set order is incorrect.")
                require("data:image/png;base64," in app.scenario_stimulus_html(state),
                        "Reading phase would be blank.")

                state["reading_end"] = app.utc_now()
                state["distractor_start"] = app.utc_now()
                state["distractor_end"] = app.utc_now()
                state["recall_start"] = app.utc_now()
                recalled = "\n".join(t["text"] for t in scenario["tasks"])
                distractor_answer = scenario["distractor"].get("answer", "")

                require(app.append_set_results(state, recalled, distractor_answer),
                        f"Set {set_number} could not be finalized.")
                finished, path = app.advance_after_set(state)
                if set_number < 5:
                    require(not finished, "Session ended before Set 5.")
                else:
                    require(finished and path is not None and path.exists(), "Completed session was not saved.")

            targets = [r for r in state["results"] if r.get("Record_Type") == "Target"]
            require(len(targets) == 20, f"Expected 20 target rows, got {len(targets)}.")
            require(sorted({int(r["Set_Index"]) for r in targets}) == [1, 2, 3, 4, 5],
                    "Saved target data contains invalid set indices.")
            require(len(app.current_df_rows(state)) == 5,
                    "Participant-facing final summary must contain exactly five set rows.")
    finally:
        registry.REGISTRY_PATH = original_registry
        app.OUTPUT_DIR = original_output_dir
        app.llm_candidate_matches = original_llm_matches

    print("Memory Recall Pilot v8.3 regression check: PASS")
    print("  - app/schema version consistency: PASS")
    print("  - five-set protocol and 4 targets/set: PASS")
    print("  - equivalent-form/distraction counterbalancing: PASS")
    print("  - protected stimulus PNG rendering: PASS")
    print("  - all five stimuli pre-render before assessment: PASS")
    print("  - automatic Participant ID uniqueness: PASS")
    print("  - concurrent duplicate-ID protection: PASS")
    print("  - complete five-set state-machine simulation: PASS")
    print("  - exactly 20 saved target rows: PASS")
    print("  - final UI summary exactly five rows: PASS")


if __name__ == "__main__":
    main()
