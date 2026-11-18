-- Adds market probabilities (vig removed) and bet outcomes to each game.
with g as (select * from {{ ref('stg_games') }}),

probs as (
    select
        *,
        {{ american_to_prob('home_moneyline') }} as home_raw_prob,
        {{ american_to_prob('away_moneyline') }} as away_raw_prob
    from g
)

select
    *,
    home_raw_prob + away_raw_prob - 1                       as moneyline_hold,
    -- A real two-sided price always has a small positive hold. Anything else means the two
    -- sides were scraped from different books or times, so the probability isn't trustworthy.
    coalesce(home_raw_prob + away_raw_prob - 1 between 0 and 0.15, false) as has_valid_moneyline,
    case when home_raw_prob + away_raw_prob - 1 between 0 and 0.15
         then home_raw_prob / (home_raw_prob + away_raw_prob) end as home_win_prob_novig,
    case when home_margin > 0 then 1 when home_margin < 0 then 0 end as home_won,  -- ties null
    home_margin = 0                                          as is_tie,

    -- against the spread
    home_margin - home_spread                                as home_ats_margin,
    case
        when home_margin - home_spread > 0 then 'home'
        when home_margin - home_spread < 0 then 'away'
        else 'push'
    end                                                      as ats_winner,
    case
        when home_spread > 0 then 'home'
        when home_spread < 0 then 'away'
        else 'pickem'
    end                                                      as spread_favorite,

    -- totals
    total_points - total_line                                as total_vs_line,
    case
        when total_points > total_line then 'over'
        when total_points < total_line then 'under'
        else 'push'
    end                                                      as total_result
from probs
