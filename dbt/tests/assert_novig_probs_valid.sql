-- Any game we assign a probability to must have a sane two-sided price.
select game_id, home_win_prob_novig, moneyline_hold
from {{ ref('fct_games') }}
where home_win_prob_novig is not null
  and (home_win_prob_novig <= 0 or home_win_prob_novig >= 1
       or moneyline_hold < 0 or moneyline_hold > 0.15)
