from __future__ import annotations

import base64
import copy
import csv
import io
import json
import math
import re
import secrets
import time
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

import gradio as gr
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI

from ReminderRuleEngine import UniversalReminderRuleEngine
from participant_registry import (
    ActiveSessionError,
    InvalidCredentialsError,
    ParticipantInactiveError,
    ParticipantLockedError,
    authenticate_and_acquire_session,
    create_auto_participant,
    normalize_participant_id,
    release_session,
)
from pilot_config import (
    APP_RUNTIME_VERSION,
    APP_TITLE,
    COMPLEXITY_DEPTH_WEIGHT,
    COMPLEXITY_INDEX_SCALE,
    COMPLEXITY_OVERLAP_WEIGHT,
    COMPLEXITY_WORD_NORMALIZER,
    COMPLEXITY_WORD_WEIGHT,
    CUSTOM_CSS,
    DEFAULT_ROLE,
    DEFAULT_TARGET_WORD_COUNT,
    DEPENDENCY_DEPTH_MAX,
    DEPENDENCY_DEPTH_MIN,
    DEPENDENCY_MARKERS,
    DISPLAY_COLUMNS as CONFIG_DISPLAY_COLUMNS,
    DISTRACTOR_TIME_SECONDS,
    EVALUATOR_MAX_TOKENS,
    EVALUATOR_TEMPERATURE,
    EXACT_MATCH_THRESHOLD,
    GENERAL_ROLE_PROMPT,
    GENERATION_ERROR_PREVIEW_CHARS,
    GRADIO_SHARE,
    GROQ_API_KEY,
    GROQ_BASE_URL,
    ISO_TIMESPEC,
    MATCH_SCORE_MAX,
    METRIC_ROUND_DIGITS,
    MODEL_HEALTHCHECK_MAX_TOKENS,
    MODEL_HEALTHCHECK_TEMPERATURE,
    MODEL_MAX_RETRIES,
    MODEL_NAME,
    MODEL_REASONING_EFFORT,
    MODEL_TIMEOUT_SECONDS,
    NON_INSTRUCTION_DETAILS_PER_SCENARIO,
    OTHER_ROLE_VALUE,
    OUTPUT_COLLISION_SUFFIX_BYTES,
    OUTPUT_DELIMITER,
    OUTPUT_DOWNLOAD_LABEL,
    OUTPUT_ENCODING,
    OUTPUT_FILE_EXTENSION,
    OUTPUT_FILE_PREFIX,
    OUTPUT_TIMESTAMP_FORMAT,
    PROTECTION_JS,
    QUIET_DISTRACTOR_CONDITION,
    RATE_LIMIT_AUTO_WAIT_MAX_SECONDS,
    READING_TIME_SECONDS,
    RECALL_INPUT_LINES,
    RECALL_TIME_SECONDS,
    RESULTS_TABLE_COLUMN_WIDTHS,
    RESULTS_TABLE_MAX_HEIGHT,
    ROLE_GENERATION_CHUNK_SIZE,
    ROLE_GENERATION_TOKEN_OVERHEAD,
    ROLE_GENERATION_TOKENS_PER_SET,
    ROLE_GENERATION_MAX_TOKENS,
    ROLE_GENERATION_RETRIES,
    ROLE_REPAIR_MAX_TOKENS,
    ROLE_REPAIR_TEMPERATURE,
    ROLE_GENERATION_TEMPERATURE,
    ROLE_GENERATION_VERSION,
    ROLE_SLUG_FALLBACK,
    ROLE_SLUG_MAX_LENGTH,
    ROLES,
    SEMANTIC_MATCH_THRESHOLD,
    STIMULUS_BACKGROUND_RGB,
    STIMULUS_FONT_NAME,
    STIMULUS_FONT_SIZE,
    STIMULUS_HEADER_RGB,
    STIMULUS_HEADER_X,
    STIMULUS_HEADER_Y,
    STIMULUS_HEIGHT,
    STIMULUS_LINE_HEIGHT,
    STIMULUS_MARGIN,
    STIMULUS_RULE_RGB,
    STIMULUS_RULE_Y,
    STIMULUS_SEQUENCE,
    STIMULUS_SMALL_FONT_SIZE,
    STIMULUS_TEXT_RGB,
    STIMULUS_TEXT_START_Y,
    STIMULUS_WIDTH,
    SUBJECT_ID_MAX_LENGTH,
    TARGETS_PER_SCENARIO,
    TARGET_WORD_TOLERANCE,
    TIMER_INTERVAL_SECONDS,
)
from pilot_schema import (
    APP_VERSION,
    SCHEMA_VERSION,
    RULE_ENGINE_VERSION,
    CONSENT_TEXT_VERSION,
    PARTICIPANT_REGISTRY_VERSION,
    CANONICAL_COLUMNS,
    OUTPUT_DIR,
)
from protocol_design import prepare_session_scenarios
from scenario_bank import SCENARIO_FAMILIES

# ==========================================================================
# RUNTIME MODEL CLIENT
# ==========================================================================
print(
    f"[PILOT RUNTIME] version={APP_RUNTIME_VERSION} "
    f"model={MODEL_NAME} reasoning_effort={MODEL_REASONING_EFFORT} "
    f"chunk_size={ROLE_GENERATION_CHUNK_SIZE} "
    f"generation_cap={ROLE_GENERATION_MAX_TOKENS}",
    flush=True,
)

print(
    "[PILOT UI] one-second timer outputs only state/countdowns/phase signal; "
    "static components are not part of timer.tick",
    flush=True,
)

client = (
    OpenAI(
        base_url=GROQ_BASE_URL,
        api_key=GROQ_API_KEY,
        timeout=MODEL_TIMEOUT_SECONDS,
        max_retries=MODEL_MAX_RETRIES,
    )
    if GROQ_API_KEY
    else None
)


def require_model_client() -> OpenAI:
    if client is None:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Set it in the environment running this app. "
            "Role-specific scenario generation requires the configured model backend."
        )
    return client


def test_model_connection() -> None:
    """Optional backend health check."""
    c = require_model_client()
    try:
        response = c.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": "Reply with exactly OK."}],
            temperature=MODEL_HEALTHCHECK_TEMPERATURE,
            max_tokens=MODEL_HEALTHCHECK_MAX_TOKENS,
        )
        content = (response.choices[0].message.content or "").strip()
        print(f"[MODEL READY] model={MODEL_NAME} response={content!r}", flush=True)
    except Exception as exc:
        raise RuntimeError(
            f"Could not reach configured model {MODEL_NAME}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


ROLES_LIST = list(ROLES)
TOTAL_SETS = len(SCENARIO_FAMILIES)

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str:
    return dt.isoformat(timespec=ISO_TIMESPEC) if dt else ""


def seconds_between(start: datetime | None, end: datetime | None) -> float:
    if not start or not end:
        return 0.0
    return round(max(0.0, (end - start).total_seconds()), METRIC_ROUND_DIGITS)


def sanitize_subject_id(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", (value or "").strip())
    return value[:SUBJECT_ID_MAX_LENGTH] or "participant"


def next_session_number(user: str) -> int:
    """Return the next completed-session number for this participant.

    Only completed CSVs count. An aborted run can therefore be restarted with the
    same session number, which is useful during local testing.
    """
    pattern = re.compile(rf"^{re.escape(OUTPUT_FILE_PREFIX)}_{re.escape(user)}_S(\d+)_")
    max_seen = 0
    for path in OUTPUT_DIR.glob(f"{OUTPUT_FILE_PREFIX}_{user}_S*{OUTPUT_FILE_EXTENSION}"):
        m = pattern.match(path.name)
        if m:
            max_seen = max(max_seen, int(m.group(1)))
    return max_seen + 1


def render_text_to_watermarked_image(text: str, subject_id: str, role: str, session_number: int) -> Image.Image:
    width, height = STIMULUS_WIDTH, STIMULUS_HEIGHT
    img = Image.new("RGB", (width, height), STIMULUS_BACKGROUND_RGB)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(STIMULUS_FONT_NAME, STIMULUS_FONT_SIZE)
        small = ImageFont.truetype(STIMULUS_FONT_NAME, STIMULUS_SMALL_FONT_SIZE)
    except Exception:
        font = ImageFont.load_default()
        small = ImageFont.load_default()

    draw.text(
        (STIMULUS_HEADER_X, STIMULUS_HEADER_Y),
        f"MEMORY PILOT  •  {subject_id}  •  {role}  •  SESSION {session_number}",
        fill=STIMULUS_HEADER_RGB, font=small,
    )
    draw.line([(STIMULUS_HEADER_X, STIMULUS_RULE_Y), (width - STIMULUS_HEADER_X, STIMULUS_RULE_Y)], fill=STIMULUS_RULE_RGB, width=1)

    margin, y = STIMULUS_MARGIN, STIMULUS_TEXT_START_Y
    words = text.split()
    line = []
    max_text_width = width - 2 * margin
    for word in words:
        candidate = " ".join(line + [word])
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if (bbox[2] - bbox[0]) > max_text_width and line:
            draw.text((margin, y), " ".join(line), fill=STIMULUS_TEXT_RGB, font=font)
            y += STIMULUS_LINE_HEIGHT
            line = [word]
        else:
            line.append(word)
    if line:
        draw.text((margin, y), " ".join(line), fill=STIMULUS_TEXT_RGB, font=font)
    return img



def render_protected_stimulus_html(
    text: str,
    subject_id: str,
    role: str,
    session_number: int,
) -> str:
    """Render the stimulus as an inline HTML image with no Gradio image toolbar."""
    image = render_text_to_watermarked_image(text, subject_id, role, session_number)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return (
        '<div class="protected-stimulus-frame">'
        '<img class="protected-stimulus-image" '
        f'src="data:image/png;base64,{encoded}" '
        'alt="Memory instructions" draggable="false" />'
        '</div>'
    )


def cache_and_validate_stimuli(
    scenarios: list[dict],
    subject_id: str,
    role: str,
    session_number: int,
) -> None:
    """Pre-render all five stimuli before the assessment can start.

    This is deliberately a preflight step. If rendering fails, registration/startup
    fails before any experimental timer begins, so a participant can never advance
    through a blank reading phase.
    """
    if len(scenarios) != TOTAL_SETS:
        raise RuntimeError(
            f"Protocol error: expected {TOTAL_SETS} scenarios, got {len(scenarios)}."
        )

    expected_indices = list(range(1, TOTAL_SETS + 1))
    actual_indices = [int(s.get("set_index", -1)) for s in scenarios]
    if actual_indices != expected_indices:
        raise RuntimeError(
            f"Protocol error: set indices must be {expected_indices}, got {actual_indices}."
        )

    for scenario in scenarios:
        text = str(scenario.get("scenario_text", "")).strip()
        tasks = scenario.get("tasks") or []
        if not text:
            raise RuntimeError(
                f"Stimulus error: Set {scenario['set_index']} has no scenario text."
            )
        if len(tasks) != TARGETS_PER_SCENARIO:
            raise RuntimeError(
                f"Protocol error: Set {scenario['set_index']} must contain exactly {TARGETS_PER_SCENARIO} target tasks."
            )

        html = render_protected_stimulus_html(
            text, subject_id, role, session_number
        )
        if (
            not html
            or "data:image/png;base64," not in html
            or "protected-stimulus-image" not in html
        ):
            raise RuntimeError(
                f"Stimulus error: Set {scenario['set_index']} did not render correctly."
            )
        scenario["stimulus_html"] = html


def current_scenario(state: dict) -> dict:
    """Return the scenario for the authoritative zero-based set position.

    `state["set_idx"]` + `state["scenarios"]` are the source of truth.
    `state["scenario"]` is maintained only as a compatibility/cache field for
    existing UI code. This prevents timer/manual-submit callbacks from leaving
    the cached scenario and set counter out of sync.
    """
    if not state:
        raise RuntimeError("Session state is unavailable.")

    scenarios = state.get("scenarios") or []
    try:
        set_idx = int(state.get("set_idx", -1))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Invalid internal set position: {state.get('set_idx')!r}."
        ) from exc

    if not 0 <= set_idx < len(scenarios):
        raise RuntimeError(
            f"Internal set position {set_idx} is outside the scenario list "
            f"(count={len(scenarios)})."
        )

    scenario = scenarios[set_idx]
    expected_set_index = set_idx + 1

    try:
        actual_set_index = int(scenario.get("set_index", -1))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Scenario at position {set_idx} has invalid set_index "
            f"{scenario.get('set_index')!r}."
        ) from exc

    if actual_set_index != expected_set_index:
        raise RuntimeError(
            "Scenario list invariant violated: "
            f"position={set_idx}, expected set_index={expected_set_index}, "
            f"actual set_index={actual_set_index}, "
            f"scenario_id={scenario.get('scenario_id', '')!r}."
        )

    # Repair only the redundant cached pointer, never the research structure.
    cached = state.get("scenario")
    if cached is not scenario:
        state["scenario"] = scenario

    return scenario


