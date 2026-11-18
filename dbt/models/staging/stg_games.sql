-- One row per completed NFL game, typed and renamed. Source: nflverse games.csv
with src as (
    select * from read_csv_auto('{{ var("raw_games_path") }}', header = true)
)

select
    game_id,
    season::int                       as season,
    game_type,
    week::int                         as week,
    gameday::date                     as game_date,
    home_team,
    away_team,
    home_score::int                   as home_score,
    away_score::int                   as away_score,
    result::int                       as home_margin,      -- home minus away
    total::int                        as total_points,
    coalesce(overtime, 0)::int = 1    as is_overtime,
    location = 'Neutral'              as is_neutral_site,
    div_game::int = 1                 as is_division_game,
    home_moneyline::double            as home_moneyline,
    away_moneyline::double            as away_moneyline,
    spread_line::double               as home_spread,      -- points home is favored by
    home_spread_odds::double          as home_spread_odds,
    away_spread_odds::double          as away_spread_odds,
    total_line::double                as total_line,
    over_odds::double                 as over_odds,
    under_odds::double                as under_odds,
    home_rest::int                    as home_rest_days,
    away_rest::int                    as away_rest_days,
    roof,
    wind::double                      as wind_mph,
    temp::double                      as temp_f
from src
where result is not null
