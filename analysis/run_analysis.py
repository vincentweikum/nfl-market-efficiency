"""Statistical analysis on top of the dbt marts.

Run after `dbt build`. Writes charts to reports/figures and every number quoted in
the README to reports/findings.json, so the write-up can always be checked against
the code.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression

from nflmarket.elo import walk_forward
from nflmarket.odds import BREAKEVEN_MINUS_110, american_to_payout, brier, log_loss

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "reports" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
FIRST_ML_SEASON = 2007
# franchises that moved keep one rating history
FRANCHISE = {"OAK": "LV", "SD": "LAC", "STL": "LA"}

INK, MUTED, GRID = "#1f2937", "#6b7280", "#e5e7eb"
BLUE, ORANGE = "#2563eb", "#ea580c"
plt.rcParams.update({
    "figure.dpi": 150, "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
})


def load() -> pd.DataFrame:
    con = duckdb.connect(str(ROOT / "data" / "warehouse.duckdb"), read_only=True)
    df = con.sql("select * from fct_games").df()
    con.close()
    for col in ("home_team", "away_team"):
        df[col] = df[col].replace(FRANCHISE)
    df["game_date"] = pd.to_datetime(df["game_date"])
    return df


def calibration(df: pd.DataFrame) -> dict:
    """Is the closing moneyline calibrated? Fit outcome ~ logit(market prob).

    A slope of 1 means perfectly calibrated. Slope above 1 means the market is too
    timid: favorites should be priced even higher (the favorite-longshot bias).
    """
    m = df[(df.season >= FIRST_ML_SEASON) & df.has_valid_moneyline & df.home_won.notna()].copy()
    p = m.home_win_prob_novig.to_numpy()
    y = m.home_won.to_numpy().astype(int)
    x = np.log(p / (1 - p)).reshape(-1, 1)

    def slope(xs, ys):
        return LogisticRegression(C=1e6).fit(xs, ys).coef_[0][0]

    rng = np.random.default_rng(7)
    boots = []
    for _ in range(500):
        i = rng.integers(0, len(y), len(y))
        boots.append(slope(x[i], y[i]))
    lo, hi = np.percentile(boots, [2.5, 97.5])

    # reliability chart, from the favorite's side
    fav_p = np.maximum(p, 1 - p)
    fav_y = np.where(p >= 0.5, y, 1 - y)
    bins = np.minimum(np.floor(fav_p * 20) / 20, 0.9)
    tab = pd.DataFrame({"b": bins, "p": fav_p, "y": fav_y}).groupby("b").agg(
        n=("y", "size"), p=("p", "mean"), y=("y", "mean"))
    se = np.sqrt(tab.y * (1 - tab.y) / tab.n)

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot([0.5, 1], [0.5, 1], color=MUTED, ls="--", lw=1, label="Perfect calibration")
    ax.errorbar(tab.p, tab.y, yerr=1.96 * se, fmt="o", color=BLUE, ms=6, capsize=3,
                label="Actual win rate (95% CI)")
    for _, r in tab.iterrows():
        ax.annotate(f"n={int(r.n)}", (r.p, r.y), textcoords="offset points", xytext=(8, -12),
                    fontsize=7, color=MUTED)
    ax.set(xlabel="Market win probability for the favorite (vig removed)",
           ylabel="How often the favorite actually won",
           title="Closing moneylines are close to calibrated\n"
                 f"{len(m):,} games, {FIRST_ML_SEASON}-{m.season.max()}")
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG / "moneyline_calibration.png")
    plt.close(fig)

    big = m[np.maximum(p, 1 - p) >= 0.85]
    big_fav_won = np.where(big.home_win_prob_novig >= 0.5, big.home_won, 1 - big.home_won)
    return {
        "games": int(len(m)),
        "dropped_bad_prices": int(((df.season >= FIRST_ML_SEASON) & ~df.has_valid_moneyline).sum()),
        "brier_market": brier(p, y),
        "logloss_market": log_loss(p, y),
        "calibration_slope": float(slope(x, y)),
        "calibration_slope_ci95": [float(lo), float(hi)],
        "big_fav_games": int(len(big)),
        "big_fav_priced": float(np.maximum(big.home_win_prob_novig, 1 - big.home_win_prob_novig).mean()),
        "big_fav_actual": float(np.mean(big_fav_won)),
    }


def elo_vs_market(df: pd.DataFrame) -> dict:
    """Can a public model built from scores beat the closing line?"""
    reg = df.sort_values("game_date")
    elo_p = walk_forward(reg)
    m = reg.join(elo_p, on="game_id")
    m = m[(m.season >= 2009) & m.has_valid_moneyline & m.home_won.notna()]  # 2 seasons of Elo burn-in
    y = m.home_won.astype(int).to_numpy()
    mk, el = m.home_win_prob_novig.to_numpy(), m.elo_home_prob.to_numpy()

    # Does adding Elo to the market help? Fit on early seasons, test on later ones.
    def logit(v):
        return np.log(v / (1 - v))
    X = np.column_stack([logit(mk), logit(el)])
    train = (m.season <= 2018).to_numpy()
    blend = LogisticRegression(C=1e6).fit(X[train], y[train])
    blend_p = blend.predict_proba(X[~train])[:, 1]
    return {
        "games": int(len(m)),
        "brier_market": brier(mk, y), "brier_elo": brier(el, y),
        "logloss_market": log_loss(mk, y), "logloss_elo": log_loss(el, y),
        "accuracy_market": float(np.mean((mk > 0.5) == y)),
        "accuracy_elo": float(np.mean((el > 0.5) == y)),
        "test_seasons": f"2019-{int(m.season.max())}",
        "test_brier_market": brier(mk[~train], y[~train]),
        "test_brier_blend": brier(blend_p, y[~train]),
        "blend_weight_market": float(blend.coef_[0][0]),
        "blend_weight_elo": float(blend.coef_[0][1]),
    }


def against_the_spread(df: pd.DataFrame) -> dict:
    """Favorite cover rates by spread size, and whether any simple rule beats -110."""
    d = df[(df.spread_favorite != "pickem") & (df.ats_winner != "push")].copy()
    d["fav_spread"] = d.home_spread.abs()
    d["fav_covered"] = (d.ats_winner == d.spread_favorite).astype(int)
    d["bucket"] = pd.cut(d.fav_spread, [0, 3, 6.5, 9.5, 30], labels=["0.5-3", "3.5-6.5", "7-9.5", "10+"])

    rows = []
    for b, g in d.groupby("bucket", observed=True):
        k, n = int(g.fav_covered.sum()), len(g)
        dog_rate = 1 - k / n
        # one-sided test: does betting the underdog in this bucket beat the -110 breakeven?
        pval = stats.binomtest(n - k, n, BREAKEVEN_MINUS_110, alternative="greater").pvalue
        rows.append({"bucket": str(b), "games": n, "fav_cover_rate": k / n,
                     "dog_cover_rate": dog_rate, "p_value_dog_beats_vig": pval})
    n_tests = len(rows)
    for r in rows:
        r["p_value_bonferroni"] = min(1.0, r["p_value_dog_beats_vig"] * n_tests)

    fig, ax = plt.subplots(figsize=(6, 4))
    xs = np.arange(len(rows))
    rates = [r["fav_cover_rate"] for r in rows]
    ses = [np.sqrt(r * (1 - r) / row["games"]) for r, row in zip(rates, rows, strict=True)]
    ax.bar(xs, rates, color=BLUE, width=0.6)
    ax.errorbar(xs, rates, yerr=[1.96 * s for s in ses], fmt="none", color=INK, capsize=4, lw=1)
    ax.axhline(0.5, color=MUTED, ls="--", lw=1, label="50%")
    ax.axhline(1 - BREAKEVEN_MINUS_110, color=ORANGE, ls=":", lw=1.5,
               label="Favorite must cover less than this\nfor underdog bets to profit at -110")
    ax.legend(frameon=False, fontsize=7, loc="upper right")
    ax.set_xticks(xs, [f"{r['bucket']}\n(n={r['games']:,})" for r in rows])
    ax.set_ylim(0.4, 0.58)
    ax.set(xlabel="Point spread", ylabel="Favorite cover rate",
           title="Favorites cover a bit under 50%, but not enough to beat the vig")
    fig.tight_layout()
    fig.savefig(FIG / "ats_by_spread.png")
    plt.close(fig)
    return {"overall_fav_cover_rate": float(d.fav_covered.mean()), "games": int(len(d)),
            "buckets": rows, "breakeven_minus_110": BREAKEVEN_MINUS_110}


def home_field(df: pd.DataFrame) -> dict:
    h = df[~df.is_neutral_site].groupby("season").agg(
        actual=("home_margin", "mean"), priced=("home_spread", "mean"), games=("game_id", "size"))
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(h.index, h.actual, color=BLUE, marker="o", ms=3, lw=1.5, label="Actual home margin")
    ax.plot(h.index, h.priced, color=ORANGE, lw=2, label="Average home spread (what the market priced)")
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.axvspan(2019.5, 2020.5, color=GRID, alpha=0.8)
    ax.text(2020, h.actual.max() * 0.95, "2020\nno fans", ha="center", fontsize=7, color=MUTED)
    last = int(h.index.max())
    ax.set(xlabel="Season", ylabel="Points per game",
           title=f"Home field advantage has shrunk, and the market followed it\n({last} is a partial season)")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "home_field.png")
    plt.close(fig)

    early, late = h.loc[1999:2009], h.loc[2015:last - 1]
    cur = df[(df.season == last) & ~df.is_neutral_site]
    cur_decided = cur[cur.ats_winner != "push"]
    return {
        "home_margin_1999_2009": float(np.average(early.actual, weights=early.games)),
        "home_margin_2015_on": float(np.average(late.actual, weights=late.games)),
        "home_spread_1999_2009": float(np.average(early.priced, weights=early.games)),
        "home_spread_2015_on": float(np.average(late.priced, weights=late.games)),
        "current_season": last,
        "current_season_games": int(len(cur)),
        "current_season_through_week": int(cur.week.max()),
        "current_home_cover_rate": float((cur_decided.ats_winner == "home").mean()),
        "current_home_cover_p_value": float(stats.binomtest(
            int((cur_decided.ats_winner == "home").sum()), len(cur_decided), 0.5).pvalue),
    }


def key_numbers(df: pd.DataFrame) -> dict:
    m = df.home_margin.abs()
    share = m.value_counts(normalize=True).sort_index()
    top = share.loc[1:21]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    colors = [ORANGE if i in (3, 7) else BLUE for i in top.index]
    ax.bar(top.index, top.values * 100, color=colors)
    ax.set_xticks(top.index)
    ax.set(xlabel="Final margin (points)", ylabel="% of games",
           title=f"3 and 7 dominate final margins ({len(df):,} games since 1999)")
    fig.tight_layout()
    fig.savefig(FIG / "key_numbers.png")
    plt.close(fig)
    return {"share_margin_3": float(share.get(3, 0)), "share_margin_7": float(share.get(7, 0)),
            "share_margin_2": float(share.get(2, 0)), "share_margin_4": float(share.get(4, 0))}


def moneyline_backtest(df: pd.DataFrame) -> dict:
    """Flat 1 unit bets on every big favorite (85%+) at the actual closing price."""
    m = df[(df.season >= FIRST_ML_SEASON) & df.has_valid_moneyline & df.home_won.notna()].copy()
    fav_home = m.home_win_prob_novig >= 0.5
    m["fav_prob"] = np.where(fav_home, m.home_win_prob_novig, 1 - m.home_win_prob_novig)
    m["fav_odds"] = np.where(fav_home, m.home_moneyline, m.away_moneyline)
    m["fav_won"] = np.where(fav_home, m.home_won, 1 - m.home_won)
    b = m[m.fav_prob >= 0.85]
    profit = np.where(b.fav_won == 1, [american_to_payout(o) for o in b.fav_odds], -1.0)
    return {"bets": int(len(b)), "win_rate": float(b.fav_won.mean()),
            "roi": float(profit.mean()), "units": float(profit.sum()),
            "roi_se": float(profit.std(ddof=1) / np.sqrt(len(profit)))}


def main() -> None:
    df = load()
    findings = {
        "data": {"games": int(len(df)), "first_season": int(df.season.min()),
                 "last_season": int(df.season.max()),
                 "last_game_date": str(df.game_date.max().date())},
        "calibration": calibration(df),
        "elo_vs_market": elo_vs_market(df),
        "against_the_spread": against_the_spread(df),
        "home_field": home_field(df),
        "key_numbers": key_numbers(df),
        "big_favorite_backtest": moneyline_backtest(df),
    }
    out = ROOT / "reports" / "findings.json"
    out.write_text(json.dumps(findings, indent=2))
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
