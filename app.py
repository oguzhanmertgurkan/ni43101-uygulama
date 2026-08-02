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

from grade_recovery_model import (
    predict_recovery,
    MODELS as RECOVERY_MODELS,
    DRILLDATA_MODELS as RECOVERY_DRILLDATA_MODELS,
)
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
    ARANZAZU_BOND_WI_REFERENCE,
    check_work_index_against_reference,
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

st.set_page_config(page_title="Flotasyon CAPEX/OPEX Aracı", layout="wide")

st.title("Flotasyon Tesisi CAPEX/OPEX Karar Destek Aracı")
st.caption(
    "Prototip - NI 43-101 teknik raporlarından (Aranzazu, Altar, La Mina) "
    "türetilen modellere dayanır. Sadece dahili test/geliştirme amaçlıdır."
)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "Tenör - Verim", "Reaktif Maliyeti", "CAPEX Ölçekleme",
        "Boyut Küçültme", "Flotasyon Hücresi", "Yoğunlaştırma/Susuzlaştırma",
    ]
)

# ------------------------------------------------------------------
# TAB 1: Tenor - Verim
# ------------------------------------------------------------------
with tab1:
    st.header("Tenör - Verim Tahmini")
    st.markdown(
        "Kaynak: **Aranzazu Mine** NI 43-101 (SLR, 28 Mart 2025), Bölüm 13.5 "
        "(Recovery Projections for the Cash Flow Model), Tablo 13-18/13-19."
    )

    veri_seti = st.radio(
        "Veri Seti",
        options=["plant_data", "drill_data"],
        format_func=lambda x: (
            "Resmi Model (Plant Data — Eylül-Aralık 2024 işletme verisi, "
            "nakit akışı modelinde kullanılan denklem)"
            if x == "plant_data"
            else "Variability Test (Drill Data — 210 karot örneği, GENİŞ aralık, DÜŞÜK R²)"
        ),
        help=(
            "Plant Data: dar aralık ama yüksek güvenilirlik (gerçek işletme "
            "koşulları). Drill Data: çok geniş aralık (farklı mineralojik "
            "zonlar dahil) ama düşük R² (0.05-0.11) — sadece kaba eğilim, "
            "kesin tahmin değil."
        ),
    )

    col1, col2 = st.columns([1, 2])

    with col1:
        metal = st.selectbox("Metal", options=list(RECOVERY_MODELS.keys()))
        birim = "%" if metal == "Cu" else "g/t"
        models_dict = RECOVERY_MODELS if veri_seti == "plant_data" else RECOVERY_DRILLDATA_MODELS
        model = models_dict[metal]
        varsayilan = (model.valid_grade_min + model.valid_grade_max) / 2
        tenor = st.number_input(
            f"Tenör ({birim})",
            min_value=0.0,
            value=float(varsayilan),
            step=0.01,
            format="%.3f",
        )

    with col2:
        sonuc = predict_recovery(metal, tenor, dataset=veri_seti)
        st.metric("Tahmini Verim", f"%{sonuc['predicted_recovery_pct']}")
        if sonuc["r_squared"] is not None:
            st.caption(f"Model R² = {sonuc['r_squared']}")
        if sonuc["warning"]:
            st.warning(sonuc["warning"])
        else:
            st.success(f"Girilen tenör, test edilen aralık içinde ({model.valid_grade_min}-{model.valid_grade_max} {birim})")
        st.caption(f"Kaynak: {sonuc['source']}")

    if veri_seti == "drill_data":
        st.info(
            "Bu veri seti (variability test, 210 karot örneği) yatağın FARKLI "
            "mineralojik zonlarını (GH Pillar, BW, Mexicana South, AA) kapsar — "
            "tenör tek başına verimi zayıf açıklar (R² 0.05-0.11), saha/"
            "mineraloji değişkenliği çok daha baskındır. Değişken/benzer "
            "olmayan yataklanma senaryoları için KABA bir referans olarak "
            "kullanılabilir, ama Plant Data modelinin yerine geçmez."
        )

