# Memory Recall Pilot v8.3 — Stability Review

## Regression that triggered this build

The v8.2 protected-stimulus renderer referenced `io.BytesIO` and `base64.b64encode` without importing `io` or `base64`. Because session state/timing could already be mutated before rendering completed, a rendering exception could allow the timer-driven state machine to continue after a blank reading screen.

## Corrective architecture

- Added the missing imports.
- All five stimuli are pre-rendered before session start.
- Each cached stimulus is validated for a non-empty inline PNG.
- Every scenario is validated for non-empty text, set index 1..5, and exactly four target tasks.
- The timer refuses to operate on state that did not pass stimulus preflight.
- Mid-session reading screens use cached stimuli rather than regenerating them.
- App/schema version metadata are synchronized to `pilot-8.3`.
- Gradio is pinned to 6.5.1, the API line used for this build.

## Tests performed

- Python compilation for every `.py` file.
- Application module/UI construction under Gradio 6.5.1.
- Protected stimulus rendering produced a non-empty `data:image/png;base64,...` image.
- All five scenarios pre-rendered successfully before session start.
- Simulated complete five-set assessment with exact recalled tasks.
- Exactly 20 target rows produced.
- Set indices limited to 1..5.
- Final participant summary limited to five rows.
- Automatic participant-ID uniqueness and duplicate active-session blocking.
- Local Gradio server launch and HTTP root-page response.

## Remaining limitations

- Browser-level stimulus protection cannot prevent OS screenshots, screen recordings, cameras, or developer tools.
- Equivalent forms are structurally matched but still require empirical equivalence testing.
- Instruction complexity and reminder risk are heuristics until calibrated on real participant data.
- LLM semantic matching should eventually be validated against human-coded recall judgments.
