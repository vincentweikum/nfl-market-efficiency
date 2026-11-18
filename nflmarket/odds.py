"""Odds math. Kept separate from the analysis so it can be unit tested."""
from __future__ import annotations

import numpy as np

BREAKEVEN_MINUS_110 = 110 / 210  # win rate needed to break even at -110, about 52.38%


def american_to_prob(odds: float) -> float:
    """Implied probability from American odds (vig included)."""
    if odds is None or np.isnan(odds):
        return np.nan
    if odds < 0:
        return -odds / (-odds + 100)
    return 100 / (odds + 100)


def american_to_payout(odds: float) -> float:
    """Profit on a 1 unit stake if the bet wins."""
    return 100 / -odds if odds < 0 else odds / 100


def remove_vig(p_home: float, p_away: float) -> tuple[float, float]:
    """Proportional vig removal: scale both sides so they sum to 1."""
    total = p_home + p_away
    return p_home / total, p_away / total


def brier(p: np.ndarray, y: np.ndarray) -> float:
    p, y = np.asarray(p, float), np.asarray(y, float)
    return float(np.mean((p - y) ** 2))


def log_loss(p: np.ndarray, y: np.ndarray, eps: float = 1e-12) -> float:
    p = np.clip(np.asarray(p, float), eps, 1 - eps)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
