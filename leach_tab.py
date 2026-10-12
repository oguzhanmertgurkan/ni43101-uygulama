"""
Liç Kinetiği sekmesi (Streamlit arayüzü)
=========================================
Hesaplar leach_kinetics_model.py içindedir; bu dosya yalnızca veri girişi ve gösterimi yapar.
app.py içinden leach_tab.render(rota) olarak çağrılır.
"""

import io

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from capex_scaling_model import estimate_area_capex, ALAN_TURLERI
from leach_kinetics_model import (
    MODELLER,
    ENCHI_CIL_REFERANS,
    modelleri_uydur,
    sure_hesapla,
    arrhenius,
    cil_boyutlandirma,
    reaktif_tuketimi,
    ornek_sentetik_veri,
)

_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
_SUTUN_ADAYLARI = {
    "sure": ("sure", "time", "zaman", "hour", "saat", "day", "gun"),
    "x": ("ekstr", "extr", "recov", "verim", "dissol", "cozun"),
    "T": ("sicak", "temp"),
}
CIL_ROTASI_ALANLARI = ["kirma", "ogutme", "on_koyulastirma", "cil", "adr", "reaktif"]


def _norm(ad: str) -> str:
    return str(ad).translate(_TR).lower()


def _sayi(seri: pd.Series) -> pd.Series:
    """Virgüllü ondalıkları da kabul ederek sayıya çevirir; çevrilemeyen hücre NaN olur."""
    if not pd.api.types.is_numeric_dtype(seri):
        seri = seri.astype(str).str.strip().str.replace(",", ".", regex=False)
    return pd.to_numeric(seri, errors="coerce")


def _otomatik_sutun(sutunlar, anahtarlar, haric=()):
    for s in sutunlar:
        if s in haric:
            continue
        n = _norm(s)
        if any(a in n for a in anahtarlar):
            return s
    return None


def dosya_oku(veri: bytes, ad: str) -> pd.DataFrame:
    """CSV (virgül/noktalı virgül/sekme ayracı otomatik) veya Excel dosyasını DataFrame'e okur."""
    if ad.lower().endswith((".xlsx", ".xlsm", ".xls")):
        return pd.read_excel(io.BytesIO(veri))
    metin = veri.decode("utf-8-sig", errors="replace")
    return pd.read_csv(io.StringIO(metin), sep=None, engine="python")


def _sablon_csv() -> str:
    o = ornek_sentetik_veri()
    satirlar = ["sure_h,ekstraksiyon_pct,sicaklik_C"]
    satirlar += [f"{t},{x}," for t, x in zip(o["sure_h"], o["ekstraksiyon_pct"])]
    return "\n".join(satirlar) + "\n"


