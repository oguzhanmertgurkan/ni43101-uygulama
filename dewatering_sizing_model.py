"""
Yogunlastirma / Susuzlastirma Boyutlandirma Modulu
======================================================
Konsantre koyulastirici (thickener) ve filtre (dewatering filter) icin
standart muhendislik alan hesabi.

GERCEK, RAPORDAN DOGRULANMIS VERI (Altar PEA, Bolum 17.1.4 / 17.1.5):
- Konsantre Koyulastirici (Concentrate Thickener) mevcut
- Konsantre Pres Filtresi (Concentrate Filter) mevcut
- Atik Koyulastirici (Tailings Thickener) mevcut

NOT: Bu ekipmanlarin ALAN/KAPASITE degerleri (m2, birim yuk orani vb.)
rapor tarafindan acikca verilmemistir. Gercek boyutlandirma icin,
konsantre/atik numunesi uzerinde yapilan COKELME (settling) ve
FILTRASYON test sonuclari gereklidir - bu standart bir cevher hazirlama
laboratuvar hizmetidir (tipik olarak "Unit Area Test" / "Coe-Clevenger
Test" olarak bilinir).

Bu modul, KULLANICININ kendi test sonuclarini (birim alan yuk orani,
filtrasyon hizi) girerek gerekli alani hesaplamasini saglar - varsayilan/
tipik degerler sadece ORNEK amaclidir, herhangi bir rapor veya projeye
ozel gercek veri DEGILDIR.
"""

import math
from dataclasses import dataclass


def thickener_area(
    solids_mass_flow_tph: float,
    unit_area_rate_kg_per_m2_h: float,
) -> dict:
    """
    Koyulastirici (thickener) icin gerekli alani hesaplar.

    solids_mass_flow_tph: kuru kati kutle debisi (ton/saat)
    unit_area_rate_kg_per_m2_h: birim alan yuk orani (kg kati/m2/saat) -
        COKELME (settling) test sonucundan gelir, laboratuvar verisi

    Formul: Alan (m2) = Kati Kutle Debisi (kg/h) / Birim Alan Yuk Orani (kg/m2/h)
    """
    if solids_mass_flow_tph <= 0 or unit_area_rate_kg_per_m2_h <= 0:
        raise ValueError("Kati kutle debisi ve birim alan yuk orani pozitif olmali.")

    solids_kg_per_h = solids_mass_flow_tph * 1000
    required_area_m2 = solids_kg_per_h / unit_area_rate_kg_per_m2_h
    diameter_m = math.sqrt(4 * required_area_m2 / math.pi)

    return {
        "solids_mass_flow_tph": solids_mass_flow_tph,
        "unit_area_rate_kg_per_m2_h": unit_area_rate_kg_per_m2_h,
        "required_area_m2": round(required_area_m2, 1),
        "equivalent_diameter_m": round(diameter_m, 2),
        "formula": "Alan (m2) = Kati Debisi (kg/h) / Birim Alan Yuk Orani (kg/m2/h)",
        "note": (
            "Birim alan yuk orani (unit area rate) COKELME (settling) test "
            "sonucundan gelmelidir (orn. Coe-Clevenger veya dinamik cokelme "
            "testi) - bu deger olmadan guvenilir bir alan hesabi yapilamaz. "
            "Tipik degerler mineral/parcacik boyutuna gore genis bir "
            "aralikta degisir (konsantre icin genelde daha yuksek, atik/"
            "tailings icin daha dusuktur)."
        ),
    }


def filter_area(
    solids_mass_flow_tph: float,
    specific_filtration_rate_kg_per_m2_h: float,
) -> dict:
    """
    Susuzlastirma filtresi (basincli/vakum filtre) icin gerekli alani hesaplar.

    solids_mass_flow_tph: kuru kati kutle debisi (ton/saat)
    specific_filtration_rate_kg_per_m2_h: spesifik filtrasyon hizi
        (kg kuru kati/m2/saat) - FILTRASYON TEST sonucundan gelir
    """
    if solids_mass_flow_tph <= 0 or specific_filtration_rate_kg_per_m2_h <= 0:
        raise ValueError("Kati kutle debisi ve filtrasyon hizi pozitif olmali.")

    solids_kg_per_h = solids_mass_flow_tph * 1000
    required_area_m2 = solids_kg_per_h / specific_filtration_rate_kg_per_m2_h

    return {
        "solids_mass_flow_tph": solids_mass_flow_tph,
        "specific_filtration_rate_kg_per_m2_h": specific_filtration_rate_kg_per_m2_h,
        "required_area_m2": round(required_area_m2, 1),
        "formula": "Alan (m2) = Kati Debisi (kg/h) / Spesifik Filtrasyon Hizi (kg/m2/h)",
        "note": (
            "Spesifik filtrasyon hizi FILTRASYON test sonucundan gelmelidir "
            "(filtre tipine - basincli, vakum, disk vb. - ve konsantre "
            "ozelliklerine gore degisir). Bu deger olmadan guvenilir bir "
            "alan hesabi yapilamaz."
        ),
    }


@dataclass
class DewateringEquipmentReference:
    equipment_type: str
    description: str
    source: str


# Altar Project - GERCEK, dogrulanmis ekipman VARLIGI (alan/kapasite verisi YOK)
ALTAR_DEWATERING_REFERENCE = [
    DewateringEquipmentReference(
        "Konsantre Koyulastirici",
        "Flotasyon konsantresini yogunlastirmak icin",
        "Altar PEA, Bolum 17.1.4",
    ),
    DewateringEquipmentReference(
        "Konsantre Pres Filtresi",
        "Koyulastirilmis konsantreyi susuzlastirmak icin (nihai urun nem hedefi)",
        "Altar PEA, Bolum 17.1.4",
    ),
    DewateringEquipmentReference(
        "Atik Koyulastirici",
        "Flotasyon atigini (tailings) yogunlastirmak icin, TSF'ye gonderim oncesi",
        "Altar PEA, Bolum 17.1.5",
    ),
]


if __name__ == "__main__":
    print("Yogunlastirma/Susuzlastirma Boyutlandirma - Ornek Kullanim\n" + "-" * 55)
    print("(Birim alan yuk orani ve filtrasyon hizi SADECE ORNEK/TEMSILI degerlerdir)\n")

    # Konsantre kutle debisi ornegi - SADECE gosterim icin, gercek deger
    # kutle dengesinden (besleme x tenor x kurtarma / konsantre tenoru) hesaplanmali
    konsantre_debisi_tph = 145  # ORNEK deger

    print("--- 1. Konsantre Koyulastirici ---")
    koyu_sonuc = thickener_area(konsantre_debisi_tph, unit_area_rate_kg_per_m2_h=800)
    print(
        f"Gerekli Alan: {koyu_sonuc['required_area_m2']:,.0f} m2 "
        f"(esdeger cap: {koyu_sonuc['equivalent_diameter_m']} m)"
    )

    print("\n--- 2. Konsantre Filtresi ---")
    filtre_sonuc = filter_area(konsantre_debisi_tph, specific_filtration_rate_kg_per_m2_h=250)
    print(f"Gerekli Alan: {filtre_sonuc['required_area_m2']:,.0f} m2")

    print("\n--- 3. Altar Project Referans Ekipman Listesi ---")
    for eq in ALTAR_DEWATERING_REFERENCE:
        print(f"  [{eq.equipment_type}] {eq.description}")
