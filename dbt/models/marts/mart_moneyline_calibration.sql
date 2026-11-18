-- Market win probability vs how often teams actually won, in 5-point buckets.
-- Each game counted once from the favorite's side so buckets run 50% to 100%.
with fav as (
    select
        season,
        greatest(home_win_prob_novig, 1 - home_win_prob_novig) as fav_prob,
        case when home_win_prob_novig >= 0.5 then home_won else 1 - home_won end as fav_won
    from {{ ref('fct_games') }}
    where season >= {{ var('first_moneyline_season') }}
      and home_win_prob_novig is not null
      and home_won is not null
)

select
    least(floor(fav_prob * 20) / 20, 0.95)  as prob_bucket,
    count(*)                                as games,
    avg(fav_prob)                           as avg_market_prob,
    avg(fav_won)                            as actual_win_rate,
    avg(fav_won) - avg(fav_prob)            as gap
from fav
group by 1
order by 1
