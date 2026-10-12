"""
Flotasyon Hücresi Boyutlandırma Modülü
=========================================
Standart mühendislik pulp hacim hesabı (Wills' Mineral Processing Technology
ve benzeri referans kaynaklarda yer alan klasik yöntem) kullanarak, verilen
flotasyon süresi (retention time) ve besleme koşullarından gerekli toplam
hücre hacmini hesaplar.

GERÇEK, RAPORDAN DOĞRULANMIŞ VERİ (Altar PEA, Şekil 17-2):
- Rougher flotasyon süresi: 23 dakika
- Cleaner-1 flotasyon süresi: 15 dakika
- Cleaner-2 flotasyon süresi: 12.5 dakika
- Cleaner-3 flotasyon süresi: 10 dakika

GERÇEK, RAPORDAN DOĞRULANMIŞ VERİ (Aranzazu NI 43-101, 2018 TR, Şekil 13-9
ve 13-12) - LABORATUVAR BATCH TEST süreleri (endüstriyel tasarım retention
time'i DEĞİL):
- Rougher batch test: 4 aşama x 2 dk = 8 dk toplam
- Cleaner batch test: Cleaner 1A (2dk) + 1B (4dk) + 1C (6dk) = 12 dk toplam

ÖLÇEK BÜYÜTME (SCALE-UP) - GENEL LİTERATÜR, KİTAP/RAPOR VERİSİ DEĞİL:
Laboratuvar batch test süresinden endüstriyel tasarım retention time'ina
geçiş için bir "scale-up factor" (ölçek büyütme katsayısı) gerekir - bu,
Wills'in kitabında (elimizdeki özet bölümde) sayısal olarak verilmeyen,
ama genel mineral işleme mühendisliği literatüründe iyi belgelenmiş bir
konu. Bu modül, akademik/endüstri kaynaklarından (Murphy & Heath 2011
AusIMM; Yianatos ve diğerleri) derlenmiş TİPİK ARALIKLARI referans olarak
sunar - proje-özel bir değer DEĞİLDİR, sadece "batch test süresi X ise,
tasarım retention time'i kabaca ne olabilir" sorusuna kaba bir tahmin
sağlar. Gerçek tasarım değeri HER ZAMAN pilot test/detaylı mühendislik
değerlendirmesi gerektirir.

NOT: Pulp yoğunluğu (% katı oran) ve cevher özgül ağırlığı her devre
aşaması için rapor tarafından açıkça verilmediği için bu değerler
KULLANICI GİRDİSİ olarak alınır (varsayılan değerler sadece ÖRNEK/TEMSİLİ
tipik değerlerdir, Altar raporundan alınmış gerçek veri DEĞİLDİR).
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
    Belirli bir flotasyon süresi için gerekli toplam hücre hacmini hesaplar.

    throughput_tph: kuru katı besleme miktarı (ton/saat)
    retention_time_min: hedeflenen flotasyon süresi (dakika)
    pulp_solids_pct: pulp içi katı oran, ağırlıkça (%)
    ore_specific_gravity: cevherin özgül ağırlığı (t/m3) - varsayılan 2.8
        tipik bir bakır porfiri cevheri için KABA bir ORTALAMA değerdir,
        gerçek değer numuneden ölçülmelidir
    """
    if not (0 < pulp_solids_pct < 100):
        raise ValueError("Pulp katı oranı 0-100 arasında olmalı.")
    if throughput_tph <= 0 or retention_time_min <= 0:
        raise ValueError("Besleme miktarı ve flotasyon süresi pozitif olmalı.")

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
        "formula": "V = Q_pulp (m3/h) x Flotasyon Süresi (dk) / 60",
        "note": (
            "Standart mühendislik pulp hacim hesabı kullanılmıştır (Wills' "
            "Mineral Processing Technology). Cevher özgül ağırlığı ve pulp "
            "katı oranı numune/tasarım kriterlerine göre değiştirilmelidir - "
            "buradaki değerler tipik varsayımlardır, rapor verisi değildir."
        ),
    }


def suggest_cell_count(required_volume_m3: float, unit_cell_volume_m3: float) -> dict:
    """
    Gerekli toplam hacme ulaşmak için, verilen birim hücre hacmiyle kaç
    adet hücreye ihtiyaç olduğunu hesaplar (yukarı yuvarlanır).
    """
    if unit_cell_volume_m3 <= 0:
        raise ValueError("Birim hücre hacmi pozitif olmalı.")

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


