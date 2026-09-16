from __future__ import annotations

import os


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return default if value is None else int(value)


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    return default if value is None else float(value)


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    return default if value is None else value.strip()


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# ==========================================================================
# MODEL / BACKEND
# ==========================================================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "***").strip()
GROQ_BASE_URL = os.environ.get(
    "GROQ_BASE_URL",
    "https://api.groq.com/openai/v1",
).strip()

MODEL_NAME = os.environ.get(
    "MODEL_NAME",
    "openai/gpt-oss-20b",
).strip()

MODEL_TIMEOUT_SECONDS = _env_float("MODEL_TIMEOUT_SECONDS", 35.0)
MODEL_MAX_RETRIES = _env_int("MODEL_MAX_RETRIES", 1)

MODEL_HEALTHCHECK_TEMPERATURE = 0.0
MODEL_HEALTHCHECK_MAX_TOKENS = 8

# Recall semantic-matching request.
EVALUATOR_TEMPERATURE = 0.0
EVALUATOR_MAX_TOKENS = _env_int("EVALUATOR_MAX_TOKENS", 800)

# Role-specific scenario generation.
APP_RUNTIME_VERSION = "memory-recall-role-v8-timer-isolated"

ROLE_GENERATION_VERSION = "role-adapted-v8-chunked"
ROLE_GENERATION_RETRIES = _env_int("ROLE_GENERATION_RETRIES", 2)

# GPT-OSS defaults to medium reasoning. These stimuli do not need deep reasoning,
# so low effort preserves output tokens and reduces latency/TPM consumption.
MODEL_REASONING_EFFORT = _env_str("MODEL_REASONING_EFFORT", "low")

ROLE_GENERATION_TEMPERATURE = _env_float(
    "ROLE_GENERATION_TEMPERATURE", 0.30
)
ROLE_REPAIR_TEMPERATURE = _env_float(
    "ROLE_REPAIR_TEMPERATURE", 0.20
)

# Generate a few scenarios per request rather than all five in one large request.
ROLE_GENERATION_CHUNK_SIZE = _env_int("ROLE_GENERATION_CHUNK_SIZE", 3)

# Completion budget is computed per chunk and capped by this value.
ROLE_GENERATION_TOKEN_OVERHEAD = _env_int(
    "ROLE_GENERATION_TOKEN_OVERHEAD", 180
)
ROLE_GENERATION_TOKENS_PER_SET = _env_int(
    "ROLE_GENERATION_TOKENS_PER_SET", 330
)
ROLE_GENERATION_MAX_TOKENS = _env_int(
    "ROLE_GENERATION_MAX_TOKENS", 1300
)

# Small budget for regenerating an individual missing/invalid set.
ROLE_REPAIR_MAX_TOKENS = _env_int(
    "ROLE_REPAIR_MAX_TOKENS", 520
)

# If Groq says to retry shortly, wait once rather than immediately failing and
# forcing the researcher to restart registration.
RATE_LIMIT_AUTO_WAIT_MAX_SECONDS = _env_float(
    "RATE_LIMIT_AUTO_WAIT_MAX_SECONDS", 12.0
)


# ==========================================================================
# EXPERIMENT PROTOCOL
# ==========================================================================
ROLES = (
    "Student",
    "Teacher / Educator",
    "Healthcare Professional",
    "Software Engineer",
    "Scientist / Researcher",
    "Athlete",
    "Parent / Caregiver",
    "Office Professional",
    "Household Manager",
    "Examiner / Inspector",
    "Other / Prefer not to say",
)

DEFAULT_ROLE = "Student"
OTHER_ROLE_VALUE = "Other / Prefer not to say"
GENERAL_ROLE_PROMPT = "a general everyday adult context"

READING_TIME_SECONDS = _env_int("READING_TIME_SECONDS", 40)
DISTRACTOR_TIME_SECONDS = _env_int("DISTRACTOR_TIME_SECONDS", 15)
RECALL_TIME_SECONDS = _env_int("RECALL_TIME_SECONDS", 40)
TIMER_INTERVAL_SECONDS = _env_float("TIMER_INTERVAL_SECONDS", 1.0)

TARGETS_PER_SCENARIO = _env_int("TARGETS_PER_SCENARIO", 4)
NON_INSTRUCTION_DETAILS_PER_SCENARIO = _env_int(
    "NON_INSTRUCTION_DETAILS_PER_SCENARIO", 2
)

# Layout of generated material in the protected stimulus.
# The values refer to generated target/detail indices.
STIMULUS_SEQUENCE = (
    "context",
    "target:0",
    "detail:0",
    "target:1",
    "target:2",
    "detail:1",
    "target:3",
)

DEFAULT_TARGET_WORD_COUNT = 10
TARGET_WORD_TOLERANCE = 4
ROLE_SLUG_MAX_LENGTH = 28
ROLE_SLUG_FALLBACK = "GENERAL"

# How many recent scenario summaries the optional single-scenario helper avoids.
RECENT_SCENARIO_HISTORY = 4

# Provider/model output parser.
GENERATION_ERROR_PREVIEW_CHARS = 300

# The quiet condition identifier comes from protocol_design/scenario data.
QUIET_DISTRACTOR_CONDITION = "NONE"


