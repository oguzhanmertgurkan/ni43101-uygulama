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

GERCEK, RAPORDAN DOGRULANMIS VERI (Aranzazu NI 43-101, 2018 TR, Sekil 13-9
ve 13-12) - LABORATUVAR BATCH TEST sureleri (endustriyel tasarim retention
time'i DEGIL):
- Rougher batch test: 4 asama x 2 dk = 8 dk toplam
- Cleaner batch test: Cleaner 1A (2dk) + 1B (4dk) + 1C (6dk) = 12 dk toplam

OLCEK BUYUTME (SCALE-UP) - GENEL LITERATUR, KITAP/RAPOR VERISI DEGIL:
Laboratuvar batch test suresinden endustriyel tasarim retention time'ina
gecis icin bir "scale-up factor" (olcek buyutme katsayisi) gerekir - bu,
Wills'in kitabinda (elimizdeki ozet bolumde) sayisal olarak verilmeyen,
ama genel mineral isleme muhendisligi literaturunde iyi belgelenmis bir
konu. Bu modul, akademik/endustri kaynaklarindan (Murphy & Heath 2011
AusIMM; Yianatos ve digerleri) derlenmis TIPIK ARALIKLARI referans olarak
sunar - proje-ozel bir deger DEGILDIR, sadece "batch test suresi X ise,
tasarim retention time'i kabaca ne olabilir" sorusuna kaba bir tahmin
saglar. Gercek tasarim degeri HER ZAMAN pilot test/detayli muhendislik
degerlendirmesi gerektirir.

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

# Aranzazu Mine - GERCEK, LABORATUVAR BATCH TEST sureleri (Sekil 13-9/13-12).
# ONEMLI: Bunlar endustriyel tasarim retention time'i DEGIL, kucuk olcekli
# (lab flotasyon hucresi) kinetik test sureleridir - dogrudan tasarima
# KULLANILAMAZ, ancak SCALE-UP FACTOR uygulanarak kaba bir tasarim tahmini
# icin baslangic noktasi olabilir (bkz. estimate_industrial_retention_time).
ARANZAZU_BATCH_TEST_TIMES = [
    FlotationStageReference("Rougher (batch test, 4 asama toplami)", 8, "Aranzazu NI 43-101 (2018 TR, Sekil 13-9)"),
    FlotationStageReference("Cleaner (batch test, 1A+1B+1C toplami)", 12, "Aranzazu NI 43-101 (2018 TR, Sekil 13-12)"),
]


@dataclass
class ScaleUpFactorReference:
    """Laboratuvar batch flotasyon test suresinden endustriyel tasarim
    retention time'ina gecis icin GENEL LITERATUR olcek buyutme katsayisi.
    RAPOR VERISI veya Wills'in kitabindan DOGRUDAN alinmis bir sayi DEGILDIR
    - genel mineral isleme muhendisligi literaturunden derlenmistir."""
    category: str
    factor_min: float
    factor_max: float
    typical_value: float
    note: str
    source: str


# GENEL LITERATUR REFERANSI - proje raporlarindan (Aranzazu/Altar/La Mina)
# BAGIMSIZ, akademik/endustri kaynaklarindan derlenmis tipik olcek buyutme
# araliklari. Farkli hucre tipi/cevher/karisma kosuluna gore GENIS bir
# aralikta degisebilir - kesin tasarim degeri HER ZAMAN pilot test/
# muhendislik degerlendirmesi gerektirir.
FLOTATION_SCALEUP_LITERATURE = [
    ScaleUpFactorReference(
        "Genel (tum cevher tipleri, mekanik hucre)",
        1.5, 3.0, 2.15,
        "Endustri genelinde en yaygin kullanilan aralik - makine tipi, "
        "cevher tipi ve deneyime gore secilir.",
        "Murphy & Heath (2011, AusIMM, 'Selection of Mechanical Flotation "
        "Equipment'); ayrica cesitli akademik calismalar (Yianatos ve "
        "digerleri, Kalapudas 1985, Arbiter 2000) benzer araligi dogrular",
    ),
    ScaleUpFactorReference(
        "Bakir sulfur flotasyonu (mekanik hucre)",
        2.1, 2.6, 2.35,
        "Bakir (ve Mo by-product) icin endustride siklikla atifta "
        "bulunulan spesifik aralik - genel araligin ust-orta kismina "
        "denk gelir.",
        "911Metallurgist derlemesi, gercek bir NI 43-101 ornegine "
        "dayanarak (Pebble Project, Northern Dynasty Minerals, Alaska - "
        "Cu-Mo flotasyonu)",
    ),
    ScaleUpFactorReference(
        "Kolon hucreler (mekanik hucre DEGIL)",
        6.0, 10.0, None,
        "Mekanik hucrelerden COK DAHA YUKSEK - farkli hidrodinamik/"
        "karisma rejimi (plug-flow'a daha yakin). Bu proje mekanik "
        "hucre varsayimi kullaniyor (Altar/Aranzazu referanslariyla "
        "tutarli), bu satir sadece karsilastirma icin.",
        "911Metallurgist derlemesi",
    ),
]


def estimate_industrial_retention_time(
    batch_test_time_min: float,
    scale_up_factor: float = None,
    category: str = "bakir_sulfur",
) -> dict:
    """
    Laboratuvar batch flotasyon test suresinden, GENEL LITERATUR olcek
    buyutme katsayisi kullanarak KABA bir endustriyel tasarim retention
    time TAHMINI uretir.

    ONEMLI SINIRLAMA: Bu KESIN bir tasarim degeri DEGILDIR - sadece
    "batch test suresi X ise, tasarim ne civarda olabilir" sorusuna kaba
    bir baslangic noktasi saglar. Gercek tasarim icin pilot test veya
    detayli muhendislik degerlendirmesi (hucre tipi, karisma rejimi,
    cevher-spesifik faktorler dahil) gerekir.

    batch_test_time_min: laboratuvar batch test suresi (dakika)
    scale_up_factor: elle bir katsayi verilebilir; verilmezse `category`
        parametresine gore FLOTATION_SCALEUP_LITERATURE'daki tipik deger
        kullanilir
    category: "genel" veya "bakir_sulfur" (FLOTATION_SCALEUP_LITERATURE
        referans kategorileriyle eslesir)
    """
    if batch_test_time_min <= 0:
        raise ValueError("Batch test suresi pozitif olmali.")

    category_map = {
        "genel": FLOTATION_SCALEUP_LITERATURE[0],
        "bakir_sulfur": FLOTATION_SCALEUP_LITERATURE[1],
    }
    if category not in category_map:
        raise ValueError(f"Desteklenmeyen kategori: {category}. Secenekler: {list(category_map)}")

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
            f"Bu, {ref.category.lower()} icin GENEL LITERATUR katsayisiyla "
            f"({ref.factor_min}x-{ref.factor_max}x araligi, tipik "
            f"{ref.typical_value}x) uretilmis KABA bir tahmindir - rapor "
            f"verisi veya kesin tasarim degeri DEGILDIR. Gercek tasarim "
            f"icin pilot test/detayli muhendislik degerlendirmesi gerekir."
        ),
        "source": ref.source,
    }


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

    print("\n--- Olcek Buyutme Capraz Kontrolu: Aranzazu batch test -> tahmini tasarim ---")
    print("(GENEL LITERATUR katsayisiyla KABA tahmin - kesin deger degil)")
    for stage in ARANZAZU_BATCH_TEST_TIMES:
        tahmin = estimate_industrial_retention_time(stage.retention_time_min, category="bakir_sulfur")
        print(
            f"[{stage.stage}] Batch: {stage.retention_time_min} dk -> "
            f"Tahmini tasarim: {tahmin['estimated_design_retention_time_min']} dk "
            f"(aralik: {tahmin['estimated_range_min']}-{tahmin['estimated_range_max']} dk)"
        )
    print(
        "\nKarsilastirma: Altar'in GERCEK tasarim degeri Rougher icin 23 dk idi. "
        "Aranzazu batch test (8 dk) x 2.1-2.6 = 16.8-20.8 dk araligi, Altar'in "
        "gercek degeriyle (23 dk) MAKUL BIR BUYUKLUK MERTEBESINDE - farkli "
        "yataklar/tesisler oldugu icin birebir eslesmesi beklenmez, ama metodoloji "
        "tutarliligi icin iyi bir isaret."
    )
