"""Pipeline: Veritabanındaki son tarihe bakar, eksik günleri çekip yükler."""

import argparse
from datetime import date, timedelta

from sqlalchemy import Engine, text

from extract import veri_cek
from load import TABLO_SQL, baglanti_olustur, yukle

ILK_TARIH = "2015-01-01"  # Veritabanı boşsa buradan başlar
GERI_GUN = 10             # Son tarihten kaç gün geriye gidip tekrar çeksin


def durum(engine: Engine) -> tuple[date | None, date | None, int]:
    """Veritabanındaki ilk tarihi, son tarihi ve toplam kayıt sayısını döndürür."""
    with engine.begin() as conn:
        conn.execute(text(TABLO_SQL))
        sonuc = conn.execute(text("SELECT MIN(tarih), MAX(tarih), COUNT(*) FROM ham_fiyatlar"))
        return sonuc.one()


def baslangici_hesapla(son_tarih: date | None) -> str:
    """Veritabanı boşsa en baştan, doluysa son tarihin biraz gerisinden başlar."""
    if son_tarih is None:
        return ILK_TARIH
    return (son_tarih - timedelta(days=GERI_GUN)).isoformat()


def calistir(baslangic: str | None = None) -> None:
    engine = baglanti_olustur()

    ilk, son, adet = durum(engine)
    print(f"ÖNCE  -> {adet} kayıt, {ilk} ile {son} arası")

    if baslangic is None:
        baslangic = baslangici_hesapla(son)
    print(f"Çekilecek aralık: {baslangic} -> bugün\n")

    df = veri_cek(baslangic)
    gonderilen = yukle(df, engine)

    ilk, son, adet = durum(engine)
    print(f"\n{gonderilen} kayıt gönderildi.")
    print(f"SONRA -> {adet} kayıt, {ilk} ile {son} arası")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Altın veri pipeline'ını çalıştırır.")
    parser.add_argument("--baslangic", help="Elle başlangıç tarihi (YYYY-AA-GG). Verilmezse otomatik hesaplanır.")
    args = parser.parse_args()
    calistir(args.baslangic)