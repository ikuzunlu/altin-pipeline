"""Ham fiyat verisini PostgreSQL'e upsert eder."""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text

PROJE_KOKU = Path(__file__).resolve().parent.parent
load_dotenv(PROJE_KOKU / ".env")

TABLO_SQL = """
CREATE TABLE IF NOT EXISTS ham_fiyatlar (
    tarih        DATE             NOT NULL,
    sembol       TEXT             NOT NULL,
    kapanis      DOUBLE PRECISION NOT NULL,
    guncellenme  TIMESTAMPTZ      NOT NULL DEFAULT now(),
    PRIMARY KEY (tarih, sembol)
);
"""

UPSERT_SQL = """
INSERT INTO ham_fiyatlar (tarih, sembol, kapanis)
VALUES (:tarih, :sembol, :kapanis)
ON CONFLICT (tarih, sembol)
DO UPDATE SET kapanis     = EXCLUDED.kapanis,
              guncellenme = now();
"""


def baglanti_olustur() -> Engine:
    """.env dosyasındaki DATABASE_URL ile veritabanı bağlantısı kurar."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL bulunamadı. .env dosyasını kontrol et.")
    return create_engine(url)


def genisten_uzuna(df: pd.DataFrame) -> pd.DataFrame:
    """Her varlığın bir kolon olduğu tabloyu, her satırın bir ölçüm olduğu tabloya çevirir."""
    uzun = df.reset_index().melt(id_vars="tarih", var_name="sembol", value_name="kapanis")
    uzun = uzun.dropna(subset=["kapanis"])
    uzun["tarih"] = uzun["tarih"].dt.date
    return uzun


def yukle(df: pd.DataFrame, engine: Engine) -> int:
    """Veriyi ham_fiyatlar tablosuna upsert eder, yüklenen kayıt sayısını döndürür."""
    kayitlar = genisten_uzuna(df).to_dict(orient="records")
    if not kayitlar:  # Yüklenecek bir şey yoksa veritabanına boş liste gönderme
        return 0
    with engine.begin() as conn:
        conn.execute(text(TABLO_SQL))
        conn.execute(text(UPSERT_SQL), kayitlar)
    return len(kayitlar)


if __name__ == "__main__":
    from extract import veri_cek

    engine = baglanti_olustur()
    df = veri_cek("2026-10-01")
    adet = yukle(df, engine)
    print(f"\n{adet} kayıt yüklendi.\n")

    ozet_sql = """
        SELECT sembol, COUNT(*) AS gun_sayisi, MIN(tarih) AS ilk, MAX(tarih) AS son
        FROM ham_fiyatlar
        GROUP BY sembol
        ORDER BY sembol;
    """
    with engine.connect() as conn:
        print(pd.read_sql(text(ozet_sql), conn))