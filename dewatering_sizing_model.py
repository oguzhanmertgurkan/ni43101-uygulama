"""
Yoğunlaştırma / Susuzlaştırma Boyutlandırma Modülü
======================================================
Konsantre koyulaştırıcı (thickener) ve filtre (dewatering filter) için
standart mühendislik alan hesabı.

GERÇEK, RAPORDAN DOĞRULANMIŞ VERİ (Altar PEA, Bölüm 17.1.4 / 17.1.5):
- Konsantre Koyulaştırıcı (Concentrate Thickener) mevcut
- Konsantre Pres Filtresi (Concentrate Filter) mevcut
- Atık Koyulaştırıcı (Tailings Thickener) mevcut

NOT: Bu ekipmanların ALAN/KAPASITE değerleri (m2, birim yük oranı vb.)
rapor tarafından açıkça verilmemiştir. Gerçek boyutlandırma için,
konsantre/atık numunesi üzerinde yapılan ÇÖKELME (settling) ve
FİLTRASYON test sonuçları gereklidir - bu standart bir cevher hazırlama
laboratuvar hizmetidir (tipik olarak "Unit Area Test" / "Coe-Clevenger
Test" olarak bilinir).

Bu modül, KULLANICININ kendi test sonuçlarını (birim alan yük oranı,
filtrasyon hızı) girerek gerekli alanı hesaplamasını sağlar - varsayılan/
tipik değerler sadece ÖRNEK amaçlıdır, herhangi bir rapor veya projeye
özel gerçek veri DEĞİLDİR.
"""

import math
from dataclasses import dataclass


def thickener_area(
    solids_mass_flow_tph: float,
    unit_area_rate_kg_per_m2_h: float,
) -> dict:
    """
    Koyulaştırıcı (thickener) için gerekli alanı hesaplar.

    solids_mass_flow_tph: kuru katı besleme miktarı (ton/saat)
    unit_area_rate_kg_per_m2_h: birim alan yük oranı (kg katı/m2/saat) -
        ÇÖKELME (settling) test sonucundan gelir, laboratuvar verisi

    Formül: Alan (m2) = Katı Besleme Miktarı (kg/h) / Birim Alan Yük Oranı (kg/m2/h)
    """
    if solids_mass_flow_tph <= 0 or unit_area_rate_kg_per_m2_h <= 0:
        raise ValueError("Katı besleme miktarı ve birim alan yük oranı pozitif olmalı.")

    solids_kg_per_h = solids_mass_flow_tph * 1000
    required_area_m2 = solids_kg_per_h / unit_area_rate_kg_per_m2_h
    diameter_m = math.sqrt(4 * required_area_m2 / math.pi)

    return {
        "solids_mass_flow_tph": solids_mass_flow_tph,
        "unit_area_rate_kg_per_m2_h": unit_area_rate_kg_per_m2_h,
        "required_area_m2": round(required_area_m2, 1),
        "equivalent_diameter_m": round(diameter_m, 2),
        "formula": "Alan (m2) = Katı Besleme Miktarı (kg/h) / Birim Alan Yük Oranı (kg/m2/h)",
        "note": (
            "Birim alan yük oranı (unit area rate) ÇÖKELME (settling) test "
            "sonucundan gelmelidir (orn. Coe-Clevenger veya dinamik çökelme "
            "testi) - bu değer olmadan güvenilir bir alan hesabı yapılamaz. "
            "Tipik değerler mineral/parçacık boyutuna göre geniş bir "
            "aralıkta değişir (konsantre için genelde daha yüksek, atık/"
            "tailings için daha düşüktür)."
        ),
    }


def filter_area(
    solids_mass_flow_tph: float,
    specific_filtration_rate_kg_per_m2_h: float,
) -> dict:
    """
    Susuzlaştırma filtresi (basınçlı/vakum filtre) için gerekli alanı hesaplar.

    solids_mass_flow_tph: kuru katı besleme miktarı (ton/saat)
    specific_filtration_rate_kg_per_m2_h: spesifik filtrasyon hızı
        (kg kuru katı/m2/saat) - FİLTRASYON TEST sonucundan gelir
    """
    if solids_mass_flow_tph <= 0 or specific_filtration_rate_kg_per_m2_h <= 0:
        raise ValueError("Katı besleme miktarı ve filtrasyon hızı pozitif olmalı.")

    solids_kg_per_h = solids_mass_flow_tph * 1000
    required_area_m2 = solids_kg_per_h / specific_filtration_rate_kg_per_m2_h

    return {
        "solids_mass_flow_tph": solids_mass_flow_tph,
        "specific_filtration_rate_kg_per_m2_h": specific_filtration_rate_kg_per_m2_h,
        "required_area_m2": round(required_area_m2, 1),
        "formula": "Alan (m2) = Katı Besleme Miktarı (kg/h) / Spesifik Filtrasyon Hızı (kg/m2/h)",
        "note": (
            "Spesifik filtrasyon hızı FİLTRASYON test sonucundan gelmelidir "
            "(filtre tipine - basınçlı, vakum, disk vb. - ve konsantre "
            "özelliklerine göre değişir). Bu değer olmadan güvenilir bir "
            "alan hesabı yapılamaz."
        ),
    }


@dataclass
class DewateringEquipmentReference:
    equipment_type: str
    description: str
    source: str


# Altar Project - GERÇEK, doğrulanmış ekipman VARLIĞI (alan/kapasite verisi YOK)
ALTAR_DEWATERING_REFERENCE = [
    DewateringEquipmentReference(
        "Konsantre Koyulaştırıcı",
        "Flotasyon konsantresini yoğunlaştırmak için",
        "Altar PEA, Bölüm 17.1.4",
    ),
    DewateringEquipmentReference(
        "Konsantre Pres Filtresi",
        "Koyulaştırılmış konsantreyi susuzlaştırmak için (nihai ürün nem hedefi)",
        "Altar PEA, Bölüm 17.1.4",
    ),
    DewateringEquipmentReference(
        "Atık Koyulaştırıcı",
        "Flotasyon atığını (tailings) yoğunlaştırmak için, TSF'ye gönderim öncesi",
        "Altar PEA, Bölüm 17.1.5",
    ),
]


if __name__ == "__main__":
    print("Yoğunlaştırma/Susuzlaştırma Boyutlandırma - Örnek Kullanım\n" + "-" * 55)
    print("(Birim alan yük oranı ve filtrasyon hızı SADECE ÖRNEK/TEMSİLİ değerlerdir)\n")

    # Konsantre besleme miktarı örneği - SADECE gösterim için, gerçek değer
    # kütle dengesinden (besleme x tenör x verim / konsantre tenörü) hesaplanmalı
    konsantre_besleme_tph = 145  # ÖRNEK değer

    print("--- 1. Konsantre Koyulaştırıcı ---")
    koyu_sonuc = thickener_area(konsantre_besleme_tph, unit_area_rate_kg_per_m2_h=800)
    print(
        f"Gerekli Alan: {koyu_sonuc['required_area_m2']:,.0f} m2 "
        f"(eşdeğer çap: {koyu_sonuc['equivalent_diameter_m']} m)"
    )

    print("\n--- 2. Konsantre Filtresi ---")
    filtre_sonuc = filter_area(konsantre_besleme_tph, specific_filtration_rate_kg_per_m2_h=250)
    print(f"Gerekli Alan: {filtre_sonuc['required_area_m2']:,.0f} m2")

    print("\n--- 3. Altar Project Referans Ekipman Listesi ---")
    for eq in ALTAR_DEWATERING_REFERENCE:
        print(f"  [{eq.equipment_type}] {eq.description}")
