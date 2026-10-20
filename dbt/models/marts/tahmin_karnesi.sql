-- Canlı karne: Sonucu belli olan her tahmin için hata, yön ve kümülatif başarı.
{{ config(materialized='view') }}   -- View: predict.py gerçekleşeni doldurduğu an burada da görünür

with sonuclanan as (
    select *
    from {{ ref('stg_tahminler') }}
    where gerceklesen_yuzde is not null
),

karne as (
    select
        tahmin_tarihi,
        model,
        gram_fiyat,
        tahmin_yuzde,
        baseline_yuzde,
        gerceklesen_yuzde,
        abs(tahmin_yuzde - gerceklesen_yuzde)   as hata_model,
        abs(baseline_yuzde - gerceklesen_yuzde) as hata_baseline,
        sign(tahmin_yuzde) = sign(gerceklesen_yuzde) as yon_dogru,
        abs(tahmin_yuzde - gerceklesen_yuzde) < abs(baseline_yuzde - gerceklesen_yuzde) as model_daha_iyi
    from sonuclanan
)

select
    *,
    -- Window function'lar: O güne kadar biriken başarı (Faz 1'deki LAG'in akrabası)
    count(*)        over w as sonuclanan_tahmin,
    avg(hata_model) over w as ort_hata_model,
    avg(hata_baseline) over w as ort_hata_baseline,
    avg(case when yon_dogru then 1.0 else 0.0 end) over w * 100 as yon_isabeti_yuzde
from karne
window w as (partition by model order by tahmin_tarihi)