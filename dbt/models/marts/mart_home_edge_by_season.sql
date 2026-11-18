-- Home field advantage per season: what the market priced vs what happened.
select
    season,
    count(*)                    as games,
    avg(home_margin)            as avg_home_margin,
    avg(home_spread)            as avg_home_spread,
    avg(home_ats_margin)        as avg_home_ats_margin,
    avg(case when ats_winner = 'push' then null when ats_winner = 'home' then 1 else 0 end) as home_cover_rate
from {{ ref('fct_games') }}
where not is_neutral_site
group by 1
order by 1
