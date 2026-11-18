-- How favorites do against the spread, by size of the spread.
with f as (
    select
        abs(home_spread) as fav_spread,
        case
            when ats_winner = 'push' then null
            when ats_winner = spread_favorite then 1 else 0
        end as fav_covered,
        not is_neutral_site and spread_favorite = 'home' as fav_is_home
    from {{ ref('fct_games') }}
    where spread_favorite <> 'pickem'
)

select
    case
        when fav_spread <= 3   then '0.5-3'
        when fav_spread <= 6.5 then '3.5-6.5'
        when fav_spread <= 9.5 then '7-9.5'
        else '10+'
    end                         as spread_bucket,
    count(*)                    as games,
    count(fav_covered)          as decided_games,
    avg(fav_covered)            as fav_cover_rate
from f
group by 1
order by min(fav_spread)
