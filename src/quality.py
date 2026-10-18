"""ham_fiyatlar tablosu için veri kalite kontrolleri. Veriyi değiştirmez, sadece raporlar."""

import pandas as pd
from sqlalchemy import Engine, text

from load import baglanti_olustur

# (kontrol adı, SQL sorgusu, sorgu parametreleri)
KONTROLLER = [
    (
        "Pozitif olmayan fiyat",
        """
        SELECT sembol, tarih, kapanis
        FROM ham_fiyatlar
        WHERE kapanis <= 0
        ORDER BY sembol, tarih
        """,
        {},
    ),
    (
        "Uzun boşluk (eksik günler)",
        """
        SELECT sembol, onceki_tarih, tarih, tarih - onceki_tarih AS bosluk_gun
        FROM (
            SELECT sembol, tarih,
                   LAG(tarih) OVER (PARTITION BY sembol ORDER BY tarih) AS onceki_tarih
            FROM ham_fiyatlar
        ) t
        WHERE tarih - onceki_tarih > :max_bosluk
        ORDER BY sembol, tarih
        """,
        {"max_bosluk": 5},
    ),
    (
        "Aşırı günlük hareket",
        """
        SELECT sembol, tarih, onceki_kapanis, kapanis,
               ROUND(((kapanis / onceki_kapanis - 1) * 100)::numeric, 2) AS degisim_yuzde
        FROM (
            SELECT sembol, tarih, kapanis,
                   LAG(kapanis) OVER (PARTITION BY sembol ORDER BY tarih) AS onceki_kapanis
            FROM ham_fiyatlar
        ) t
        WHERE onceki_kapanis > 0
          AND ABS(kapanis / onceki_kapanis - 1) > :max_degisim
        ORDER BY tarih, sembol
        """,
        {"max_degisim": 0.08},
    ),
    (
        "Bayat veri",
        """
        SELECT sembol, MAX(tarih) AS son_tarih, CURRENT_DATE - MAX(tarih) AS gecikme_gun
        FROM ham_fiyatlar
        GROUP BY sembol
        HAVING CURRENT_DATE - MAX(tarih) > :max_gecikme
        ORDER BY sembol
        """,
        {"max_gecikme": 4},
    ),
]


def kontrol_et(engine: Engine) -> dict[str, pd.DataFrame]:
    """Bütün kontrolleri çalıştırır, her kontrolün bulgularını döndürür."""
    sonuclar = {}
    with engine.connect() as conn:
        for ad, sql, parametreler in KONTROLLER:
            sonuclar[ad] = pd.read_sql(text(sql), conn, params=parametreler)
    return sonuclar


if __name__ == "__main__":
    engine = baglanti_olustur()
    for ad, bulgular in kontrol_et(engine).items():
        durum = "[OK] Sorun yok" if bulgular.empty else f"[!] {len(bulgular)} bulgu"
        print(f"\n=== {ad}: {durum} ===")
        if not bulgular.empty:
            print(bulgular.to_string(index=False))