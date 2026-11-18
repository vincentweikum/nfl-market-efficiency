-- Game-level fact table for analysis.
select * from {{ ref('int_game_markets') }}
