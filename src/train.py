"""Günlük tahmin modelini bütün geçmiş veriyle eğitip models/ klasörüne kaydeder.

evaluate.py'de walk-forward ile test ettiğimiz modelin AYNISINI (aynı ayarlarla) eğitiyoruz.
Tek fark: Burada bütün veri eğitime giriyor, çünkü bu model geleceği tahmin edecek.
"""

from datetime import datetime
from pathlib import Path

import joblib

from evaluate import modeller
from features import feature_uret, ham_veriyi_oku
from load import baglanti_olustur

PROJE_KOKU = Path(__file__).resolve().parent.parent
MODEL_DOSYASI = PROJE_KOKU / "models" / "model_gunluk.pkl"
MODEL_ADI = "rf_gunluk"


def egit():
    genis = ham_veriyi_oku(baglanti_olustur())
    X = feature_uret(genis, duragan=True, ufuk=1).dropna()
    feature_kolonlari = [c for c in X.columns if c != "hedef"]

    model = modeller()["rf"]
    model.fit(X[feature_kolonlari], X["hedef"])

    # Modelin "kimlik kartı": Ne zaman, hangi veriyle, hangi feature'larla eğitildi?
    bilgi = {
        "model_adi": MODEL_ADI,
        "egitim_zamani": datetime.now().isoformat(timespec="seconds"),
        "veri_baslangic": X.index.min().date().isoformat(),
        "veri_bitis": X.index.max().date().isoformat(),
        "egitim_gun_sayisi": len(X),
        "feature_kolonlari": feature_kolonlari,
        "gecmis_ortalama": float(X["hedef"].mean()),  # "Geçmiş ortalama" baseline'ı için
    }

    joblib.dump({"model": model, "bilgi": bilgi}, MODEL_DOSYASI)
    return bilgi


if __name__ == "__main__":
    bilgi = egit()
    print(f"Model kaydedildi: {MODEL_DOSYASI}")
    for anahtar, deger in bilgi.items():
        if anahtar != "feature_kolonlari":
            print(f"  {anahtar}: {deger}")
    print(f"  feature sayısı: {len(bilgi['feature_kolonlari'])}")