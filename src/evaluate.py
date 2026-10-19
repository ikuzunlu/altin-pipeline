"""Walk-forward validation: Eski (seviye) ve yeni (durağan) yöntemi yıl yıl karşılaştırır.

Her test yılı için model SADECE o yıldan önceki verilerle eğitilir.
Sonuçlar data/degerlendirme.csv dosyasına kaydedilir.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from xgboost import XGBRegressor

PROJE_KOKU = Path(__file__).resolve().parent.parent
ILK_TEST_YILI = 2019


def modeller():
    """Her test yılında sıfırdan eğitilecek modeller."""
    return {
        "rf": RandomForestRegressor(n_estimators=300, max_depth=5, min_samples_leaf=20,
                                    random_state=42, n_jobs=-1),
        "xgb": XGBRegressor(n_estimators=200, max_depth=3, learning_rate=0.03,
                            subsample=0.8, random_state=42),
    }


def walk_forward(X: pd.DataFrame) -> pd.DataFrame:
    """Her yıl için: önceki yıllarla eğit, o yılı test et."""
    feature_kolonlari = [c for c in X.columns if c != "hedef"]
    satirlar = []

    for yil in range(ILK_TEST_YILI, X.index.year.max() + 1):
        egitim = X[X.index.year < yil]
        test = X[X.index.year == yil]
        if test.empty:
            continue

        satir = {"yil": yil, "test_gun": len(test),
                 "mae_baseline": test["hedef"].abs().mean(),          # "Yarın değişim olmayacak"
                 "yukselis_orani": (test["hedef"] > 0).mean()}         # "Her gün yükselir" tahmininin isabeti

        for ad, model in modeller().items():
            model.fit(egitim[feature_kolonlari], egitim["hedef"])
            tahmin = model.predict(test[feature_kolonlari])
            satir[f"mae_{ad}"] = mean_absolute_error(test["hedef"], tahmin)
            satir[f"yon_{ad}"] = (np.sign(tahmin) == np.sign(test["hedef"])).mean()

        satirlar.append(satir)

    return pd.DataFrame(satirlar).set_index("yil")


def ozetle(sonuc: pd.DataFrame, ad: str) -> None:
    print(f"\n=== {ad} ===")
    print(sonuc.round(3).to_string())
    for m in ["rf", "xgb"]:
        kazanilan = (sonuc[f"mae_{m}"] < sonuc["mae_baseline"]).sum()
        print(f"{m.upper():>4}: ort. MAE {sonuc[f'mae_{m}'].mean():.3f}  "
              f"(baseline {sonuc['mae_baseline'].mean():.3f})  ->  "
              f"baseline'dan iyi olduğu yıl: {kazanilan} / {len(sonuc)}")


if __name__ == "__main__":
    from features import feature_uret, ham_veriyi_oku
    from load import baglanti_olustur

    genis = ham_veriyi_oku(baglanti_olustur())
    tum_sonuclar = []

    for duragan, ad in [(False, "SEVİYE (eski)"), (True, "DURAĞAN (yeni)")]:
        X = feature_uret(genis, duragan).dropna()
        sonuc = walk_forward(X)
        ozetle(sonuc, ad)
        tum_sonuclar.append(sonuc.assign(yontem="duragan" if duragan else "seviye"))

    cikti = PROJE_KOKU / "data" / "degerlendirme.csv"
    pd.concat(tum_sonuclar).to_csv(cikti)
    print(f"\nKaydedildi: {cikti}")