# Memory Recall Pilot v8.3 — Stabilization Build

This build intentionally adds no new participant-facing features. It stabilizes the existing five-set repeated-session pilot and adds end-to-end regression checks.

## Important fix in v8.3

v8.2 could advance through a blank reading phase if protected-stimulus rendering failed. The HTML renderer used `io` and `base64` without importing them, and the experimental timer could already be active when that failure occurred.

v8.3 changes the architecture:

1. All five instruction stimuli are rendered and validated **before a session can start**.
2. The five rendered stimuli are cached in session state.
3. The state machine displays only those prevalidated stimuli; it does not regenerate an image in the middle of the experiment.
4. If stimulus preflight fails, participant registration/startup fails before any experimental timer begins.
5. App/schema metadata are consistently `pilot-8.3`.
6. Gradio is pinned to the tested version `6.5.1` for reproducibility.

## Recall screen vs. reading screen

During **Reading**, the instruction stimulus must be visible.

During **Recall**, the instructions are intentionally hidden. A recall screen that contains only the recall textbox is therefore correct *provided that the participant saw the preceding reading stimulus*. A session that advances after a blank reading screen is invalid and should not be used as research data.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

The app expects Ollama at `http://localhost:11434/v1` with model `llama3.2`. If Ollama is unavailable, lexical recall matching still works, but semantic matching is reduced.

## Participant flow

### New participant

The default path automatically generates a unique pseudonymous Participant ID and private return code. The participant saves both before the first reading timer starts.

### Returning participant

A returning participant enters the existing Participant ID and private access code. The next completed-session number is assigned from existing results for that ID.

## Protocol

Each completed session has exactly:

- 5 sets;
- 4 target instructions per set;
- 20 target rows total in the detailed CSV;
- one of NONE / LOW / HIGH distraction conditions per set;
- a maximum of 5 participant-facing summary rows at the end.

A completed result file is refused if the set indices are not exactly 1, 2, 3, 4, 5.

## Protected stimulus

The stimulus is displayed as an inline PNG inside `gr.HTML`, so Gradio does not create its image download/fullscreen toolbar. Browser drag and context-menu actions are deterred on the protected stimulus.

This is not DRM. Operating-system screenshots, screen recording, browser developer tools, or photographing the display cannot be reliably prevented by a web app. The research protocol should explicitly prohibit retaining stimulus material.

## Main files

- `memory_recall_app.py` — participant UI and five-set state machine
- `scenario_bank.py` — fixed A/B/C equivalent forms and distractor banks
- `protocol_design.py` — counterbalancing
- `complexity_metrics.py` — instruction-complexity features
- `participant_registry.py` — pseudonymous IDs, access-code hashes, lockout/session protection
- `participant_admin.py` — researcher registry administration
- `pilot_schema.py` — canonical single schema
- `analyze_pilot_memory_logic.py` — descriptive multi-session analysis
- `ReminderRuleEngine.py` — deterministic reminder heuristic
- `export_google_calendar.py` — calendar adapter
- `self_check.py` — end-to-end offline regression test

## Research interpretation

The current complexity index, reminder-risk score, and matching thresholds remain pilot heuristics. They are not validated clinical or psychometric measures. Real pilot data should be used to estimate reliability, equivalent-form comparability, distraction effects, and later risk calibration.
