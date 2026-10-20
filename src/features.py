"""Ham fiyatlardan model için feature tablosu üretir.

Temel fikir: Modele fiyat SEVİYELERİ değil, DEĞİŞİMLER verilir.
Böylece eğitimde hiç görülmemiş fiyat seviyelerinde de feature'lar tanıdık aralıkta kalır.
"""

import pandas as pd
from sqlalchemy import text

ONS_GRAM = 31.1035
GETIRI_SINIRI = 20.0  # Günlük getiriler ±%20 ile sınırlanır (negatif petrol fiyatı gibi uç durumlar için)
VARLIKLAR = ["gold_usd", "usd_index", "sp500", "oil_usd", "usd_try", "silver_usd", "eur_try"]


def ham_veriyi_oku(engine) -> pd.DataFrame:
    """ham_fiyatlar tablosunu okuyup her varlığın bir kolon olduğu geniş tabloya çevirir."""
    sql = "SELECT tarih, sembol, kapanis FROM ham_fiyatlar ORDER BY tarih"
    with engine.connect() as conn:
        uzun = pd.read_sql(text(sql), conn, parse_dates=["tarih"])
    return uzun.pivot(index="tarih", columns="sembol", values="kapanis")


def gram_altin_tablosu(genis: pd.DataFrame) -> pd.DataFrame:
    """Modelin kullanacağı günleri seçer ve gram altın fiyatını hesaplar."""
    df = genis.dropna(subset=["gold_usd", "usd_try"])          # Gram altın için ikisi şart
    df = df[df.index.dayofweek < 5]                              # Hafta sonu satırlarını at
    # Container'ın saati UTC: Gece 01:00 TR = 22:00 UTC (önceki gün). O yüzden "bugün"ü Türkiye saatiyle alıyoruz
    bugun_tr = pd.Timestamp.now(tz="Europe/Istanbul").normalize().tz_localize(None)
    df = df[df.index < bugun_tr]                                 # Bugün henüz bitmedi, kapanışı yok
    df = df.ffill()                                              # Diğer varlıkların tatil boşlukları
    df["gram_altin_try"] = df["gold_usd"] / ONS_GRAM * df["usd_try"]
    return df


def feature_uret(genis: pd.DataFrame, duragan: bool = True, ufuk: int = 1) -> pd.DataFrame:
    """Feature'ları ve hedefi (ufuk kadar iş günü sonraki gram altın % değişimi) üretir.

    ufuk=1 -> yarın, ufuk=5 -> bir hafta sonra, ufuk=20 -> yaklaşık bir ay sonra

    duragan=True  -> Yeni yöntem: getiriler, ortalamadan sapmalar, yüzde volatilite
    duragan=False -> Eski yöntem: fiyat seviyeleri (karşılaştırma için)
    """
    df = gram_altin_tablosu(genis)
    g = df["gram_altin_try"]
    X = pd.DataFrame(index=df.index)

    if duragan:
        for v in [c for c in VARLIKLAR if c in df.columns] + ["gram_altin_try"]:
            getiri = df[v].pct_change(fill_method=None) * 100
            X[f"getiri_{v}"] = getiri.clip(-GETIRI_SINIRI, GETIRI_SINIRI)
        X["getiri_7g"] = g.pct_change(7, fill_method=None) * 100
        X["ma7_sapma"] = (g / g.rolling(7).mean() - 1) * 100
        X["ma30_sapma"] = (g / g.rolling(30).mean() - 1) * 100
        X["volatilite_7"] = X["getiri_gram_altin_try"].rolling(7).std()
    else:
        for v in ["gold_usd", "usd_index", "sp500", "oil_usd", "usd_try"]:
            X[v] = df[v]
        X["gram_altin_lag1"] = g.shift(1)
        X["gram_altin_lag7"] = g.shift(7)
        X["ma_7"] = g.rolling(7).mean()
        X["ma_30"] = g.rolling(30).mean()
        X["volatilite_7"] = g.rolling(7).std()

    X["hedef"] = (g.shift(-ufuk) / g - 1) * 100
    return X


if __name__ == "__main__":
    from load import baglanti_olustur

    genis = ham_veriyi_oku(baglanti_olustur())
    for duragan in [False, True]:
        X = feature_uret(genis, duragan).dropna()
        ad = "DURAĞAN (yeni)" if duragan else "SEVİYE (eski)"
        print(f"\n=== {ad}: {len(X)} gün, {X.shape[1] - 1} feature ===")
        print(X.drop(columns="hedef").describe().T[["min", "max"]].round(2))