def _veri_al(rota: str):
    """Kullanıcıdan veriyi alır; (DataFrame, zaman birimi) veya (None, birim) döndürür."""
    varsayilan_birim = 1 if rota in ("yigin_cu", "yigin_au") else 0
    birim = st.radio("Zaman birimi", ["saat (h)", "gün"], index=varsayilan_birim, horizontal=True,
                     key="lic_birim")
    kisa = "h" if birim.startswith("saat") else "gün"
    secim = st.radio("Veri girişi", ["Tabloya yaz", "Dosya yükle (CSV / Excel)", "Örnek (sentetik) veriyle dene"],
                     horizontal=True, key="lic_giris")
    if secim.startswith("Örnek"):
        st.warning("Bu veri yapay üretildi (birinci derece eğri, Xmax=92, k=0.12). Gerçek bir ölçüm DEĞİLDİR; "
                   "yalnızca arayüzü denemek içindir.")
        o = ornek_sentetik_veri()
        return pd.DataFrame({"sure": o["sure_h"], "x": o["ekstraksiyon_pct"], "T": np.nan}), kisa
    if secim.startswith("Tabloya"):
        st.caption(f"Her satır bir ölçüm. Süre ({kisa}) ve ekstraksiyon (%) zorunlu; sıcaklık (°C) isteğe bağlı "
                   "(birden fazla sıcaklıkta deney varsa doldur, Arrhenius analizi yapılır).")
        bos = pd.DataFrame({"Süre": [np.nan] * 8, "Ekstraksiyon (%)": [np.nan] * 8, "Sıcaklık (°C)": [np.nan] * 8})
        d = st.data_editor(bos, num_rows="dynamic", use_container_width=True, key="lic_tablo")
        return pd.DataFrame({"sure": _sayi(d["Süre"]), "x": _sayi(d["Ekstraksiyon (%)"]),
                             "T": _sayi(d["Sıcaklık (°C)"])}), kisa
    st.caption("Dosyada şu sütunlar bulunmalı: süre, ekstraksiyon (%) ve istersen sıcaklık (°C). "
               "Sütun adları Türkçe veya İngilizce olabilir; aşağıda eşleşmeyi kontrol edebilirsin. "
               "Ondalık ayracı nokta veya virgül olabilir. İlk sayfa okunur.")
    st.download_button("Örnek şablonu indir (sentetik veri)", _sablon_csv(), "ornek_sablon_SENTETIK.csv",
                       "text/csv", key="lic_sablon")
    f = st.file_uploader("Dosya", type=["csv", "xlsx", "xls"], key="lic_dosya")
    if f is None:
        return None, kisa
    try:
        ham = dosya_oku(f.getvalue(), f.name)
    except Exception as e:  # noqa: BLE001 - kullanıcıya okunabilir mesaj
        st.error(f"Dosya okunamadı: {e}")
        return None, kisa
    sutunlar = [str(c) for c in ham.columns]
    ham.columns = sutunlar
    otom_t = _otomatik_sutun(sutunlar, _SUTUN_ADAYLARI["sure"])
    otom_x = _otomatik_sutun(sutunlar, _SUTUN_ADAYLARI["x"], haric=(otom_t,))
    otom_T = _otomatik_sutun(sutunlar, _SUTUN_ADAYLARI["T"], haric=(otom_t, otom_x))
    c1, c2, c3 = st.columns(3)
    sec_t = c1.selectbox("Süre sütunu", sutunlar, index=sutunlar.index(otom_t) if otom_t else 0, key="lic_s_t")
    sec_x = c2.selectbox("Ekstraksiyon sütunu", sutunlar,
                         index=sutunlar.index(otom_x) if otom_x else min(1, len(sutunlar) - 1), key="lic_s_x")
    sec_T = c3.selectbox("Sıcaklık sütunu (isteğe bağlı)", ["(yok)"] + sutunlar,
                         index=(sutunlar.index(otom_T) + 1) if otom_T else 0, key="lic_s_T")
    d = pd.DataFrame({"sure": _sayi(ham[sec_t]), "x": _sayi(ham[sec_x]),
                      "T": _sayi(ham[sec_T]) if sec_T != "(yok)" else np.nan})
    st.dataframe(ham.head(12), use_container_width=True)
    return d, kisa


def _egri_grafigi(gruplar, secilen_modeller, kisa):
    """gruplar: {etiket: (t, x, [KinetikSonuc...])}"""
    nokta_satir, egri_satir = [], []
    for etiket, (t, x, sonuclar) in gruplar.items():
        for a, b in zip(t, x):
            nokta_satir.append({"Süre": a, "Ekstraksiyon (%)": b, "Seri": etiket})
        tg = np.linspace(0, float(np.max(t)) * 1.1, 120)
        for s in sonuclar:
            if s.model not in secilen_modeller:
                continue
            seri = s.model if len(gruplar) == 1 else etiket
            for a, b in zip(tg, s.tahmin(tg)):
                egri_satir.append({"Süre": a, "Ekstraksiyon (%)": b, "Seri": seri, "Model": s.model})
    egri = alt.Chart(pd.DataFrame(egri_satir)).mark_line().encode(
        x=alt.X("Süre:Q", title=f"Süre ({kisa})"),
        y=alt.Y("Ekstraksiyon (%):Q", scale=alt.Scale(domain=[0, 100])),
        color=alt.Color("Seri:N"), detail="Model:N")
    nokta = alt.Chart(pd.DataFrame(nokta_satir)).mark_point(filled=True, size=70).encode(
        x="Süre:Q", y="Ekstraksiyon (%):Q", color=alt.Color("Seri:N"),
        tooltip=["Seri", "Süre", "Ekstraksiyon (%)"])
    st.altair_chart((egri + nokta).properties(height=380), use_container_width=True)


def _sonuc_tablosu(sonuclar):
    satirlar = []
    for s in sonuclar:
        p = s.parametreler
        satirlar.append({
            "Model": s.ad,
            "k (1/süre)": f"{p['k']:.4g}",
            "Xmax (%)": f"{p['Xmax']:.1f}",
            "n": f"{p['n']:.2f}" if "n" in p else "-",
            "RMSE (puan)": f"{s.rmse:.2f}",
            "R²": f"{s.r2:.4f}",
            "AICc": "-" if s.aicc is None else f"{s.aicc:.1f}",
            "Uyarı": s.uyari or "-",
        })
    return pd.DataFrame(satirlar)


