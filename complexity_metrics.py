"""Transparent structural-complexity metrics for the pilot instruction sets.

These are engineering descriptors, not validated psychological scales. They are
stored component-by-component so later pilot data can show which features matter.
"""
from __future__ import annotations

import re
from itertools import combinations

COMPLEXITY_METHOD_VERSION = "ici-structural-1.0"


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(_tokens(a)), set(_tokens(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def measure_scenario(tasks: list[dict]) -> dict:
    if not tasks:
        raise ValueError("Cannot measure an empty scenario.")

    word_counts = [len(_tokens(t["text"])) for t in tasks]
    dependency_depths = [max(0, int(t.get("dependency_depth", 0))) for t in tasks]

    pair_scores = [_jaccard(a["text"], b["text"]) for a, b in combinations(tasks, 2)]
    scenario_overlap = sum(pair_scores) / len(pair_scores) if pair_scores else 0.0

    target_overlaps = []
    for i, task in enumerate(tasks):
        scores = [_jaccard(task["text"], other["text"]) for j, other in enumerate(tasks) if j != i]
        target_overlaps.append(sum(scores) / len(scores) if scores else 0.0)

    n = len(tasks)
    mean_words = sum(word_counts) / n
    mean_depth = sum(dependency_depths) / n

    # 0-10 structural index. Components are intentionally separate from
    # distractor condition and from high-demand/open-ended task semantics.
    task_count_component = min(n / 6.0, 1.0) * 2.5
    length_component = min(mean_words / 15.0, 1.0) * 2.5
    dependency_component = min(mean_depth / 2.0, 1.0) * 2.5
    overlap_component = min(scenario_overlap, 1.0) * 2.5
    ici = round(task_count_component + length_component + dependency_component + overlap_component, 3)

    target_metrics = []
    for wc, dep, overlap in zip(word_counts, dependency_depths, target_overlaps):
        target_score = (
            min(wc / 15.0, 1.0) * 5.0
            + min(dep / 2.0, 1.0) * 3.0
            + min(overlap, 1.0) * 2.0
        )
        target_metrics.append({
            "word_count": wc,
            "dependency_depth": dep,
            "semantic_overlap": round(overlap, 3),
            "structural_complexity": round(target_score, 3),
        })

    return {
        "target_count": n,
        "mean_target_words": round(mean_words, 3),
        "mean_dependency_depth": round(mean_depth, 3),
        "scenario_semantic_overlap": round(scenario_overlap, 3),
        "instruction_complexity_index": ici,
        "complexity_method_version": COMPLEXITY_METHOD_VERSION,
        "target_metrics": target_metrics,
    }
