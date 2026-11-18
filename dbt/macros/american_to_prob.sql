{# Implied probability from American odds, vig still included. #}
{% macro american_to_prob(odds) -%}
    case
        when {{ odds }} is null then null
        when {{ odds }} < 0 then (-{{ odds }}) / ((-{{ odds }}) + 100.0)
        else 100.0 / ({{ odds }} + 100.0)
    end
{%- endmacro %}