def render(rota: str):
    st.header("Liç Kinetiği ve CIL Boyutlandırma")
    st.markdown(
        "Deney verisinden (süre ve ekstraksiyon) liç kinetiği modelleri uydurur, hangi modelin veriyi daha iyi "
        "açıkladığını gösterir, hedef ekstraksiyon için gereken süreyi hesaplar. Siyanür liçi (CIL/CIP) rotasında "
        "tank hacmi ve reaktif tüketimini de hesaplar.\n\n"
        "**Ne girmelisin:** Her ölçüm için süre ve ekstraksiyon (%). Birden fazla sıcaklıkta deney yaptıysan "
        "sıcaklık (°C) sütununu da doldur. En az 4 farklı süre noktası gerekir, 6-8 nokta önerilir."
    )
    if rota == "gravite":
        st.info("Gravite rotası için henüz ayrı bir hesap sekmesi yok. Bu sekme liç içindir.")
    if rota in ("yigin_cu", "yigin_au"):
        st.info("Yığın liçi için kolon testi verisini (süre gün olarak) kinetik analize verebilirsin. Yığın boyutlandırma "
                "(pad alanı, sulama debisi) henüz yok, aşağıdaki tank hesabı CIL devresine özgüdür.")

    d, kisa = _veri_al(rota)
    if d is None:
        st.info("Analiz için veri bekleniyor.")
        return
    d = d.dropna(subset=["sure", "x"])
    if d.empty:
        st.info("Süre ve ekstraksiyon sütunlarında geçerli sayı bulunamadı.")
        return

    st.subheader("Kinetik model uydurma")
    c1, c2 = st.columns([1, 2])
    xmax_scm = c1.number_input("Ulaşılabilir maksimum ekstraksiyon (%) (büzülen çekirdek modelleri için)",
                               min_value=1.0, max_value=100.0, value=100.0, step=1.0,
                               help="X, bu değere bölünerek normalize edilir. Bilmiyorsan 100 bırak. "
                                    "Birinci derece ve Avrami modelleri bu değeri veriden kendisi bulur.")
    secilen = c2.multiselect("Modeller", list(MODELLER), default=list(MODELLER),
                             format_func=lambda m: MODELLER[m], key="lic_modeller")
    if not secilen:
        st.warning("En az bir model seç.")
        return

    d = d.copy()
    d["etiket"] = d["T"].apply(lambda v: "Sıcaklık yok" if pd.isna(v) else f"{v:g} °C")
    gruplar = {}
    for etiket, g in d.groupby("etiket", sort=False):
        try:
            s = modelleri_uydur(g["sure"].values, g["x"].values, xmax_scm=xmax_scm, modeller=secilen)
        except ValueError as e:
            st.error(f"{etiket}: {e}")
            continue
        gruplar[etiket] = (g["sure"].values, g["x"].values, s)
    if not gruplar:
        return

    for etiket, (_, _, s) in gruplar.items():
        if len(gruplar) > 1:
            st.markdown(f"**{etiket}**")
        st.dataframe(_sonuc_tablosu(s), hide_index=True, use_container_width=True)
        st.caption(f"En iyi model (AICc, yoksa RMSE'ye göre): {s[0].ad}")
    _egri_grafigi(gruplar, secilen, kisa)
    st.caption("Küçük veri setlerinde birden fazla model benzer iyi uyum verebilir; model seçimini yalnızca "
               "istatistiğe değil, mekanizmaya (kimyasal kontrol, difüzyon) ve ek deneylere dayandır. "
               "Xmax %100'e dayanıyorsa veri henüz platoya ulaşmamış demektir.")

    # --- Hedef ekstraksiyona ulaşma süresi ---
    st.subheader("Hedef ekstraksiyon için süre")
    hedef = st.number_input("Hedef ekstraksiyon (%)", min_value=1.0, max_value=99.9, value=80.0, step=1.0,
                            key="lic_hedef")
    satir = []
    for etiket, (_, _, s) in gruplar.items():
        for r in s:
            sure = sure_hesapla(r, hedef)
            satir.append({"Seri": etiket, "Model": r.ad,
                          f"Gereken süre ({kisa})": "ulaşılamaz (Xmax altında)" if sure is None else f"{sure:.1f}"})
    st.dataframe(pd.DataFrame(satir), hide_index=True, use_container_width=True)

    # --- Arrhenius ---
    sicakli = [e for e in gruplar if e != "Sıcaklık yok"]
    if len(sicakli) >= 3:
        st.subheader("Sıcaklık etkisi (Arrhenius)")
        ortalama_rmse = {m: np.mean([[r.rmse for r in s if r.model == m][0] for (_, _, s) in
                                      (gruplar[e] for e in sicakli)]) for m in secilen}
        varsayilan = min(ortalama_rmse, key=ortalama_rmse.get)
        sec_m = st.selectbox("Arrhenius için model", secilen, index=secilen.index(varsayilan),
                             format_func=lambda m: MODELLER[m], key="lic_arr_model")
        sic_v, k_v = [], []
        for e in sicakli:
            r = [r for r in gruplar[e][2] if r.model == sec_m][0]
            sic_v.append(float(e.replace(" °C", "")))
            k_v.append(r.parametreler["k"])
        try:
            a = arrhenius(sic_v, k_v)
            m1, m2 = st.columns(2)
            m1.metric("Aktivasyon enerjisi Ea", f"{a.ea_kj_mol:.1f} kJ/mol")
            m2.metric("R² (ln k - 1/T)", f"{a.r2:.3f}")
            st.caption(a.yorum)
        except ValueError as e:
            st.warning(str(e))
    elif len(sicakli) > 0:
        st.caption("Arrhenius analizi için en az 3 farklı sıcaklıkta deney gerekir.")

    # --- CIL tasarım ---
    st.divider()
    st.subheader("CIL tank boyutlandırma ve reaktif tüketimi")
    if rota != "siyanur":
        st.caption("Bu bölüm siyanür liçi (CIL) rotası içindir. Yine de hesabı kullanabilirsin.")
    ref = ENCHI_CIL_REFERANS
    with st.expander("Raporlardan referans tasarım değerleri (Enchi PFS)"):
        st.dataframe(pd.DataFrame({
            "Senaryo": ref["senaryolar"],
            "Bekleme süresi (h)": ref["bekleme_suresi_h"],
            "Katı oranı (% w/w)": ref["katı_orani_pct_w"],
            "NaCN (kg/t)": ref["nacn_kg_t"],
            "Kireç (kg/t)": ref["kirec_kg_t"],
        }), hide_index=True, use_container_width=True)
        st.caption(f"Kaynak: {ref['kaynak']}. Devre: {ref['tank_adedi']} CIL tankı, tek hat. "
                   f"Öğütme devresi kullanılabilirliği %{ref['kullanilabilirlik_ogutme_pct']}. {ref['not']}")

    a1, a2, a3, a4 = st.columns(4)
    tpd = a1.number_input("Tasarım besleme (kuru t/gün)", min_value=100.0, max_value=200_000.0, value=15_000.0,
                          step=500.0, key="lic_tpd")
    kull = a2.number_input("Kullanılabilirlik (%)", min_value=50.0, max_value=100.0, value=91.3, step=0.5,
                           help="Başlangıç değeri Enchi PFS'teki öğütme devresi kullanılabilirliğidir.",
                           key="lic_kull")
    kati = a3.number_input("Pulp katı oranı (% w/w)", min_value=20.0, max_value=70.0, value=45.0, step=1.0,
                           key="lic_kati")
    sg = a4.number_input("Katı özgül ağırlığı (t/m³)", min_value=1.5, max_value=6.0, value=2.7, step=0.1,
                         help="Başlangıç değeri örnektir; kendi cevherinin ölçümünü gir.", key="lic_sg")

    b1, b2, b3, b4 = st.columns(4)
    kaynak = b1.radio("Bekleme süresi", ["Kinetik sonuçtan", "Elle gir"], key="lic_sure_kaynak")
    carpan = b2.number_input("Ölçek büyütme çarpanı", min_value=1.0, max_value=3.0, value=1.0, step=0.05,
                             help="Laboratuvar süresini tesise taşırken kullanacağın güvenlik çarpanı. "
                                  "Bu bir tasarım kararıdır; kaynak raporlardan alınmış bir değer değildir.",
                             key="lic_carpan")
    tank = b3.number_input("Tank adedi", min_value=1, max_value=20, value=ref["tank_adedi"], step=1,
                           help="Başlangıç değeri Enchi PFS'teki tank adedidir.", key="lic_tank")
    doluluk = b4.number_input("Doluluk oranı", min_value=0.5, max_value=1.0, value=0.9, step=0.01,
                              help="Pulp hacmi / tank geometrik hacmi.", key="lic_doluluk")

    bekleme = None
    if kaynak == "Kinetik sonuçtan":
        ilk = next(iter(gruplar.values()))
        en_iyi = ilk[2][0]
        s_h = sure_hesapla(en_iyi, hedef)
        if s_h is None:
            st.warning("Seçili hedefe model Xmax altında kaldığı için ulaşamıyor. Hedefi düşür ya da süreyi elle gir.")
        else:
            if kisa == "gün":
                s_h *= 24.0
            bekleme = s_h * carpan
            st.caption(f"Kullanılan model: {en_iyi.ad}. %{hedef:g} için {s_h:.1f} h × {carpan:g} = {bekleme:.1f} h.")
    if bekleme is None:
        bekleme = st.number_input("CIL bekleme süresi (h)", min_value=1.0, max_value=200.0, value=24.0, step=1.0,
                                  key="lic_bekleme")
    try:
        r = cil_boyutlandirma(tpd, kull / 100.0, kati, sg, bekleme, int(tank), doluluk)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Katı debisi", f"{r['katı_debisi_t_h']:,.0f} t/h")
        m2.metric("Pulp debisi", f"{r['pulp_debisi_m3_h']:,.0f} m³/h")
        m3.metric("Toplam tank hacmi", f"{r['toplam_geometrik_hacim_m3']:,.0f} m³")
        m4.metric("Tank başına hacim", f"{r['tank_basina_hacim_m3']:,.0f} m³")
        st.caption(f"Tank başına bekleme süresi: {r['tank_basina_bekleme_h']:.1f} h. "
                   "Tank çapı/yüksekliği ve karbon envanteri bu hesapta yok.")
    except ValueError as e:
        st.error(str(e))

    st.markdown("**Reaktif tüketimi**")
    r1, r2, r3, r4 = st.columns(4)
    nacn = r1.number_input("NaCN (kg/t cevher)", min_value=0.0, max_value=10.0, value=1.00, step=0.05,
                           help="Başlangıç değeri Enchi PFS oksit (P80 53 µm) senaryosudur. Kendi test sonucunu gir.",
                           key="lic_nacn")
    kirec = r2.number_input("Kireç (kg/t cevher)", min_value=0.0, max_value=30.0, value=2.54, step=0.1,
                            help="Başlangıç değeri Enchi PFS oksit (P80 53 µm) senaryosudur.", key="lic_kirec")
    f_nacn = r3.number_input("NaCN fiyatı ($/t)", min_value=0.0, value=0.0, step=50.0,
                             help="Fiyatı sen gir; sıfırsa maliyet hesaplanmaz.", key="lic_fnacn")
    f_kirec = r4.number_input("Kireç fiyatı ($/t)", min_value=0.0, value=0.0, step=10.0, key="lic_fkirec")
    rt = reaktif_tuketimi(tpd, nacn, kirec, f_nacn, f_kirec)
    q1, q2, q3 = st.columns(3)
    q1.metric("NaCN", f"{rt['nacn_t_gun']:,.1f} t/gün", f"{rt['nacn_t_yil']:,.0f} t/yıl", delta_color="off")
    q2.metric("Kireç", f"{rt['kirec_t_gun']:,.1f} t/gün", f"{rt['kirec_t_yil']:,.0f} t/yıl", delta_color="off")
    if "toplam_usd_t_cevher" in rt:
        q3.metric("Reaktif maliyeti", f"${rt['toplam_usd_t_cevher']:,.2f} /t cevher")

    # --- CAPEX bağlantısı ---
    st.subheader("Bu rotanın alan bazlı CAPEX referansı")
    st.caption("Aynı tasarım debisinde, rapor referanslarından alan bazlı doğrudan maliyet aralığı. "
               "Dolaylı maliyet ve gider payı hariçtir; ayrıntı için CAPEX Ölçekleme sekmesine bak.")
    satir, alt_t, ust_t = [], 0.0, 0.0
    for kod in CIL_ROTASI_ALANLARI:
        e = estimate_area_capex(kod, tpd)
        if not e["veri_var"]:
            satir.append({"Alan": ALAN_TURLERI[kod], "En düşük": "veri yok", "En yüksek": "veri yok", "Referans": "-"})
            continue
        alt_t += e["min_usd"]
        ust_t += e["max_usd"]
        satir.append({"Alan": ALAN_TURLERI[kod], "En düşük": f"${e['min_usd']:,.0f}",
                      "En yüksek": f"${e['max_usd']:,.0f}",
                      "Referans": ", ".join(x["project"] for x in e["referanslar"])})
    st.dataframe(pd.DataFrame(satir), hide_index=True, use_container_width=True)
    t1, t2 = st.columns(2)
    t1.metric("Alanlar toplamı (en düşük)", f"${alt_t:,.0f}")
    t2.metric("Alanlar toplamı (en yüksek)", f"${ust_t:,.0f}")
