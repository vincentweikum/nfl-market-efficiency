import math

import numpy as np
import pandas as pd
import pytest

from nflmarket.elo import Elo, walk_forward
from nflmarket.odds import american_to_payout, american_to_prob, brier, log_loss, remove_vig


def test_american_to_prob():
    assert american_to_prob(-110) == pytest.approx(110 / 210)
    assert american_to_prob(+150) == pytest.approx(0.4)
    assert american_to_prob(-200) == pytest.approx(2 / 3)
    assert math.isnan(american_to_prob(float("nan")))


def test_payout():
    assert american_to_payout(-110) == pytest.approx(100 / 110)
    assert american_to_payout(+250) == pytest.approx(2.5)


def test_remove_vig_sums_to_one():
    h, a = remove_vig(american_to_prob(-150), american_to_prob(+130))
    assert h + a == pytest.approx(1)
    assert h > 0.5 > a


def test_scores():
    y = np.array([1, 0, 1, 0])
    assert brier(np.full(4, 0.5), y) == pytest.approx(0.25)
    assert log_loss(np.full(4, 0.5), y) == pytest.approx(math.log(2))
    assert brier(y, y) == 0


def test_elo_home_field_and_update():
    e = Elo()
    assert e.win_prob("A", "B") > 0.5
    assert e.win_prob("A", "B", neutral=True) == pytest.approx(0.5)
    e.update("A", "B", margin=14)
    assert e.rating("A") > 1500 > e.rating("B")
    assert e.rating("A") + e.rating("B") == pytest.approx(3000)  # zero sum


def test_walk_forward_has_no_lookahead():
    games = pd.DataFrame({
        "game_id": ["g1", "g2"], "season": [2020, 2020],
        "game_date": pd.to_datetime(["2020-09-01", "2020-09-08"]),
        "home_team": ["A", "A"], "away_team": ["B", "B"],
        "home_margin": [30, 3], "is_neutral_site": [False, False],
    })
    p = walk_forward(games)
    assert p["g1"] == pytest.approx(Elo().win_prob("A", "B"))  # first game uses priors only
    assert p["g2"] > p["g1"]                                   # second game sees the blowout
