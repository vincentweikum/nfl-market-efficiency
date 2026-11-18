-- The margin column has to agree with the two scores.
select game_id from {{ ref('fct_games') }}
where home_score - away_score <> home_margin
