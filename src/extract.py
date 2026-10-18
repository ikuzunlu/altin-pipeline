"""yfinance'ten ham piyasa verisini çeker. Hesaplama ya da doldurma yapmaz."""

import pandas as pd
import yfinance as yf

TICKERS = {
    "GC=F": "gold_usd",       # Altın vadeli işlem (ons/USD)
    "DX-Y.NYB": "usd_index",  # Dolar endeksi (DXY)
    "^GSPC": "sp500",         # S&P 500
    "CL=F": "oil_usd",        # Ham petrol
    "USDTRY=X": "usd_try",    # Dolar/TL kuru
    "SI=F": "silver_usd",     # Gümüş vadeli işlem (ons/USD)
    "EURTRY=X": "eur_try",    # Euro/TL kuru
}


def tek_sembol_cek(sembol: str, baslangic: str, bitis: str | None = None) -> pd.Series:
    """Tek bir sembolün günlük kapanış fiyatlarını döndürür."""
    gecmis = yf.Ticker(sembol).history(start=baslangic, end=bitis, interval="1d")

    if gecmis.empty:
        raise ValueError(f"{sembol} için veri gelmedi ({baslangic} -> {bitis})")

    seri = gecmis["Close"]
    seri.index = seri.index.tz_localize(None).normalize()
    seri = seri[~seri.index.duplicated(keep="last")]
    seri.name = TICKERS[sembol]
    return seri


def veri_cek(baslangic: str, bitis: str | None = None) -> pd.DataFrame:
    """Bütün sembolleri çekip tarih index'li tek bir tabloda birleştirir."""
    seriler = {}
    for sembol, isim in TICKERS.items():
        print(f"Çekiliyor: {sembol} ({isim})")
        seriler[isim] = tek_sembol_cek(sembol, baslangic, bitis)

    df = pd.DataFrame(seriler).sort_index()
    df.index.name = "tarih"
    return df


if __name__ == "__main__":
    df = veri_cek("2026-10-01")
    print(df)
    print("\nEksik değer sayıları:")
    print(df.isna().sum())