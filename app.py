"""
Flotasyon Tesisi CAPEX/OPEX Karar Destek Araci - Test Arayuzu
================================================================
Calistirmak icin (terminalde, bu dosyanin bulundugu klasorde):

    streamlit run app.py

Tarayicida otomatik acilir (genelde http://localhost:8501)

Gereksinim: grade_recovery_model.py, reagent_cost_model.py ve
capex_scaling_model.py dosyalari bu dosyayla AYNI KLASORDE olmali.
"""

import streamlit as st
import pandas as pd

from grade_recovery_model import predict_recovery, MODELS as RECOVERY_MODELS
from reagent_cost_model import (
    calculate_reagent_cost,
    UserReagentInput,
    COPPER_SULFIDE_FLOTATION_REAGENTS,
    ALTAR_TOTAL_PROCESSING_OPEX_USD_PER_T,
    ALTAR_TOTAL_PROCESSING_OPEX_SOURCE,
)
from capex_scaling_model import (
    estimate_process_capex,
    fit_scaling_exponent,
    ALTAR_DATA_POINT,
    LA_MINA_DATA_POINT,
)
from comminution_sizing_model import (
    bond_grinding_power_kw,
    suggest_crushing_stages,
    ALTAR_EQUIPMENT_REFERENCE,
)
from flotation_cell_sizing_model import (
    flotation_cell_volume,
    suggest_cell_count,
    ALTAR_RETENTION_TIMES,
)
from dewatering_sizing_model import (
    thickener_area,
    filter_area,
    ALTAR_DEWATERING_REFERENCE,
)

st.set_page_config(page_title="Flotasyon CAPEX/OPEX Araci", layout="wide")

st.title("Flotasyon Tesisi CAPEX/OPEX Karar Destek Araci")
st.caption(
    "Prototip - NI 43-101 teknik raporlarindan (Aranzazu, Altar, La Mina) "
    "turetilen modellere dayanir. Sadece dahili test/gelistirme amaclidir."
)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "Tenor - Kurtarma", "Reaktif Maliyeti", "CAPEX Olcekleme",
        "Boyut Kucultme", "Flotasyon Hucresi", "Yogunlastirma/Susuzlastirma",
    ]
)

# ------------------------------------------------------------------
# TAB 1: Tenor - Kurtarma
# ------------------------------------------------------------------
with tab1:
    st.header("Tenor - Kurtarma Tahmini")
    st.markdown("Kaynak: **Aranzazu Mine** NI 43-101 (2025), 2024 isletme verisi korelasyonu")

    col1, col2 = st.columns([1, 2])

    with col1:
        metal = st.selectbox("Metal", options=list(RECOVERY_MODELS.keys()))
        birim = "%" if metal == "Cu" else "g/t"
        model = RECOVERY_MODELS[metal]
        varsayilan = (model.valid_grade_min + model.valid_grade_max) / 2
        tenor = st.number_input(
            f"Tenor ({birim})",
            min_value=0.0,
            value=float(varsayilan),
            step=0.01,
            format="%.3f",
        )

    with col2:
        sonuc = predict_recovery(metal, tenor)
        st.metric("Tahmini Kurtarma", f"%{sonuc['predicted_recovery_pct']}")
        if sonuc["extrapolating"]:
            st.warning(sonuc["warning"])
        else:
            st.success(f"Girilen tenor, test edilen aralik icinde ({model.valid_grade_min}-{model.valid_grade_max} {birim})")
        st.caption(f"Kaynak: {sonuc['source']}")