# ==========================================================================
# RECALL MATCHING
# ==========================================================================
SEMANTIC_MATCH_THRESHOLD = 0.55
EXACT_MATCH_THRESHOLD = 0.95
MATCH_SCORE_MAX = 1.0


# ==========================================================================
# COMPLEXITY METRIC
# ==========================================================================
DEPENDENCY_MARKERS = frozenset({
    "after",
    "before",
    "when",
    "while",
    "until",
    "unless",
    "if",
    "once",
    "then",
    "because",
    "although",
    "except",
    "and",
    "or",
})

DEPENDENCY_DEPTH_MIN = 1
DEPENDENCY_DEPTH_MAX = 5

COMPLEXITY_WORD_WEIGHT = 0.50
COMPLEXITY_DEPTH_WEIGHT = 0.35
COMPLEXITY_OVERLAP_WEIGHT = 0.15
COMPLEXITY_WORD_NORMALIZER = 20.0
COMPLEXITY_INDEX_SCALE = 100.0


# ==========================================================================
# PARTICIPANT / FILE OUTPUT
# ==========================================================================
SUBJECT_ID_MAX_LENGTH = 64

OUTPUT_FILE_PREFIX = "memory_recall_results"
OUTPUT_FILE_EXTENSION = ".csv"
OUTPUT_DELIMITER = ","
OUTPUT_ENCODING = "utf-8"
OUTPUT_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"
OUTPUT_COLLISION_SUFFIX_BYTES = 3

ISO_TIMESPEC = "milliseconds"
METRIC_ROUND_DIGITS = 3

# Set to ".tsv" and "\t" above if TSV is preferred.
OUTPUT_DOWNLOAD_LABEL = "Download detailed research CSV"


# ==========================================================================
# STIMULUS IMAGE
# ==========================================================================
STIMULUS_WIDTH = 1120
STIMULUS_HEIGHT = 460
STIMULUS_BACKGROUND_RGB = (18, 20, 27)

STIMULUS_FONT_NAME = "DejaVuSans.ttf"
STIMULUS_FONT_SIZE = 25
STIMULUS_SMALL_FONT_SIZE = 15

STIMULUS_HEADER_RGB = (145, 153, 180)
STIMULUS_RULE_RGB = (65, 72, 92)
STIMULUS_TEXT_RGB = (242, 244, 249)

STIMULUS_HEADER_X = 30
STIMULUS_HEADER_Y = 20
STIMULUS_RULE_Y = 48

STIMULUS_MARGIN = 42
STIMULUS_TEXT_START_Y = 82
STIMULUS_LINE_HEIGHT = 43


# ==========================================================================
# UI
# ==========================================================================
APP_TITLE = "Memory Recall Pilot"
GRADIO_SHARE = _env_bool("GRADIO_SHARE", True)

DISPLAY_COLUMNS = (
    "Set",
    "Scenario",
    "Distractor",
    "Complexity",
    "Recall",
    "In order",
    "Intrusions",
    "Distractor result",
)

RESULTS_TABLE_MAX_HEIGHT = 360
RESULTS_TABLE_COLUMN_WIDTHS = (60, 220, 100, 90, 120, 90, 85, 160)
RECALL_INPUT_LINES = 8

CUSTOM_CSS = """
.gradio-container { max-width: 1180px !important; margin: 0 auto !important; }
.card-panel {
    border: 1px solid rgba(127,127,127,.28) !important;
    border-radius: 18px !important;
    padding: 24px !important;
    margin-bottom: 18px !important;
    box-shadow: 0 10px 30px rgba(0,0,0,.08);
}
.pilot-hero { padding: 8px 2px 16px 2px; }
.phase-box {
    border: 1px solid rgba(127,127,127,.22);
    border-radius: 14px;
    padding: 14px 18px;
    background: rgba(127,127,127,.06);
}
.metric-grid {
    display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:14px 0 18px 0;
}
.metric-card {
    border:1px solid rgba(127,127,127,.22); border-radius:14px; padding:16px;
    background:rgba(127,127,127,.06);
}
.metric-label { font-size:.82rem; opacity:.72; margin-bottom:4px; }
.metric-value { font-size:1.45rem; font-weight:700; }
.result-note { opacity:.78; font-size:.92rem; margin-top:10px; }
@media (max-width: 800px) { .metric-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }

/* Protected stimulus is plain HTML, so Gradio creates no download/fullscreen toolbar. */
#protected-instruction-canvas .protected-stimulus-frame {
    display: flex;
    justify-content: center;
    align-items: center;
    width: 100%;
    min-height: 300px;
    padding: 8px 0;
    overflow: hidden;
}
#protected-instruction-canvas .protected-stimulus-image {
    display: block;
    max-width: 100%;
    height: auto;
    -webkit-user-select: none !important;
    user-select: none !important;
    -webkit-user-drag: none !important;
    user-drag: none !important;
    pointer-events: none !important;
}
"""

PROTECTION_JS = """
function() {
    function protectedTarget(target) {
        return target && target.closest &&
               target.closest('#protected-instruction-canvas');
    }

    document.addEventListener('dragstart', function(e) {
        if (protectedTarget(e.target)) e.preventDefault();
    });

    document.addEventListener('contextmenu', function(e) {
        if (protectedTarget(e.target)) e.preventDefault();
    });
}
"""