# Altar Project - GERÇEK, doğrulanmış flotasyon süreleri (Şekil 17-2)
ALTAR_RETENTION_TIMES = [
    FlotationStageReference("Rougher", 23, "Altar PEA, Şekil 17-2"),
    FlotationStageReference("Cleaner-1", 15, "Altar PEA, Şekil 17-2"),
    FlotationStageReference("Cleaner-2", 12.5, "Altar PEA, Şekil 17-2"),
    FlotationStageReference("Cleaner-3", 10, "Altar PEA, Şekil 17-2"),
]

# Aranzazu Mine - GERÇEK, LABORATUVAR BATCH TEST süreleri (Şekil 13-9/13-12).
# ÖNEMLİ: Bunlar endüstriyel tasarım retention time'i DEĞİL, küçük ölçekli
# (lab flotasyon hücresi) kinetik test süreleridir - doğrudan tasarıma
# KULLANILAMAZ, ancak SCALE-UP FACTOR uygulanarak kaba bir tasarım tahmini
# için başlangıç noktası olabilir (bkz. estimate_industrial_retention_time).
ARANZAZU_BATCH_TEST_TIMES = [
    FlotationStageReference("Rougher (batch test, 4 aşama toplamı)", 8, "Aranzazu NI 43-101 (2018 TR, Şekil 13-9)"),
    FlotationStageReference("Cleaner (batch test, 1A+1B+1C toplamı)", 12, "Aranzazu NI 43-101 (2018 TR, Şekil 13-12)"),
]


@dataclass
class ScaleUpFactorReference:
    """Laboratuvar batch flotasyon test süresinden endüstriyel tasarım
    retention time'ina geçiş için GENEL LİTERATÜR ölçek büyütme katsayısı.
    RAPOR VERİSİ veya Wills'in kitabından DOĞRUDAN alınmış bir sayı DEĞİLDİR
    - genel mineral işleme mühendisliği literatüründen derlenmiştir."""
    category: str
    factor_min: float
    factor_max: float
    typical_value: float
    note: str
    source: str


# GENEL LİTERATÜR REFERANSI - proje raporlarından (Aranzazu/Altar/La Mina)
# BAĞIMSIZ, akademik/endüstri kaynaklarından derlenmiş tipik ölçek büyütme
# aralıkları. Farklı hücre tipi/cevher/karışma koşuluna göre GENİŞ bir
# aralıkta değişebilir - kesin tasarım değeri HER ZAMAN pilot test/
# mühendislik değerlendirmesi gerektirir.
FLOTATION_SCALEUP_LITERATURE = [
    ScaleUpFactorReference(
        "Genel (tüm cevher tipleri, mekanik hücre)",
        1.5, 3.0, 2.15,
        "Endüstri genelinde en yaygın kullanılan aralık - makine tipi, "
        "cevher tipi ve deneyime göre seçilir.",
        "Murphy & Heath (2011, AusIMM, 'Selection of Mechanical Flotation "
        "Equipment'); ayrıca çeşitli akademik çalışmalar (Yianatos ve "
        "diğerleri, Kalapudas 1985, Arbiter 2000) benzer aralığı dogrular",
    ),
    ScaleUpFactorReference(
        "Bakır sulfur flotasyonu (mekanik hücre)",
        2.1, 2.6, 2.35,
        "Bakır (ve Mo by-product) için endüstride sıklıkla atıfta "
        "bulunulan spesifik aralık - genel aralığın üst-orta kısmına "
        "denk gelir.",
        "911Metallurgist derlemesi, gerçek bir NI 43-101 örneğine "
        "dayanarak (Pebble Project, Northern Dynasty Minerals, Alaska - "
        "Cu-Mo flotasyonu)",
    ),
    ScaleUpFactorReference(
        "Kolon hücreler (mekanik hücre DEĞİL)",
        6.0, 10.0, None,
        "Mekanik hücrelerden ÇOK DAHA YÜKSEK - farklı hidrodinamik/"
        "karışma rejimi (plug-flow'a daha yakın). Bu proje mekanik "
        "hücre varsayımı kullanıyor (Altar/Aranzazu referanslarıyla "
        "tutarlı), bu satır sadece karşılaştırma için.",
        "911Metallurgist derlemesi",
    ),
]