def scenario_stimulus_html(state: dict) -> str:
    """Return a prevalidated stimulus; never silently return a blank canvas."""
    scenario = current_scenario(state)
    html = scenario.get("stimulus_html")
    if not html or "data:image/png;base64," not in html:
        raise RuntimeError(
            f"Stimulus unavailable for Set {scenario.get('set_index', '?')}. "
            "The assessment has been stopped rather than advancing without instructions."
        )
    return html

# ==========================================================================
# RECALL MATCHING
# ==========================================================================
def lexical_similarity(a: str, b: str) -> float:
    def norm(s: str) -> str:
        s = re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())
        return re.sub(r"\s+", " ", s).strip()

    a2, b2 = norm(a), norm(b)
    if not a2 or not b2:
        return 0.0
    seq = SequenceMatcher(None, a2, b2).ratio()
    a_set, b_set = set(a2.split()), set(b2.split())
    jaccard = len(a_set & b_set) / max(1, len(a_set | b_set))
    containment = 1.0 if a2 in b2 or b2 in a2 else 0.0
    return max(seq, jaccard, containment)


def llm_candidate_matches(tasks: list[dict], recall_lines: list[str]) -> list[dict]:
    """Ask the local model for semantic candidates; deterministic code resolves conflicts."""
    if not recall_lines:
        return []
    targets = [{"target_id": t["target_id"], "text": t["text"]} for t in tasks]
    prompt = f"""
Match recalled lines to original tasks by meaning. A recall line may match at most one target.
Do not label extra detail as a separate intrusion if it belongs to a matched target.
Return JSON only:
{{"matches":[{{"recall_index":0,"target_id":"...","score":0.0,"match_type":"Semantic"}}]}}

TARGETS:
{json.dumps(targets, ensure_ascii=False)}

RECALL LINES:
{json.dumps(recall_lines, ensure_ascii=False)}
"""
    try:
        response = require_model_client().chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Return only one strict JSON object with no Markdown or commentary."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=EVALUATOR_TEMPERATURE,
            max_tokens=EVALUATOR_MAX_TOKENS,
            extra_body=_groq_reasoning_extra_body(),
        )
        data = _extract_generation_payload(
            response.choices[0].message.content or ""
        )
        return data.get("matches", [])
    except Exception:
        # The app still works using deterministic lexical matching if semantic evaluation is unavailable.
        return []


def score_recall(tasks: list[dict], recall_lines: list[str]) -> tuple[list[dict], list[str]]:
    """One-to-one target/recall assignment.

    A matched recall line can never also become an intrusion.
    """
    candidates: list[dict] = []

    for ri, recall in enumerate(recall_lines):
        for task in tasks:
            score = lexical_similarity(recall, task["text"])
            if score >= SEMANTIC_MATCH_THRESHOLD:
                candidates.append({
                    "recall_index": ri,
                    "target_id": task["target_id"],
                    "score": score,
                    "match_type": "Exact" if score >= EXACT_MATCH_THRESHOLD else "Semantic",
                })

    for c in llm_candidate_matches(tasks, recall_lines):
        try:
            ri = int(c["recall_index"])
            tid = str(c["target_id"])
            score = float(c.get("score", 0.0))
            if (
                0 <= ri < len(recall_lines)
                and any(t["target_id"] == tid for t in tasks)
                and score >= SEMANTIC_MATCH_THRESHOLD
            ):
                candidates.append({
                    "recall_index": ri,
                    "target_id": tid,
                    "score": min(score, MATCH_SCORE_MAX),
                    "match_type": c.get("match_type", "Semantic"),
                })
        except (KeyError, TypeError, ValueError):
            continue

    candidates.sort(key=lambda x: x["score"], reverse=True)
    used_recalls, used_targets = set(), set()
    selected = []
    for c in candidates:
        if c["recall_index"] in used_recalls or c["target_id"] in used_targets:
            continue
        used_recalls.add(c["recall_index"])
        used_targets.add(c["target_id"])
        selected.append(c)

    match_by_target = {c["target_id"]: c for c in selected}
    target_rows = []
    matched_recall_order = []
    for task in tasks:
        c = match_by_target.get(task["target_id"])
        if c:
            matched_recall_order.append((task["target_id"], c["recall_index"]))
            target_rows.append({
                "target_id": task["target_id"],
                "remembered": True,
                "user_recall_text": recall_lines[c["recall_index"]],
                "match_type": c["match_type"],
                "match_score": round(float(c["score"]), METRIC_ROUND_DIGITS),
                "recall_index": c["recall_index"],
            })
        else:
            target_rows.append({
                "target_id": task["target_id"],
                "remembered": False,
                "user_recall_text": "",
                "match_type": "None",
                "match_score": 0.0,
                "recall_index": None,
            })

    recalled_target_order = [tid for tid, _ in sorted(matched_recall_order, key=lambda x: x[1])]
    original_matched_order = [t["target_id"] for t in tasks if t["target_id"] in used_targets]
    position_in_recall = {tid: i for i, tid in enumerate(recalled_target_order)}
    position_in_original = {tid: i for i, tid in enumerate(original_matched_order)}
    for row in target_rows:
        tid = row["target_id"]
        row["out_of_order"] = bool(
            row["remembered"] and position_in_recall.get(tid) != position_in_original.get(tid)
        )

    intrusions = [line for i, line in enumerate(recall_lines) if i not in used_recalls]
    return target_rows, intrusions


# ==========================================================================
# ROLE-AWARE STIMULUS GENERATION + SESSION / COUNTERBALANCING
# ==========================================================================
def _word_tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", str(text or "").lower())


def _dependency_depth(text: str) -> int:
    """Small deterministic proxy for syntactic/dependency load.

    This is intentionally transparent rather than LLM-scored. It counts common
    conditional/temporal dependency markers and coordination, then caps the
    value so one unusually long sentence cannot dominate the session metric.
    """
    tokens = _word_tokens(text)
    return max(
        DEPENDENCY_DEPTH_MIN,
        min(
            DEPENDENCY_DEPTH_MAX,
            DEPENDENCY_DEPTH_MIN
            + sum(token in DEPENDENCY_MARKERS for token in tokens),
        ),
    )


def _pairwise_semantic_overlap(text: str, others: list[str]) -> float:
    words = set(_word_tokens(text))
    if not words or not others:
        return 0.0
    scores = []
    for other in others:
        other_words = set(_word_tokens(other))
        if not other_words:
            continue
        scores.append(len(words & other_words) / max(1, len(words | other_words)))
    return round(sum(scores) / len(scores), METRIC_ROUND_DIGITS) if scores else 0.0


def _recompute_role_adapted_complexity(scenario: dict) -> None:
    """Refresh text-dependent complexity fields after role adaptation.

    The experimental flags (serial position, open-ended/high-demand status,
    interference assignment) still come from the counterbalanced template.
    Text-derived measures are recomputed from the generated role-specific text.
    """
    tasks = scenario["tasks"]
    texts = [str(task["text"]).strip() for task in tasks]

    structural_values = []
    for i, task in enumerate(tasks):
        words = len(_word_tokens(task["text"]))
        depth = _dependency_depth(task["text"])
        overlap = _pairwise_semantic_overlap(
            task["text"], [text for j, text in enumerate(texts) if j != i]
        )
        # 0..1 deterministic composite used only for this role-adapted version.
        structural = round(
            COMPLEXITY_WORD_WEIGHT
            * min(words / COMPLEXITY_WORD_NORMALIZER, 1.0)
            + COMPLEXITY_DEPTH_WEIGHT
            * min(depth / float(DEPENDENCY_DEPTH_MAX), 1.0)
            + COMPLEXITY_OVERLAP_WEIGHT * overlap,
            METRIC_ROUND_DIGITS,
        )
        task["word_count"] = words
        task["dependency_depth"] = depth
        task["semantic_overlap"] = overlap
        task["structural_complexity"] = structural
        structural_values.append(structural)

    mean_words = sum(task["word_count"] for task in tasks) / len(tasks)
    mean_depth = sum(task["dependency_depth"] for task in tasks) / len(tasks)
    scenario_overlap = sum(task["semantic_overlap"] for task in tasks) / len(tasks)
    complexity_index = COMPLEXITY_INDEX_SCALE * sum(structural_values) / len(structural_values)

    scenario["complexity"] = {
        "mean_target_words": round(mean_words, METRIC_ROUND_DIGITS),
        "mean_dependency_depth": round(mean_depth, METRIC_ROUND_DIGITS),
        "scenario_semantic_overlap": round(scenario_overlap, METRIC_ROUND_DIGITS),
        "instruction_complexity_index": round(complexity_index, METRIC_ROUND_DIGITS),
        "complexity_method_version": ROLE_GENERATION_VERSION,
    }


def _role_prompt_name(role: str) -> str:
    role = str(role or "").strip()
    if not role or role == OTHER_ROLE_VALUE:
        return GENERAL_ROLE_PROMPT
    return role


