"""Günlük tahmin ve model izleme.

Her çalıştığında iki iş yapar:
  1. Son kapanış gününün verisiyle ertesi iş gününü tahmin edip 'tahminler' tablosuna yazar.
  2. Geçmiş tahminlerden sonucu artık belli olanların gerçekleşen değerini doldurur.

Böylece tablo zamanla modelin CANLI performans karnesine dönüşür.
"""

import joblib
import pandas as pd
from sqlalchemy import text

from features import feature_uret, gram_altin_tablosu, ham_veriyi_oku
from load import baglanti_olustur
from train import MODEL_DOSYASI

TABLO_SQL = """
CREATE TABLE IF NOT EXISTS tahminler (
    tahmin_tarihi      DATE             NOT NULL,  -- Tahmin yapılırken kullanılan son kapanış günü
    model              TEXT             NOT NULL,
    gram_fiyat         DOUBLE PRECISION NOT NULL,  -- O günün gram altın fiyatı
    tahmin_yuzde       DOUBLE PRECISION NOT NULL,  -- Modelin ertesi iş günü için tahmini
    baseline_yuzde     DOUBLE PRECISION NOT NULL,  -- "Geçmiş ortalama" baseline'ının tahmini
    gerceklesen_yuzde  DOUBLE PRECISION,           -- Ertesi iş günü belli olunca doldurulur
    olusturma          TIMESTAMPTZ      NOT NULL DEFAULT now(),
    PRIMARY KEY (tahmin_tarihi, model)
);
"""

# DİKKAT: Burada upsert DEĞİL, "DO NOTHING" var. Bir kez yapılmış tahmin asla değiştirilmez.
EKLE_SQL = """
INSERT INTO tahminler (tahmin_tarihi, model, gram_fiyat, tahmin_yuzde, baseline_yuzde)
VALUES (:tahmin_tarihi, :model, :gram_fiyat, :tahmin_yuzde, :baseline_yuzde)
ON CONFLICT (tahmin_tarihi, model) DO NOTHING;
"""

ACIK_TAHMINLER_SQL = "SELECT tahmin_tarihi FROM tahminler WHERE gerceklesen_yuzde IS NULL"

GERCEKLESEN_SQL = """
UPDATE tahminler
SET gerceklesen_yuzde = :gerceklesen_yuzde
WHERE tahmin_tarihi = :tahmin_tarihi AND gerceklesen_yuzde IS NULL;
"""

KARNE_SQL = """
SELECT tahmin_tarihi, gram_fiyat,
       ROUND(tahmin_yuzde::numeric, 3)      AS tahmin,
       ROUND(baseline_yuzde::numeric, 3)    AS baseline,
       ROUND(gerceklesen_yuzde::numeric, 3) AS gerceklesen,
       ROUND(ABS(tahmin_yuzde - gerceklesen_yuzde)::numeric, 3)   AS hata_model,
       ROUND(ABS(baseline_yuzde - gerceklesen_yuzde)::numeric, 3) AS hata_baseline
FROM tahminler
ORDER BY tahmin_tarihi DESC
LIMIT 10;
"""


def tahmin_et_ve_izle():
    paket = joblib.load(MODEL_DOSYASI)
    model, bilgi = paket["model"], paket["bilgi"]
    feature_kolonlari = bilgi["feature_kolonlari"]

    engine = baglanti_olustur()
    genis = ham_veriyi_oku(engine)
    X = feature_uret(genis, duragan=True, ufuk=1)
    gram = gram_altin_tablosu(genis)["gram_altin_try"]

    # 1) Yeni tahmin: Feature'ları tam olan EN SON gün (hedefi henüz bilinmiyor, olması gereken de bu)
    son_gun = X[feature_kolonlari].dropna().iloc[[-1]]
    tahmin_tarihi = son_gun.index[0]
    kayit = {
        "tahmin_tarihi": tahmin_tarihi.date(),
        "model": bilgi["model_adi"],
        "gram_fiyat": float(gram.loc[tahmin_tarihi]),
        "tahmin_yuzde": float(model.predict(son_gun)[0]),
        "baseline_yuzde": bilgi["gecmis_ortalama"],
    }

    with engine.begin() as conn:
        conn.execute(text(TABLO_SQL))
        sonuc = conn.execute(text(EKLE_SQL), kayit)
        yeni_mi = sonuc.rowcount == 1

        # 2) İzleme: Sonucu artık belli olan eski tahminleri doldur
        acik = [r[0] for r in conn.execute(text(ACIK_TAHMINLER_SQL))]
        gerceklesenler = X["hedef"].dropna()
        guncellemeler = [
            {"tahmin_tarihi": t, "gerceklesen_yuzde": float(gerceklesenler.loc[pd.Timestamp(t)])}
            for t in acik if pd.Timestamp(t) in gerceklesenler.index
        ]
        if guncellemeler:
            conn.execute(text(GERCEKLESEN_SQL), guncellemeler)

    durum = "kaydedildi" if yeni_mi else "zaten vardı, değiştirilmedi"
    print(f"Tahmin ({tahmin_tarihi:%d.%m.%Y} kapanışından ertesi iş gününe): "
          f"{kayit['tahmin_yuzde']:+.3f}%  ->  {durum}")
    print(f"Sonucu yeni belli olan tahmin sayısı: {len(guncellemeler)}\n")

    with engine.connect() as conn:
        print(pd.read_sql(text(KARNE_SQL), conn).to_string(index=False))


if __name__ == "__main__":
    tahmin_et_ve_izle()