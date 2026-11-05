"""Smoke tests for the scoring method's configuration in src/score_players.py.

These tests read the CONFIG block directly out of score_players.py with `ast`,
rather than importing the module, because the module runs its pipeline (reads
CSVs, writes scores.csv) at import time. That keeps this file as the single
source of truth for the weights -- nothing here is duplicated by hand, so a
weight that gets edited in score_players.py is checked automatically next run.

Run:  python -m pytest tests/ -v
"""
import ast
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "src" / "score_players.py"


def _load_constants():
    """Parse score_players.py's top-level assignments without executing it."""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            name = node.targets[0]
            if isinstance(name, ast.Name):
                try:
                    # eval (not literal_eval): SCHEMES contains "1 / 3" arithmetic,
                    # which literal_eval rejects. Safe here: this is the project's
                    # own trusted source file, not external input.
                    values[name.id] = eval(
                        compile(ast.Expression(node.value), "<config>", "eval"),
                        {"__builtins__": {}}, {},
                    )
                except Exception:
                    pass  # skip anything that can't be evaluated standalone
    return values


CONST = _load_constants()


def test_score_players_exists():
    assert SCRIPT.exists(), f"expected to find {SCRIPT}"


@pytest.mark.parametrize("scheme_name,weights", CONST["SCHEMES"].items())
def test_scheme_weights_sum_to_one(scheme_name, weights):
    assert len(weights) == 3, f"{scheme_name} should be (individual, team, fair_play)"
    assert sum(weights) == pytest.approx(1.0), f"{scheme_name} weights don't sum to 1.0: {weights}"
    assert all(w >= 0 for w in weights), f"{scheme_name} has a negative weight: {weights}"


@pytest.mark.parametrize("position,metrics", CONST["POS_METRICS"].items())
def test_position_group_metric_weights_sum_to_one(position, metrics):
    assert sum(metrics.values()) == pytest.approx(1.0), (
        f"{position} metric weights don't sum to 1.0: {metrics}"
    )


def test_common_metric_weights_sum_to_one():
    assert sum(CONST["COMMON_METRICS"].values()) == pytest.approx(1.0)


def test_team_parts_sum_to_one():
    assert sum(CONST["TEAM_PARTS"].values()) == pytest.approx(1.0)


def test_stage_score_is_monotonic_non_increasing():
    """A later knockout stage should never score less than an earlier exit."""
    order = [
        "Winner", "Runner-up", "Semi-final", "Quarter-final", "Round of 16",
        "Round of 32", "Knockout playoff round", "League phase",
        "Group stage", "Did not qualify",
    ]
    scores = CONST["STAGE_SCORE"]
    assert set(scores) == set(order), "STAGE_SCORE keys changed -- update this test's order too"
    values = [scores[name] for name in order if name not in ("Knockout playoff round",)]
    assert values == sorted(values, reverse=True), f"stage scores are not monotonic: {values}"
    assert scores["Winner"] == 100
    assert scores["Did not qualify"] == 0


def test_fair_play_floor_is_within_bounds():
    assert 0 <= CONST["FAIR_PLAY_FLOOR"] <= 100


def test_official_scheme_matches_ballon_dor_criteria():
    """The project's headline scheme should be the official 50/30/20 split."""
    assert CONST["SCHEMES"]["official_50_30_20"] == (0.50, 0.30, 0.20)
