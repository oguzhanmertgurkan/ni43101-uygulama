"""
Boyut Küçültme (Comminution) Boyutlandırma Modülü
=====================================================
Kırma + Öğütme devresi için teknik boyutlandırma araçları.

İçerik:
1. Bond İş İndeksi (Bond Work Index) denklemi ile öğütme güç ihtiyacı hesabı
   - Bu, Fred Bond'un 1952'de geliştirdiği, sektörde evrensel kabul gören
     bir mühendislik denklemidir (rapor/proje verisi değil, genel bilim -
     tıpkı CAPEX modülündeki "güç yasası ölçekleme" gibi genel bir yöntem).
2. Kırma devresi aşama sayısı için kaba mühendislik kuralı (boyut küçültme
   oranı bazlı)
3. Altar Project referans veri noktası (GERÇEK, doğrulanmış ekipman
   boyutları - ama güç/Bond İş İndeksi verisi rapor tarafından açıkça
   verilmediği için Bond hesabı Altar üzerinden YAPILAMAZ, sadece
   ekipman konfigürasyonu referans/karşılaştırma amaçlı sunuluyor)
4. Aranzazu Mine Bond İş İndeksi REFERANS verisi (GERÇEK, ölçülmüş -
   Tablo 13-14) - 5 farklı zondan alinan variability örneklerinin
   laboratuvar Bond testi sonuçları. Bu değerler HESAPLAMADA VARSAYILAN
   OLARAK KULLANILMAZ (Wi hâlâ kullanıcının kendi test sonucunu girmesini
   gerektirir) - sadece "girdiğin değer makul bir aralıkta mi" şeklinde
   bir ÇAPRAZ KONTROL/MANTIK KONTROLÜ sağlar. Bu referans SADECE Aranzazu
   (skarn tipi Cu-Au-Ag, Glory Hole zonu) için geçerlidir - farklı
   mineralojide (orn. porfiri) doğrudan kullanılmamalıdır.

MİMARİ NOT: Ekipman MARKA/MODEL seçimi (orn. hangi tedarikçiden hangi
mill) bu modülün kapsamı DIŞINDA - o kullanıcının kendi tedarikçi
kataloglarından/tekliflerinden gireceği bilgi (reaktif modülündeki
mantıkla aynı).

MÜHENDİSLİK SINIRLAMASI: Bond denklemi orijinal olarak bilyalı değirmen
(ball mill) için geliştirilmiştir. SAG değirmen (yarı-otojen) devrelerinde
kesin sonuç için SPI/SMC gibi özel test yöntemleri kullanılır. Buradaki
hesap, kırma+öğütme devresinin TOPLAM enerji ihtiyacı için basitleştirilmiş
bir ilk yaklaşım (first-pass estimate) sunar - kesin mühendislik tasarımı
yerine geçmez.
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
    Bond'un Üçüncü Teorisi (Third Theory of Comminution) ile öğütme güç
    ihtiyacını hesaplar (Bond, 1952):

        W (kWh/t) = 10 * Wi * (1/sqrt(P80) - 1/sqrt(F80))

    throughput_tph: işlenen cevher besleme miktarı (ton/saat)
    work_index_kwh_per_t: Bond İş İndeksi - LABORATUVAR TESTİNDEN gelir,
        kullanıcı kendi cevher numunesinin test sonucunu girmeli
    f80_um: besleme boyutu, %80 geçen (mikron)
    p80_um: ürün (hedef öğütme) boyutu, %80 geçen (mikron)
    """
    if f80_um <= p80_um:
        raise ValueError("Besleme boyutu (F80), ürün boyutundan (P80) büyük olmalı.")
    if work_index_kwh_per_t <= 0 or throughput_tph <= 0:
        raise ValueError("İş indeksi ve besleme miktarı pozitif olmalı.")

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
        "formula": "Bond Üçüncü Teorisi (1952): W = 10 x Wi x (1/sqrt(P80) - 1/sqrt(F80))",
        "note": (
            "Wi değeri laboratuvar Bond İş İndeksi testinden gelmelidir "
            "(standart bir cevher hazırlama test hizmeti). Bu değer olmadan "
            "güvenilir bir güç tahmini yapılamaz. SAG değirmen için bu "
            "basitleştirilmiş bir ilk yaklaşımdır, kesin tasarım için "
            "SPI/SMC test yöntemleri önerilir."
        ),
    }