# ------------------------------------------------------------------
# TAB 2: Reaktif Maliyeti
# ------------------------------------------------------------------
with tab2:
    st.header("Reaktif Maliyeti")
    st.markdown(
        "Reaktif **turleri** Altar PEA'dan (Bolum 17.1.3 / Sekil 17-2) dogrulanmis, "
        "ama **tuketim miktari ve fiyat rapor tarafindan acikca verilmiyor** - "
        "bu degerleri kendi tedarikci teklifinden gir."
    )
    st.info(
        "Bu tasarim bilincli: gercek dunyada her sirket kendi tedarikcisinden "
        "farkli fiyat/tuketim verisi alacak. Uygulama sana hangi reaktif "
        "turlerine ihtiyacin oldugunu soyler, maliyeti SENIN girdigin sayilarla hesaplar."
    )

    kapasite = st.number_input("Gunluk Isleme Kapasitesi (ton/gun)", min_value=1000, value=60000, step=1000)

    st.subheader("Reaktif Verilerini Gir (kendi tedarikci teklifinden)")
    user_inputs = []
    cols = st.columns(2)
    for i, spec in enumerate(COPPER_SULFIDE_FLOTATION_REAGENTS):
        with cols[i % 2]:
            st.markdown(f"**{spec.name}** ({spec.category})")
            st.caption(spec.typical_role)
            c1, c2 = st.columns(2)
            tuketim = c1.number_input(
                "Tuketim (kg/t)", min_value=0.0, value=0.0, step=0.001,
                format="%.4f", key=f"cons_{spec.name}",
            )
            fiyat = c2.number_input(
                "Fiyat ($/kg)", min_value=0.0, value=0.0, step=0.01,
                key=f"price_{spec.name}",
            )
            if tuketim > 0 and fiyat > 0:
                user_inputs.append(UserReagentInput(spec.name, tuketim, fiyat))

    st.divider()

    if user_inputs:
        sonuc = calculate_reagent_cost(daily_tonnage=kapasite, user_inputs=user_inputs)

        st.subheader("Sonuclar")
        col1, col2, col3 = st.columns(3)
        col1.metric("Toplam Birim Maliyet", f"${sonuc['total_cost_usd_per_t']:.2f}/ton")
        col2.metric("Gunluk Toplam", f"${sonuc['total_daily_cost_usd']:,.0f}")
        col3.metric("Yillik Toplam", f"${sonuc['total_annual_cost_usd']:,.0f}")

        df = pd.DataFrame(sonuc["line_items"])
        st.dataframe(
            df[["reagent", "consumption_kg_per_t", "unit_price_usd_per_kg", "cost_usd_per_t", "daily_cost_usd"]]
            .rename(columns={
                "reagent": "Reaktif",
                "consumption_kg_per_t": "Tuketim (kg/t)",
                "unit_price_usd_per_kg": "Birim Fiyat ($/kg)",
                "cost_usd_per_t": "Maliyet ($/t)",
                "daily_cost_usd": "Gunluk Maliyet ($)",
            }),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(sonuc["benchmark_note"])
    else:
        st.warning("Sonuc gormek icin en az 1 reaktif icin tuketim VE fiyat degeri gir.")
        st.caption(
            f"Referans (kirilimsiz): Altar PEA'da toplam isleme maliyeti "
            f"${ALTAR_TOTAL_PROCESSING_OPEX_USD_PER_T}/ton olarak raporlanmisti "
            f"({ALTAR_TOTAL_PROCESSING_OPEX_SOURCE})."
        )

# ------------------------------------------------------------------
# TAB 3: CAPEX Olcekleme
# ------------------------------------------------------------------
with tab3:
    st.header("CAPEX Olcekleme (Process Plant)")
    st.markdown(
        "Kaynak: **Altar Project** (60,000 tpd, $579M) ve **La Mina Project** "
        "(15,000 tpd, $224.7M) - guc yasasi (six-tenths rule) olceklemesi"
    )

    n = fit_scaling_exponent(LA_MINA_DATA_POINT, ALTAR_DATA_POINT)
    st.info(f"2 veri noktasindan hesaplanan olcekleme usteli: **n = {n:.4f}** (endustri araligi: 0.6-0.7)")

    hedef_kapasite = st.slider("Hedef Kapasite (ton/gun)", min_value=5000, max_value=150000, value=30000, step=1000)

    sonuc = estimate_process_capex(target_capacity_tpd=hedef_kapasite)

    col1, col2 = st.columns(2)
    col1.metric("Tahmini Process Plant CAPEX", f"${sonuc['estimated_process_capex_usd']:,.0f}")
    col2.metric("Kullanilan Referans", sonuc["reference_project"])

    st.caption(sonuc["note"])

    # Olcekleme egrisini gorsellestir
    kapasiteler = list(range(5000, 150001, 5000))
    tahminler = [estimate_process_capex(k)["estimated_process_capex_usd"] for k in kapasiteler]
    egri_df = pd.DataFrame({"Kapasite (tpd)": kapasiteler, "Tahmini CAPEX ($)": tahminler}).set_index("Kapasite (tpd)")
    st.line_chart(egri_df)

    st.caption(
        f"Referans noktalar: Altar ({ALTAR_DATA_POINT.capacity_tpd:,.0f} tpd, "
        f"${ALTAR_DATA_POINT.process_capex_usd:,.0f}) ve La Mina "
        f"({LA_MINA_DATA_POINT.capacity_tpd:,.0f} tpd, ${LA_MINA_DATA_POINT.process_capex_usd:,.0f})"
    )

# ------------------------------------------------------------------
# TAB 4: Boyut Kucultme (Kirma + Ogutme)
# ------------------------------------------------------------------
with tab4:
    st.header("Boyut Kucultme (Kirma + Ogutme) Boyutlandirma")
    st.markdown(
        "Bond denklemi (1952) - evrensel muhendislik formulu - ve genel "
        "endustri kurallariyla teknik boyutlandirma. Ekipman marka/model "
        "secimi kapsam disinda; bu sadece TEKNIK ihtiyaci hesaplar."
    )

    sub1, sub2 = st.columns(2)

    with sub1:
        st.subheader("Kirma Asama Onerisi")
        rom = st.number_input("ROM Cevher Boyutu (mm)", min_value=1.0, value=1000.0, step=10.0)
        hedef = st.number_input("Hedef Boyut / SAG Besleme (mm)", min_value=1.0, value=150.0, step=5.0)

        try:
            kirma_sonuc = suggest_crushing_stages(rom, hedef)
            st.metric("Boyut Kucultme Orani", f"{kirma_sonuc['reduction_ratio']}:1")
            st.info(kirma_sonuc["suggested_configuration"])
            st.caption(kirma_sonuc["note"])

            st.markdown("**Kirici Maliyeti - her asama icin ayri (farkli ekipman tipi, farkli fiyat)**")
            asama_isimleri = ["Birincil (Gyratory/Jaw)", "Ikincil (Cone)", "Ucuncul (Cone/HPGR)"]
            kirici_capex = 0.0
            for i in range(kirma_sonuc["suggested_stage_count"]):
                asama_adi = asama_isimleri[i] if i < len(asama_isimleri) else f"Asama {i+1}"
                c1, c2 = st.columns(2)
                adet = c1.number_input(f"{asama_adi} - Adet", min_value=1, value=1, step=1, key=f"kirici_adet_{i}")
                fiyat = c2.number_input(f"{asama_adi} - Fiyat ($)", min_value=0.0, value=0.0, step=50000.0, key=f"kirici_fiyat_{i}")
                kirici_capex += adet * fiyat
            if kirici_capex > 0:
                st.metric("Kirma CAPEX (Toplam)", f"${kirici_capex:,.0f}")
        except ValueError as e:
            st.error(str(e))
            kirici_capex = 0.0

    with sub2:
        st.subheader("Ogutme Guc Ihtiyaci (Bond Denklemi)")
        tph = st.number_input(
            "Besleme Miktari (ton/saat)", min_value=1.0, value=2717.0, step=10.0,
            help=(
                "Varsayilan deger ORNEKTIR: 60,000 tpd / (24h x %92 varsayilan "
                "kullanilabilirlik) - bu %92 Altar raporundan degil, tipik bir "
                "endustri varsayimindan geliyor. Kendi projenin gercek "
                "kullanilabilirlik oranini kullanarak hesapla."
            ),
        )
        wi = st.number_input(
            "Bond Is Indeksi - Wi (kWh/t)", min_value=0.1, value=14.0, step=0.1,
            help="Laboratuvar Bond testinden gelmeli - buradaki deger sadece ornek",
        )
        f80 = st.number_input("Besleme F80 (mikron)", min_value=1.0, value=150000.0, step=1000.0)
        p80 = st.number_input("Urun P80 (mikron)", min_value=1.0, value=190.0, step=10.0)

        try:
            ogutme_sonuc = bond_grinding_power_kw(tph, wi, f80, p80)
            st.metric("Gerekli Toplam Guc (SAG+Bilyali+Regrind)", f"{ogutme_sonuc['required_power_kw']:,.0f} kW")
            st.caption(f"Spesifik enerji: {ogutme_sonuc['specific_energy_kwh_per_t']} kWh/t")
            st.caption(ogutme_sonuc["note"])
            st.caption(
                "NOT: Bond hesabi devrenin TOPLAM gucunu verir, SAG/Bilyali/Regrind "
                "arasindaki guc paylasimini ayirmaz - bu, detayli devre tasarimi "
                "gerektiren ayri bir muhendislik karari. Asagida her ekipmani "
                "kendi tedarikci teklifinle ayri ayri fiyatlandirabilirsin."
            )

            st.markdown("**Degirmen Maliyeti - her ekipman icin ayri**")
            degirmen_tipleri = ["SAG Degirmen", "Bilyali Degirmen", "Regrind (Kule Degirmen)"]
            degirmen_capex = 0.0
            for i, tip in enumerate(degirmen_tipleri):
                c1, c2 = st.columns(2)
                adet = c1.number_input(f"{tip} - Adet", min_value=0, value=1, step=1, key=f"degirmen_adet_{i}")
                fiyat = c2.number_input(f"{tip} - Fiyat ($)", min_value=0.0, value=0.0, step=50000.0, key=f"degirmen_fiyat_{i}")
                degirmen_capex += adet * fiyat
            if degirmen_capex > 0:
                st.metric("Ogutme CAPEX (Toplam)", f"${degirmen_capex:,.0f}")
        except ValueError as e:
            st.error(str(e))
            degirmen_capex = 0.0

    toplam_boyut_kucultme_capex = kirici_capex + degirmen_capex
    if toplam_boyut_kucultme_capex > 0:
        st.divider()
        st.subheader("Boyut Kucultme Toplam Ekipman CAPEX")
        st.metric("Toplam (Kirma + Ogutme)", f"${toplam_boyut_kucultme_capex:,.0f}")
        st.caption(
            "Bu, girdigin gercek tedarikci fiyatlarindan hesaplanan 'asagidan-yukari' "
            "(bottom-up) CAPEX'tir. CAPEX Olcekleme sekmesindeki 'yukaridan-asagi' "
            "(top-down, guc yasasi) tahminiyle karsilastirarak capraz kontrol yapabilirsin."
        )

    st.divider()
    st.subheader("Referans: Altar Project Ekipman Konfigurasyonu (60,000 tpd)")
    st.caption("Bu, GERCEK ve dogrulanmis rapor verisidir - karsilastirma/benchmark amaclidir.")
    ref_df = pd.DataFrame([
        {"Ekipman": eq.equipment_type, "Spesifikasyon": eq.specification, "Kaynak": eq.source}
        for eq in ALTAR_EQUIPMENT_REFERENCE
    ])
    st.dataframe(ref_df, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------
# TAB 5: Flotasyon Hucresi Boyutlandirma
# ------------------------------------------------------------------
with tab5:
    st.header("Flotasyon Hucresi Boyutlandirma")
    st.markdown(
        "**Gerekli Hacim (m3)** kolonu OTOMATIK hesaplanir (besleme, pulp "
        "kati orani, ozgul agirlik ve flotasyon suresinden - standart pulp "
        "hacim formulu). **Birim Hucre Hacmi** ise farkli bir sey: tedarikci "
        "kataloğundaki hazir urun boyutu (orn. 'TankCell 160' = 160 m3) - bu "
        "hesaplanamaz, sen katalogdan sectigin boyutu girersin. Her asama "
        "(rougher/cleaner) farkli boyutta hucre kullanabilecegi icin bu "
        "alan asama bazinda ayri ayri."
    )

    col1, col2 = st.columns(2)
    with col1:
        besleme = st.number_input(
            "Besleme Miktari (ton/saat)", min_value=1.0, value=2717.0, step=10.0,
            key="flot_besleme",
        )
        pulp_kati = st.number_input(
            "Pulp Kati Orani (%)", min_value=1.0, max_value=99.0, value=35.0, step=1.0,
            help="Tipik ornek deger - Altar raporunda asama bazinda acikca verilmiyor",
        )
    with col2:
        ozgul_agirlik = st.number_input(
            "Cevher Ozgul Agirligi (t/m3)", min_value=1.0, value=2.8, step=0.1,
            help="Tipik bakir porfiri ornegi - kendi numunenin degerini kullan",
        )

    st.divider()
    st.subheader("Devre Asamasi Bazinda Sonuclar")

    sonuclar = []
    toplam_flotasyon_capex = 0.0
    for i, stage in enumerate(ALTAR_RETENTION_TIMES):
        try:
            hacim_sonuc = flotation_cell_volume(besleme, stage.retention_time_min, pulp_kati, ozgul_agirlik)

            st.markdown(f"**{stage.stage}** - Gerekli Hacim (otomatik hesaplanan): "
                        f"{hacim_sonuc['required_volume_m3']:,.0f} m3")
            c1, c2, c3 = st.columns(3)
            birim_hacim_i = c1.number_input(
                "Birim Hucre Hacmi (m3)", min_value=1.0, value=160.0, step=10.0,
                key=f"birim_hacim_{i}", help="Tedarikci katalogundan",
            )
            birim_fiyat_i = c2.number_input(
                "Birim Hucre Fiyati ($)", min_value=0.0, value=0.0, step=50000.0,
                key=f"birim_fiyat_{i}",
            )

            hucre_sonuc = suggest_cell_count(hacim_sonuc["required_volume_m3"], birim_hacim_i)
            stage_capex = hucre_sonuc["suggested_cell_count"] * birim_fiyat_i
            toplam_flotasyon_capex += stage_capex
            c3.metric("Onerilen Adet / CAPEX", f"{hucre_sonuc['suggested_cell_count']} adet",
                      f"${stage_capex:,.0f}")

            sonuclar.append({
                "Asama": stage.stage,
                "Flotasyon Suresi (dk)": stage.retention_time_min,
                "Gerekli Hacim (m3)": hacim_sonuc["required_volume_m3"],
                "Birim Hucre (m3)": birim_hacim_i,
                "Onerilen Hucre Adedi": hucre_sonuc["suggested_cell_count"],
                "Asama CAPEX ($)": round(stage_capex, 0),
            })
            st.divider()
        except ValueError as e:
            st.error(f"{stage.stage}: {e}")

    if sonuclar:
        df = pd.DataFrame(sonuclar)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(
            "Flotasyon sureleri kaynagi: Altar PEA, Sekil 17-2 (gercek/dogrulanmis). "
            "Pulp kati orani, ozgul agirlik ve birim hucre secimi tasarim varsayimidir."
        )
        if toplam_flotasyon_capex > 0:
            st.metric("Flotasyon Hucreleri Toplam CAPEX", f"${toplam_flotasyon_capex:,.0f}")

# ------------------------------------------------------------------
# TAB 6: Yogunlastirma / Susuzlastirma
# ------------------------------------------------------------------
with tab6:
    st.header("Yogunlastirma / Susuzlastirma Boyutlandirma")
    st.markdown(
        "Konsantre koyulastirici ve filtre icin standart alan hesabi. "
        "Altar PEA'da bu ekipmanlarin **varligi** dogrulanmis (Bolum 17.1.4/17.1.5) "
        "ama alan/kapasite degerleri raporda acikca verilmiyor - bu yuzden "
        "sonuclar tamamen SENIN girdigin test verisine bagli."
    )

    sub1, sub2 = st.columns(2)

    with sub1:
        st.subheader("Konsantre Koyulastirici")
        konsantre_debisi = st.number_input(
            "Konsantre Kati Debisi (ton/saat)", min_value=0.1, value=145.0, step=1.0,
            help="Kutle dengesinden hesaplanmali: Besleme x Tenor x Kurtarma / Konsantre Tenoru",
        )
        birim_alan = st.number_input(
            "Birim Alan Yuk Orani (kg/m2/saat)", min_value=1.0, value=800.0, step=10.0,
            help="Cokelme (settling) test sonucundan gelmeli - buradaki deger sadece ornek",
        )
        try:
            koyu_sonuc = thickener_area(konsantre_debisi, birim_alan)
            st.metric("Gerekli Alan", f"{koyu_sonuc['required_area_m2']:,.0f} m2")
            st.caption(f"Esdeger cap: {koyu_sonuc['equivalent_diameter_m']} m")
            st.caption(koyu_sonuc["note"])

            koyu_fiyat = st.number_input(
                "Koyulastirici Fiyati ($) - tedarikci teklifinden", min_value=0.0, value=0.0, step=50000.0,
            )
        except ValueError as e:
            st.error(str(e))
            koyu_fiyat = 0.0

    with sub2:
        st.subheader("Konsantre Filtresi")
        filtrasyon_hizi = st.number_input(
            "Spesifik Filtrasyon Hizi (kg/m2/saat)", min_value=1.0, value=250.0, step=10.0,
            help="Filtrasyon test sonucundan gelmeli - buradaki deger sadece ornek",
        )
        try:
            filtre_sonuc = filter_area(konsantre_debisi, filtrasyon_hizi)
            st.metric("Gerekli Alan", f"{filtre_sonuc['required_area_m2']:,.0f} m2")
            st.caption(filtre_sonuc["note"])

            filtre_fiyat = st.number_input(
                "Filtre Fiyati ($) - tedarikci teklifinden", min_value=0.0, value=0.0, step=50000.0,
            )
        except ValueError as e:
            st.error(str(e))
            filtre_fiyat = 0.0

    toplam_yogunlastirma_capex = koyu_fiyat + filtre_fiyat
    if toplam_yogunlastirma_capex > 0:
        st.divider()
        st.subheader("Yogunlastirma/Susuzlastirma Toplam CAPEX")
        st.metric("Toplam (Koyulastirici + Filtre)", f"${toplam_yogunlastirma_capex:,.0f}")

    st.divider()
    st.subheader("Referans: Altar Project Ekipman Listesi")
    st.caption("Ekipman VARLIGI gercek/dogrulanmis - alan/kapasite verisi rapor tarafindan verilmiyor.")
    ref_df = pd.DataFrame([
        {"Ekipman": eq.equipment_type, "Aciklama": eq.description, "Kaynak": eq.source}
        for eq in ALTAR_DEWATERING_REFERENCE
    ])
    st.dataframe(ref_df, use_container_width=True, hide_index=True)