def estimate_industrial_retention_time(
    batch_test_time_min: float,
    scale_up_factor: float = None,
    category: str = "bakir_sulfur",
) -> dict:
    """
    Laboratuvar batch flotasyon test süresinden, GENEL LİTERATÜR ölçek
    büyütme katsayısı kullanarak KABA bir endüstriyel tasarım retention
    time TAHMİNİ uretir.

    ÖNEMLİ SINIRLAMA: Bu KESİN bir tasarım değeri DEĞİLDİR - sadece
    "batch test süresi X ise, tasarım ne civarda olabilir" sorusuna kaba
    bir başlangıç noktası sağlar. Gerçek tasarım için pilot test veya
    detaylı mühendislik değerlendirmesi (hücre tipi, karışma rejimi,
    cevher-spesifik faktörler dahil) gerekir.

    batch_test_time_min: laboratuvar batch test süresi (dakika)
    scale_up_factor: elle bir katsayı verilebilir; verilmezse `category`
        parametresine göre FLOTATION_SCALEUP_LITERATURE'daki tipik değer
        kullanılır
    category: "genel" veya "bakir_sulfur" (FLOTATION_SCALEUP_LITERATURE
        referans kategorileriyle eşleşir)
    """
    if batch_test_time_min <= 0:
        raise ValueError("Batch test süresi pozitif olmalı.")

    category_map = {
        "genel": FLOTATION_SCALEUP_LITERATURE[0],
        "bakir_sulfur": FLOTATION_SCALEUP_LITERATURE[1],
    }
    if category not in category_map:
        raise ValueError(f"Desteklenmeyen kategori: {category}. Seçenekler: {list(category_map)}")

    ref = category_map[category]
    factor = scale_up_factor if scale_up_factor is not None else ref.typical_value

    estimated_min = batch_test_time_min * factor
    estimated_range_min = batch_test_time_min * ref.factor_min
    estimated_range_max = batch_test_time_min * ref.factor_max

    return {
        "batch_test_time_min": batch_test_time_min,
        "scale_up_factor_used": factor,
        "estimated_design_retention_time_min": round(estimated_min, 1),
        "estimated_range_min": round(estimated_range_min, 1),
        "estimated_range_max": round(estimated_range_max, 1),
        "category": category,
        "note": (
            f"Bu, {ref.category.lower()} için GENEL LİTERATÜR katsayısıyla "
            f"({ref.factor_min}x-{ref.factor_max}x aralığı, tipik "
            f"{ref.typical_value}x) üretilmiş KABA bir tahmindir - rapor "
            f"verisi veya kesin tasarım değeri DEĞİLDİR. Gerçek tasarım "
            f"için pilot test/detaylı mühendislik değerlendirmesi gerekir."
        ),
        "source": ref.source,
    }


if __name__ == "__main__":
    print("Flotasyon Hücresi Boyutlandırma - Örnek Kullanım\n" + "-" * 55)
    print("(Besleme miktarı ve pulp katı oranı SADECE ÖRNEK/TEMSİLİ değerlerdir)\n")

    for stage in ALTAR_RETENTION_TIMES:
        sonuc = flotation_cell_volume(
            throughput_tph=2717,  # ÖRNEK değer, gerçek Altar verisi değil
            retention_time_min=stage.retention_time_min,
            pulp_solids_pct=35,  # ÖRNEK değer, gerçek Altar verisi değil
        )
        print(
            f"[{stage.stage}] Flotasyon Süresi: {stage.retention_time_min} dk -> "
            f"Gerekli Hacim: {sonuc['required_volume_m3']:,.0f} m3"
        )

    print("\n--- Örnek: Rougher için hücre adedi (birim hücre 160 m3 varsayımıyla) ---")
    rougher_hacim = flotation_cell_volume(2717, 23, 35)
    hucre_sonuc = suggest_cell_count(rougher_hacim["required_volume_m3"], unit_cell_volume_m3=160)
    print(
        f"Önerilen hücre adedi: {hucre_sonuc['suggested_cell_count']} adet "
        f"(toplam {hucre_sonuc['actual_total_volume_m3']} m3, "
        f"%{hucre_sonuc['excess_capacity_pct']} fazla kapasite)"
    )

    print("\n--- Ölçek Büyütme Çapraz Kontrolü: Aranzazu batch test -> tahmini tasarım ---")
    print("(GENEL LİTERATÜR katsayısıyla KABA tahmin - kesin değer değil)")
    for stage in ARANZAZU_BATCH_TEST_TIMES:
        tahmin = estimate_industrial_retention_time(stage.retention_time_min, category="bakir_sulfur")
        print(
            f"[{stage.stage}] Batch: {stage.retention_time_min} dk -> "
            f"Tahmini tasarım: {tahmin['estimated_design_retention_time_min']} dk "
            f"(aralık: {tahmin['estimated_range_min']}-{tahmin['estimated_range_max']} dk)"
        )
    print(
        "\nKarsilastirma: Altar'ın GERÇEK tasarım değeri Rougher için 23 dk idi. "
        "Aranzazu batch test (8 dk) x 2.1-2.6 = 16.8-20.8 dk aralığı, Altar'ın "
        "gerçek değeriyle (23 dk) MAKUL BİR BÜYÜKLÜK MERTEBESINDE - farklı "
        "yataklar/tesisler olduğu için birebir eşleşmesi beklenmez, ama metodoloji "
        "tutarlılığı için iyi bir işaret."
    )