def _extract_generation_payload(raw_text: str) -> dict:
    """Parse a JSON object without depending on provider-side JSON validation.

    Groq's server-side json_object mode can reject a long otherwise-useful generation
    before the application ever receives it. We therefore request plain text and do
    strict validation locally.

    Accepted model output:
      * a bare JSON object;
      * a fenced ```json block;
      * a short preamble followed by a JSON object.
    """
    raw_text = str(raw_text or "").strip()
    if not raw_text:
        raise ValueError("Generator returned empty content.")

    # First try the common clean/fenced cases.
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        value = json.loads(cleaned)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    # Then scan for the first decodable JSON object in the response.
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", raw_text):
        candidate = raw_text[match.start():]
        try:
            value, _end = decoder.raw_decode(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value

    preview = re.sub(r"\s+", " ", raw_text)[:GENERATION_ERROR_PREVIEW_CHARS]
    raise ValueError(
        "Generator did not return a parseable JSON object. "
        f"Response preview: {preview!r}"
    )


def _validate_generated_role_content(payload: dict) -> tuple[str, str, list[dict], list[str]]:
    title = str(payload.get("scenario_title", "")).strip()
    context = str(payload.get("context_sentence", "")).strip()
    targets = payload.get("targets")
    details = payload.get("non_instruction_details")

    if not title:
        raise ValueError("Generated scenario title is blank.")
    if not context:
        raise ValueError("Generated context sentence is blank.")
    if not isinstance(targets, list) or len(targets) != TARGETS_PER_SCENARIO:
        raise ValueError(f"Generator must return exactly {TARGETS_PER_SCENARIO} targets.")
    if not isinstance(details, list) or len(details) != NON_INSTRUCTION_DETAILS_PER_SCENARIO:
        raise ValueError(f"Generator must return exactly {NON_INSTRUCTION_DETAILS_PER_SCENARIO} non-instruction details.")

    normalized_targets = []
    seen = set()
    for expected_index, target in enumerate(targets, start=1):
        if not isinstance(target, dict):
            raise ValueError("Each generated target must be an object.")
        actual_index = int(target.get("target_index", -1))
        text = re.sub(r"\s+", " ", str(target.get("text", "")).strip())
        trigger_anchor = re.sub(
            r"\s+", " ", str(target.get("trigger_anchor", "")).strip()
        )
        if actual_index != expected_index:
            raise ValueError(
                f"Generated target index {actual_index} does not match expected {expected_index}."
            )
        if not text:
            raise ValueError(f"Generated target {expected_index} is blank.")
        if text.lower() in seen:
            raise ValueError("Generated targets must be distinct.")
        if not trigger_anchor:
            trigger_anchor = f"target-{expected_index}"
        seen.add(text.lower())
        normalized_targets.append({
            "target_index": expected_index,
            "text": text,
            "trigger_anchor": trigger_anchor,
        })

    normalized_details = [
        re.sub(r"\s+", " ", str(item).strip()) for item in details
    ]
    if any(not item for item in normalized_details):
        raise ValueError("Non-instruction details cannot be blank.")

    return title, context, normalized_targets, normalized_details


def _build_batch_generation_request(templates: list[dict], role: str) -> list[dict]:
    """Build the controlled structure sent to the model for all five sets at once."""
    request_sets = []
    for position, template in enumerate(templates, start=1):
        template_tasks = template.get("tasks") or []
        if len(template_tasks) != TARGETS_PER_SCENARIO:
            raise RuntimeError(
                f"Role adaptation requires exactly {TARGETS_PER_SCENARIO} template tasks in Set {position}; "
                f"got {len(template_tasks)}."
            )

        request_sets.append({
            "set_index": position,
            "scenario_family_id": template.get("scenario_family_id", ""),
            "scenario_form": template.get("scenario_form", ""),
            "targets": [
                {
                    "target_index": i,
                    "serial_category": task.get("serial_category", ""),
                    "high_demand": bool(task.get("high_demand", False)),
                    "open_ended": bool(task.get("open_ended", False)),
                    "instruction_interference_present": bool(
                        task.get("instruction_interference_present", False)
                    ),
                    "desired_word_count": int(task.get("word_count") or DEFAULT_TARGET_WORD_COUNT),
                }
                for i, task in enumerate(template_tasks, start=1)
            ],
        })
    return request_sets


def _completion_text(response, purpose: str) -> str:
    """Extract final assistant content and give useful diagnostics if it is empty."""
    if not response or not getattr(response, "choices", None):
        raise ValueError(f"{purpose}: model returned no choices.")

    choice = response.choices[0]
    message = choice.message
    content = getattr(message, "content", None)

    if isinstance(content, str) and content.strip():
        return content.strip()

    # GPT-OSS may spend the completion budget on reasoning. Do not parse private
    # reasoning as research output; report enough metadata to diagnose the issue.
    reasoning = getattr(message, "reasoning", None)
    reasoning_chars = len(str(reasoning)) if reasoning else 0
    finish_reason = getattr(choice, "finish_reason", None)

    raise ValueError(
        f"{purpose}: generator returned empty final content "
        f"(finish_reason={finish_reason!r}, reasoning_chars={reasoning_chars})."
    )


def _groq_reasoning_extra_body() -> dict:
    """Parameters supported by Groq GPT-OSS models."""
    return {
        "reasoning_effort": MODEL_REASONING_EFFORT,
        "include_reasoning": False,
    }


def _retry_after_seconds(exc: Exception) -> float | None:
    """Extract Groq's 'try again in Xs' hint from a rate-limit exception."""
    match = re.search(
        r"try again in\s+([0-9]+(?:\.[0-9]+)?)s",
        str(exc),
        flags=re.IGNORECASE,
    )
    return float(match.group(1)) if match else None


def _chat_generation_request(
    prompt: str,
    *,
    temperature: float,
    max_tokens: int,
    purpose: str,
):
    """Issue one GPT-OSS generation call with one bounded automatic 429 wait."""
    last_error: Exception | None = None

    for attempt in range(2):
        try:
            response = require_model_client().chat.completions.create(
                model=MODEL_NAME,
                # Groq recommends keeping GPT-OSS instructions in the user message.
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body=_groq_reasoning_extra_body(),
            )
            return _completion_text(response, purpose)

        except Exception as exc:
            last_error = exc
            is_rate_limit = exc.__class__.__name__ == "RateLimitError"
            wait = _retry_after_seconds(exc) if is_rate_limit else None

            if (
                attempt == 0
                and wait is not None
                and wait <= RATE_LIMIT_AUTO_WAIT_MAX_SECONDS
            ):
                actual_wait = wait + 0.35
                print(
                    f"[ROLE GENERATION RATE LIMIT] purpose={purpose!r} "
                    f"waiting={actual_wait:.2f}s before one retry",
                    flush=True,
                )
                time.sleep(actual_wait)
                continue

            raise

    raise RuntimeError(
        f"{purpose}: generation failed: {type(last_error).__name__}: {last_error}"
    )


def _collect_valid_generated_scenarios(
    payload: dict,
    expected_sets: int,
) -> tuple[dict[int, dict], list[str]]:
    """Collect valid generated scenarios from several common JSON shapes.

    Preferred:
        {"scenarios": [{...}, {...}]}

    Also accepted:
        {"set_index": 1, ...}
        {"1": {...}, "2": {...}}
        {"scenario": {...}}
    """
    errors: list[str] = []

    scenarios = payload.get("scenarios")

    if not isinstance(scenarios, list):
        # Single scenario object.
        if "set_index" in payload and "targets" in payload:
            scenarios = [payload]

        # {"scenario": {...}}
        elif isinstance(payload.get("scenario"), dict):
            scenarios = [payload["scenario"]]

        # Numeric-key mapping: {"1": {...}, "2": {...}}
        else:
            numeric_items = []
            for key, value in payload.items():
                if str(key).isdigit() and isinstance(value, dict):
                    item = dict(value)
                    item.setdefault("set_index", int(key))
                    numeric_items.append(item)

            if numeric_items:
                scenarios = numeric_items
            else:
                return {}, [
                    "top-level JSON did not contain a usable scenario list/object"
                ]

    valid: dict[int, dict] = {}

    for item in scenarios:
        if not isinstance(item, dict):
            errors.append("non-object scenario item")
            continue

        try:
            set_index = int(item.get("set_index", -1))
        except (TypeError, ValueError):
            errors.append("scenario with invalid set_index")
            continue

        if not 1 <= set_index <= expected_sets:
            errors.append(f"out-of-range set_index={set_index}")
            continue

        if set_index in valid:
            errors.append(f"duplicate set_index={set_index}")
            continue

        try:
            _validate_generated_role_content(item)
        except Exception as exc:
            errors.append(
                f"set {set_index}: {type(exc).__name__}: {exc}"
            )
            continue

        valid[set_index] = item

    return valid, errors


def _missing_generation_prompt(
    role_name: str,
    request_sets: list[dict],
    missing_indices: list[int],
) -> str:
    """Build a compact repair prompt for only the missing role-specific sets."""
    missing_structures = [
        item for item in request_sets
        if int(item["set_index"]) in set(missing_indices)
    ]

    return f"""
Generate ONLY the missing prospective-memory scenarios for role/context:
{role_name}

Required set_index values: {missing_indices}

For every requested set:
- exactly {TARGETS_PER_SCENARIO} actionable target instructions;
- exactly {NON_INSTRUCTION_DETAILS_PER_SCENARIO} declarative non-instruction details;
- preserve the supplied target flags and serial categories;
- keep each target near its desired word count +/- {TARGET_WORD_TOLERANCE};
- make the content realistic for the role;
- do not mention memory, recall, experiments, distractors, or serial position;
- no names, emails, phone numbers, addresses, diagnoses, or identifiers.

CONTROLLED SET STRUCTURE:
{json.dumps(missing_structures, ensure_ascii=False)}

Return ONLY:
{{"scenarios":[ ... ]}}

Each returned item must include its requested set_index and follow this shape:
{_generation_output_example(include_set_index=True)}
""".strip()


def _compose_generated_scenario_text(
    context: str,
    generated_targets: list[dict],
    details: list[str],
) -> str:
    """Compose the participant-facing stimulus from configured sequence tokens."""
    pieces: list[str] = []

    for item in STIMULUS_SEQUENCE:
        if item == "context":
            pieces.append(str(context).strip())
            continue

        try:
            kind, raw_index = item.split(":", 1)
            index = int(raw_index)
        except (ValueError, TypeError) as exc:
            raise RuntimeError(
                f"Invalid STIMULUS_SEQUENCE entry: {item!r}"
            ) from exc

        if kind == "target":
            if not 0 <= index < len(generated_targets):
                raise RuntimeError(
                    f"STIMULUS_SEQUENCE target index {index} is out of range "
                    f"for {len(generated_targets)} generated targets."
                )
            pieces.append(str(generated_targets[index]["text"]).strip())

        elif kind == "detail":
            if not 0 <= index < len(details):
                raise RuntimeError(
                    f"STIMULUS_SEQUENCE detail index {index} is out of range "
                    f"for {len(details)} generated details."
                )
            pieces.append(str(details[index]).strip())

        else:
            raise RuntimeError(
                f"Unknown STIMULUS_SEQUENCE item kind: {kind!r}"
            )

    return " ".join(piece for piece in pieces if piece)


def _apply_generated_role_content(
    template: dict,
    generated_payload: dict,
    role: str,
    session_number: int,
    set_index: int,
) -> dict:
    """Apply validated generated wording to a controlled template."""
    title, context, generated_targets, details = _validate_generated_role_content(
        generated_payload
    )

    scenario = copy.deepcopy(template)
    scenario["title"] = title
    scenario["scenario_text"] = _compose_generated_scenario_text(
        context, generated_targets, details
    )
    scenario["non_instruction_distractor_count"] = NON_INSTRUCTION_DETAILS_PER_SCENARIO
    scenario["role_generation_version"] = ROLE_GENERATION_VERSION
    scenario["role_context"] = role

    role_name = _role_prompt_name(role)
    role_slug = re.sub(r"[^A-Za-z0-9]+", "_", role_name).strip("_")[:ROLE_SLUG_MAX_LENGTH] or ROLE_SLUG_FALLBACK
    base_scenario_id = str(template.get("scenario_id", f"SET{set_index}"))
    scenario["scenario_id"] = (
        f"{base_scenario_id}__ROLEGEN_{role_slug}_S{session_number:02d}_SET{set_index}"
    )

    for generated, task in zip(generated_targets, scenario["tasks"]):
        base_target_id = str(
            task.get("target_id", f"T{generated['target_index']}")
        )
        task["target_id"] = (
            f"{base_target_id}__ROLEGEN_{role_slug}_S{session_number:02d}_SET{set_index}"
        )
        task["text"] = generated["text"]
        task["trigger_anchor"] = generated["trigger_anchor"]

    _recompute_role_adapted_complexity(scenario)
    return scenario



def _generation_output_example(include_set_index: bool = True) -> str:
    example = {
        "scenario_title": "short role-appropriate title",
        "context_sentence": "one concise setup sentence",
        "targets": [
            {
                "target_index": i,
                "text": "...",
                "trigger_anchor": "...",
            }
            for i in range(1, TARGETS_PER_SCENARIO + 1)
        ],
        "non_instruction_details": [
            "declarative detail"
            for _ in range(NON_INSTRUCTION_DETAILS_PER_SCENARIO)
        ],
    }
    if include_set_index:
        example = {"set_index": 1, **example}
    return json.dumps(example, ensure_ascii=False, indent=2)

def prepare_role_aware_session(
    user: str,
    role: str,
    session_number: int,
) -> tuple[str, list[dict]]:
    """Generate role-specific stimuli in small chunks and repair only missing sets.

    This avoids the previous failure mode where one 5-scenario request consumed
    most of the 8k TPM budget and a second full retry immediately hit a 429.
    """
    form_id, templates = prepare_session_scenarios(  user=user, session_number=session_number,)
    if len(templates) != TOTAL_SETS:
        raise RuntimeError(
            f"Protocol error: expected {TOTAL_SETS} counterbalanced templates, "
            f"got {len(templates)}."
        )

    role_name = _role_prompt_name(role)
    request_sets = _build_batch_generation_request(templates, role)
    generated_by_index: dict[int, dict] = {}
    last_error: Exception | None = None

    all_indices = list(range(1, TOTAL_SETS + 1))
    chunks = [
        all_indices[i:i + ROLE_GENERATION_CHUNK_SIZE]
        for i in range(0, len(all_indices), ROLE_GENERATION_CHUNK_SIZE)
    ]

    for chunk_number, chunk_indices in enumerate(chunks, start=1):
        chunk_structures = [
            item for item in request_sets
            if int(item["set_index"]) in set(chunk_indices)
        ]

        prompt = f"""
Create prospective-memory assessment scenarios for role/context: {role_name}.

Generate ONLY these set_index values: {chunk_indices}.

For every requested set:
- exactly {TARGETS_PER_SCENARIO} actionable target instructions;
- exactly {NON_INSTRUCTION_DETAILS_PER_SCENARIO} declarative non-instruction details;
- preserve the supplied serial_category, high_demand, open_ended, and
  instruction_interference_present properties;
- keep each target near its desired word count +/- {TARGET_WORD_TOLERANCE};
- make the setting and actions realistic for the selected role;
- make scenarios in this response clearly different from one another;
- do not copy canned scenario-bank wording;
- do not include names, emails, phone numbers, addresses, diagnoses, or identifiers;
- do not mention memory, recall, experiments, distractors, difficulty, or serial position;
- trigger_anchor must be a short situational cue.

CONTROLLED STRUCTURE:
{json.dumps(chunk_structures, ensure_ascii=False)}

Return ONLY one JSON object:
{{"scenarios":[ ... ]}}

Each item must include its requested set_index and use this shape:
{_generation_output_example(include_set_index=True)}
""".strip()

        max_tokens = min(
            ROLE_GENERATION_MAX_TOKENS,
            ROLE_GENERATION_TOKEN_OVERHEAD
            + ROLE_GENERATION_TOKENS_PER_SET * len(chunk_indices),
        )

        try:
            raw = _chat_generation_request(
                prompt,
                temperature=ROLE_GENERATION_TEMPERATURE,
                max_tokens=max_tokens,
                purpose=f"role generation chunk {chunk_number} {chunk_indices}",
            )
            payload = _extract_generation_payload(raw)
            valid, errors = _collect_valid_generated_scenarios(
                payload,
                TOTAL_SETS,
            )

            for set_index, item in valid.items():
                if set_index in chunk_indices:
                    generated_by_index[set_index] = item

            print(
                "[ROLE GENERATION CHUNK] "
                f"chunk={chunk_number}/{len(chunks)} "
                f"requested={chunk_indices} "
                f"accepted={sorted(i for i in valid if i in chunk_indices)} "
                f"errors={errors}",
                flush=True,
            )

        except Exception as exc:
            last_error = exc
            print(
                "[ROLE GENERATION CHUNK ERROR] "
                f"chunk={chunk_number}/{len(chunks)} requested={chunk_indices} "
                f"error={type(exc).__name__}: {exc}",
                flush=True,
            )

    # Repair only missing or invalid sets, one at a time. A small request is much
    # less likely to exceed TPM and avoids throwing away previously valid output.
    missing = [
        i for i in all_indices
        if i not in generated_by_index
    ]

    for set_index in list(missing):
        structure = next(
            item for item in request_sets
            if int(item["set_index"]) == set_index
        )

        repair_prompt = f"""
Generate ONE prospective-memory scenario for role/context: {role_name}.

Required set_index: {set_index}

Requirements:
- exactly {TARGETS_PER_SCENARIO} actionable target instructions;
- exactly {NON_INSTRUCTION_DETAILS_PER_SCENARIO} declarative non-instruction details;
- preserve every supplied experimental property;
- each target near desired word count +/- {TARGET_WORD_TOLERANCE};
- realistic for the selected role;
- no names, contact details, addresses, diagnoses, or identifiers;
- do not mention memory, recall, experiment design, distractors, difficulty, or serial position.

CONTROLLED STRUCTURE:
{json.dumps(structure, ensure_ascii=False)}

Return ONLY:
{{"scenarios":[{_generation_output_example(include_set_index=True)}]}}
""".strip()

        success = False
        for repair_attempt in range(1, ROLE_GENERATION_RETRIES + 1):
            try:
                raw = _chat_generation_request(
                    repair_prompt,
                    temperature=ROLE_REPAIR_TEMPERATURE,
                    max_tokens=ROLE_REPAIR_MAX_TOKENS,
                    purpose=f"repair set {set_index}",
                )
                payload = _extract_generation_payload(raw)
                valid, errors = _collect_valid_generated_scenarios(
                    payload,
                    TOTAL_SETS,
                )
                item = valid.get(set_index)
                if item is None:
                    raise ValueError(
                        f"Repair response did not contain valid set {set_index}; "
                        f"errors={errors}"
                    )

                generated_by_index[set_index] = item
                success = True
                print(
                    "[ROLE GENERATION REPAIR] "
                    f"set={set_index} attempt={repair_attempt}/"
                    f"{ROLE_GENERATION_RETRIES} success",
                    flush=True,
                )
                break

            except Exception as exc:
                last_error = exc
                print(
                    "[ROLE GENERATION REPAIR ERROR] "
                    f"set={set_index} attempt={repair_attempt}/"
                    f"{ROLE_GENERATION_RETRIES} "
                    f"error={type(exc).__name__}: {exc}",
                    flush=True,
                )

                # _chat_generation_request already performs one short provider-
                # requested 429 wait. Do not compound a persistent rate limit.
                if exc.__class__.__name__ == "RateLimitError":
                    break

        if not success:
            continue

    missing = [
        i for i in all_indices
        if i not in generated_by_index
    ]
    if missing:
        detail = (
            f"{type(last_error).__name__}: {last_error}"
            if last_error is not None
            else "model returned incomplete/invalid scenario data"
        )
        raise RuntimeError(
            f"Could not generate all role-specific scenarios for {role}. "
            f"Missing set indices: {missing}; valid sets: "
            f"{sorted(generated_by_index)}. Last error: {detail}. "
            "No canned fallback was used."
        )

    scenarios = [
        _apply_generated_role_content(
            template=template,
            generated_payload=generated_by_index[position],
            role=role,
            session_number=session_number,
            set_index=position,
        )
        for position, template in enumerate(templates, start=1)
    ]

    normalized_texts = [
        re.sub(r"\s+", " ", s["scenario_text"].lower()).strip()
        for s in scenarios
    ]
    if len(set(normalized_texts)) != len(normalized_texts):
        raise RuntimeError(
            "Generated scenarios were not unique across the session."
        )

    return form_id, scenarios


def make_state(subject_id: str, role: str, consent_timestamp: datetime, registry_session_token: str) -> dict:
    user = normalize_participant_id(subject_id)
    session_number = next_session_number(user)
    form_id, scenarios = prepare_role_aware_session(
        user=user, role=role, session_number=session_number
    )
    # Full stimulus preflight happens before session state is returned.
    cache_and_validate_stimuli(scenarios, user, role, session_number)
    now = utc_now()
    return {
        "session_id": registry_session_token,
        "session_number": session_number,
        "session_start": now,
        "consent_confirmed": True,
        "consent_timestamp": consent_timestamp,
        "consent_text_version": CONSENT_TEXT_VERSION,
        "participant_id_verified": True,
        "participant_registry_version": PARTICIPANT_REGISTRY_VERSION,
        "registry_session_token": registry_session_token,
        "session_form": form_id,
        "user": user,
        "role": role,
        "set_idx": 0,
        "scenarios": scenarios,
        "scenario": scenarios[0],
        "phase": "reading",
        "phase_remaining": READING_TIME_SECONDS,
        "phase_deadline_epoch": time.time() + READING_TIME_SECONDS,
        "reading_start": now,
        "reading_end": None,
        "distractor_start": None,
        "distractor_end": None,
        "distractor_response_time_sec": None,
        "recall_start": None,
        "recall_end": None,
        "results": [],
        "reading_skipped": False,
        "is_processing": False,
        "submitted_distractor_answer": None,
        "distractor_answer_updates": [],
        "completed_set_indices": [],
        "stimuli_preflight_ok": True,
    }


DISPLAY_COLUMNS = list(CONFIG_DISPLAY_COLUMNS)


def empty_display_df() -> pd.DataFrame:
    return pd.DataFrame(columns=DISPLAY_COLUMNS)


def current_df_rows(state: dict) -> pd.DataFrame:
    """Participant-facing summary: exactly one row per completed set (maximum five)."""
    if not state or not state.get("results"):
        return empty_display_df()

    rows = []
    for set_index in range(1, TOTAL_SETS + 1):
        targets = [
            r for r in state["results"]
            if r.get("Record_Type") == "Target" and int(r.get("Set_Index", 0) or 0) == set_index
        ]
        if not targets:
            continue
        intrusions = [
            r for r in state["results"]
            if r.get("Record_Type") == "Intrusion" and int(r.get("Set_Index", 0) or 0) == set_index
        ]
        first = targets[0]
        remembered = sum(r.get("Remembered") == "Y" for r in targets)
        in_order = sum(
            r.get("Remembered") == "Y" and r.get("Out_of_Order") == "N"
            for r in targets
        )
        condition = first.get("Distractor_Condition", "")
        if condition == QUIET_DISTRACTOR_CONDITION:
            distraction_perf = "Quiet baseline"
        else:
            answered = int(float(first.get("Distractor_Items_Answered") or 0))
            correct = int(float(first.get("Distractor_Items_Correct") or 0))
            presented = int(float(first.get("Distractor_Items_Presented") or 0))
            distraction_perf = f"{correct}/{answered} correct" if answered else f"0/{presented} answered"

        rows.append({
            "Set": set_index,
            "Scenario": first.get("Scenario_Title", ""),
            "Distractor": condition,
            "Complexity": round(float(first.get("Instruction_Complexity_Index") or 0), 2),
            "Recall": f"{remembered}/{len(targets)} ({100.0 * remembered / len(targets):.0f}%)",
            "In order": f"{in_order}/{len(targets)}",
            "Intrusions": len(intrusions),
            "Distractor result": distraction_perf,
        })

    return pd.DataFrame(rows, columns=DISPLAY_COLUMNS)


def session_set_title(state: dict) -> str:
    s = current_scenario(state)
    return (
        f"### Set {s['set_index']} of {TOTAL_SETS}  •  {s['title']}\n"
        f"Equivalent form: **{s['scenario_form']}**"
    )


def register_new_participant(role, consent_confirmed):
    """Allocate credentials automatically for a first-time participant.

    The participant pauses on a credential screen so the ID/access code can be
    saved before any memory material is displayed.
    """
    if not consent_confirmed:
        return (
            None,
            gr.update(visible=False),
            "",
            "",
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(interactive=True),
            "Consent confirmation is required before registration.",
        )

    participant_id = None
    access_code = None
    registry_session_token = None

    try:
        # Avoid a redundant model probe; the batched generation call itself
        # verifies the backend.
        require_model_client()
        participant_id, access_code = create_auto_participant()
        registry_session_token = f"{participant_id}_{uuid.uuid4().hex}"

        # Acquire the same active-session lock used for returning participants.
        canonical_id = authenticate_and_acquire_session(
            participant_id, access_code, registry_session_token
        )

        consent_timestamp = utc_now()
        state = make_state(
            canonical_id, role, consent_timestamp, registry_session_token
        )

        # Do not start the experimental clock until the participant explicitly
        # confirms that the generated credentials have been saved.
        state["phase"] = "registration"
        state["reading_start"] = None
        state["phase_deadline_epoch"] = None
        state["phase_remaining"] = READING_TIME_SECONDS

        return (
            state,
            gr.update(visible=True),
            participant_id,
            access_code,
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
            "",
        )

    except Exception as exc:
        # If registration succeeded but something later failed, do not leave an
        # active-session lock behind.
        if participant_id and registry_session_token:
            try:
                release_session(participant_id, registry_session_token)
            except Exception:
                pass

        return (
            None,
            gr.update(visible=False),
            "",
            "",
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(interactive=True),
            f"Could not register a new participant: {exc}",
        )


def begin_new_participant_assessment(state):
    """Start the experimental clock after credentials have been saved."""
    if not state or state.get("phase") != "registration":
        return (
            state,
            gr.update(visible=True),
            gr.update(visible=False),
            "",
            None,
            "",
            "Registration state is unavailable. Please restart the application.",
        )

    now = utc_now()
    state["phase"] = "reading"
    state["reading_start"] = now
    state["phase_remaining"] = READING_TIME_SECONDS
    state["phase_deadline_epoch"] = time.time() + READING_TIME_SECONDS

    scenario = current_scenario(state)
    canvas = scenario_stimulus_html(state)

    return (
        state,
        gr.update(visible=False),
        gr.update(visible=True),
        session_set_title(state),
        canvas,
        f"Reading time: **{READING_TIME_SECONDS}s**",
        "",
    )


def toggle_participant_mode(mode):
    returning = mode == "Returning participant"
    return (
        gr.update(visible=not returning),
        gr.update(visible=returning),
    )


def start_returning_experiment(subject_id, access_code, role, consent_confirmed):
    if not subject_id or not subject_id.strip():
        return (
            None,
            gr.update(visible=True), gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False), gr.update(visible=False),
            "Enter the pseudonymous Participant ID assigned by the researcher.",
            "", None, "", "", "", "", gr.update(value=""),
            "", "", gr.update(value=""), "", empty_display_df(), None,
        )

    if not access_code or not access_code.strip():
        return (
            None,
            gr.update(visible=True), gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False), gr.update(visible=False),
            "Enter the private access code supplied with this Participant ID.",
            "", None, "", "", "", "", gr.update(value=""),
            "", "", gr.update(value=""), "", empty_display_df(), None,
        )

    if not consent_confirmed:
        return (
            None,
            gr.update(visible=True), gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False), gr.update(visible=False),
            "Consent confirmation is required before the assessment can begin.",
            "", None, "", "", "", "", gr.update(value=""),
            "", "", gr.update(value=""), "", empty_display_df(), None,
        )

    registry_session_token = f"{normalize_participant_id(subject_id)}_{uuid.uuid4().hex}"
    try:
        # Verify generation before taking an active-session lock.
        require_model_client()
        canonical_id = authenticate_and_acquire_session(
            subject_id, access_code, registry_session_token
        )
    except (
        InvalidCredentialsError,
        ParticipantInactiveError,
        ParticipantLockedError,
        ActiveSessionError,
        ValueError,
    ) as exc:
        return (
            None,
            gr.update(visible=True), gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False), gr.update(visible=False),
            str(exc),
            "", None, "", "", "", "", gr.update(value=""),
            "", "", gr.update(value=""), "", empty_display_df(), None,
        )

    consent_timestamp = utc_now()
    try:
        state = make_state(
            canonical_id, role, consent_timestamp, registry_session_token
        )
    except Exception:
        release_session(canonical_id, registry_session_token)
        raise

    s = current_scenario(state)
    canvas = scenario_stimulus_html(state)
    return (
        state,
        gr.update(visible=False), gr.update(visible=True), gr.update(visible=False),
        gr.update(visible=False), gr.update(visible=False),
        "",
        session_set_title(state), canvas, f"Reading time: **{READING_TIME_SECONDS}s**",
        "", "", "", gr.update(value=""),
        "", "", gr.update(value=""), "", empty_display_df(), None,
    )


