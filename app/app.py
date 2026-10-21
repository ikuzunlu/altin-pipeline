"""
Altın Fiyatı Tahmin Projesi - Streamlit Arayüzü

Çalıştırmak için (proje kök klasöründen):
    streamlit run app/app.py
"""

import sys
from pathlib import Path

import altair as alt
import joblib
import pandas as pd
import streamlit as st
from sqlalchemy import text

PROJE_KOKU = Path(__file__).resolve().parent.parent
DATA_DIR = PROJE_KOKU / "data"
MODEL_DOSYASI = PROJE_KOKU / "models" / "model_gunluk.pkl"

# src/ klasöründeki modülleri (load.py gibi) kullanabilmek için Python'a o klasörü de göster
sys.path.append(str(PROJE_KOKU / "src"))
from load import baglanti_olustur  # noqa: E402

ONS_GRAM = 31.1035  # 1 ons = 31,1035 gram

st.set_page_config(page_title="Altın Fiyatı Tahmin Projesi", layout="wide")


# ================= Veri yükleme =================
@st.cache_data(ttl=600)
def canli_veri_yukle() -> pd.DataFrame:
    """Veritabanından altın ve kur verisini çekip gram altın fiyatını hesaplar."""
    sql = """
        SELECT tarih, sembol, kapanis
        FROM ham_fiyatlar
        WHERE sembol IN ('gold_usd', 'usd_try', 'eur_try')
        ORDER BY tarih
    """
    with baglanti_olustur().connect() as conn:
        uzun = pd.read_sql(text(sql), conn, parse_dates=["tarih"])
    genis = uzun.pivot(index="tarih", columns="sembol", values="kapanis")
    genis = genis.dropna(subset=["gold_usd", "usd_try"])  # Gram altın için ikisi şart
    genis["gram_altin_try"] = genis["gold_usd"] / ONS_GRAM * genis["usd_try"]
    return genis


@st.cache_data(ttl=600)
def tahminleri_yukle() -> pd.DataFrame | None:
    """tahminler tablosunu okur. Tablo henüz yoksa (predict.py hiç çalışmadıysa) None döner."""
    try:
        with baglanti_olustur().connect() as conn:
            return pd.read_sql(text("SELECT * FROM tahminler ORDER BY tahmin_tarihi"),
                               conn, parse_dates=["tahmin_tarihi"])
    except Exception:
        return None


@st.cache_data
def degerlendirme_yukle(ufuk: int) -> pd.DataFrame | None:
    dosya = DATA_DIR / f"degerlendirme_ufuk{ufuk}.csv"
    return pd.read_csv(dosya) if dosya.exists() else None


@st.cache_resource
def model_bilgisi() -> dict | None:
    return joblib.load(MODEL_DOSYASI)["bilgi"] if MODEL_DOSYASI.exists() else None


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
if "eur_try" in canli.columns and canli["eur_try"].notna().any():
    son_euro = canli["eur_try"].dropna()
    col4.metric("Euro/TL", f"{son_euro.iloc[-1]:,.4f}",
                help=f"Son değer tarihi: {son_euro.index[-1]:%d.%m.%Y}")

son_tarih = canli.index[-1]
uyari = "  ·  ⏳ Bugünün kapanışı henüz belli değil, değer anlık" if son_tarih.date() == pd.Timestamp.now(tz="Europe/Istanbul").date() else ""
st.caption(f"Son veri tarihi: {son_tarih:%d.%m.%Y}  ·  Toplam {len(canli):,} işlem günü{uyari}")

donem = st.radio("Dönem", ["Son 3 ay", "Son 1 yıl", "Tümü"], horizontal=True)
gun_sayisi = {"Son 3 ay": 90, "Son 1 yıl": 365, "Tümü": None}[donem]
grafik = canli if gun_sayisi is None else canli[canli.index >= son_tarih - pd.Timedelta(days=gun_sayisi)]

# Altair ile çiziyoruz ki dikey eksen 0'dan başlamasın, hareketler ezik görünmesin
fiyat_grafigi = (
    alt.Chart(grafik.reset_index())
    .mark_line()
    .encode(
        x=alt.X("tarih:T", title=None),
        y=alt.Y("gram_altin_try:Q", title="Gram altın (TL)", scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip("tarih:T", format="%d.%m.%Y"),
                 alt.Tooltip("gram_altin_try:Q", format=",.2f", title="Gram altın")],
    )
)
st.altair_chart(fiyat_grafigi, width="stretch")

st.divider()

# ================= Bölüm 2: Son tahmin =================
st.header("🔮 Model tahmini")

tahminler = tahminleri_yukle()
bilgi = model_bilgisi()

