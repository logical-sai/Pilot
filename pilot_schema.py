"""Single active schema and shared constants for the memory-recall pilot."""
from __future__ import annotations

from pathlib import Path

APP_VERSION = "pilot-8.3"
SCHEMA_VERSION = "pilot-8.3"
RULE_ENGINE_VERSION = "pilot-rule-3.0"
CONSENT_TEXT_VERSION = "pilot-consent-1.0"
PARTICIPANT_REGISTRY_VERSION = "participant-registry-2.0"

OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CANONICAL_COLUMNS = [
    # Session / repeated-measures identity
    "Session_ID",
    "Session_Number",
    "Session_Start_UTC",
    "Consent_Confirmed",
    "Consent_Timestamp_UTC",
    "Consent_Text_Version",
    "Participant_ID_Verified",
    "Participant_Registry_Version",
    "User",                 # pseudonymous Participant ID only; never name/phone/email
    "Role",

    # Scenario / equivalent-form identity
    "Set_Index",
    "Scenario_Order_Position",
    "Scenario_Family_ID",
    "Scenario_Form",
    "Scenario_ID",
    "Scenario_Title",

    # Target / recall scoring
    "Record_Type",              # Target | Intrusion
    "Target_ID",
    "Target_Family_ID",
    "Target_Index",
    "Target_Count",
    "Target_Instruction",
    "User_Recall_Text",
    "Remembered",
    "Out_of_Order",
    "Match_Type",               # Exact | Semantic | None | Intrusion
    "Match_Score",
    "Serial_Category",          # Primacy | Middle | Recency

    # Task meaning stored once at scenario preparation
    "High_Demand",
    "Open_Ended",
    "Instruction_Interference_Present",
    "Trigger_Anchor",

    # Structural instruction-complexity measurements
    "Target_Word_Count",
    "Target_Dependency_Depth",
    "Target_Semantic_Overlap",
    "Target_Structural_Complexity",
    "Scenario_Mean_Target_Words",
    "Scenario_Mean_Dependency_Depth",
    "Scenario_Semantic_Overlap",
    "Instruction_Complexity_Index",
    "Complexity_Method_Version",
    "Scenario_Total_Word_Count",
    "Embedded_Distractor_Count",

    # Exposure timing
    "Reading_Start_UTC",
    "Reading_End_UTC",
    "Reading_Time_Sec",
    "Reading_Skipped",

    # Controlled distractor condition
    "Distractor_Condition",     # NONE | LOW | HIGH
    "Distractor_ID",
    "Distractor_Difficulty_Score",
    "Distractor_Task",
    "Distractor_Expected_Answer",
    "Distractor_Answer",
    "Distractor_Submitted",
    "Distractor_Correct",
    "Distractor_Response_Time_Sec",
    "Distractor_Items_Presented",
    "Distractor_Items_Answered",
    "Distractor_Items_Correct",
    "Distractor_Accuracy_Pct",
    "Distractor_Mean_Response_Time_Sec",
    "Distractor_Responses_JSON",
    "Distractor_Start_UTC",
    "Distractor_End_UTC",
    "Distractor_Time_Sec",

    # Recall timing
    "Recall_Start_UTC",
    "Recall_End_UTC",
    "Recall_Time_Sec",

    # Reminder heuristic
    "Risk_Score",
    "Risk_Level",
    "Requires_Reminder",

    # Provenance
    "App_Version",
    "Schema_Version",
    "Evaluator_Model",
    "Rule_Engine_Version",
]

REQUIRED_ANALYSIS_COLUMNS = {
    "Session_ID", "Session_Number", "Session_Start_UTC",
    "Consent_Confirmed", "Consent_Timestamp_UTC", "Consent_Text_Version",
    "Participant_ID_Verified", "Participant_Registry_Version",
    "User", "Role",
    "Set_Index", "Scenario_Family_ID", "Scenario_Form", "Scenario_ID",
    "Record_Type", "Target_ID", "Target_Family_ID", "Target_Index",
    "Target_Count", "Target_Instruction", "Remembered", "Out_of_Order",
    "Serial_Category", "Instruction_Interference_Present", "Open_Ended", "High_Demand",
    "Instruction_Complexity_Index", "Complexity_Method_Version",
    "Distractor_Condition", "Distractor_Difficulty_Score",
    "Distractor_Items_Presented", "Distractor_Items_Answered",
    "Distractor_Items_Correct", "Distractor_Accuracy_Pct",
    "Distractor_Mean_Response_Time_Sec",
    "Reading_Time_Sec", "Distractor_Time_Sec",
    "Recall_Time_Sec", "Risk_Score", "Risk_Level", "Requires_Reminder",
    "Schema_Version",
}


def serial_category(position: int, total: int) -> str:
    """25% / 50% / 25% serial-position grouping."""
    if total <= 0:
        return "Middle"
    if position <= max(1, total * 0.25):
        return "Primacy"
    if position > total * 0.75:
        return "Recency"
    return "Middle"


def validate_columns(columns) -> None:
    missing = REQUIRED_ANALYSIS_COLUMNS - set(columns)
    if missing:
        raise ValueError(
            "Results file does not match the single active pilot schema. Missing columns: "
            + ", ".join(sorted(missing))
        )