def transition_to_distractor(state: dict) -> dict:
    now = utc_now()
    state["reading_end"] = now
    state["phase"] = "distractor"
    state["phase_remaining"] = DISTRACTOR_TIME_SECONDS
    state["phase_deadline_epoch"] = time.time() + DISTRACTOR_TIME_SECONDS
    state["distractor_start"] = now
    state["distractor_response_time_sec"] = None
    state["submitted_distractor_answer"] = None
    state["distractor_answer_updates"] = []
    return state


def transition_to_recall(state: dict) -> dict:
    now = utc_now()
    state["distractor_end"] = now
    state["phase"] = "recall"
    state["phase_remaining"] = RECALL_TIME_SECONDS
    state["phase_deadline_epoch"] = time.time() + RECALL_TIME_SECONDS
    state["recall_start"] = now
    return state


def normalize_answer(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().lower())


def split_distractor_answers(value: str) -> list[str]:
    value = str(value or "").strip()
    if not value:
        return []
    parts = re.split(r"[,;\n]+", value)
    return [normalize_answer(x) for x in parts if str(x).strip()]


def score_distractor_response(distractor: dict, answer: str, response_updates: list[dict]) -> dict:
    expected = [normalize_answer(x) for x in distractor.get("answers", [])]
    actual = split_distractor_answers(answer)
    presented = len(expected)
    answered = min(len(actual), presented)
    correct = sum(
        i < len(actual) and actual[i] == expected[i]
        for i in range(presented)
    )
    accuracy = round(100.0 * correct / presented, 1) if presented else None
    response_times = [float(x.get("time_sec", 0)) for x in response_updates if x.get("time_sec") not in (None, "")]
    mean_rt = round(sum(response_times) / len(response_times), METRIC_ROUND_DIGITS) if response_times else None
    return {
        "presented": presented,
        "answered": answered,
        "correct": correct,
        "accuracy_pct": accuracy,
        "mean_response_time_sec": mean_rt,
        "responses_json": json.dumps(response_updates, ensure_ascii=False),
    }


