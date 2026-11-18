"""Sanity checks on the analysis output. Skipped until the pipeline has been run."""
import json
from pathlib import Path

import pytest

F = Path(__file__).resolve().parents[1] / "reports" / "findings.json"
pytestmark = pytest.mark.skipif(not F.exists(), reason="run `make all` first")


@pytest.fixture(scope="module")
def f():
    return json.loads(F.read_text())


def test_market_beats_elo(f):
    e = f["elo_vs_market"]
    assert e["brier_market"] < e["brier_elo"]


def test_market_is_near_calibrated(f):
    lo, hi = f["calibration"]["calibration_slope_ci95"]
    assert lo < 1.25 and hi > 0.8


def test_key_numbers(f):
    k = f["key_numbers"]
    assert k["share_margin_3"] > k["share_margin_7"] > k["share_margin_4"]
