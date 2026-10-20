-- Gram altın (TL): Her tam iş günü için tek satır.
-- Python'daki features.gram_altin_tablosu() ile aynı kurallar:
--   1) Altın (USD) ve dolar/TL ikisi de olmalı
--   2) Sadece hafta içi (staging'de süzüldü)
--   3) Bugün hariç: Bugün bitmedi, kapanışı yok

with genis as (
    -- Uzun -> geniş: Her sembol bir kolon (Python'daki pivot)
    select
        tarih,
        max(case when sembol = 'gold_usd' then kapanis end) as altin_usd,
        max(case when sembol = 'usd_try'  then kapanis end) as usd_try,
        max(case when sembol = 'eur_try'  then kapanis end) as eur_try
    from {{ ref('stg_ham_fiyatlar') }}
    group by tarih
),

gram as (
    select
        tarih,
        altin_usd,
        usd_try,
        eur_try,
        altin_usd / {{ var('ons_gram', 31.1035) }} * usd_try as gram_altin_try
    from genis
    where altin_usd is not null
      and usd_try is not null
      -- Veritabanının saati UTC. Gece 01:00 TR = 22:00 UTC (önceki gün), o yüzden Türkiye tarihine çeviriyoruz
      and tarih < (now() at time zone 'Europe/Istanbul')::date
)

select
    tarih,
    altin_usd,
    usd_try,
    eur_try,
    gram_altin_try,
    (gram_altin_try / lag(gram_altin_try) over (order by tarih) - 1) * 100 as gunluk_degisim_yuzde
from gram