if tahminler is None or tahminler.empty:
    st.info("Henüz tahmin yok. `python src/predict.py` komutunu çalıştır.")
else:
    son_tahmin = tahminler.iloc[-1]
    st.caption(f"{son_tahmin['tahmin_tarihi']:%d.%m.%Y} kapanışından bir sonraki iş günü için")

    col1, col2, col3 = st.columns(3)
    col1.metric("Model tahmini", f"{son_tahmin['tahmin_yuzde']:+.3f}%",
                help="Random Forest'ın ertesi iş günü için gram altın değişim tahmini")
    col2.metric("Baseline: geçmiş ortalama", f"{son_tahmin['baseline_yuzde']:+.3f}%",
                help="2015'ten beri gram altının günlük ortalama değişimi")
    tahmini_fiyat = son_tahmin["gram_fiyat"] * (1 + son_tahmin["tahmin_yuzde"] / 100)
    col3.metric("Tahmin edilen gram altın", f"{tahmini_fiyat:,.2f} TL")

    if bilgi:
        st.caption(f"Model: {bilgi['model_adi']}  ·  Eğitim: {bilgi['egitim_zamani'][:10]}  ·  "
                   f"Veri: {bilgi['veri_baslangic']} – {bilgi['veri_bitis']} "
                   f"({bilgi['egitim_gun_sayisi']:,} gün, {len(bilgi['feature_kolonlari'])} feature)")

    # ---- Canlı karne ----
    st.subheader("📋 Canlı karne")
    st.caption("Her gün yapılan tahmin, ertesi iş günü gerçekleşenle karşılaştırılıyor. "
               "Tahminler bir kez kaydedildikten sonra değiştirilmiyor.")

    sonuclanan = tahminler.dropna(subset=["gerceklesen_yuzde"])
    if sonuclanan.empty:
        st.info("Henüz sonucu belli olan tahmin yok. Karne her iş günü bir satır dolacak.")
    else:
        hata_model = (sonuclanan["tahmin_yuzde"] - sonuclanan["gerceklesen_yuzde"]).abs()
        hata_baseline = (sonuclanan["baseline_yuzde"] - sonuclanan["gerceklesen_yuzde"]).abs()
        model_kazandi = (hata_model < hata_baseline).sum()
        yon_isabeti = ((sonuclanan["tahmin_yuzde"] > 0) == (sonuclanan["gerceklesen_yuzde"] > 0)).mean()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Sonuçlanan tahmin", len(sonuclanan))
        col2.metric("Ortalama hata: model", f"{hata_model.mean():.3f}%")
        col3.metric("Ortalama hata: baseline", f"{hata_baseline.mean():.3f}%")
        col4.metric("Modelin daha iyi olduğu gün", f"{model_kazandi} / {len(sonuclanan)}",
                    help=f"Yön isabeti: %{yon_isabeti * 100:.0f}")

    # ---- Karne tablosu: Her satır = "Bu günün kapanışına bakıp ertesi iş gününü tahmin ettik" ----
    karne = tahminler.sort_values("tahmin_tarihi", ascending=False).head(20).copy()
    karne["gerceklesen_yuzde"] = pd.to_numeric(karne["gerceklesen_yuzde"])

    islem_gunleri = canli.index[canli.index.dayofweek < 5]

    def hedef_gun(tarih):
        """Tahmin gününden sonraki ilk işlem günü. Henüz veri yoksa bir sonraki iş günü."""
        sonraki = islem_gunleri[islem_gunleri > tarih]
        return sonraki[0] if len(sonraki) else tarih + pd.offsets.BDay(1)

    def yon(satir):
        if pd.isna(satir["gerceklesen_yuzde"]):
            return "⏳ bekleniyor"
        ayni_yon = (satir["tahmin_yuzde"] > 0) == (satir["gerceklesen_yuzde"] > 0)
        return "✅ tuttu" if ayni_yon else "❌ tutmadı"

    karne["hedef_gun"] = pd.to_datetime(karne["tahmin_tarihi"].apply(hedef_gun))
    karne["tahmin_fiyat"] = karne["gram_fiyat"] * (1 + karne["tahmin_yuzde"] / 100)
    # Gerçekleşen fiyat: Hedef günün gerçek kapanışı (sonuç belli değilse boş)
    karne["gercek_fiyat"] = [
        canli["gram_altin_try"].get(h) if pd.notna(g) else None
        for h, g in zip(karne["hedef_gun"], karne["gerceklesen_yuzde"])
    ]

    def tl(x):
        return "—" if pd.isna(x) else f"{x:,.2f}"

    def yuzde(x):
        return "—" if pd.isna(x) else f"{x:+.3f}%"

    tablo = pd.DataFrame({
        "Tahmin günü": karne["tahmin_tarihi"].dt.strftime("%d.%m.%Y"),
        "Hedef gün": karne["hedef_gun"].dt.strftime("%d.%m.%Y"),
        "Kapanış (TL)": karne["gram_fiyat"].map(tl),
        "Model tahmini": karne["tahmin_yuzde"].map(yuzde),
        "Tahmin edilen (TL)": karne["tahmin_fiyat"].map(tl),
        "Gerçekleşen (TL)": karne["gercek_fiyat"].map(tl),
        "Gerçekleşen": karne["gerceklesen_yuzde"].map(yuzde),
        "Yön": karne.apply(yon, axis=1),
    })
    st.caption("Tahmin günü: Modelin baktığı kapanış. Hedef gün: Tahmin edilen gün (bir sonraki işlem günü).")
    st.dataframe(tablo, hide_index=True, width="stretch")

