-- Ham fiyatlar: Hafta sonu satırları atılır, her satıra benzersiz bir anahtar eklenir.
select
    tarih,
    sembol,
    kapanis,
    tarih || '_' || sembol as anahtar,
    guncellenme
from {{ source('ham', 'ham_fiyatlar') }}
where extract(isodow from tarih) < 6      -- 6 = Cumartesi, 7 = Pazar