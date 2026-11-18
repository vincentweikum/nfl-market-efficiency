"""A simple walk-forward Elo model built only from final scores.

This is the "public model" baseline: if a model this simple could beat the closing
line, the market would not be efficient. Ratings only ever use games played before
the game being predicted, so there is no look-ahead.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Elo:
    k: float = 20.0
    home_field: float = 48.0          # Elo points, roughly 1.7 points of spread
    revert: float = 1 / 3             # pull toward the mean between seasons
    ratings: dict[str, float] = field(default_factory=dict)

    def rating(self, team: str) -> float:
        return self.ratings.get(team, 1500.0)

    def win_prob(self, home: str, away: str, neutral: bool = False) -> float:
        diff = self.rating(home) - self.rating(away) + (0 if neutral else self.home_field)
        return 1 / (1 + 10 ** (-diff / 400))

    def update(self, home: str, away: str, margin: int, neutral: bool = False) -> None:
        p = self.win_prob(home, away, neutral)
        actual = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
        diff = self.rating(home) - self.rating(away) + (0 if neutral else self.home_field)
        # FiveThirtyEight-style margin of victory multiplier, damped for big favorites
        winner_diff = diff if margin > 0 else -diff
        mov = math.log(abs(margin) + 1) * 2.2 / (winner_diff * 0.001 + 2.2) if margin else 1.0
        shift = self.k * mov * (actual - p)
        self.ratings[home] = self.rating(home) + shift
        self.ratings[away] = self.rating(away) - shift

    def new_season(self) -> None:
        self.ratings = {t: 1500 + (r - 1500) * (1 - self.revert) for t, r in self.ratings.items()}


def walk_forward(games: pd.DataFrame, **kwargs) -> pd.Series:
    """Pre-game Elo home win probability for every game, in date order."""
    elo = Elo(**kwargs)
    out = {}
    season = None
    for row in games.sort_values(["game_date", "game_id"]).itertuples():
        if season is not None and row.season != season:
            elo.new_season()
        season = row.season
        out[row.game_id] = elo.win_prob(row.home_team, row.away_team, row.is_neutral_site)
        elo.update(row.home_team, row.away_team, row.home_margin, row.is_neutral_site)
    return pd.Series(out, name="elo_home_prob")