def append_set_results(state: dict, recalled_text: str, distractor_answer: str) -> bool:
    """Finalize the current set exactly once.

    The set position and scenario are resolved from one authoritative source.
    Results are accumulated locally and committed only after scoring succeeds,
    preventing a failed callback from partially marking a set complete.
    """
    set_idx = int(state["set_idx"])
    scenario = current_scenario(state)
    scenario_set_index = set_idx + 1

    completed = state.setdefault("completed_set_indices", [])
    if scenario_set_index in completed:
        return False

    now = utc_now()
    state["recall_end"] = now
    recall_lines = [line.strip() for line in (recalled_text or "").splitlines() if line.strip()]
    scored, intrusions = score_recall(scenario["tasks"], recall_lines)
    scored_by_id = {x["target_id"]: x for x in scored}

    reading_time = seconds_between(state["reading_start"], state["reading_end"])
    distractor_time = seconds_between(state["distractor_start"], state["distractor_end"])
    recall_time = seconds_between(state["recall_start"], state["recall_end"])

    saved = state.get("submitted_distractor_answer")
    distractor_answer = str(distractor_answer or "").strip()
    # Prefer whatever is currently in the textbox. Use the last explicit Save
    # only as a fallback if the UI value is unavailable/cleared.
    if not distractor_answer and saved is not None:
        distractor_answer = str(saved).strip()

    distractor = scenario["distractor"]
    requires_answer = bool(distractor.get("requires_answer", True))
    if not requires_answer:
        distractor_answer = ""
    distractor_metrics = score_distractor_response(
        distractor,
        distractor_answer,
        state.get("distractor_answer_updates", []),
    )
    submitted = bool(distractor_answer) if requires_answer else False
    distractor_correct = (
        "Y" if requires_answer
        and distractor_metrics["presented"] > 0
        and distractor_metrics["correct"] == distractor_metrics["presented"]
        else ("N" if requires_answer and submitted else "")
    )
    if distractor_metrics["mean_response_time_sec"] is None and distractor_answer and requires_answer:
        distractor_metrics["mean_response_time_sec"] = distractor_time
    state["distractor_response_time_sec"] = distractor_metrics["mean_response_time_sec"]

    total = len(scenario["tasks"])
    cm = scenario["complexity"]
    new_rows: list[dict] = []

    for task in scenario["tasks"]:
        scored_item = scored_by_id[task["target_id"]]
        risk_score, risk_level, requires, _ = UniversalReminderRuleEngine.calculate(
            serial_category=task["serial_category"],
            instruction_interference_present=task["instruction_interference_present"],
            open_ended=task["open_ended"],
            high_demand=task["high_demand"],
        )
        row = {
            "Session_ID": state["session_id"],
            "Session_Number": state["session_number"],
            "Session_Start_UTC": iso(state["session_start"]),
            "Consent_Confirmed": "Y" if state.get("consent_confirmed") else "N",
            "Consent_Timestamp_UTC": iso(state.get("consent_timestamp")),
            "Consent_Text_Version": state.get("consent_text_version", CONSENT_TEXT_VERSION),
            "Participant_ID_Verified": "Y" if state.get("participant_id_verified") else "N",
            "Participant_Registry_Version": state.get(
                "participant_registry_version", PARTICIPANT_REGISTRY_VERSION
            ),
            "User": state["user"],
            "Role": state["role"],
            "Set_Index": scenario_set_index,
            "Scenario_Order_Position": scenario["scenario_order_position"],
            "Scenario_Family_ID": scenario["scenario_family_id"],
            "Scenario_Form": scenario["scenario_form"],
            "Scenario_ID": scenario["scenario_id"],
            "Scenario_Title": scenario["title"],
            "Record_Type": "Target",
            "Target_ID": task["target_id"],
            "Target_Family_ID": task["target_family_id"],
            "Target_Index": task["target_index"],
            "Target_Count": total,
            "Target_Instruction": task["text"],
            "User_Recall_Text": scored_item["user_recall_text"],
            "Remembered": "Y" if scored_item["remembered"] else "N",
            "Out_of_Order": "Y" if scored_item["out_of_order"] else "N",
            "Match_Type": scored_item["match_type"],
            "Match_Score": scored_item["match_score"],
            "Serial_Category": task["serial_category"],
            "High_Demand": "Y" if task["high_demand"] else "N",
            "Open_Ended": "Y" if task["open_ended"] else "N",
            "Instruction_Interference_Present": "Y" if task["instruction_interference_present"] else "N",
            "Trigger_Anchor": task["trigger_anchor"],
            "Target_Word_Count": task["word_count"],
            "Target_Dependency_Depth": task["dependency_depth"],
            "Target_Semantic_Overlap": task["semantic_overlap"],
            "Target_Structural_Complexity": task["structural_complexity"],
            "Scenario_Mean_Target_Words": cm["mean_target_words"],
            "Scenario_Mean_Dependency_Depth": cm["mean_dependency_depth"],
            "Scenario_Semantic_Overlap": cm["scenario_semantic_overlap"],
            "Instruction_Complexity_Index": cm["instruction_complexity_index"],
            "Complexity_Method_Version": cm["complexity_method_version"],
            "Scenario_Total_Word_Count": len(re.findall(r"[A-Za-z0-9]+", scenario["scenario_text"])),
            "Embedded_Distractor_Count": scenario["non_instruction_distractor_count"],
            "Reading_Start_UTC": iso(state["reading_start"]),
            "Reading_End_UTC": iso(state["reading_end"]),
            "Reading_Time_Sec": reading_time,
            "Reading_Skipped": "Y" if state["reading_skipped"] else "N",
            "Distractor_Condition": scenario["distractor_condition"],
            "Distractor_ID": distractor["distractor_id"],
            "Distractor_Difficulty_Score": distractor["difficulty_score"],
            "Distractor_Task": distractor["task"],
            "Distractor_Expected_Answer": distractor["answer"],
            "Distractor_Answer": distractor_answer,
            "Distractor_Submitted": "Y" if submitted else "N",
            "Distractor_Correct": distractor_correct,
            "Distractor_Response_Time_Sec": (
                "" if state.get("distractor_response_time_sec") is None
                else round(float(state["distractor_response_time_sec"]), METRIC_ROUND_DIGITS)
            ),
            "Distractor_Items_Presented": distractor_metrics["presented"],
            "Distractor_Items_Answered": distractor_metrics["answered"],
            "Distractor_Items_Correct": distractor_metrics["correct"],
            "Distractor_Accuracy_Pct": ("" if distractor_metrics["accuracy_pct"] is None else distractor_metrics["accuracy_pct"]),
            "Distractor_Mean_Response_Time_Sec": ("" if distractor_metrics["mean_response_time_sec"] is None else distractor_metrics["mean_response_time_sec"]),
            "Distractor_Responses_JSON": distractor_metrics["responses_json"],
            "Distractor_Start_UTC": iso(state["distractor_start"]),
            "Distractor_End_UTC": iso(state["distractor_end"]),
            "Distractor_Time_Sec": distractor_time,
            "Recall_Start_UTC": iso(state["recall_start"]),
            "Recall_End_UTC": iso(state["recall_end"]),
            "Recall_Time_Sec": recall_time,
            "Risk_Score": risk_score,
            "Risk_Level": risk_level,
            "Requires_Reminder": "Y" if requires else "N",
            "App_Version": APP_VERSION,
            "Schema_Version": SCHEMA_VERSION,
            "Evaluator_Model": MODEL_NAME,
            "Rule_Engine_Version": RULE_ENGINE_VERSION,
        }
        new_rows.append(row)

    # Unmatched recall lines only. Matched lines cannot also appear as intrusions.
    for intrusion in intrusions:
        row = {col: "" for col in CANONICAL_COLUMNS}
        row.update({
            "Session_ID": state["session_id"],
            "Session_Number": state["session_number"],
            "Session_Start_UTC": iso(state["session_start"]),
            "Consent_Confirmed": "Y" if state.get("consent_confirmed") else "N",
            "Consent_Timestamp_UTC": iso(state.get("consent_timestamp")),
            "Consent_Text_Version": state.get("consent_text_version", CONSENT_TEXT_VERSION),
            "Participant_ID_Verified": "Y" if state.get("participant_id_verified") else "N",
            "Participant_Registry_Version": state.get(
                "participant_registry_version", PARTICIPANT_REGISTRY_VERSION
            ),
            "User": state["user"],
            "Role": state["role"],
            "Set_Index": scenario_set_index,
            "Scenario_Order_Position": scenario["scenario_order_position"],
            "Scenario_Family_ID": scenario["scenario_family_id"],
            "Scenario_Form": scenario["scenario_form"],
            "Scenario_ID": scenario["scenario_id"],
            "Scenario_Title": scenario["title"],
            "Record_Type": "Intrusion",
            "User_Recall_Text": intrusion,
            "Remembered": "N",
            "Out_of_Order": "N",
            "Match_Type": "Intrusion",
            "Scenario_Mean_Target_Words": cm["mean_target_words"],
            "Scenario_Mean_Dependency_Depth": cm["mean_dependency_depth"],
            "Scenario_Semantic_Overlap": cm["scenario_semantic_overlap"],
            "Instruction_Complexity_Index": cm["instruction_complexity_index"],
            "Complexity_Method_Version": cm["complexity_method_version"],
            "Scenario_Total_Word_Count": len(re.findall(r"[A-Za-z0-9]+", scenario["scenario_text"])),
            "Embedded_Distractor_Count": scenario["non_instruction_distractor_count"],
            "Reading_Start_UTC": iso(state["reading_start"]),
            "Reading_End_UTC": iso(state["reading_end"]),
            "Reading_Time_Sec": reading_time,
            "Reading_Skipped": "Y" if state["reading_skipped"] else "N",
            "Distractor_Condition": scenario["distractor_condition"],
            "Distractor_ID": distractor["distractor_id"],
            "Distractor_Difficulty_Score": distractor["difficulty_score"],
            "Distractor_Task": distractor["task"],
            "Distractor_Expected_Answer": distractor["answer"],
            "Distractor_Answer": distractor_answer,
            "Distractor_Submitted": "Y" if submitted else "N",
            "Distractor_Correct": distractor_correct,
            "Distractor_Response_Time_Sec": (
                "" if state.get("distractor_response_time_sec") is None
                else round(float(state["distractor_response_time_sec"]), METRIC_ROUND_DIGITS)
            ),
            "Distractor_Items_Presented": distractor_metrics["presented"],
            "Distractor_Items_Answered": distractor_metrics["answered"],
            "Distractor_Items_Correct": distractor_metrics["correct"],
            "Distractor_Accuracy_Pct": ("" if distractor_metrics["accuracy_pct"] is None else distractor_metrics["accuracy_pct"]),
            "Distractor_Mean_Response_Time_Sec": ("" if distractor_metrics["mean_response_time_sec"] is None else distractor_metrics["mean_response_time_sec"]),
            "Distractor_Responses_JSON": distractor_metrics["responses_json"],
            "Distractor_Start_UTC": iso(state["distractor_start"]),
            "Distractor_End_UTC": iso(state["distractor_end"]),
            "Distractor_Time_Sec": distractor_time,
            "Recall_Start_UTC": iso(state["recall_start"]),
            "Recall_End_UTC": iso(state["recall_end"]),
            "Recall_Time_Sec": recall_time,
            "App_Version": APP_VERSION,
            "Schema_Version": SCHEMA_VERSION,
            "Evaluator_Model": MODEL_NAME,
            "Rule_Engine_Version": RULE_ENGINE_VERSION,
        })
        new_rows.append(row)

    # Commit only after the complete set has been scored successfully.
    state["results"].extend(new_rows)
    completed.append(scenario_set_index)
    return True


