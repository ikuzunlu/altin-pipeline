"""
Altın Fiyatı Tahmin Projesi - Streamlit Arayüzü

Çalıştırmak için:
    streamlit run app.py

NOT: Bu dosyayı, notebook'ta kaydettiğin şu dosyalarla AYNI klasöre koy:
    model_rf.pkl, model_xgb.pkl, X_test.csv, y_pct_test.csv, sonuclar.json
"""

import streamlit as st
import pandas as pd
import joblib
import json
from pathlib import Path

PROJE_KOKU = Path(__file__).resolve().parent.parent
DATA_DIR = PROJE_KOKU / "data"
MODELS_DIR = PROJE_KOKU / "models"

st.set_page_config(page_title="Altın Fiyatı Tahmin Projesi", layout="wide")

# ---- Verileri yükle ----
@st.cache_resource
def yukle():
    model_rf = joblib.load(MODELS_DIR / "model_rf.pkl")
    model_xgb = joblib.load(MODELS_DIR / "model_xgb.pkl")
    X_test = pd.read_csv(DATA_DIR / "X_test.csv", index_col=0, parse_dates=True)
    y_test = pd.read_csv(DATA_DIR / "y_pct_test.csv", index_col=0, parse_dates=True).iloc[:, 0]
    gercek_fiyat = pd.read_csv(DATA_DIR / "gercek_fiyatlar.csv", index_col=0, parse_dates=True).iloc[:, 0]
    with open(DATA_DIR / "sonuclar.json") as f:
        sonuclar = json.load(f)
    return model_rf, model_xgb, X_test, y_test, gercek_fiyat, sonuclar

model_rf, model_xgb, X_test, y_test, gercek_fiyat, sonuclar = yukle()

st.title("🪙 Altın Fiyatı Tahmin Projesi")
st.caption("Random Forest ve XGBoost ile günlük gram altın (TL) fiyat değişimi tahmini")

# ---- Üst kısım: model karşılaştırma metrikleri ----
st.subheader("Model karşılaştırması (MAE - Ortalama Mutlak Hata)")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Random Forest", f"{sonuclar['mae_rf']:.3f}%")
col2.metric("XGBoost", f"{sonuclar['mae_xgb']:.3f}%")
col3.metric("Baseline (0%)", f"{sonuclar['mae_baseline_sifir']:.3f}%",
            delta="En iyi", delta_color="off")
col4.metric("Baseline (dünkü devam)", f"{sonuclar['mae_baseline_devam']:.3f}%")

st.info(
    "📌 **Dürüst bulgu:** Hiçbir model, en basit baseline'ı (her zaman "
    "'değişim olmayacak' varsayımı) geçemedi. Bu, günlük altın fiyat "
    "değişiminin kısa vadede büyük ölçüde öngörülemez olduğunu gösteriyor "
    "(etkin piyasa hipotezi ile tutarlı)."
)

st.divider()

# ---- Sekmeler: her model için ayrı detay ----
tab1, tab2, tab3 = st.tabs(["📊 Random Forest", "📊 XGBoost", "🔍 Feature Importance"])

with tab1:
    st.subheader("Random Forest — Tahmin vs Gerçek")
    tahmin_rf = model_rf.predict(X_test)
    tahmin_rf_tl = gercek_fiyat.values * (1 + tahmin_rf / 100)
    gercek_yarin_tl = gercek_fiyat.values * (1 + y_test.values / 100)

    karsilastirma_rf = pd.DataFrame({
        "Bugünkü fiyat (TL)": gercek_fiyat.values,
        "Gerçek yarınki fiyat (TL)": gercek_yarin_tl,
        "Tahmin edilen yarınki fiyat (TL)": tahmin_rf_tl,
        "Gerçek % değişim": y_test.values,
        "Tahmin % değişim": tahmin_rf
    }, index=X_test.index)
    st.line_chart(karsilastirma_rf[["Gerçek yarınki fiyat (TL)", "Tahmin edilen yarınki fiyat (TL)"]])
    st.dataframe(karsilastirma_rf.tail(15).style.format("{:.2f}"), width='stretch')

with tab2:
    st.subheader("XGBoost — Tahmin vs Gerçek")
    tahmin_xgb = model_xgb.predict(X_test)
    tahmin_xgb_tl = gercek_fiyat.values * (1 + tahmin_xgb / 100)
    gercek_yarin_tl = gercek_fiyat.values * (1 + y_test.values / 100)

    karsilastirma_xgb = pd.DataFrame({
        "Bugünkü fiyat (TL)": gercek_fiyat.values,
        "Gerçek yarınki fiyat (TL)": gercek_yarin_tl,
        "Tahmin edilen yarınki fiyat (TL)": tahmin_xgb_tl,
        "Gerçek % değişim": y_test.values,
        "Tahmin % değişim": tahmin_xgb
    }, index=X_test.index)
    st.line_chart(karsilastirma_xgb[["Gerçek yarınki fiyat (TL)", "Tahmin edilen yarınki fiyat (TL)"]])
    st.dataframe(karsilastirma_xgb.tail(15).style.format("{:.2f}"), width='stretch')

with tab3:
    st.subheader("Hangi değişken modele ne kadar etki ediyor?")
    onem_df = pd.DataFrame({
        "feature": sonuclar["feature_kolonlari"],
        "Random Forest": model_rf.feature_importances_,
        "XGBoost": model_xgb.feature_importances_
    }).set_index("feature").sort_values("Random Forest", ascending=False)
    st.bar_chart(onem_df)

st.divider()

# ---- Canlı tahmin bölümü ----
st.subheader("🔮 Bugünün verisiyle canlı tahmin")
st.caption("En son satırdaki (bugünün) feature değerleriyle iki modelin tahminini karşılaştır")

son_satir = X_test.iloc[[-1]]
bugunku_fiyat = gercek_fiyat.iloc[-1]
tahmin_rf_bugun = model_rf.predict(son_satir)[0]
tahmin_xgb_bugun = model_xgb.predict(son_satir)[0]

tahmin_rf_tl_bugun = bugunku_fiyat * (1 + tahmin_rf_bugun / 100)
tahmin_xgb_tl_bugun = bugunku_fiyat * (1 + tahmin_xgb_bugun / 100)

st.metric("Bugünkü gram altın fiyatı", f"{bugunku_fiyat:,.2f} TL")

col1, col2 = st.columns(2)
col1.metric(
    "Random Forest — yarınki tahmin",
    f"{tahmin_rf_tl_bugun:,.2f} TL",
    delta=f"{tahmin_rf_bugun:+.3f}%"
)
col2.metric(
    "XGBoost — yarınki tahmin",
    f"{tahmin_xgb_tl_bugun:,.2f} TL",
    delta=f"{tahmin_xgb_bugun:+.3f}%"
)

with st.expander("Kullanılan feature değerlerini gör"):
    st.dataframe(son_satir.T, width='stretch')