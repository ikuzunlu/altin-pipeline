"""Walk-forward validation: Eski (seviye) ve yeni (durağan) yöntemi yıl yıl karşılaştırır.

Her test yılı için model SADECE o yıldan önceki verilerle eğitilir.
Modeller üç farklı baseline ile karşılaştırılır.

Kullanım:
    python src/evaluate.py             # Günlük tahmin (yarın)
    python src/evaluate.py --ufuk 5    # Haftalık tahmin (5 iş günü sonra)
"""

import argparse
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


def walk_forward(X: pd.DataFrame, ufuk: int = 1) -> pd.DataFrame:
    """Her yıl için: önceki yıllarla eğit, o yılı test et."""
    feature_kolonlari = [c for c in X.columns if c != "hedef"]
    satirlar = []

    for yil in range(ILK_TEST_YILI, X.index.year.max() + 1):
        # Eğitimin son 'ufuk' gününü at: Onların hedefi test yılına taşıyor (sızıntı olmasın)
        egitim = X[X.index.year < yil].iloc[:-ufuk]
        test = X[X.index.year == yil]
        if test.empty:
            continue

        gecmis_ortalama = egitim["hedef"].mean()
        satir = {
            "yil": yil,
            "test_gun": len(test),
            # Baseline 1: "Değişim olmayacak"
            "mae_base_sifir": test["hedef"].abs().mean(),
            # Baseline 2: "Geçmişte ortalama ne kadar değiştiyse o kadar değişecek"
            "mae_base_ort": mean_absolute_error(test["hedef"], np.full(len(test), gecmis_ortalama)),
            # Baseline 3 (yön için): "Her zaman yükselir" deseydin isabet oranı
            "yukselis_orani": (test["hedef"] > 0).mean(),
        }

        for ad, model in modeller().items():
            model.fit(egitim[feature_kolonlari], egitim["hedef"])
            tahmin = model.predict(test[feature_kolonlari])
            satir[f"mae_{ad}"] = mean_absolute_error(test["hedef"], tahmin)
            satir[f"yon_{ad}"] = (np.sign(tahmin) == np.sign(test["hedef"])).mean()

        satirlar.append(satir)

    return pd.DataFrame(satirlar).set_index("yil")


def ozetle(sonuc: pd.DataFrame, ad: str) -> None:
    n = len(sonuc)
    print(f"\n=== {ad} ===")
    print(sonuc.round(3).to_string())
    print(f"\nOrtalama MAE -> değişim olmaz: {sonuc['mae_base_sifir'].mean():.3f}  |  "
          f"geçmiş ortalama: {sonuc['mae_base_ort'].mean():.3f}")
    for m in ["rf", "xgb"]:
        sifir = (sonuc[f"mae_{m}"] < sonuc["mae_base_sifir"]).sum()
        ort = (sonuc[f"mae_{m}"] < sonuc["mae_base_ort"]).sum()
        yon = (sonuc[f"yon_{m}"] > sonuc["yukselis_orani"]).sum()
        print(f"{m.upper():>4}: MAE {sonuc[f'mae_{m}'].mean():.3f}  |  kazandığı yıl -> "
              f"değişim olmaz: {sifir}/{n}, geçmiş ortalama: {ort}/{n}, yönde 'hep yükselir': {yon}/{n}")


if __name__ == "__main__":
    from features import feature_uret, ham_veriyi_oku
    from load import baglanti_olustur

    parser = argparse.ArgumentParser(description="Walk-forward model değerlendirmesi")
    parser.add_argument("--ufuk", type=int, default=1, help="Kaç iş günü sonrası tahmin edilsin (varsayılan: 1)")
    args = parser.parse_args()

    genis = ham_veriyi_oku(baglanti_olustur())
    tum_sonuclar = []
    print(f"Tahmin ufku: {args.ufuk} iş günü")

    for duragan, ad in [(False, "SEVİYE (eski)"), (True, "DURAĞAN (yeni)")]:
        X = feature_uret(genis, duragan, args.ufuk).dropna()
        sonuc = walk_forward(X, args.ufuk)
        ozetle(sonuc, ad)
        tum_sonuclar.append(sonuc.assign(yontem="duragan" if duragan else "seviye", ufuk=args.ufuk))

    cikti = PROJE_KOKU / "data" / f"degerlendirme_ufuk{args.ufuk}.csv"
    pd.concat(tum_sonuclar).to_csv(cikti)
    print(f"\nKaydedildi: {cikti}")