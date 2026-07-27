"""
Boyut Kucultme (Comminution) Boyutlandirma Modulu
=====================================================
Kirma + Ogutme devresi icin teknik boyutlandirma araclari.

Icerik:
1. Bond Is Indeksi (Bond Work Index) denklemi ile ogutme guc ihtiyaci hesabi
   - Bu, Fred Bond'un 1952'de gelistirdigi, sektorde evrensel kabul goren
     bir muhendislik denklemidir (rapor/proje verisi degil, genel bilim -
     tipki CAPEX modulundeki "guc yasasi olcekleme" gibi genel bir yontem).
2. Kirma devresi asama sayisi icin kaba muhendislik kurali (boyut kucultme
   orani bazli)
3. Altar Project referans veri noktasi (GERCEK, dogrulanmis ekipman
   boyutlari - ama guc/Bond Is Indeksi verisi rapor tarafindan acikca
   verilmedigi icin Bond hesabi Altar uzerinden YAPILAMAZ, sadece
   ekipman konfigurasyonu referans/karsilastirma amacli sunuluyor)

MIMARI NOT: Ekipman MARKA/MODEL secimi (orn. hangi tedarikciden hangi
mill) bu modulun kapsami DISINDA - o kullanicinin kendi tedarikci
kataloglarindan/tekliflerinden girecegi bilgi (reaktif modulundeki
mantikla ayni).

MUHENDISLIK SINIRLAMASI: Bond denklemi orijinal olarak bilyali degirmen
(ball mill) icin gelistirilmistir. SAG degirmen (yari-otojen) devrelerinde
kesin sonuc icin SPI/SMC gibi ozel test yontemleri kullanilir. Buradaki
hesap, kirma+ogutme devresinin TOPLAM enerji ihtiyaci icin basitlestirilmis
bir ilk yaklasim (first-pass estimate) sunar - kesin muhendislik tasarimi
yerine gecmez.
"""

import math
from dataclasses import dataclass


def bond_grinding_power_kw(
    throughput_tph: float,
    work_index_kwh_per_t: float,
    f80_um: float,
    p80_um: float,
) -> dict:
    """
    Bond'un Ucuncu Teorisi (Third Theory of Comminution) ile ogutme guc
    ihtiyacini hesaplar (Bond, 1952):

        W (kWh/t) = 10 * Wi * (1/sqrt(P80) - 1/sqrt(F80))

    throughput_tph: islenen cevher besleme miktari (ton/saat)
    work_index_kwh_per_t: Bond Is Indeksi - LABORATUVAR TESTINDEN gelir,
        kullanici kendi cevher numunesinin test sonucunu girmeli
    f80_um: besleme boyutu, %80 gecen (mikron)
    p80_um: urun (hedef ogutme) boyutu, %80 gecen (mikron)
    """
    if f80_um <= p80_um:
        raise ValueError("Besleme boyutu (F80), urun boyutundan (P80) buyuk olmali.")
    if work_index_kwh_per_t <= 0 or throughput_tph <= 0:
        raise ValueError("Is indeksi ve besleme miktari pozitif olmali.")

    specific_energy_kwh_per_t = 10 * work_index_kwh_per_t * (
        1 / math.sqrt(p80_um) - 1 / math.sqrt(f80_um)
    )
    power_kw = specific_energy_kwh_per_t * throughput_tph

    return {
        "specific_energy_kwh_per_t": round(specific_energy_kwh_per_t, 3),
        "required_power_kw": round(power_kw, 1),
        "throughput_tph": throughput_tph,
        "f80_um": f80_um,
        "p80_um": p80_um,
        "work_index_kwh_per_t": work_index_kwh_per_t,
        "formula": "Bond Ucuncu Teorisi (1952): W = 10 x Wi x (1/sqrt(P80) - 1/sqrt(F80))",
        "note": (
            "Wi degeri laboratuvar Bond Is Indeksi testinden gelmelidir "
            "(standart bir cevher hazirlama test hizmeti). Bu deger olmadan "
            "guvenilir bir guc tahmini yapilamaz. SAG degirmen icin bu "
            "basitlestirilmis bir ilk yaklasimdir, kesin tasarim icin "
            "SPI/SMC test yontemleri onerilir."
        ),
    }


