-- How often each final margin happens. Shows the "key numbers" 3 and 7.
select
    abs(home_margin) as margin,
    count(*)         as games,
    count(*) / sum(count(*)) over () as share
from {{ ref('fct_games') }}
group by 1
order by 1