def suggest_crushing_stages(rom_size_mm: float, target_size_mm: float) -> dict:
    """
    ROM (Run of Mine) cevher boyutundan hedef boyuta ulaşmak için kaç
    aşamalı kırma gerekebileceğine dair KABA BİR MÜHENDİSLİK KURALI
    (rule of thumb) sunar. Kesin ekipman seçimi değil, ön-değerlendirme
    amaçlıdır.

    Tipik boyut küçültme oranları (genel endüstri kabulü):
    - Birincil (Primary) kırma: 3:1 - 6:1 (Gyratory/Jaw)
    - İkincil (Secondary) kırma: 3:1 - 5:1 (Cone)
    - Üçüncül (Tertiary) kırma: 2:1 - 4:1 (Cone/HPGR)
    """
    if target_size_mm <= 0 or rom_size_mm <= target_size_mm:
        raise ValueError("ROM boyutu, hedef boyuttan büyük olmalı.")

    reduction_ratio = rom_size_mm / target_size_mm

    if reduction_ratio <= 6:
        stages = 1
        config = "Tek aşamalı birincil kırma (Gyratory veya Jaw Crusher) yeterli olabilir"
    elif reduction_ratio <= 25:
        stages = 2
        config = "Birincil + İkincil kırma (Gyratory/Jaw + Cone Crusher) önerilir"
    else:
        stages = 3
        config = "Birincil + İkincil + Üçüncül kırma (veya HPGR entegrasyonu) gerekebilir"

    return {
        "rom_size_mm": rom_size_mm,
        "target_size_mm": target_size_mm,
        "reduction_ratio": round(reduction_ratio, 1),
        "suggested_stage_count": stages,
        "suggested_configuration": config,
        "note": (
            "Bu kaba bir ön-değerlendirmedir (genel endüstri kuralı), kesin "
            "mühendislik tasarımı değildir. Kesin ekipman seçimi için cevher "
            "sertliği (Crushability Index, Abrasion Index vb.) ve tedarikçi "
            "mühendislik değerlendirmesi gerekir."
        ),
    }


@dataclass
class BondWorkIndexReference:
    sample: str
    bond_wi_172um_kwh_per_t: float
    bond_wi_125um_kwh_per_t: float
    source: str


# Aranzazu Mine - GERÇEK, laboratuvarda ÖLÇÜLMÜŞ Bond İş İndeksi değerleri
# (Glory Hole zonu, 5 farklı variability orneği). Kapanma eleği (closing
# screen) 172um -> P80 150um öğütmeye, 125um -> P80 100um öğütmeye karşılık
# gelir (daha ince öğütmede Wi tipik olarak artar - cevher daha zor öğütülür
# hale gelir gibi görünür, bu "single-particle" öğütme mekanizmasi kayması
# ile açıklanır).
# bond_wi_125um_kwh_per_t = None -> bu örnek için 125um testi yapılmamış.
ARANZAZU_BOND_WI_REFERENCE = [
    BondWorkIndexReference("GH Pillar West", 10.5, 11.4, "Aranzazu NI 43-101 (2018 TR, Tablo 13-14)"),
    BondWorkIndexReference("GH Pillar Centre", 10.2, 11.7, "Aranzazu NI 43-101 (2018 TR, Tablo 13-14)"),
    BondWorkIndexReference("GH Pillar East", 9.3, 11.0, "Aranzazu NI 43-101 (2018 TR, Tablo 13-14)"),
    BondWorkIndexReference("BW Composite", 7.5, None, "Aranzazu NI 43-101 (2018 TR, Tablo 13-14)"),
    BondWorkIndexReference("Mexicana South", 9.6, None, "Aranzazu NI 43-101 (2018 TR, Tablo 13-14)"),
]


def check_work_index_against_reference(
    work_index_kwh_per_t: float,
    reference: list = ARANZAZU_BOND_WI_REFERENCE,
    closing_screen: str = "172um",
) -> dict:
    """
    Kullanıcının girdiği Bond İş İndeksi (Wi) değerini, Aranzazu'nun
    GERÇEK ölçülmüş Wi aralığıyla karşılaştırır. Bu bir ÇAPRAZ KONTROL/
    MANTIK KONTROLÜDÜR - Wi'yi HESAPLAMADA DEĞİŞTİRMEZ, sadece kullanıcıya
    "girdiğin değer, benzer bir skarn tipi Cu cevherinde ölçülmüş
    değerlerle tutarlı mi" konusunda bir fikir verir.

    SADECE Aranzazu (skarn tipi Cu-Au-Ag, Glory Hole zonu) için geçerlidir.
    Farklı mineralojide (orn. porfiri, epitermal) bu referans ARALIĞI
    ANLAMSIZDIR - Wi cevher tipine göre çok geniş bir aralıkta değişir
    (tipik endüstri aralığı ~5-25 kWh/t).

    closing_screen: "172um" (P80 150um öğütmeye karşılık gelir) veya
        "125um" (P80 100um öğütmeye karşılık gelir, sadece 3/5 örnekte
        test edilmiş)
    """
    if closing_screen not in ("172um", "125um"):
        raise ValueError('closing_screen "172um" veya "125um" olmalı.')

    field = "bond_wi_172um_kwh_per_t" if closing_screen == "172um" else "bond_wi_125um_kwh_per_t"
    values = [getattr(r, field) for r in reference if getattr(r, field) is not None]

    ref_min, ref_max = min(values), max(values)
    in_range = ref_min <= work_index_kwh_per_t <= ref_max

    return {
        "work_index_kwh_per_t": work_index_kwh_per_t,
        "closing_screen": closing_screen,
        "reference_min": ref_min,
        "reference_max": ref_max,
        "reference_sample_count": len(values),
        "in_range": in_range,
        "note": (
            f"Girilen Wi ({work_index_kwh_per_t} kWh/t), Aranzazu'da "
            f"{closing_screen} kapanma eleğinde ölçülmüş Bond İş İndeksi "
            f"aralığı ({ref_min}-{ref_max} kWh/t, {len(values)} örnek) "
            + ("içinde." if in_range else "DIŞINDA - farklı bir cevher tipi/sertliği olabilir, veya lab test hatası olabilir; kontrol önerilir.")
        ),
        "source": "Aranzazu NI 43-101 (2018 TR, Tablo 13-14) - SADECE Aranzazu/benzer skarn Cu cevheri için geçerli bir referans aralığıdır.",
    }