def save_results(state: dict) -> Path:
    # Hard research invariant: one completed session contains exactly Sets 1..TOTAL_SETS.
    target_rows = [r for r in state.get("results", []) if r.get("Record_Type") == "Target"]
    set_indices = sorted({int(r["Set_Index"]) for r in target_rows})
    expected_sets = list(range(1, TOTAL_SETS + 1))
    if set_indices != expected_sets:
        raise RuntimeError(
            f"Refusing to save an incomplete/invalid session: set indices {set_indices}; expected {expected_sets}."
        )
    if sorted(state.get("completed_set_indices", [])) != expected_sets:
        raise RuntimeError(
            f"Refusing to save because completed set indices "
            f"{sorted(state.get('completed_set_indices', []))} do not match "
            f"expected {expected_sets}."
        )

    timestamp = utc_now().strftime(OUTPUT_TIMESTAMP_FORMAT)
    stem = f"{OUTPUT_FILE_PREFIX}_{state['user']}_S{state['session_number']:02d}_{timestamp}"

    # Participant IDs themselves are never silently changed: that would break
    # longitudinal linkage. If a filename somehow collides, add a random file suffix.
    path = OUTPUT_DIR / f"{stem}{OUTPUT_FILE_EXTENSION}"
    while True:
        try:
            with path.open("x", newline="", encoding=OUTPUT_ENCODING) as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=CANONICAL_COLUMNS,
                    extrasaction="ignore",
                    delimiter=OUTPUT_DELIMITER,
                )
                writer.writeheader()
                for row in state["results"]:
                    writer.writerow({col: row.get(col, "") for col in CANONICAL_COLUMNS})
            break
        except FileExistsError:
            path = OUTPUT_DIR / f"{stem}_{secrets.token_hex(OUTPUT_COLLISION_SUFFIX_BYTES).upper()}{OUTPUT_FILE_EXTENSION}"

    release_session(
        state["user"],
        state.get("registry_session_token", state["session_id"]),
    )
    return path


def final_summary(state: dict) -> str:
    targets = [r for r in state["results"] if r.get("Record_Type") == "Target"]
    intrusions = [r for r in state["results"] if r.get("Record_Type") == "Intrusion"]
    remembered = sum(r.get("Remembered") == "Y" for r in targets)
    in_order = sum(r.get("Remembered") == "Y" and r.get("Out_of_Order") == "N" for r in targets)
    total = len(targets)
    completed_sets = len({int(r["Set_Index"]) for r in targets})
    recall_pct = (100 * remembered / total) if total else 0

    return f"""
<div class="pilot-hero">
  <h2 style="margin-bottom:4px">Session complete</h2>
  <div style="opacity:.75">Participant <strong>{state['user']}</strong> • Session {state['session_number']} • {completed_sets}/{TOTAL_SETS} sets complete</div>
</div>
<div class="metric-grid">
  <div class="metric-card"><div class="metric-label">Target recall</div><div class="metric-value">{remembered}/{total}</div><div>{recall_pct:.1f}%</div></div>
  <div class="metric-card"><div class="metric-label">Recalled in order</div><div class="metric-value">{in_order}/{total}</div></div>
  <div class="metric-card"><div class="metric-label">Possible intrusions</div><div class="metric-value">{len(intrusions)}</div></div>
  <div class="metric-card"><div class="metric-label">Completed sets</div><div class="metric-value">{completed_sets}/{TOTAL_SETS}</div></div>
</div>
<div class="result-note">The table below intentionally shows one row per completed set. The downloadable CSV contains the detailed target-level research data. This is descriptive pilot output, not a clinical score.</div>
"""