def suggest_crushing_stages(rom_size_mm: float, target_size_mm: float) -> dict:
    """
    ROM (Run of Mine) cevher boyutundan hedef boyuta ulasmak icin kac
    asamali kirma gerekebilecegine dair KABA BIR MUHENDISLIK KURALI
    (rule of thumb) sunar. Kesin ekipman secimi degil, on-degerlendirme
    amaclidir.

    Tipik boyut kucultme oranlari (genel endustri kabulu):
    - Birincil (Primary) kirma: 3:1 - 6:1 (Gyratory/Jaw)
    - Ikincil (Secondary) kirma: 3:1 - 5:1 (Cone)
    - Ucuncul (Tertiary) kirma: 2:1 - 4:1 (Cone/HPGR)
    """
    if target_size_mm <= 0 or rom_size_mm <= target_size_mm:
        raise ValueError("ROM boyutu, hedef boyuttan buyuk olmali.")

    reduction_ratio = rom_size_mm / target_size_mm

    if reduction_ratio <= 6:
        stages = 1
        config = "Tek asamali birincil kirma (Gyratory veya Jaw Crusher) yeterli olabilir"
    elif reduction_ratio <= 25:
        stages = 2
        config = "Birincil + Ikincil kirma (Gyratory/Jaw + Cone Crusher) onerilir"
    else:
        stages = 3
        config = "Birincil + Ikincil + Ucuncul kirma (veya HPGR entegrasyonu) gerekebilir"

    return {
        "rom_size_mm": rom_size_mm,
        "target_size_mm": target_size_mm,
        "reduction_ratio": round(reduction_ratio, 1),
        "suggested_stage_count": stages,
        "suggested_configuration": config,
        "note": (
            "Bu kaba bir on-degerlendirmedir (genel endustri kurali), kesin "
            "muhendislik tasarimi degildir. Kesin ekipman secimi icin cevher "
            "sertligi (Crushability Index, Abrasion Index vb.) ve tedarikci "
            "muhendislik degerlendirmesi gerekir."
        ),
    }


@dataclass
class EquipmentReference:
    project: str
    capacity_tpd: float
    equipment_type: str
    specification: str
    source: str


# Altar Project - GERCEK, dogrulanmis ekipman konfigurasyonu (60,000 tpd icin)
# Guc/Wi verisi rapor tarafindan verilmedigi icin SADECE referans/karsilastirma
# amaclidir, hesaplama girdisi olarak KULLANILMAZ.
ALTAR_EQUIPMENT_REFERENCE = [
    EquipmentReference(
        "Altar Project", 60000, "Kirma",
        "1x Ocak-ici yari-mobil Gyratory Crusher, ROM -> ~150mm (6 inch)",
        "Altar PEA, Bolum 17.1.1",
    ),
    EquipmentReference(
        "Altar Project", 60000, "SAG Degirmen",
        "1x 40ft x 26ft EGL, kapali devre (cakil elegi ile)",
        "Altar PEA, Bolum 17.1.2",
    ),
    EquipmentReference(
        "Altar Project", 60000, "Bilyali Degirmen",
        "1x 26ft cap x 40.7ft boy, kapali devre (hidrosiklon), P80=190um",
        "Altar PEA, Bolum 17.1.2",
    ),
    EquipmentReference(
        "Altar Project", 60000, "Yeniden Ogutme (Regrind)",
        "1x Karistirmali Kule Degirmen (Tower Mill), P80=18-20um",
        "Altar PEA, Bolum 17.1.2",
    ),
]


if __name__ == "__main__":
    print("Boyut Kucultme Boyutlandirma Modulu - Ornek Kullanim\n" + "-" * 55)

    print("--- 1. Kirma Asama Onerisi ---")
    kirma = suggest_crushing_stages(rom_size_mm=1000, target_size_mm=150)
    print(
        f"ROM: {kirma['rom_size_mm']}mm -> Hedef: {kirma['target_size_mm']}mm "
        f"(boyut kucultme orani: {kirma['reduction_ratio']}:1)"
    )
    print(f"Oneri: {kirma['suggested_configuration']}\n")

    print("--- 2. Ogutme Guc Ihtiyaci (Bond Denklemi, ORNEK Wi ile) ---")
    print("(Wi=14 kWh/t sadece TEMSILI ornek - gercekte laboratuvar testinden gelmeli)")
    ogutme = bond_grinding_power_kw(
        throughput_tph=2717,  # ORNEK deger: 60,000 tpd / (24h x %92 kullanilabilirlik varsayimi)
                               # NOT: %92 kullanilabilirlik Altar raporundan DEGIL, tipik bir
                               # endustri varsayimindan geliyor - gercek deger degil
        work_index_kwh_per_t=14.0,  # ORNEK deger
        f80_um=150000,  # 150mm = 150,000 mikron (kirma sonrasi, Altar'in gercek degeri)
        p80_um=190,  # Altar'in gercek hedef degeri
    )
    print(f"Spesifik enerji: {ogutme['specific_energy_kwh_per_t']} kWh/t")
    print(f"Gerekli guc: {ogutme['required_power_kw']:,.0f} kW\n")

    print("--- 3. Altar Project Referans Ekipman Konfigurasyonu (60,000 tpd) ---")
    for eq in ALTAR_EQUIPMENT_REFERENCE:
        print(f"  [{eq.equipment_type}] {eq.specification}")
