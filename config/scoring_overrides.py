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


RULES: list[OverrideRule] = [
    {
        "name": "ds_analytical_llm_floor",
        "description": "GPT-4o-mini under-scores Data Scientist roles with analytical LLM stack",
        "conditions": {
            "title_contains_any": ["data "],
            "tech_stack_any_of": ["llm", "prompt engineering", "a/b testing", "ab testing"],
            "fit_score_lte": 3,
        },
        "action": {
            "set_fit_score": 5,
            "append_reasoning": "[POST-PROCESSING: Score raised to 5 — analytical LLM signals detected; score <= 3 over-penalized for this role type.]",
        },
    },
]
