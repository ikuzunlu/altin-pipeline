select
    tahmin_tarihi,
    model,
    gram_fiyat,
    tahmin_yuzde,
    baseline_yuzde,
    gerceklesen_yuzde,
    olusturma
from {{ source('ham', 'tahminler') }}