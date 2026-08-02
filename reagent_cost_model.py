"""
Reaktif Maliyeti Hesaplama Cercevesi (Framework)
===================================================

DUZELTME NOTU: Bu dosyanin ilk versiyonunda, Altar Project raporundan geldigi
iddia edilen reaktif bazinda kg/ton tuketim ve birim fiyat degerleri
YANLISLIKLA UYDURULMUSTU. NI 43-101 PEA raporlari genelde bu kirilimi kamuya
acmaz (sadece toplu $/ton rakami verirler). Bu versiyon o hatayi duzeltir:
artik hicbir sayi uydurulmuyor.

GERCEK, RAPORDAN DOGRULANMIS VERI:
- Reaktif TURLERI (Altar PEA, Bolum 17.1.3 / Sekil 17-2):
    PAX (toplayici), Kirec (pH duzenleyici/pirit bastirici, hedef pH 10.5-11),
    MIBC (kopurtucu), Flokulant (koyulastirma)
- Tesis toplam isleme birim maliyeti - reaktif+asinma+enerji HEPSI DAHIL,
  KIRILIMSIZ: $6.93 / ton cevher (Altar PEA, Tablo 21-2 / 1-4, 2025)
- Aranzazu Mine LOCKED CYCLE TEST reaktif dozajlari (Aranzazu NI 43-101,
  2018 TR, Tablo 13-10) - GERCEK, TEST OLCEGINDE FIILEN KULLANILMIS g/ton
  dozajlar. Bu test, raporun "%21 Cu, 14 g/t Au, 216 g/t Ag konsantre,
  >%90 Cu kurtarma" basari sonucunu URETEN reaktif semasidir.
- Aranzazu arsenik depresan deneme sonuclari (Tablo 13-8) - farkli
  depresan secenekleri (peroksit, NaS2, Na2ClO3, DETA/SO2) ve bunlarin
  Cu/As selektivitesine etkisi.

ONEMLI SINIRLAMA: Yukaridaki Aranzazu verileri TEST OLCEGINDEDIR (2kg
laboratuvar numunesi) - tam olcekli tesis tuketimi FARKLI olabilir
(devir/resirkulasyon, reaktif bozunmasi, verimlilik farklari nedeniyle).
Ayrica Aranzazu'nun reaktif SUITI (Cytec 5100/3477 - thionocarbamate/
dithiophosphate) Altar'in kullandigi PAX'tan (ksantat ailesi) FARKLI bir
kimyasal secimdir - dogrudan karsilastirilamaz, sadece "ayni kategori
icin makul BUYUKLUK MERTEBESI" fikri vermek amaciyla referans olarak
sunulur.

Mimari mantik: 3. sahis kullanicilar (sirketler) uygulamaya girdiginde,
KENDI tedarikci tekliflerini (kg/ton tuketim + $/kg fiyat) kendileri
girecek. Bu modulun gorevi hangi reaktif TURLERINE ihtiyac oldugunu dogru
onermek ve kullanicinin girdigi gercek sayilardan maliyeti hesaplamak -
varsayilan sayi uydurmak degil.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ReagentSpec:
    """Bir reaktifin turu/rolu - miktar/fiyat icermez, bunlar kullanici girdisi olacak."""
    name: str
    category: str
    typical_role: str
    source: str


# Altar PEA'da adi gecen reaktif TURLERI icin oneri listesi (miktar/fiyat YOK)
COPPER_SULFIDE_FLOTATION_REAGENTS = [
    ReagentSpec(
        "PAX (Potassium Amyl Xanthate)", "toplayici",
        "Bakir sulfur minerallerini yuzdurmek icin ana toplayici",
        "Altar PEA, Bolum 17.1.3 / Sekil 17-2",
    ),
    ReagentSpec(
        "Kirec (Lime)", "pH_duzenleyici",
        "Ortam pH'ini 10.5-11 araliginda tutmak ve pirit bastirmak icin",
        "Altar PEA, Bolum 17.1.3 / Sekil 17-2",
    ),
    ReagentSpec(
        "MIBC", "kopurtucu",
        "Kopuk olusturmak icin (frother)",
        "Altar PEA, Bolum 17.1.3 / Sekil 17-2",
    ),
    ReagentSpec(
        "Flokulant", "flokulant",
        "Konsantre/atik koyulasticilarinda cokelmeyi hizlandirmak icin",
        "Altar PEA, Bolum 17.1.3 / Sekil 17-2",
    ),
]

# Bilinen tek guvenilir TOPLU referans deger - kirilim degil, sadece capraz kontrol icin
ALTAR_TOTAL_PROCESSING_OPEX_USD_PER_T = 6.93
ALTAR_TOTAL_PROCESSING_OPEX_SOURCE = "Altar PEA, Tablo 21-2 / 1-4 (2025) - reaktif+asinma+enerji dahil, kirilimsiz"


@dataclass
class ReagentTestDosage:
    """Laboratuvar test olceginde FIILEN KULLANILMIS reaktif dozaji (g/ton) -
    kullanicinin girdigi degerle KARSILASTIRMA/BUYUKLUK MERTEBESI kontrolu
    icin, HESAPLAMAYA VARSAYILAN OLARAK DAHIL EDILMEZ."""
    reagent_name: str
    reagent_role: str
    dosage_g_per_t: float
    test_stage: str
    source: str


# Aranzazu Mine - GERCEK, Locked Cycle Test'te (Tablo 13-10) FIILEN
# KULLANILMIS reaktif dozajlari. Bu sema, raporun basari olarak sundugu
# "%21 Cu, 14 g/t Au, 216 g/t Ag konsantre, >%90 Cu kurtarma" sonucunu
# URETEN gercek reaktif rejimidir - varsayimsal/temsili DEGIL.
# TEST OLCEGI (5x2kg numune) - tam olcekli tesis tuketimi farkli olabilir.
ARANZAZU_LOCKED_CYCLE_TEST_DOSAGES = [
    ReagentTestDosage(
        "Kirec (Lime)", "pH_duzenleyici/pirit_bastirici", 2000,
        "Birincil Ogutme (pH 11.3 hedefiyle)",
        "Aranzazu NI 43-101 (2018 TR, Tablo 13-10)",
    ),
    ReagentTestDosage(
        "Cytec 5100 (thionocarbamate)", "toplayici", 4,
        "Birincil Ogutme",
        "Aranzazu NI 43-101 (2018 TR, Tablo 13-10)",
    ),
    ReagentTestDosage(
        "Cytec 3477 (dithiophosphate)", "toplayici", 4,
        "Rougher 1+2 + Rougher Scavenger 1+2 (toplam, 1 g/t x 4 asama)",
        "Aranzazu NI 43-101 (2018 TR, Tablo 13-10)",
    ),
    ReagentTestDosage(
        "MIBC", "kopurtucu", 44,
        "Rougher 1",
        "Aranzazu NI 43-101 (2018 TR, Tablo 13-10)",
    ),
]


@dataclass
class ArsenicDepressantTrial:
    """Aranzazu cleaner flotasyon testlerinde denenen arsenik depresan
    secenekleri (Tablo 13-8) - farkli kimyasallarin Cu/As selektivitesine
    etkisi. SADECE Cu-As (enargit/tennantit) ayirma zorlugu olan skarn/
    porfiri Cu yataklari icin referans niteliginde."""
    compound: str
    dosage_g_per_t: Optional[float]
    addition_point: str
    cu_recovery_pct: float
    cu_as_selectivity_ratio: float
    note: str
    source: str


# Aranzazu Mine - GERCEK cleaner test sonuclari (Tablo 13-8, secilmis
# ornekler). Cu-As (Cu/As) orani, konsantredeki Cu/As kutle oranidir -
# yuksek deger = daha iyi arsenik reddi (selektivite).
ARANZAZU_ARSENIC_DEPRESSANT_TRIALS = [
    ArsenicDepressantTrial(
        "Depresan yok (baseline)", 0, "-", 87.1, 4.8,
        "Referans/baseline test - depresansiz",
        "Aranzazu NI 43-101 (2018 TR, Tablo 13-8, Test 13)",
    ),
    ArsenicDepressantTrial(
        "Hidrojen Peroksit", 85, "conditioning", 89.1, 6.3,
        "Marjinal selektivite artisi",
        "Aranzazu NI 43-101 (2018 TR, Tablo 13-8, Test 16)",
    ),
    ArsenicDepressantTrial(
        "DETA/SO2 (patentli As depresani)", None, "conditioning", 90.1, 4.5,
        "DOZAJ DEGERI KAYNAK TABLODA OKUNAKLI DEGIL (Excel tarih formati "
        "bozulmasi olasi - '17-May' gibi anlamsiz bir deger gorunuyor, "
        "gercek g/t degeri belirsiz). En yuksek Cu kurtarma gorulen test - "
        "enargiti AKTIVE etmis gibi gorunuyor (selektiviteyi artirmadi, "
        "kurtarmayi artirdi).",
        "Aranzazu NI 43-101 (2018 TR, Tablo 13-8, Test 18)",
    ),
    ArsenicDepressantTrial(
        "Sodyum Sulfid (NaS2)", 220, "conditioning", 87.5, 6.6,
        "REDOX potansiyeli ile dozaj kontrolu yapildi",
        "Aranzazu NI 43-101 (2018 TR, Tablo 13-8, Test 19)",
    ),
    ArsenicDepressantTrial(
        "Sodyum Sulfid (NaS2)", 662, "conditioning", 90.1, 6.9,
        "En yuksek NaS2 dozaji - en iyi selektivite ama yuksek reaktif "
        "maliyeti",
        "Aranzazu NI 43-101 (2018 TR, Tablo 13-8, Test 35)",
    ),
]


@dataclass
class UserReagentInput:
    """Kullanicinin (sirketin) kendi tedarikcisinden aldigi gercek veri."""
    name: str
    consumption_kg_per_t: float
    unit_price_usd_per_kg: float


def calculate_reagent_cost(daily_tonnage: float, user_inputs: list) -> dict:
    """
    Kullanicinin girdigi gercek tuketim + fiyat verisinden maliyet hesaplar.
    Hicbir varsayilan/uydurma deger icermez - tum sayisal degerler kullanici girdisidir.
    """
    if not user_inputs:
        raise ValueError("En az 1 reaktif girdisi gerekli (kullanici kendi tedarikci verisini girmeli).")

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
            f"Karsilastirma icin: Altar Project raporunda toplam isleme maliyeti "
            f"(reaktif+asinma+enerji, kirilimsiz) ${ALTAR_TOTAL_PROCESSING_OPEX_USD_PER_T}/ton "
            f"olarak raporlanmisti ({ALTAR_TOTAL_PROCESSING_OPEX_SOURCE}). Girilen sadece "
            f"reaktif maliyeti oldugu icin bu rakamdan DUSUK cikmasi beklenir - "
            f"aradaki fark asinma malzemesi + enerji maliyetini temsil eder."
        ),
    }


if __name__ == "__main__":
    print("Reaktif Maliyeti Hesaplama - ORNEK Kullanim\n" + "-" * 55)
    print("(Asagidaki sayilar SADECE TEMSILI ORNEK - gercek tedarikci verisi DEGIL,")
    print(" gercek kullanimda bu degerler kullanici tarafindan girilecek)\n")

    ornek_girdi = [
        UserReagentInput("PAX", consumption_kg_per_t=0.010, unit_price_usd_per_kg=4.20),
        UserReagentInput("Kirec (Lime)", consumption_kg_per_t=1.0, unit_price_usd_per_kg=0.35),
        UserReagentInput("MIBC", consumption_kg_per_t=0.015, unit_price_usd_per_kg=3.80),
    ]

    sonuc = calculate_reagent_cost(daily_tonnage=60000, user_inputs=ornek_girdi)

    for item in sonuc["line_items"]:
        print(
            f"  {item['reagent']:<20} {item['consumption_kg_per_t']:.3f} kg/t x "
            f"${item['unit_price_usd_per_kg']:.2f}/kg = ${item['cost_usd_per_t']:.4f}/t"
        )

    print(f"\n  TOPLAM (bu ornek girdiyle): ${sonuc['total_cost_usd_per_t']:.2f}/ton")
    print(f"\n{sonuc['benchmark_note']}")

    print("\n--- Aranzazu Locked Cycle Test Reaktif Dozajlari (Tablo 13-10) ---")
    print("(GERCEK test verisi - TEST OLCEGI, tam olcekli tesis tuketimi degil)")
    for d in ARANZAZU_LOCKED_CYCLE_TEST_DOSAGES:
        print(f"  [{d.reagent_name}] {d.dosage_g_per_t} g/t - {d.test_stage}")

    print("\n--- Aranzazu Arsenik Depresan Deneme Sonuclari (Tablo 13-8) ---")
    for t in ARANZAZU_ARSENIC_DEPRESSANT_TRIALS:
        dozaj = f"{t.dosage_g_per_t} g/t" if t.dosage_g_per_t is not None else "dozaj belirsiz"
        print(f"  [{t.compound}] {dozaj} -> Cu Kurtarma: %{t.cu_recovery_pct}, Cu/As oran: {t.cu_as_selectivity_ratio}")