st.divider()

# ================= Bölüm 3: Walk-forward değerlendirmesi =================
st.header("🧪 Model değerlendirmesi (walk-forward)")
st.caption("Her test yılı için model sadece o yıldan önceki verilerle eğitildi. "
           "Hata (MAE) ne kadar düşükse o kadar iyi.")

ufuk_secimi = st.radio("Tahmin ufku", ["Günlük (1 iş günü)", "Haftalık (5 iş günü)"], horizontal=True)
ufuk = 1 if ufuk_secimi.startswith("Günlük") else 5
degerlendirme = degerlendirme_yukle(ufuk)

if degerlendirme is None:
    st.info(f"Sonuç dosyası yok. `python src/evaluate.py --ufuk {ufuk}` komutunu çalıştır.")
else:
    duragan = degerlendirme[degerlendirme["yontem"] == "duragan"].set_index("yil")
    seviye = degerlendirme[degerlendirme["yontem"] == "seviye"].set_index("yil")

    karsilastirma = pd.DataFrame({
        "RF – eski (seviye)": seviye["mae_rf"],
        "RF – yeni (durağan)": duragan["mae_rf"],
        "Baseline: değişim olmaz": duragan["mae_base_sifir"],
        "Baseline: geçmiş ortalama": duragan["mae_base_ort"],
    })
    uzun = karsilastirma.reset_index().melt(id_vars="yil", var_name="Yöntem", value_name="MAE (%)")
    mae_grafigi = (
        alt.Chart(uzun)
        .mark_line(point=True)
        .encode(
            x=alt.X("yil:O", title="Test yılı", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("MAE (%):Q", scale=alt.Scale(zero=False)),
            # Baseline'lar gri tonlarda (arka plan), modeller belirgin renklerde
            color=alt.Color("Yöntem:N", legend=alt.Legend(orient="bottom", title=None),
                            scale=alt.Scale(domain=list(karsilastirma.columns),
                                            range=["#E8833A", "#2E86DE", "#9E9E9E", "#5F5F5F"])),
            strokeDash=alt.condition(alt.datum["Yöntem"] == "RF – eski (seviye)",
                                     alt.value([5, 4]), alt.value([0])),
            tooltip=["yil", "Yöntem", alt.Tooltip("MAE (%):Q", format=".3f")],
        )
    )
    st.altair_chart(mae_grafigi, width="stretch")

    n = len(duragan)
    col1, col2, col3 = st.columns(3)
    col1.metric("Eski RF, 'değişim olmaz'ı geçtiği yıl",
                f"{(seviye['mae_rf'] < seviye['mae_base_sifir']).sum()} / {n}")
    col2.metric("Yeni RF, 'geçmiş ortalama'yı geçtiği yıl",
                f"{(duragan['mae_rf'] < duragan['mae_base_ort']).sum()} / {n}")
    col3.metric("Yeni RF, yönde 'hep yükselir'i geçtiği yıl",
                f"{(duragan['yon_rf'] > duragan['yukselis_orani']).sum()} / {n}")

    st.info(
        "📌 **Bulgu:** Fiyat seviyesi feature'ları, ağaç modellerinin eğitimde görmediği "
        "fiyat aralığına çıkamaması yüzünden hiçbir test yılında baseline'ı geçemedi. "
        "Durağan feature'larla (getiriler, ortalamadan sapma) bu hata giderildi. Ancak üç farklı "
        "baseline ile yapılan karşılaştırma, modelin güvenilir bir avantaj sağlamadığını gösteriyor. "
        "Haftalık ufuktaki görünür başarı, TL'nin değer kaybından kaynaklanan yükseliş eğiliminden geliyor."
    )