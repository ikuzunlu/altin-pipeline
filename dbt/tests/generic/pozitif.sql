{% test pozitif(model, column_name) %}
-- Kendi yazdığımız test: Kolonda 0 ya da negatif değer varsa o satırları döndürür.
-- dbt'de kural: Test sorgusu satır döndürürse test BAŞARISIZ.
select *
from {{ model }}
where {{ column_name }} <= 0
{% endtest %}