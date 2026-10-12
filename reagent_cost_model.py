"""
Reaktif Maliyeti Hesaplama Çerçevesi (Framework)
===================================================

DÜZELTME NOTU: Bu dosyanın ilk versiyonunda, Altar Project raporundan geldiği
iddia edilen reaktif bazında kg/ton tüketim ve birim fiyat değerleri
YANLIŞLIKLA UYDURULMUŞTU. NI 43-101 PEA raporları genelde bu kırılımı kamuya
açmaz (sadece toplu $/ton rakamı verirler). Bu versiyon o hatayı düzeltir:
artık hiçbir sayı uydurulmuyor.

GERÇEK, RAPORDAN DOĞRULANMIŞ VERİ:
- Reaktif TÜRLERİ (Altar PEA, Bölüm 17.1.3 / Şekil 17-2):
    PAX (toplayıcı), Kireç (pH düzenleyici/pirit bastırıcı, hedef pH 10.5-11),
    MIBC (köpürtücü), Flokulant (koyulaştırma)
- Tesis toplam işleme birim maliyeti - reaktif+aşınma+enerji HEPSİ DAHİL,
  KIRILIMSIZ: $6.93 / ton cevher (Altar PEA, Tablo 21-2 / 1-4, 2025)
- Aranzazu Mine LOCKED CYCLE TEST reaktif dozajları (Aranzazu NI 43-101,
  2018 TR, Tablo 13-10) - GERÇEK, TEST ÖLÇEĞİNDE FİİLEN KULLANILMIŞ g/ton
  dozajlar. Bu test, raporun "%21 Cu, 14 g/t Au, 216 g/t Ag konsantre,
  >%90 Cu verim" başarı sonucunu ÜRETEN reaktif şemasıdır.
- Aranzazu arsenik depresan deneme sonuçları (Tablo 13-8) - farklı
  depresan seçenekleri (peroksit, NaS2, Na2ClO3, DETA/SO2) ve bunların
  Cu/As selektivitesine etkisi.

ÖNEMLİ SINIRLAMA: Yukarıdaki Aranzazu verileri TEST ÖLÇEĞİNDEDİR (2kg
laboratuvar numunesi) - tam ölçekli tesis tüketimi FARKLI olabilir
(devir/resirkülasyon, reaktif bozunması, verimlilik farkları nedeniyle).
Ayrıca Aranzazu'nun reaktif SUITI (Cytec 5100/3477 - thionocarbamate/
dithiophosphate) Altar'ın kullandığı PAX'tan (ksantat ailesi) FARKLI bir
kimyasal seçimdir - doğrudan karşılaştırılamaz, sadece "aynı kategori
için makul BÜYÜKLÜK MERTEBESI" fikri vermek amacıyla referans olarak
sunulur.

Mimari mantık: 3. şahıs kullanıcılar (şirketler) uygulamaya girdiğinde,
KENDİ tedarikçi tekliflerini (kg/ton tüketim + $/kg fiyat) kendileri
girecek. Bu modülün görevi hangi reaktif TÜRLERİNE ihtiyaç olduğunu doğru
önermek ve kullanıcının girdiği gerçek sayılardan maliyeti hesaplamak -
varsayılan sayı uydurmak değil.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ReagentSpec:
    """Bir reaktifin türü/rolü - miktar/fiyat içermez, bunlar kullanıcı girdisi olacak."""
    name: str
    category: str
    typical_role: str
    source: str


# Altar PEA'da adı geçen reaktif TÜRLERİ için öneri listesi (miktar/fiyat YOK)
COPPER_SULFIDE_FLOTATION_REAGENTS = [
    ReagentSpec(
        "PAX (Potassium Amyl Xanthate)", "toplayıcı",
        "Bakır sulfur minerallerini yüzdürmek için ana toplayıcı",
        "Altar PEA, Bölüm 17.1.3 / Şekil 17-2",
    ),
    ReagentSpec(
        "Kireç (Lime)", "pH_duzenleyici",
        "Ortam pH'ini 10.5-11 aralığında tutmak ve pirit bastırmak için",
        "Altar PEA, Bölüm 17.1.3 / Şekil 17-2",
    ),
    ReagentSpec(
        "MIBC", "köpürtücü",
        "Köpük oluşturmak için (frother)",
        "Altar PEA, Bölüm 17.1.3 / Şekil 17-2",
    ),
    ReagentSpec(
        "Flokulant", "flokulant",
        "Konsantre/atık koyulaştırıcılarında çökelmeyi hızlandırmak için",
        "Altar PEA, Bölüm 17.1.3 / Şekil 17-2",
    ),
]

# Bilinen tek güvenilir TOPLU referans değer - kırılım değil, sadece çapraz kontrol için
ALTAR_TOTAL_PROCESSING_OPEX_USD_PER_T = 6.93
ALTAR_TOTAL_PROCESSING_OPEX_SOURCE = "Altar PEA, Tablo 21-2 / 1-4 (2025) - reaktif+aşınma+enerji dahil, kırılımsız"


@dataclass
class ReagentTestDosage:
    """Laboratuvar test ölçeğinde FİİLEN KULLANILMIŞ reaktif dozajı (g/ton) -
    kullanıcının girdiği değerle KARŞILAŞTIRMA/BÜYÜKLÜK MERTEBESI kontrolü
    için, HESAPLAMAYA VARSAYILAN OLARAK DAHİL EDİLMEZ."""
    reagent_name: str
    reagent_role: str
    dosage_g_per_t: float
    test_stage: str
    source: str


# Aranzazu Mine - GERÇEK, Locked Cycle Test'te (Tablo 13-10) FİİLEN
# KULLANILMIŞ reaktif dozajları. Bu şema, raporun başarı olarak sunduğu
# "%21 Cu, 14 g/t Au, 216 g/t Ag konsantre, >%90 Cu verim" sonucunu
# ÜRETEN gerçek reaktif rejimidir - varsayımsal/temsili DEĞİL.
# TEST ÖLÇEĞİ (5x2kg numune) - tam ölçekli tesis tüketimi farklı olabilir.
ARANZAZU_LOCKED_CYCLE_TEST_DOSAGES = [
    ReagentTestDosage(
        "Kireç (Lime)", "pH_duzenleyici/pirit_bastirici", 2000,
        "Birincil Öğütme (pH 11.3 hedefiyle)",
        "Aranzazu NI 43-101 (2018 TR, Tablo 13-10)",
    ),
    ReagentTestDosage(
        "Cytec 5100 (thionocarbamate)", "toplayıcı", 4,
        "Birincil Öğütme",
        "Aranzazu NI 43-101 (2018 TR, Tablo 13-10)",
    ),
    ReagentTestDosage(
        "Cytec 3477 (dithiophosphate)", "toplayıcı", 4,
        "Rougher 1+2 + Rougher Scavenger 1+2 (toplam, 1 g/t x 4 aşama)",
        "Aranzazu NI 43-101 (2018 TR, Tablo 13-10)",
    ),
    ReagentTestDosage(
        "MIBC", "köpürtücü", 44,
        "Rougher 1",
        "Aranzazu NI 43-101 (2018 TR, Tablo 13-10)",
    ),
]


@dataclass
class ArsenicDepressantTrial:
    """Aranzazu cleaner flotasyon testlerinde denenen arsenik depresan
    seçenekleri (Tablo 13-8) - farklı kimyasalların Cu/As selektivitesine
    etkisi. SADECE Cu-As (enargit/tennantit) ayırma zorluğu olan skarn/
    porfiri Cu yatakları için referans niteliğinde."""
    compound: str
    dosage_g_per_t: Optional[float]
    addition_point: str
    cu_recovery_pct: float
    cu_as_selectivity_ratio: float
    note: str
    source: str


# Aranzazu Mine - GERÇEK cleaner test sonuçları (Tablo 13-8, seçilmiş
# örnekler). Cu-As (Cu/As) oranı, konsantredeki Cu/As kütle oranıdır -
# yüksek değer = daha iyi arsenik reddi (selektivite).
ARANZAZU_ARSENIC_DEPRESSANT_TRIALS = [
    ArsenicDepressantTrial(
        "Depresan yok (baseline)", 0, "-", 87.1, 4.8,
        "Referans/baseline test - depresansız",
        "Aranzazu NI 43-101 (2018 TR, Tablo 13-8, Test 13)",
    ),
    ArsenicDepressantTrial(
        "Hidrojen Peroksit", 85, "conditioning", 89.1, 6.3,
        "Marjinal selektivite artışı",
        "Aranzazu NI 43-101 (2018 TR, Tablo 13-8, Test 16)",
    ),
    ArsenicDepressantTrial(
        "DETA/SO2 (patentli As depresanı)", None, "conditioning", 90.1, 4.5,
        "DOZAJ DEĞERİ KAYNAK TABLODA OKUNAKLI DEĞİL (Excel tarih formatı "
        "bozulması olası - '17-May' gibi anlamsız bir değer görünüyor, "
        "gerçek g/t değeri belirsiz). En yüksek Cu verim görülen test - "
        "enargiti AKTİVE etmiş gibi görünüyor (selektiviteyi artırmadı, "
        "verimi artırdı).",
        "Aranzazu NI 43-101 (2018 TR, Tablo 13-8, Test 18)",
    ),
    ArsenicDepressantTrial(
        "Sodyum Sülfid (NaS2)", 220, "conditioning", 87.5, 6.6,
        "REDOX potansiyeli ile dozaj kontrolü yapıldı",
        "Aranzazu NI 43-101 (2018 TR, Tablo 13-8, Test 19)",
    ),
    ArsenicDepressantTrial(
        "Sodyum Sülfid (NaS2)", 662, "conditioning", 90.1, 6.9,
        "En yüksek NaS2 dozajı - en iyi selektivite ama yüksek reaktif "
        "maliyeti",
        "Aranzazu NI 43-101 (2018 TR, Tablo 13-8, Test 35)",
    ),
]


@dataclass
class UserReagentInput:
    """Kullanıcının (şirketin) kendi tedarikçisinden aldığı gerçek veri."""
    name: str
    consumption_kg_per_t: float
    unit_price_usd_per_kg: float


def calculate_reagent_cost(daily_tonnage: float, user_inputs: list) -> dict:
    """
    Kullanıcının girdiği gerçek tüketim + fiyat verisinden maliyet hesaplar.
    Hiçbir varsayılan/uydurma değer içermez - tüm sayısal değerler kullanıcı girdisidir.
    """
    if not user_inputs:
        raise ValueError("En az 1 reaktif girdisi gerekli (kullanıcı kendi tedarikçi verisini girmeli).")

    line_items = []
    total_cost_per_t = 0.0

    for inp in user_inputs:
        cost_per_t = inp.consumption_kg_per_t * inp.unit_price_usd_per_kg
        total_cost_per_t += cost_per_t
        line_items.append({
            "reagent": inp.name,
            "consumption_kg_per_t": inp.consumption_kg_per_t,
            "unit_price_usd_per_kg": inp.unit_price_usd_per_kg,
            "cost_usd_per_t": round(cost_per_t, 4),
            "daily_cost_usd": round(cost_per_t * daily_tonnage, 2),
        })

    return {
        "daily_tonnage": daily_tonnage,
        "total_cost_usd_per_t": round(total_cost_per_t, 4),
        "total_daily_cost_usd": round(total_cost_per_t * daily_tonnage, 2),
        "total_annual_cost_usd": round(total_cost_per_t * daily_tonnage * 365, 2),
        "line_items": line_items,
        "benchmark_note": (
            f"Karşılaştırma için: Altar Project raporunda toplam işleme maliyeti "
            f"(reaktif+aşınma+enerji, kırılımsız) ${ALTAR_TOTAL_PROCESSING_OPEX_USD_PER_T}/ton "
            f"olarak raporlanmıştı ({ALTAR_TOTAL_PROCESSING_OPEX_SOURCE}). Girilen sadece "
            f"reaktif maliyeti olduğu için bu rakamdan DÜŞÜK çıkması beklenir - "
            f"aradaki fark aşınma malzemesi + enerji maliyetini temsil eder."
        ),
    }


if __name__ == "__main__":
    print("Reaktif Maliyeti Hesaplama - ÖRNEK Kullanım\n" + "-" * 55)
    print("(Aşağıdaki sayılar SADECE TEMSİLİ ÖRNEK - gerçek tedarikçi verisi DEĞİL,")
    print(" gerçek kullanımda bu değerler kullanıcı tarafından girilecek)\n")

    ornek_girdi = [
        UserReagentInput("PAX", consumption_kg_per_t=0.010, unit_price_usd_per_kg=4.20),
        UserReagentInput("Kireç (Lime)", consumption_kg_per_t=1.0, unit_price_usd_per_kg=0.35),
        UserReagentInput("MIBC", consumption_kg_per_t=0.015, unit_price_usd_per_kg=3.80),
    ]

    sonuc = calculate_reagent_cost(daily_tonnage=60000, user_inputs=ornek_girdi)

    for item in sonuc["line_items"]:
        print(
            f"  {item['reagent']:<20} {item['consumption_kg_per_t']:.3f} kg/t x "
            f"${item['unit_price_usd_per_kg']:.2f}/kg = ${item['cost_usd_per_t']:.4f}/t"
        )

    print(f"\n  TOPLAM (bu örnek girdiyle): ${sonuc['total_cost_usd_per_t']:.2f}/ton")
    print(f"\n{sonuc['benchmark_note']}")

    print("\n--- Aranzazu Locked Cycle Test Reaktif Dozajları (Tablo 13-10) ---")
    print("(GERÇEK test verisi - TEST ÖLÇEĞİ, tam ölçekli tesis tüketimi değil)")
    for d in ARANZAZU_LOCKED_CYCLE_TEST_DOSAGES:
        print(f"  [{d.reagent_name}] {d.dosage_g_per_t} g/t - {d.test_stage}")

    print("\n--- Aranzazu Arsenik Depresan Deneme Sonuçları (Tablo 13-8) ---")
    for t in ARANZAZU_ARSENIC_DEPRESSANT_TRIALS:
        dozaj = f"{t.dosage_g_per_t} g/t" if t.dosage_g_per_t is not None else "dozaj belirsiz"
        print(f"  [{t.compound}] {dozaj} -> Cu Verim: %{t.cu_recovery_pct}, Cu/As oran: {t.cu_as_selectivity_ratio}")