def advance_after_set(state: dict) -> tuple[bool, Path | None]:
    state["set_idx"] += 1
    if state["set_idx"] >= TOTAL_SETS:
        return True, save_results(state)

    # Resolve from the scenario list, then refresh the compatibility cache.
    scenario = state["scenarios"][state["set_idx"]]
    expected_set_index = state["set_idx"] + 1
    actual_set_index = int(scenario.get("set_index", -1))
    if actual_set_index != expected_set_index:
        raise RuntimeError(
            "Cannot advance session: scenario ordering changed unexpectedly. "
            f"position={state['set_idx']}, expected set_index={expected_set_index}, "
            f"actual set_index={actual_set_index}."
        )
    now = utc_now()
    state.update({
        "scenario": scenario,
        "phase": "reading",
        "phase_remaining": READING_TIME_SECONDS,
        "phase_deadline_epoch": time.time() + READING_TIME_SECONDS,
        "reading_start": now,
        "reading_end": None,
        "distractor_start": None,
        "distractor_end": None,
        "distractor_response_time_sec": None,
        "recall_start": None,
        "recall_end": None,
        "reading_skipped": False,
        "submitted_distractor_answer": None,
        "distractor_answer_updates": [],
    })
    return False, None


def render_tick(state, distractor_answer, recalled_text, force_submit=False):
    """Advance/render the serialized state machine.

    Important UI rule:
    A one-second timer tick must not resend static components. In particular,
    replacing the protected HTML image every second makes the stimulus visibly
    flash even though its content is unchanged. Static content is therefore sent
    only when entering a new phase/set; steady-state timer ticks update only the
    relevant countdown.
    """
    if not state:
        return (
            state,
            gr.skip(), gr.skip(), gr.skip(), gr.skip(),
            gr.skip(), gr.skip(), gr.skip(),
            gr.skip(), gr.skip(), gr.skip(),
            gr.skip(), gr.skip(), gr.skip(),
            gr.skip(), gr.skip(), gr.skip(), gr.skip(),
        )

    if not state.get("stimuli_preflight_ok"):
        raise RuntimeError(
            "Stimulus preflight did not complete. The assessment will not advance."
        )

    phase_before = state["phase"]

    # New participants pause on the credential screen. The global timer must be
    # a complete no-op while registration is displayed.
    if phase_before == "registration":
        return (
            state,
            gr.skip(), gr.skip(), gr.skip(), gr.skip(),
            gr.skip(), gr.skip(), gr.skip(),
            gr.skip(), gr.skip(), gr.skip(),
            gr.skip(), gr.skip(), gr.skip(),
            gr.skip(), gr.skip(), gr.skip(), gr.skip(),
        )

    if force_submit and phase_before == "recall":
        state["phase_remaining"] = 0
    else:
        deadline = float(state.get("phase_deadline_epoch", time.time()))
        state["phase_remaining"] = max(
            0, int(math.ceil(deadline - time.time()))
        )

    # --------------------------------------------------------------
    # Phase transitions
    # --------------------------------------------------------------
    if phase_before == "reading" and state["phase_remaining"] <= 0:
        transition_to_distractor(state)

    elif phase_before == "distractor" and state["phase_remaining"] <= 0:
        transition_to_recall(state)

    elif phase_before == "recall" and state["phase_remaining"] <= 0:
        if state.get("is_processing"):
            return gr.skip()

        active_set_index = int(state["set_idx"]) + 1
        if active_set_index in state.get("completed_set_indices", []):
            return gr.skip()

        state["is_processing"] = True
        try:
            finalized = append_set_results(
                state,
                recalled_text or "",
                distractor_answer or "",
            )
            if not finalized:
                return gr.skip()

            finished, path = advance_after_set(state)

            if finished:
                state["phase"] = "complete"
                state["output_path"] = str(path)
                return (
                    state,
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=True),
                    gr.skip(),
                    gr.skip(),
                    gr.skip(),
                    gr.skip(),
                    gr.skip(),
                    gr.skip(),
                    gr.update(value=""),
                    gr.skip(),
                    gr.skip(),
                    gr.update(value=""),
                    final_summary(state),
                    current_df_rows(state),
                    str(path),
                )

            # Enter the next reading phase. This is one of the few moments when
            # the protected stimulus HTML must actually be sent to the browser.
            canvas = scenario_stimulus_html(state)
            return (
                state,
                gr.update(visible=True),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                session_set_title(state),
                canvas,
                f"Reading time: **{READING_TIME_SECONDS}s**",
                gr.skip(),
                gr.skip(),
                gr.skip(),
                gr.update(value=""),
                gr.skip(),
                gr.skip(),
                gr.update(value=""),
                gr.skip(),
                current_df_rows(state),
                gr.skip(),
            )
        finally:
            state["is_processing"] = False

    phase_after = state["phase"]
    scenario = current_scenario(state)

    # --------------------------------------------------------------
    # We just entered the distractor phase. Send its static UI once.
    # --------------------------------------------------------------
    if phase_before != phase_after and phase_after == "distractor":
        d = scenario["distractor"]
        requires_answer = bool(d.get("requires_answer", True))

        if requires_answer:
            prompt = (
                f"### Active distraction • {scenario['distractor_condition']} load\n"
                f"{d['task']}\n\n"
                "Work for the full interval. You may update and save your answer at any time."
            )
            answer_update = gr.update(
                visible=True,
                value="",
                placeholder="Example: 36, 35, 25, ...",
            )
        else:
            prompt = (
                "### Quiet baseline interval\n"
                f"{d['task']}\n\n"
                "This quiet interval is intentional: it provides the "
                "no-distraction comparison condition."
            )
            answer_update = gr.update(visible=False, value="")

        return (
            state,
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.skip(),
            gr.skip(),
            gr.skip(),
            gr.skip(),
            prompt,
            f"Time remaining: **{state['phase_remaining']}s**",
            answer_update,
            gr.skip(),
            gr.skip(),
            gr.update(value=""),
            gr.skip(),
            gr.skip(),
            gr.skip(),
        )

    # --------------------------------------------------------------
    # We just entered recall. Send its static heading once.
    # --------------------------------------------------------------
    if phase_before != phase_after and phase_after == "recall":
        return (
            state,
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=False),
            gr.skip(),
            gr.skip(),
            gr.skip(),
            gr.skip(),
            gr.skip(),
            gr.skip(),
            gr.skip(),
            f"### Recall • Set {scenario['set_index']} of {TOTAL_SETS}",
            f"Recall time: **{state['phase_remaining']}s**",
            gr.update(value=""),
            gr.skip(),
            gr.skip(),
            gr.skip(),
        )

    # --------------------------------------------------------------
    # Steady-state timer ticks: update ONLY the countdown component.
    # Everything else remains untouched in the browser.
    # --------------------------------------------------------------
    if phase_after == "reading":
        return (
            state,
            gr.skip(), gr.skip(), gr.skip(), gr.skip(),
            gr.skip(),                 # scenario title: unchanged
            gr.skip(),                 # protected HTML/image: unchanged
            f"Reading time: **{state['phase_remaining']}s**",
            gr.skip(), gr.skip(), gr.skip(),
            gr.skip(),
            gr.skip(), gr.skip(), gr.skip(),
            gr.skip(), gr.skip(), gr.skip(),
        )

    if phase_after == "distractor":
        return (
            state,
            gr.skip(), gr.skip(), gr.skip(), gr.skip(),
            gr.skip(), gr.skip(), gr.skip(),
            gr.skip(), gr.skip(),
            f"Time remaining: **{state['phase_remaining']}s**",
            gr.skip(),                 # answer box untouched
            gr.skip(), gr.skip(), gr.skip(),
            gr.skip(), gr.skip(), gr.skip(),
        )

    if phase_after == "recall":
        return (
            state,
            gr.skip(), gr.skip(), gr.skip(), gr.skip(),
            gr.skip(), gr.skip(), gr.skip(),
            gr.skip(), gr.skip(), gr.skip(),
            gr.skip(),
            gr.skip(),
            f"Recall time: **{state['phase_remaining']}s**",
            gr.skip(),                 # typed recall text untouched
            gr.skip(), gr.skip(), gr.skip(),
        )

    return gr.skip()

def submit_distractor_answer(answer, state):
    if not state or state.get("phase") != "distractor":
        return state
    scenario = current_scenario(state)
    if not scenario["distractor"].get("requires_answer", True):
        gr.Info("No answer is required during the quiet baseline interval.")
        return state

    value = str(answer or "").strip()
    elapsed = seconds_between(state.get("distractor_start"), utc_now())
    state["submitted_distractor_answer"] = value
    state["distractor_response_time_sec"] = elapsed
    state.setdefault("distractor_answer_updates", []).append({
        "time_sec": elapsed,
        "answer": value,
    })
    gr.Info("Answer saved. You can keep working and save again before time expires.")
    return state


def timer_tick_light(distractor_answer, recalled_text, state):
    """Advance time without touching static UI components.

    The one-second timer is allowed to output only:
      * the hidden session state;
      * the three countdown components;
      * a hidden phase-change signal.

    The protected stimulus, headings, prompts, inputs, tables, and view containers
    are deliberately absent from this event's output list. This prevents Gradio
    from marking them as processing/rerendering them every second.
    """
    if not state:
        return (
            state,
            gr.skip(),
            gr.skip(),
            gr.skip(),
            gr.skip(),
        )

    before_phase = state.get("phase")
    before_set_idx = int(state.get("set_idx", 0))

    # Reuse the tested state-machine logic, but intentionally ignore its UI tuple.
    render_tick(
        state,
        distractor_answer,
        recalled_text,
        False,
    )

    after_phase = state.get("phase")
    after_set_idx = int(state.get("set_idx", 0))

    reading_timer = gr.skip()
    distractor_timer = gr.skip()
    recall_timer = gr.skip()

    if after_phase == "reading":
        reading_timer = (
            f"Reading time: **{int(state.get('phase_remaining', 0))}s**"
        )
    elif after_phase == "distractor":
        distractor_timer = (
            f"Time remaining: **{int(state.get('phase_remaining', 0))}s**"
        )
    elif after_phase == "recall":
        recall_timer = (
            f"Recall time: **{int(state.get('phase_remaining', 0))}s**"
        )

    phase_changed = (
        before_phase != after_phase
        or before_set_idx != after_set_idx
    )

    if phase_changed:
        # The changing value triggers phase_signal.change exactly when the UI
        # actually needs to be redrawn.
        phase_signal = (
            f"{after_phase}:{after_set_idx}:"
            f"{len(state.get('completed_set_indices', []))}:"
            f"{time.time_ns()}"
        )
    else:
        phase_signal = gr.skip()

    return (
        state,
        reading_timer,
        distractor_timer,
        recall_timer,
        phase_signal,
    )


