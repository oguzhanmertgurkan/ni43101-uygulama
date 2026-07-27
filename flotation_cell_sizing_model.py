"""
Flotasyon Hucresi Boyutlandirma Modulu
=========================================
Standart muhendislik pulp hacim hesabi (Wills' Mineral Processing Technology
ve benzeri referans kaynaklarda yer alan klasik yontem) kullanarak, verilen
flotasyon suresi (retention time) ve besleme kosullarindan gerekli toplam
hucre hacmini hesaplar.

GERCEK, RAPORDAN DOGRULANMIS VERI (Altar PEA, Sekil 17-2):
- Rougher flotasyon suresi: 23 dakika
- Cleaner-1 flotasyon suresi: 15 dakika
- Cleaner-2 flotasyon suresi: 12.5 dakika
- Cleaner-3 flotasyon suresi: 10 dakika

NOT: Pulp yogunlugu (% kati oran) ve cevher ozgul agirligi her devre
asamasi icin rapor tarafindan acikca verilmedigi icin bu degerler
KULLANICI GIRDISI olarak alinir (varsayilan degerler sadece ORNEK/TEMSILI
tipik degerlerdir, Altar raporundan alinmis gercek veri DEGILDIR).
"""

import math
from dataclasses import dataclass


def flotation_cell_volume(
    throughput_tph: float,
    retention_time_min: float,
    pulp_solids_pct: float,
    ore_specific_gravity: float = 2.8,
) -> dict:
    """
    Belirli bir flotasyon suresi icin gerekli toplam hucre hacmini hesaplar.

    throughput_tph: kuru kati besleme miktari (ton/saat)
    retention_time_min: hedeflenen flotasyon suresi (dakika)
    pulp_solids_pct: pulp ici kati oran, agirlikca (%)
    ore_specific_gravity: cevherin ozgul agirligi (t/m3) - varsayilan 2.8
        tipik bir bakir porfiri cevheri icin KABA bir ORTALAMA degerdir,
        gercek deger numuneden olculmelidir
    """
    if not (0 < pulp_solids_pct < 100):
        raise ValueError("Pulp kati orani 0-100 arasinda olmali.")
    if throughput_tph <= 0 or retention_time_min <= 0:
        raise ValueError("Besleme miktari ve flotasyon suresi pozitif olmali.")

    pulp_mass_flow_tph = throughput_tph / (pulp_solids_pct / 100)
    pulp_density_t_per_m3 = 100 / (
        pulp_solids_pct / ore_specific_gravity + (100 - pulp_solids_pct) / 1.0
    )
    pulp_volumetric_flow_m3h = pulp_mass_flow_tph / pulp_density_t_per_m3
    required_volume_m3 = pulp_volumetric_flow_m3h * retention_time_min / 60

    return {
        "throughput_tph": throughput_tph,
        "retention_time_min": retention_time_min,
        "pulp_solids_pct": pulp_solids_pct,
        "pulp_density_t_per_m3": round(pulp_density_t_per_m3, 3),
        "pulp_volumetric_flow_m3h": round(pulp_volumetric_flow_m3h, 2),
        "required_volume_m3": round(required_volume_m3, 1),
        "formula": "V = Q_pulp (m3/h) x Flotasyon Suresi (dk) / 60",
        "note": (
            "Standart muhendislik pulp hacim hesabi kullanilmistir (Wills' "
            "Mineral Processing Technology). Cevher ozgul agirligi ve pulp "
            "kati orani numune/tasarim kriterlerine gore degistirilmelidir - "
            "buradaki degerler tipik varsayimlardir, rapor verisi degildir."
        ),
    }


def suggest_cell_count(required_volume_m3: float, unit_cell_volume_m3: float) -> dict:
    """
    Gerekli toplam hacme ulasmak icin, verilen birim hucre hacmiyle kac
    adet hucreye ihtiyac oldugunu hesaplar (yukari yuvarlanir).
    """
    if unit_cell_volume_m3 <= 0:
        raise ValueError("Birim hucre hacmi pozitif olmali.")

    cell_count = math.ceil(required_volume_m3 / unit_cell_volume_m3)
    actual_total_volume = cell_count * unit_cell_volume_m3

    return {
        "required_volume_m3": required_volume_m3,
        "unit_cell_volume_m3": unit_cell_volume_m3,
        "suggested_cell_count": cell_count,
        "actual_total_volume_m3": round(actual_total_volume, 1),
        "excess_capacity_pct": round(
            (actual_total_volume - required_volume_m3) / required_volume_m3 * 100, 1
        ),
    }


@dataclass
class FlotationStageReference:
    stage: str
    retention_time_min: float
    source: str


# Altar Project - GERCEK, dogrulanmis flotasyon sureleri (Sekil 17-2)
ALTAR_RETENTION_TIMES = [
    FlotationStageReference("Rougher", 23, "Altar PEA, Sekil 17-2"),
    FlotationStageReference("Cleaner-1", 15, "Altar PEA, Sekil 17-2"),
    FlotationStageReference("Cleaner-2", 12.5, "Altar PEA, Sekil 17-2"),
    FlotationStageReference("Cleaner-3", 10, "Altar PEA, Sekil 17-2"),
]


if __name__ == "__main__":
    print("Flotasyon Hucresi Boyutlandirma - Ornek Kullanim\n" + "-" * 55)
    print("(Besleme miktari ve pulp kati orani SADECE ORNEK/TEMSILI degerlerdir)\n")

    for stage in ALTAR_RETENTION_TIMES:
        sonuc = flotation_cell_volume(
            throughput_tph=2717,  # ORNEK deger, gercek Altar verisi degil
            retention_time_min=stage.retention_time_min,
            pulp_solids_pct=35,  # ORNEK deger, gercek Altar verisi degil
        )
        print(
            f"[{stage.stage}] Flotasyon Suresi: {stage.retention_time_min} dk -> "
            f"Gerekli Hacim: {sonuc['required_volume_m3']:,.0f} m3"
        )

    print("\n--- Ornek: Rougher icin hucre adedi (birim hucre 160 m3 varsayimiyla) ---")
    rougher_hacim = flotation_cell_volume(2717, 23, 35)
    hucre_sonuc = suggest_cell_count(rougher_hacim["required_volume_m3"], unit_cell_volume_m3=160)
    print(
        f"Onerilen hucre adedi: {hucre_sonuc['suggested_cell_count']} adet "
        f"(toplam {hucre_sonuc['actual_total_volume_m3']} m3, "
        f"%{hucre_sonuc['excess_capacity_pct']} fazla kapasite)"
    )
