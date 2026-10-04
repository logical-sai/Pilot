#!/usr/bin/env python3
"""Independent reconstruction of the instruction-recall pilot.

Input: local copies of the CSV outputs in logical-sai/Pilot at commit
 e85c3fde1bf5df961871ff539ff585d4a5c5a86b.

Main cohort: rows with Complexity_Method_Version=role-adapted-v10-self-paced.
This is an independent reconstruction, NOT the lost historical analysis script.
The 3 data-quality sensitivity exclusions cannot be applied unless their
session IDs are specified by the researcher/audit record.

Dependencies: numpy, pandas, scipy, statsmodels, scikit-learn.
Usage:
    python reconstruct_recall_statistics.py ./outputs --bootstrap 3000
    python reconstruct_recall_statistics.py ./outputs --exclude-session SESSION_ID ...
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

COHORT_VERSION = "role-adapted-v10-self-paced"
FAMILIES = ("pilot_s02", "pilot_s03", "pilot_s04", "pilot_s05")


def load_cohort(root: Path, excluded: set[str] | None = None):
    paths = sorted(root.glob("memory_recall_results_*.csv"))
    if not paths:
        raise FileNotFoundError(f"No memory_recall_results_*.csv files in {root}")
    all_target = []
    included = []
    versions = {}
    for p in paths:
        r = pd.read_csv(p, dtype=str, keep_default_na=False)
        r = r[r["Record_Type"].eq("Target")].copy()
        if r.empty:
            continue
        ver = r["Complexity_Method_Version"].iloc[0]
        versions[ver] = versions.get(ver, 0) + 1
        if ver != COHORT_VERSION:
            continue
        if not r["Complexity_Method_Version"].eq(ver).all():
            raise ValueError(f"Mixed protocol versions in {p}")
        if len(r) != 20 or set(r["Set_Index"]) != {"1", "2", "3", "4", "5"}:
            raise ValueError(f"Bad 20-target five-set session in {p}")
        included.append(p.name)
        all_target.append(r)
    if not all_target:
        raise ValueError(f"No {COHORT_VERSION} main-cohort files")
    data = pd.concat(all_target, ignore_index=True)
    if data.duplicated(subset=["Session_ID", "Target_ID"]).any():
        raise ValueError("Duplicate session-target pairs")
    if excluded:
        notfound = excluded - set(data["Session_ID"])
        if notfound:
            raise ValueError(f"Unknown excluded session IDs: {sorted(notfound)}")
        data = data[~data["Session_ID"].isin(excluded)].reset_index(drop=True)
    numeric_cols = ["Target_Word_Count", "Target_Dependency_Depth", "Target_Semantic_Overlap",
                    "Risk_Score", "Target_Index", "Set_Index"]
    for k in numeric_cols:
        data[k] = pd.to_numeric(data[k], errors="raise")
    data["failure"] = data["Remembered"].ne("Y").astype(int)
    print(f"Files found: {len(paths)}, main-cohort: {len(included)}, versions: {versions}")
    return data, included


def base_features(d: pd.DataFrame, structural: bool = False,
                  inferential: bool = False) -> pd.DataFrame:
    """Reference categories: Primacy, NONE, scenario pilot_s01, form A."""
    a = pd.DataFrame(index=d.index)
    a["Middle"] = d["Serial_Category"].eq("Middle").astype(float)
    a["Recency"] = d["Serial_Category"].eq("Recency").astype(float)
    a["LOW"] = d["Distractor_Condition"].eq("LOW").astype(float)
    a["HIGH"] = d["Distractor_Condition"].eq("HIGH").astype(float)
    a["WordCount"] = d["Target_Word_Count"].astype(float)
    if structural or inferential:
        a["Dependency"] = d["Target_Dependency_Depth"].astype(float)
        a["Overlap"] = d["Target_Semantic_Overlap"].astype(float)
    if inferential:
        a["OpenEnded"] = d["Open_Ended"].eq("Y").astype(float)
        a["HighDemand"] = d["High_Demand"].eq("Y").astype(float)
    for idx, f in enumerate(FAMILIES, 2):
        a[f"Family{idx}"] = d["Scenario_Family_ID"].eq(f).astype(float)
    a["FormB"] = d["Scenario_Form"].eq("B").astype(float)
    a["FormC"] = d["Scenario_Form"].eq("C").astype(float)
    return a