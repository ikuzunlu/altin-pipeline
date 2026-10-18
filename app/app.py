"""
Altın Fiyatı Tahmin Projesi - Streamlit Arayüzü

Çalıştırmak için (proje kök klasöründen):
    streamlit run app/app.py
"""

import json
import sys
from pathlib import Path

import joblib
import pandas as pd
import streamlit as st

PROJE_KOKU = Path(__file__).resolve().parent.parent
DATA_DIR = PROJE_KOKU / "data"
MODELS_DIR = PROJE_KOKU / "models"

# src/ klasöründeki modülleri (load.py gibi) kullanabilmek için Python'a o klasörü de göster
sys.path.append(str(PROJE_KOKU / "src"))
from load import baglanti_olustur  # noqa: E402

ONS_GRAM = 31.1035  # 1 ons = 31,1035 gram

st.set_page_config(page_title="Altın Fiyatı Tahmin Projesi", layout="wide")


# ---- Canlı veri: veritabanından ----
@st.cache_data(ttl=600)
def canli_veri_yukle() -> pd.DataFrame:
    """Veritabanından altın ve kur verisini çekip gram altın fiyatını hesaplar."""
    engine = baglanti_olustur()
    sql = """
        SELECT tarih, sembol, kapanis
        FROM ham_fiyatlar
        WHERE sembol IN ('gold_usd', 'usd_try', 'eur_try')
        ORDER BY tarih
    """
    uzun = pd.read_sql(sql, engine, parse_dates=["tarih"])
    genis = uzun.pivot(index="tarih", columns="sembol", values="kapanis")
    genis = genis.dropna(subset=["gold_usd", "usd_try"])  # Altın ya da kurdan biri yoksa o gün gram altın hesaplanamaz
    genis["gram_altin_try"] = genis["gold_usd"] / ONS_GRAM * genis["usd_try"]
    return genis


# ---- Model ve test sonuçları: dosyalardan ----
@st.cache_resource
def model_yukle():
    model_rf = joblib.load(MODELS_DIR / "model_rf.pkl")
    model_xgb = joblib.load(MODELS_DIR / "model_xgb.pkl")
    X_test = pd.read_csv(DATA_DIR / "X_test.csv", index_col=0, parse_dates=True)
    y_test = pd.read_csv(DATA_DIR / "y_pct_test.csv", index_col=0, parse_dates=True).iloc[:, 0]
    gercek_fiyat = pd.read_csv(DATA_DIR / "gercek_fiyatlar.csv", index_col=0, parse_dates=True).iloc[:, 0]
    with open(DATA_DIR / "sonuclar.json") as f:
        sonuclar = json.load(f)
    return model_rf, model_xgb, X_test, y_test, gercek_fiyat, sonuclar


st.title("🪙 Altın Fiyatı Tahmin Projesi")
st.caption("Veriler her gün yfinance'ten çekilip PostgreSQL'e kaydediliyor.")

# ================= Bölüm 1: Güncel veri =================
st.subheader("📈 Güncel gram altın")

canli = canli_veri_yukle()
son, onceki = canli.iloc[-1], canli.iloc[-2]
gunluk_degisim = (son["gram_altin_try"] / onceki["gram_altin_try"] - 1) * 100

col1, col2, col3, col4 = st.columns(4)
col1.metric("Gram altın (TL)", f"{son['gram_altin_try']:,.2f}", delta=f"{gunluk_degisim:+.2f}%")
col2.metric("Ons altın (USD)", f"{son['gold_usd']:,.2f}")
col3.metric("Dolar/TL", f"{son['usd_try']:,.4f}")
col4.metric("Euro/TL", f"{son['eur_try']:,.4f}")
st.caption(f"Son veri tarihi: {canli.index[-1]:%d.%m.%Y}  ·  Toplam {len(canli):,} işlem günü")

donem = st.radio("Dönem", ["Son 3 ay", "Son 1 yıl", "Tümü"], horizontal=True)
gun_sayisi = {"Son 3 ay": 90, "Son 1 yıl": 365, "Tümü": None}[donem]
if gun_sayisi is None:
    grafik_verisi = canli
else:
    grafik_verisi = canli[canli.index >= canli.index[-1] - pd.Timedelta(days=gun_sayisi)]
st.line_chart(grafik_verisi["gram_altin_try"])

st.divider()

# ================= Bölüm 2: Model değerlendirmesi =================
st.header("🧪 Model değerlendirmesi")
st.caption(
    "Bu bölüm Temmuz 2026'da eğitilen modelin test sonuçlarını gösteriyor. "
    "Model, yeni feature'larla Faz 2'de yeniden eğitilecek."
)

model_rf, model_xgb, X_test, y_test, gercek_fiyat, sonuclar = model_yukle()

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

tab1, tab2, tab3 = st.tabs(["📊 Random Forest", "📊 XGBoost", "🔍 Feature Importance"])

for tab, model, ad in [(tab1, model_rf, "Random Forest"), (tab2, model_xgb, "XGBoost")]:
    with tab:
        st.subheader(f"{ad} — Tahmin vs Gerçek")
        tahmin = model.predict(X_test)
        karsilastirma = pd.DataFrame({
            "Bugünkü fiyat (TL)": gercek_fiyat.values,
            "Gerçek yarınki fiyat (TL)": gercek_fiyat.values * (1 + y_test.values / 100),
            "Tahmin edilen yarınki fiyat (TL)": gercek_fiyat.values * (1 + tahmin / 100),
            "Gerçek % değişim": y_test.values,
            "Tahmin % değişim": tahmin,
        }, index=X_test.index)
        st.line_chart(karsilastirma[["Gerçek yarınki fiyat (TL)", "Tahmin edilen yarınki fiyat (TL)"]])
        st.dataframe(karsilastirma.tail(15).style.format("{:.2f}"), width="stretch")

with tab3:
    st.subheader("Hangi değişken modele ne kadar etki ediyor?")
    onem_df = pd.DataFrame({
        "feature": sonuclar["feature_kolonlari"],
        "Random Forest": model_rf.feature_importances_,
        "XGBoost": model_xgb.feature_importances_,
    }).set_index("feature").sort_values("Random Forest", ascending=False)
    st.bar_chart(onem_df)

st.divider()

# ---- Test setinin son günü için tahmin ----
son_test_tarihi = X_test.index[-1]
st.subheader("🔮 Test setinin son günü için tahmin")
st.caption(
    f"{son_test_tarihi:%d.%m.%Y} tarihli feature'larla yapılmış tahmin. "
    "Güncel veriyle tahmin Faz 2'de eklenecek."
)

son_satir = X_test.iloc[[-1]]
o_gunku_fiyat = gercek_fiyat.iloc[-1]
tahmin_rf_son = model_rf.predict(son_satir)[0]
tahmin_xgb_son = model_xgb.predict(son_satir)[0]

st.metric(f"{son_test_tarihi:%d.%m.%Y} gram altın fiyatı", f"{o_gunku_fiyat:,.2f} TL")
col1, col2 = st.columns(2)
col1.metric("Random Forest — ertesi gün tahmini",
            f"{o_gunku_fiyat * (1 + tahmin_rf_son / 100):,.2f} TL", delta=f"{tahmin_rf_son:+.3f}%")
col2.metric("XGBoost — ertesi gün tahmini",
            f"{o_gunku_fiyat * (1 + tahmin_xgb_son / 100):,.2f} TL", delta=f"{tahmin_xgb_son:+.3f}%")

with st.expander("Kullanılan feature değerlerini gör"):
    st.dataframe(son_satir.T, width="stretch")