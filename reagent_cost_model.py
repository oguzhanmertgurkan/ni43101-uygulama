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

Mimari mantik: 3. sahis kullanicilar (sirketler) uygulamaya girdiginde,
KENDI tedarikci tekliflerini (kg/ton tuketim + $/kg fiyat) kendileri
girecek. Bu modulun gorevi hangi reaktif TURLERINE ihtiyac oldugunu dogru
onermek ve kullanicinin girdigi gercek sayilardan maliyeti hesaplamak -
varsayilan sayi uydurmak degil.
"""

from dataclasses import dataclass


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