def render_phase_ui(state):
    """Render static UI only when the phase or set actually changes."""
    if not state:
        return (
            gr.skip(), gr.skip(), gr.skip(), gr.skip(),
            gr.skip(), gr.skip(),
            gr.skip(), gr.skip(), gr.skip(),
            gr.skip(), gr.skip(),
            gr.skip(), gr.skip(), gr.skip(),
        )

    phase = state.get("phase")

    if phase == "reading":
        scenario = current_scenario(state)
        return (
            gr.update(visible=True),    # reading_view
            gr.update(visible=False),   # distractor_view
            gr.update(visible=False),   # recall_view
            gr.update(visible=False),   # results_view
            session_set_title(state),
            scenario_stimulus_html(state),
            gr.skip(),                  # distractor title
            gr.skip(),                  # distractor prompt
            gr.update(value=""),        # distractor answer
            gr.skip(),                  # recall title
            gr.update(value=""),        # recall text
            gr.skip(),                  # summary
            current_df_rows(state),
            gr.skip(),                  # output file
        )

    if phase == "distractor":
        scenario = current_scenario(state)
        d = scenario["distractor"]
        requires_answer = bool(d.get("requires_answer", True))

        if requires_answer:
            prompt = (
                f"### Active distraction • "
                f"{scenario['distractor_condition']} load\n"
                f"{d['task']}\n\n"
                "Work for the full interval. You may update and save your "
                "answer at any time."
            )
            answer_update = gr.update(
                visible=True,
                value="",
                placeholder="Example: 36, 35, 25, ...",
            )
        else:
            prompt = (
                "### Quiet baseline interval\n"
                f"{d['task']}\n\n"
                "This quiet interval is intentional: it provides the "
                "no-distraction comparison condition."
            )
            answer_update = gr.update(visible=False, value="")

        return (
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.skip(),
            gr.skip(),
            gr.skip(),
            prompt,
            answer_update,
            gr.skip(),
            gr.skip(),
            gr.skip(),
            current_df_rows(state),
            gr.skip(),
        )

    if phase == "recall":
        scenario = current_scenario(state)
        return (
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=False),
            gr.skip(),
            gr.skip(),
            gr.skip(),
            gr.skip(),
            gr.skip(),
            f"### Recall • Set {scenario['set_index']} of {TOTAL_SETS}",
            gr.update(value=""),
            gr.skip(),
            current_df_rows(state),
            gr.skip(),
        )

    if phase == "complete":
        return (
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=True),
            gr.skip(),
            gr.skip(),
            gr.skip(),
            gr.skip(),
            gr.skip(),
            gr.skip(),
            gr.skip(),
            final_summary(state),
            current_df_rows(state),
            state.get("output_path") or None,
        )

    # Registration or any other non-assessment state: leave UI untouched.
    return tuple(gr.skip() for _ in range(14))


def submit_recall(distractor_answer, recalled_text, state):
    return render_tick(state, distractor_answer, recalled_text, True)



with gr.Blocks(title=APP_TITLE) as app:
    state_store = gr.State()

    gr.Markdown("# Memory Recall Pilot")
    gr.Markdown(
        "**First time here?** Choose **New participant** and the program will assign "
        "your Participant ID automatically. Choose **Returning participant** only if "
        "you have completed or started this study before."
    )

    with gr.Column(visible=True, elem_classes=["card-panel"]) as welcome_view:
        gr.Markdown(
            "### Participant privacy\n"
            "Do not enter a name, phone number, email address, or other direct identifier."
        )

        participant_mode = gr.Radio(
            choices=["New participant", "Returning participant"],
            value="New participant",
            label="Participation status",
        )

        role_dropdown = gr.Dropdown(
            label="Participant context (research metadata)",
            choices=ROLES_LIST,
            value=DEFAULT_ROLE,
            info="Scenario content is generated for this role while experimental structure and distractor assignment remain controlled.",
        )

        gr.Markdown(
            "### Participation confirmation\n"
            "This checkbox records confirmation of the study information presented "
            "under the study procedure. It does not replace any separate consent, "
            "parent/guardian permission, assent, or ethics-review documentation that "
            "may be required."
        )
        consent_checkbox = gr.Checkbox(
            label="I have read the study information and agree to participate.",
            value=False,
        )

        with gr.Column(visible=True) as new_participant_controls:
            gr.Markdown(
                "**New participant:** no ID is required. The system will generate "
                "a unique pseudonymous ID and a private return code."
            )
            new_register_btn = gr.Button(
                "Create my Participant ID",
                variant="primary",
            )

        with gr.Column(visible=False) as returning_participant_controls:
            subject_input = gr.Textbox(
                label="Existing Participant ID",
                placeholder="Example: P7K3Q9MX",
                info="Enter the ID generated during your first session.",
            )
            access_code_input = gr.Textbox(
                label="Private return access code",
                placeholder="Enter your existing code",
                type="password",
                info="This verifies the existing Participant ID. The code is never written to the research CSV.",
            )
            returning_start_btn = gr.Button(
                "Start returning session",
                variant="primary",
            )

        error_msg = gr.Markdown("")

        with gr.Column(visible=False, elem_classes=["card-panel"]) as credential_panel:
            gr.Markdown(
                "## Save these credentials before continuing\n"
                "You will need **both** values to return for another session. "
                "The access code cannot be displayed again later; the researcher can "
                "reset it if it is lost."
            )
            assigned_id_ui = gr.Textbox(
                label="Your Participant ID",
                interactive=False,
            )
            assigned_code_ui = gr.Textbox(
                label="Your private return access code",
                interactive=False,
            )
            gr.Markdown(
                "**Do not share these credentials with another participant.** "
                "They are used to keep repeated sessions linked to the correct pseudonymous participant."
            )
            begin_new_btn = gr.Button(
                "I saved my ID and code — Begin assessment",
                variant="primary",
            )

    with gr.Column(visible=False, elem_classes=["card-panel"]) as reading_view:
        scenario_title_ui = gr.Markdown("")
        scenario_canvas_ui = gr.HTML(
            value='<div class="protected-stimulus-frame"></div>',
            elem_id="protected-instruction-canvas",
        )
        reading_timer_ui = gr.Markdown("")

    with gr.Column(visible=False, elem_classes=["card-panel"]) as distractor_view:
        distractor_title_ui = gr.Markdown("")
        distractor_prompt_ui = gr.Markdown("")
        distractor_timer_ui = gr.Markdown("")
        distractor_answer_input = gr.Textbox(
            label="Distractor answers"
        )
        distractor_submit_btn = gr.Button("Save current answer", variant="secondary")

    with gr.Column(visible=False, elem_classes=["card-panel"]) as recall_view:
        recall_title_ui = gr.Markdown("")
        recall_timer_ui = gr.Markdown("")
        recalled_text_input = gr.Textbox(
            label="Enter remembered instructions, one per line",
            lines=RECALL_INPUT_LINES,
        )
        submit_btn = gr.Button("Submit recall now", variant="primary")

    with gr.Column(visible=False, elem_classes=["card-panel"]) as results_view:
        summary_ui = gr.HTML("")
        results_table = gr.Dataframe(
            headers=DISPLAY_COLUMNS,
            interactive=False,
            wrap=True,
            show_row_numbers=False,
            buttons=["copy"],
            max_height=RESULTS_TABLE_MAX_HEIGHT,
            column_widths=list(RESULTS_TABLE_COLUMN_WIDTHS),
            elem_classes=["results-summary-table"],
        )
        output_file = gr.File(label=OUTPUT_DOWNLOAD_LABEL)

    timer = gr.Timer(value=TIMER_INTERVAL_SECONDS, active=True)

    # Changed only when the state machine enters a new phase/set. Keeping this
    # separate allows the one-second timer to avoid static UI components entirely.
    phase_signal = gr.Textbox(
        value="",
        visible=False,
        elem_id="pilot-phase-signal",
    )

    common_outputs = [
        state_store, reading_view, distractor_view, recall_view, results_view,
        scenario_title_ui, scenario_canvas_ui, reading_timer_ui,
        distractor_title_ui, distractor_prompt_ui, distractor_timer_ui,
        distractor_answer_input, recall_title_ui, recall_timer_ui,
        recalled_text_input, summary_ui, results_table, output_file,
    ]

    participant_mode.change(
        fn=toggle_participant_mode,
        inputs=[participant_mode],
        outputs=[new_participant_controls, returning_participant_controls],
    )

    # First-time participant: system creates credentials automatically.
    new_register_btn.click(
        fn=register_new_participant,
        inputs=[role_dropdown, consent_checkbox],
        outputs=[
            state_store,
            credential_panel,
            assigned_id_ui,
            assigned_code_ui,
            new_register_btn,
            participant_mode,
            role_dropdown,
            consent_checkbox,
            error_msg,
        ],
        concurrency_limit=1,
        concurrency_id="participant_registration",
    )

    begin_new_btn.click(
        fn=begin_new_participant_assessment,
        inputs=[state_store],
        outputs=[
            state_store,
            welcome_view,
            reading_view,
            scenario_title_ui,
            scenario_canvas_ui,
            reading_timer_ui,
            error_msg,
        ],
        concurrency_limit=1,
        concurrency_id="participant_registration",
    )

    # Returning participant: verify existing credentials and begin next session.
    returning_start_btn.click(
        fn=start_returning_experiment,
        inputs=[
            subject_input,
            access_code_input,
            role_dropdown,
            consent_checkbox,
        ],
        outputs=[
            state_store, welcome_view, reading_view, distractor_view,
            recall_view, results_view, error_msg,
            scenario_title_ui, scenario_canvas_ui, reading_timer_ui,
            distractor_title_ui, distractor_prompt_ui, distractor_timer_ui,
            distractor_answer_input, recall_title_ui, recall_timer_ui,
            recalled_text_input, summary_ui, results_table, output_file,
        ],
        concurrency_limit=1,
        concurrency_id="participant_registration",
    )

    timer.tick(
        fn=timer_tick_light,
        inputs=[
            distractor_answer_input,
            recalled_text_input,
            state_store,
        ],
        outputs=[
            state_store,
            reading_timer_ui,
            distractor_timer_ui,
            recall_timer_ui,
            phase_signal,
        ],
        show_progress="hidden",
        trigger_mode="always_last",
        concurrency_limit=1,
        concurrency_id="pilot_state_machine",
    )

    # Static UI is rendered only after an actual phase/set transition.
    phase_signal.change(
        fn=render_phase_ui,
        inputs=[state_store],
        outputs=[
            reading_view,
            distractor_view,
            recall_view,
            results_view,
            scenario_title_ui,
            scenario_canvas_ui,
            distractor_title_ui,
            distractor_prompt_ui,
            distractor_answer_input,
            recall_title_ui,
            recalled_text_input,
            summary_ui,
            results_table,
            output_file,
        ],
        show_progress="hidden",
        concurrency_limit=1,
        concurrency_id="pilot_phase_render",
    )

    distractor_submit_btn.click(
        fn=submit_distractor_answer,
        inputs=[distractor_answer_input, state_store],
        outputs=[state_store],
        concurrency_limit=1,
        concurrency_id="pilot_state_machine",
    )

    submit_btn.click(
        fn=submit_recall,
        inputs=[distractor_answer_input, recalled_text_input, state_store],
        outputs=common_outputs,
        concurrency_limit=1,
        concurrency_id="pilot_state_machine",
    )


if __name__ == "__main__":
    print(f"[PILOT START] {APP_RUNTIME_VERSION} file={__file__}", flush=True)
    app.launch(share=GRADIO_SHARE, css=CUSTOM_CSS, js=PROTECTION_JS, theme=gr.themes.Soft())