@dataclass
class EquipmentReference:
    project: str
    capacity_tpd: float
    equipment_type: str
    specification: str
    source: str


# Altar Project - GERÇEK, doğrulanmış ekipman konfigürasyonu (60,000 tpd için)
# Güç/Wi verisi rapor tarafından verilmediği için SADECE referans/karşılaştırma
# amaçlıdır, hesaplama girdisi olarak KULLANILMAZ.
ALTAR_EQUIPMENT_REFERENCE = [
    EquipmentReference(
        "Altar Project", 60000, "Kırma",
        "1x Ocak-içi yarı-mobil Gyratory Crusher, ROM -> ~150mm (6 inch)",
        "Altar PEA, Bölüm 17.1.1",
    ),
    EquipmentReference(
        "Altar Project", 60000, "SAG Değirmen",
        "1x 40ft x 26ft EGL, kapalı devre (çakıl eleği ile)",
        "Altar PEA, Bölüm 17.1.2",
    ),
    EquipmentReference(
        "Altar Project", 60000, "Bilyalı Değirmen",
        "1x 26ft çap x 40.7ft boy, kapalı devre (hidrosiklon), P80=190um",
        "Altar PEA, Bölüm 17.1.2",
    ),
    EquipmentReference(
        "Altar Project", 60000, "Yeniden Öğütme (Regrind)",
        "1x Karıştırmalı Kule Değirmen (Tower Mill), P80=18-20um",
        "Altar PEA, Bölüm 17.1.2",
    ),
]


if __name__ == "__main__":
    print("Boyut Küçültme Boyutlandırma Modülü - Örnek Kullanım\n" + "-" * 55)

    print("--- 1. Kırma Aşama Önerisi ---")
    kirma = suggest_crushing_stages(rom_size_mm=1000, target_size_mm=150)
    print(
        f"ROM: {kirma['rom_size_mm']}mm -> Hedef: {kirma['target_size_mm']}mm "
        f"(boyut küçültme oranı: {kirma['reduction_ratio']}:1)"
    )
    print(f"Öneri: {kirma['suggested_configuration']}\n")

    print("--- 2. Öğütme Güç İhtiyacı (Bond Denklemi, ÖRNEK Wi ile) ---")
    print("(Wi=14 kWh/t sadece TEMSİLİ örnek - gerçekte laboratuvar testinden gelmeli)")
    ogutme = bond_grinding_power_kw(
        throughput_tph=2717,  # ÖRNEK değer: 60,000 tpd / (24h x %92 kullanılabilirlik varsayımı)
                               # NOT: %92 kullanılabilirlik Altar raporundan DEĞİL, tipik bir
                               # endüstri varsayımından geliyor - gerçek değer değil
        work_index_kwh_per_t=14.0,  # ÖRNEK değer
        f80_um=150000,  # 150mm = 150,000 mikron (kırma sonrası, Altar'ın gerçek değeri)
        p80_um=190,  # Altar'ın gerçek hedef değeri
    )
    print(f"Spesifik enerji: {ogutme['specific_energy_kwh_per_t']} kWh/t")
    print(f"Gerekli güç: {ogutme['required_power_kw']:,.0f} kW\n")

    print("--- 3. Altar Project Referans Ekipman Konfigürasyonu (60,000 tpd) ---")
    for eq in ALTAR_EQUIPMENT_REFERENCE:
        print(f"  [{eq.equipment_type}] {eq.specification}")

    print("\n--- 4. Aranzazu Bond İş İndeksi Referans Aralığı (Tablo 13-14) ---")
    for ref in ARANZAZU_BOND_WI_REFERENCE:
        wi125 = f"{ref.bond_wi_125um_kwh_per_t} kWh/t" if ref.bond_wi_125um_kwh_per_t else "test edilmemiş"
        print(f"  [{ref.sample}] 172um: {ref.bond_wi_172um_kwh_per_t} kWh/t | 125um: {wi125}")

    print("\n--- 5. Girilen Wi değerinin çapraz kontrolü (ÖRNEK) ---")
    kontrol = check_work_index_against_reference(work_index_kwh_per_t=14.0, closing_screen="172um")
    print(kontrol["note"])
    kontrol2 = check_work_index_against_reference(work_index_kwh_per_t=9.0, closing_screen="172um")
    print(kontrol2["note"])