# ------------------------------------------------------------------
# TAB 2: Reaktif Maliyeti
# ------------------------------------------------------------------
with tab2:
    st.header("Reaktif Maliyeti")
    st.markdown(
        "Reaktif **türleri** Altar PEA'dan (Bölüm 17.1.3 / Şekil 17-2) doğrulanmış, "
        "ama **tüketim miktarı ve fiyat rapor tarafından açıkça verilmiyor** - "
        "bu değerleri kendi tedarikçi teklifinden gir."
    )
    st.info(
        "Bu tasarım bilinçli: gerçek dünyada her şirket kendi tedarikçisinden "
        "farklı fiyat/tüketim verisi alacak. Uygulama sana hangi reaktif "
        "türlerine ihtiyacın olduğunu söyler, maliyeti SENİN girdiğin sayılarla hesaplar."
    )

    kapasite = st.number_input("Günlük İşleme Kapasitesi (ton/gün)", min_value=1000, value=60000, step=1000)

    st.subheader("Reaktif Verilerini Gir (kendi tedarikçi teklifinden)")
    user_inputs = []
    cols = st.columns(2)
    for i, spec in enumerate(COPPER_SULFIDE_FLOTATION_REAGENTS):
        with cols[i % 2]:
            st.markdown(f"**{spec.name}** ({spec.category})")
            st.caption(spec.typical_role)
            c1, c2 = st.columns(2)
            tuketim = c1.number_input(
                "Tüketim (kg/t)", min_value=0.0, value=0.0, step=0.001,
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

        st.subheader("Sonuçlar")
        col1, col2, col3 = st.columns(3)
        col1.metric("Toplam Birim Maliyet", f"${sonuc['total_cost_usd_per_t']:.2f}/ton")
        col2.metric("Günlük Toplam", f"${sonuc['total_daily_cost_usd']:,.0f}")
        col3.metric("Yıllık Toplam", f"${sonuc['total_annual_cost_usd']:,.0f}")

        df = pd.DataFrame(sonuc["line_items"])
        st.dataframe(
            df[["reagent", "consumption_kg_per_t", "unit_price_usd_per_kg", "cost_usd_per_t", "daily_cost_usd"]]
            .rename(columns={
                "reagent": "Reaktif",
                "consumption_kg_per_t": "Tüketim (kg/t)",
                "unit_price_usd_per_kg": "Birim Fiyat ($/kg)",
                "cost_usd_per_t": "Maliyet ($/t)",
                "daily_cost_usd": "Günlük Maliyet ($)",
            }),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(sonuc["benchmark_note"])
    else:
        st.warning("Sonuç görmek için en az 1 reaktif için tüketim VE fiyat değeri gir.")
        st.caption(
            f"Referans (kırılımsız): Altar PEA'da toplam işleme maliyeti "
            f"\\${ALTAR_TOTAL_PROCESSING_OPEX_USD_PER_T}/ton olarak raporlanmıştı "
            f"({ALTAR_TOTAL_PROCESSING_OPEX_SOURCE})."
        )

# ------------------------------------------------------------------
# TAB 3: CAPEX Olcekleme
# ------------------------------------------------------------------
with tab3:
    st.header("CAPEX Ölçekleme (Process Plant)")
    st.markdown(
        "Kaynak: **Altar Project** (60,000 tpd, \\$579M) ve **La Mina Project** "
        "(15,000 tpd, \\$224.7M) - güç yasası (six-tenths rule) ölçeklemesi"
    )

    n = fit_scaling_exponent(LA_MINA_DATA_POINT, ALTAR_DATA_POINT)
    st.info(f"2 veri noktasından hesaplanan ölçekleme üsteli: **n = {n:.4f}** (endüstri aralığı: 0.6-0.7)")

    hedef_kapasite = st.slider("Hedef Kapasite (ton/gün)", min_value=5000, max_value=150000, value=30000, step=1000)

    sonuc = estimate_process_capex(target_capacity_tpd=hedef_kapasite)

    col1, col2 = st.columns(2)
    col1.metric("Tahmini Process Plant CAPEX", f"${sonuc['estimated_process_capex_usd']:,.0f}")
    col2.metric("Kullanılan Referans", sonuc["reference_project"])

    st.caption(sonuc["note"])

    # Olcekleme egrisini gorsellestir
    kapasiteler = list(range(5000, 150001, 5000))
    tahminler = [estimate_process_capex(k)["estimated_process_capex_usd"] for k in kapasiteler]
    egri_df = pd.DataFrame({"Kapasite (tpd)": kapasiteler, "Tahmini CAPEX ($)": tahminler}).set_index("Kapasite (tpd)")
    st.line_chart(egri_df)

    st.caption(
        f"Referans noktaları: Altar ({ALTAR_DATA_POINT.capacity_tpd:,.0f} tpd, "
        f"\\${ALTAR_DATA_POINT.process_capex_usd:,.0f}) ve La Mina "
        f"({LA_MINA_DATA_POINT.capacity_tpd:,.0f} tpd, \\${LA_MINA_DATA_POINT.process_capex_usd:,.0f})"
    )

# ------------------------------------------------------------------
# TAB 4: Boyut Kucultme (Kirma + Ogutme)
# ------------------------------------------------------------------
with tab4:
    st.header("Boyut Küçültme (Kırma + Öğütme) Boyutlandırma")
    st.markdown(
        "Bond denklemi (1952) - evrensel mühendislik formülü - ve genel "
        "endüstri kurallarıyla teknik boyutlandırma. Ekipman marka/model "
        "seçimi kapsam dışında; bu sadece TEKNİK ihtiyacı hesaplar."
    )

    sub1, sub2 = st.columns(2)

    with sub1:
        st.subheader("Kırma Aşama Önerisi")
        rom = st.number_input("ROM Cevher Boyutu (mm)", min_value=1.0, value=1000.0, step=10.0)
        hedef = st.number_input("Hedef Boyut / SAG Besleme (mm)", min_value=1.0, value=150.0, step=5.0)

        try:
            kirma_sonuc = suggest_crushing_stages(rom, hedef)
            st.metric("Boyut Küçültme Oranı", f"{kirma_sonuc['reduction_ratio']}:1")
            st.info(kirma_sonuc["suggested_configuration"])
            st.caption(kirma_sonuc["note"])

            st.markdown("**Kırıcı Maliyeti - her aşama için ayrı (farklı ekipman tipi, farklı fiyat)**")
            asama_isimleri = ["Birincil (Gyratory/Jaw)", "İkincil (Cone)", "Üçüncül (Cone/HPGR)"]
            kirici_capex = 0.0
            for i in range(kirma_sonuc["suggested_stage_count"]):
                asama_adi = asama_isimleri[i] if i < len(asama_isimleri) else f"Aşama {i+1}"
                c1, c2 = st.columns(2)
                adet = c1.number_input(f"{asama_adi} - Adet", min_value=1, value=1, step=1, key=f"kirici_adet_{i}")
                fiyat = c2.number_input(f"{asama_adi} - Fiyat ($)", min_value=0.0, value=0.0, step=50000.0, key=f"kirici_fiyat_{i}")
                kirici_capex += adet * fiyat
            if kirici_capex > 0:
                st.metric("Kırma CAPEX (Toplam)", f"${kirici_capex:,.0f}")
        except ValueError as e:
            st.error(str(e))
            kirici_capex = 0.0

    with sub2:
        st.subheader("Öğütme Güç İhtiyacı (Bond Denklemi)")
        tph = st.number_input(
            "Besleme Miktarı (ton/saat)", min_value=1.0, value=2717.0, step=10.0,
            help=(
                "Varsayılan değer ÖRNEKTİR: 60,000 tpd / (24h x %92 varsayılan "
                "kullanılabilirlik) - bu %92 Altar raporundan değil, tipik bir "
                "endüstri varsayımından geliyor. Kendi projenin gerçek "
                "kullanılabilirlik oranını kullanarak hesapla."
            ),
        )
        wi = st.number_input(
            "Bond İş İndeksi - Wi (kWh/t)", min_value=0.1, value=14.0, step=0.1,
            help="Laboratuvar Bond testinden gelmeli - buradaki değer sadece örnek",
        )
        kontrol = check_work_index_against_reference(wi, closing_screen="172um")
        if kontrol["in_range"]:
            st.caption(f"✅ {kontrol['note']}")
        else:
            st.caption(f"⚠️ {kontrol['note']}")
        with st.expander("Referans: Aranzazu Mine ölçülmüş Bond Wi değerleri (Glory Hole zonu)"):
            st.caption(
                "Bu, GERÇEK ve ölçülmüş laboratuvar verisidir (Aranzazu NI 43-101, "
                "SLR 2025, Tablo 13-14) — ama SADECE skarn tipi, kalkopirit ağırlıklı "
                "bir cevhere (Glory Hole zonu) aittir. Kendi cevherin farklı "
                "mineralojideyse (örn. porfiri) doğrudan kullanma; sadece benzer "
                "skarn tipi cevherlerde görülebilecek TİPİK ARALIK için yönlendirme "
                "amaçlı bak. Kesin tasarım için her zaman kendi numunenin lab "
                "testi gerekir."
            )
            bond_wi_df = pd.DataFrame([
                {
                    "Numune/Zon": ref.sample,
                    "Wi @172µm kapanış eleği (P80≈150µm) (kWh/t)": ref.bond_wi_172um_kwh_per_t,
                    "Wi @125µm kapanış eleği (P80≈100µm) (kWh/t)": (
                        ref.bond_wi_125um_kwh_per_t if ref.bond_wi_125um_kwh_per_t else "—"
                    ),
                }
                for ref in ARANZAZU_BOND_WI_REFERENCE
            ])
            st.dataframe(bond_wi_df, use_container_width=True, hide_index=True)
            st.caption(
                "Not: daha ince öğütmede (125µm kapanış eleği / P80≈100µm) Wi "
                "değerlerinin arttığı görülüyor — yani bu cevher daha ince "
                "öğütüldükçe öğütülmesi zorlaşıyor (tipik bir davranış, ama "
                "büyüklüğü cevhere özeldir)."
            )
        f80 = st.number_input("Besleme F80 (mikron)", min_value=1.0, value=150000.0, step=1000.0)
        p80 = st.number_input("Ürün P80 (mikron)", min_value=1.0, value=190.0, step=10.0)

        try:
            ogutme_sonuc = bond_grinding_power_kw(tph, wi, f80, p80)
            st.metric("Gerekli Toplam Güç (SAG+Bilyalı+Regrind)", f"{ogutme_sonuc['required_power_kw']:,.0f} kW")
            st.caption(f"Spesifik enerji: {ogutme_sonuc['specific_energy_kwh_per_t']} kWh/t")
            st.caption(ogutme_sonuc["note"])
            st.caption(
                "NOT: Bond hesabı devrenin TOPLAM gücünü verir, SAG/Bilyalı/Regrind "
                "arasındaki güç paylaşımını ayırmaz - bu, detaylı devre tasarımı "
                "gerektiren ayrı bir mühendislik kararı. Aşağıda her ekipmanı "
                "kendi tedarikçi teklifinle ayrı ayrı fiyatlandırabilirsin."
            )

            st.markdown("**Değirmen Maliyeti - her ekipman için ayrı**")
            degirmen_tipleri = ["SAG Değirmen", "Bilyalı Değirmen", "Regrind (Kule Değirmen)"]
            degirmen_capex = 0.0
            for i, tip in enumerate(degirmen_tipleri):
                c1, c2 = st.columns(2)
                adet = c1.number_input(f"{tip} - Adet", min_value=0, value=1, step=1, key=f"degirmen_adet_{i}")
                fiyat = c2.number_input(f"{tip} - Fiyat ($)", min_value=0.0, value=0.0, step=50000.0, key=f"degirmen_fiyat_{i}")
                degirmen_capex += adet * fiyat
            if degirmen_capex > 0:
                st.metric("Öğütme CAPEX (Toplam)", f"${degirmen_capex:,.0f}")
        except ValueError as e:
            st.error(str(e))
            degirmen_capex = 0.0

    toplam_boyut_kucultme_capex = kirici_capex + degirmen_capex
    if toplam_boyut_kucultme_capex > 0:
        st.divider()
        st.subheader("Boyut Küçültme Toplam Ekipman CAPEX")
        st.metric("Toplam (Kırma + Öğütme)", f"${toplam_boyut_kucultme_capex:,.0f}")
        st.caption(
            "Bu, girdiğin gerçek tedarikçi fiyatlarından hesaplanan 'aşağıdan-yukarı' "
            "(bottom-up) CAPEX'tir. CAPEX Ölçekleme sekmesindeki 'yukarıdan-aşağı' "
            "(top-down, güç yasası) tahminiyle karşılaştırarak çapraz kontrol yapabilirsin."
        )

    st.divider()
    st.subheader("Referans: Altar Project Ekipman Konfigürasyonu (60,000 tpd)")
    st.caption("Bu, GERÇEK ve doğrulanmış rapor verisidir - karşılaştırma/benchmark amaçlıdır.")
    ref_df = pd.DataFrame([
        {"Ekipman": eq.equipment_type, "Spesifikasyon": eq.specification, "Kaynak": eq.source}
        for eq in ALTAR_EQUIPMENT_REFERENCE
    ])
    st.dataframe(ref_df, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------
# TAB 5: Flotasyon Hucresi Boyutlandirma
# ------------------------------------------------------------------
with tab5:
    st.header("Flotasyon Hücresi Boyutlandırma")
    st.markdown(
        "**Gerekli Hacim (m3)** kolonu OTOMATİK hesaplanır (besleme, pulp "
        "katı oranı, özgül ağırlık ve flotasyon süresinden - standart pulp "
        "hacim formülü). **Birim Hücre Hacmi** ise farklı bir şey: tedarikçi "
        "kataloğundaki hazır ürün boyutu (örn. 'TankCell 160' = 160 m3) - bu "
        "hesaplanamaz, sen katalogdan seçtiğin boyutu girersin. Her aşama "
        "(rougher/cleaner) farklı boyutta hücre kullanabileceği için bu "
        "alan aşama bazında ayrı ayrı."
    )

    col1, col2 = st.columns(2)
    with col1:
        besleme = st.number_input(
            "Besleme Miktarı (ton/saat)", min_value=1.0, value=2717.0, step=10.0,
            key="flot_besleme",
        )
        pulp_kati = st.number_input(
            "Pulp Katı Oranı (%)", min_value=1.0, max_value=99.0, value=35.0, step=1.0,
            help="Tipik örnek değer - Altar raporunda aşama bazında açıkça verilmiyor",
        )
    with col2:
        ozgul_agirlik = st.number_input(
            "Cevher Özgül Ağırlığı (t/m3)", min_value=1.0, value=2.8, step=0.1,
            help="Tipik bakır porfiri örneği - kendi numunenin değerini kullan",
        )

    st.divider()
    st.subheader("Devre Aşaması Bazında Sonuçlar")

    sonuclar = []
    toplam_flotasyon_capex = 0.0
    for i, stage in enumerate(ALTAR_RETENTION_TIMES):
        try:
            hacim_sonuc = flotation_cell_volume(besleme, stage.retention_time_min, pulp_kati, ozgul_agirlik)

            st.markdown(f"**{stage.stage}** - Gerekli Hacim (otomatik hesaplanan): "
                        f"{hacim_sonuc['required_volume_m3']:,.0f} m3")
            c1, c2, c3 = st.columns(3)
            birim_hacim_i = c1.number_input(
                "Birim Hücre Hacmi (m3)", min_value=1.0, value=160.0, step=10.0,
                key=f"birim_hacim_{i}", help="Tedarikçi kataloğundan",
            )
            birim_fiyat_i = c2.number_input(
                "Birim Hücre Fiyatı ($)", min_value=0.0, value=0.0, step=50000.0,
                key=f"birim_fiyat_{i}",
            )

            hucre_sonuc = suggest_cell_count(hacim_sonuc["required_volume_m3"], birim_hacim_i)
            stage_capex = hucre_sonuc["suggested_cell_count"] * birim_fiyat_i
            toplam_flotasyon_capex += stage_capex
            c3.metric("Önerilen Adet / CAPEX", f"{hucre_sonuc['suggested_cell_count']} adet",
                      f"${stage_capex:,.0f}")

            sonuclar.append({
                "Aşama": stage.stage,
                "Flotasyon Süresi (dk)": stage.retention_time_min,
                "Gerekli Hacim (m3)": hacim_sonuc["required_volume_m3"],
                "Birim Hücre (m3)": birim_hacim_i,
                "Önerilen Hücre Adedi": hucre_sonuc["suggested_cell_count"],
                "Aşama CAPEX ($)": round(stage_capex, 0),
            })
            st.divider()
        except ValueError as e:
            st.error(f"{stage.stage}: {e}")

    if sonuclar:
        df = pd.DataFrame(sonuclar)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(
            "Flotasyon süreleri kaynağı: Altar PEA, Şekil 17-2 (gerçek/doğrulanmış). "
            "Pulp katı oranı, özgül ağırlık ve birim hücre seçimi tasarım varsayımıdır."
        )
        if toplam_flotasyon_capex > 0:
            st.metric("Flotasyon Hücreleri Toplam CAPEX", f"${toplam_flotasyon_capex:,.0f}")

# ------------------------------------------------------------------
# TAB 6: Yogunlastirma / Susuzlastirma
# ------------------------------------------------------------------
with tab6:
    st.header("Yoğunlaştırma / Susuzlaştırma Boyutlandırma")
    st.markdown(
        "Konsantre koyulaştırıcı ve filtre için standart alan hesabı. "
        "Altar PEA'da bu ekipmanların **varlığı** doğrulanmış (Bölüm 17.1.4/17.1.5) "
        "ama alan/kapasite değerleri raporda açıkça verilmiyor - bu yüzden "
        "sonuçlar tamamen SENİN girdiğin test verisine bağlı."
    )

    sub1, sub2 = st.columns(2)

    with sub1:
        st.subheader("Konsantre Koyulaştırıcı")
        konsantre_debisi = st.number_input(
            "Konsantre Katı Debisi (ton/saat)", min_value=0.1, value=145.0, step=1.0,
            help="Kütle dengesinden hesaplanmalı: Besleme x Tenör x Verim / Konsantre Tenörü",
        )
        birim_alan = st.number_input(
            "Birim Alan Yük Oranı (kg/m2/saat)", min_value=1.0, value=800.0, step=10.0,
            help="Çökelme (settling) test sonucundan gelmeli - buradaki değer sadece örnek",
        )
        try:
            koyu_sonuc = thickener_area(konsantre_debisi, birim_alan)
            st.metric("Gerekli Alan", f"{koyu_sonuc['required_area_m2']:,.0f} m2")
            st.caption(f"Eşdeğer çap: {koyu_sonuc['equivalent_diameter_m']} m")
            st.caption(koyu_sonuc["note"])

            koyu_fiyat = st.number_input(
                "Koyulaştırıcı Fiyatı ($) - tedarikçi teklifinden", min_value=0.0, value=0.0, step=50000.0,
            )
        except ValueError as e:
            st.error(str(e))
            koyu_fiyat = 0.0

    with sub2:
        st.subheader("Konsantre Filtresi")
        filtrasyon_hizi = st.number_input(
            "Spesifik Filtrasyon Hızı (kg/m2/saat)", min_value=1.0, value=250.0, step=10.0,
            help="Filtrasyon test sonucundan gelmeli - buradaki değer sadece örnek",
        )
        try:
            filtre_sonuc = filter_area(konsantre_debisi, filtrasyon_hizi)
            st.metric("Gerekli Alan", f"{filtre_sonuc['required_area_m2']:,.0f} m2")
            st.caption(filtre_sonuc["note"])

            filtre_fiyat = st.number_input(
                "Filtre Fiyatı ($) - tedarikçi teklifinden", min_value=0.0, value=0.0, step=50000.0,
            )
        except ValueError as e:
            st.error(str(e))
            filtre_fiyat = 0.0

    toplam_yogunlastirma_capex = koyu_fiyat + filtre_fiyat
    if toplam_yogunlastirma_capex > 0:
        st.divider()
        st.subheader("Yoğunlaştırma/Susuzlaştırma Toplam CAPEX")
        st.metric("Toplam (Koyulaştırıcı + Filtre)", f"${toplam_yogunlastirma_capex:,.0f}")

    st.divider()
    st.subheader("Referans: Altar Project Ekipman Listesi")
    st.caption("Ekipman VARLIĞI gerçek/doğrulanmış - alan/kapasite verisi rapor tarafından verilmiyor.")
    ref_df = pd.DataFrame([
        {"Ekipman": eq.equipment_type, "Açıklama": eq.description, "Kaynak": eq.source}
        for eq in ALTAR_DEWATERING_REFERENCE
    ])
    st.dataframe(ref_df, use_container_width=True, hide_index=True)
