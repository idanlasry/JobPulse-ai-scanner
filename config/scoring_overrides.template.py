"""Code-level scoring overrides — guards against known LLM failure patterns.

Each rule runs AFTER the LLM scores and BEFORE Pydantic validation.
If ALL conditions match, the action is applied (set_fit_score, append_reasoning).

This file is part of your personal profile configuration. Keep it minimal —
start empty, and add rules only when you observe systematic mis-scoring that
prompt-level calibration in portfolio.txt cannot fix.

Supported condition keys:
    title_contains_any:     list[str]  — any substring (lowercased) in title
    tech_stack_any_of:      list[str]  — any item (lowercased) in tech_stack
    location_contains_any:  list[str]  — any substring (lowercased) in location
    fit_score_lte:          int        — LLM-returned fit_score <= N
    fit_score_gte:          int        — LLM-returned fit_score >= N
    is_junior_eq:           bool       — is_junior equals value

Supported action keys:
    set_fit_score:     int  — overwrite fit_score
    append_reasoning:  str  — append text to fit_reasoning (with leading newline)

A malformed rule (missing required keys, unknown condition/action key) will
crash the pipeline at import time. This is intentional: silent override
failures are worse than loud startup failures.
"""

from typing import TypedDict


class Conditions(TypedDict, total=False):
    title_contains_any: list[str]
    tech_stack_any_of: list[str]
    location_contains_any: list[str]
    fit_score_lte: int
    fit_score_gte: int
    is_junior_eq: bool


class Action(TypedDict, total=False):
    set_fit_score: int
    append_reasoning: str


class OverrideRule(TypedDict):
    name: str
    description: str
    conditions: Conditions
    action: Action


# Start with an empty list. Add rules only when you find a systematic LLM
# mis-scoring that you cannot fix by tweaking portfolio.txt calibration.
RULES: list[OverrideRule] = []


# ---------------------------------------------------------------------------
# Example rule — uncomment and adapt to your needs.
#
# This example floors Data Scientist roles with analytical LLM signals at
# fit_score 5 (because some smaller models systematically under-score them):
#
# RULES = [
#     {
#         "name": "ds_analytical_llm_floor",
#         "description": "Model under-scores Data Scientist roles with analytical LLM stack",
#         "conditions": {
#             "title_contains_any": ["data "],
#             "tech_stack_any_of": ["llm", "prompt engineering", "a/b testing"],
#             "fit_score_lte": 3,
#         },
#         "action": {
#             "set_fit_score": 5,
#             "append_reasoning": "[POST-PROCESSING: Score raised to 5 — analytical LLM signals detected.]",
#         },
#     },
# ]
# ---------------------------------------------------------------------------
