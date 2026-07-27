"""
CAPEX Olcekleme Modulu
========================
Kaynak 1: Altar Project NI 43-101 PEA (Aldebaran Resources, Eylul 2025)
          Initial Processing CAPEX: $579M @ 60,000 tpd (greenfield, Cu porfiri)
Kaynak 2: La Mina Project PEA (GoldMining Inc., Nisan 2026 - basin bulteni,
          tam NI 43-101 raporu henuz SEDAR'a dosyalanmadi)
          Process Plant CAPEX: $224.7M @ 15,000 tpd (greenfield, Au-Cu porfiri)

Yontem: "six-tenths rule" (guc yasasi olcekleme) - endustride CAPEX
tahmininde standart bir yaklasimdir:
    Cost_B = Cost_A * (Capacity_B / Capacity_A) ^ n
Ustel katsayi (n) genelde 0.6-0.7 araligindadir (proses tesisleri icin,
ekipmanin hacim/kapasite arttikca birim maliyetinin azalmasi prensibine
dayanir - "economies of scale").

Elimizdeki 2 veri noktasindan n ampirik olarak hesaplanmistir - degeri
0.6-0.7 araligina dustugu icin bu, farkli kaynaklardan gelen bu 2 verinin
birbiriyle makul bir sekilde tutarli oldugunun bagimsiz bir gostergesidir.

ONEMLI SINIRLAMA: Sadece 2 veri noktasi var. Bu, bir dogru gecirmek icin
yeterli ama guvenilir bir egri icin yetersiz. Ucuncu, dorduncu veri noktasi
eklendikce bu model daha saglam hale gelecek.
"""

import math
from dataclasses import dataclass


@dataclass
class CapexDataPoint:
    project: str
    capacity_tpd: float
    process_capex_usd: float
    base_year: int
    source: str


ALTAR_DATA_POINT = CapexDataPoint(
    project="Altar Project",
    capacity_tpd=60000,
    process_capex_usd=579_000_000,
    base_year=2025,
    source="Altar PEA Tablo 21-5 (Initial Processing Capex), Eylul 2025",
)

LA_MINA_DATA_POINT = CapexDataPoint(
    project="La Mina Project",
    capacity_tpd=15000,
    process_capex_usd=224_700_000,
    base_year=2026,
    source="La Mina PEA basin bulteni (Nisan 2026) - tam rapor henuz yok",
)


def fit_scaling_exponent(point_a: CapexDataPoint, point_b: CapexDataPoint) -> float:
    """
    Iki veri noktasindan guc yasasi ustelini (n) hesaplar:
    n = ln(Cost_B / Cost_A) / ln(Cap_B / Cap_A)
    """
    cost_ratio = point_b.process_capex_usd / point_a.process_capex_usd
    cap_ratio = point_b.capacity_tpd / point_a.capacity_tpd
    return math.log(cost_ratio) / math.log(cap_ratio)


def estimate_process_capex(
    target_capacity_tpd: float,
    reference: CapexDataPoint = ALTAR_DATA_POINT,
    exponent: float = None,
) -> dict:
    """
    Hedef kapasite icin Process Plant CAPEX tahmini yapar.
    exponent verilmezse, elimizdeki 2 veri noktasindan hesaplanan deger kullanilir.

    UYARI: Bu tahmin enflasyon/maliyet endeksi duzeltmesi icermez - referans
    projenin baz yili (base_year) ile bugun arasindaki fark ayri ele alinmali.
    """
    if exponent is None:
        exponent = fit_scaling_exponent(LA_MINA_DATA_POINT, ALTAR_DATA_POINT)

    scale_ratio = target_capacity_tpd / reference.capacity_tpd
    estimated_capex = reference.process_capex_usd * (scale_ratio ** exponent)

    return {
        "target_capacity_tpd": target_capacity_tpd,
        "reference_project": reference.project,
        "reference_capacity_tpd": reference.capacity_tpd,
        "reference_capex_usd": reference.process_capex_usd,
        "scaling_exponent": round(exponent, 4),
        "estimated_process_capex_usd": round(estimated_capex, 0),
        "note": (
            f"Tahmin, {reference.project} verisinden ({reference.base_year} USD baz) "
            f"n={exponent:.3f} usteliyle olceklenmistir. Enflasyon/maliyet endeksi "
            f"duzeltmesi bu hesaba dahil DEGILDIR."
        ),
    }


if __name__ == "__main__":
    print("CAPEX Olcekleme Modeli - Dogrulama\n" + "-" * 55)

    n = fit_scaling_exponent(LA_MINA_DATA_POINT, ALTAR_DATA_POINT)
    print(f"2 veri noktasindan hesaplanan olcekleme usteli (n): {n:.4f}")
    print("(Endustri standardi 'six-tenths rule' araligi: 0.6 - 0.7)")
    in_range = 0.5 <= n <= 0.8
    print(f"  -> {'ARALIK ICINDE, veri tutarli gorunuyor' if in_range else 'ARALIK DISI, dikkatli yorumlanmali'}\n")

    # Capraz kontrol (bilgi amacli - n zaten bu 2 noktadan turetildigi icin
    # birebir eslesmesi beklenir, gercek bir "test" degil, sadece matematigin
    # dogru calistigini gostermek icin)
    test = estimate_process_capex(target_capacity_tpd=15000, reference=ALTAR_DATA_POINT, exponent=n)
    print(f"Kontrol: Altar referansindan 15,000 tpd icin tahmin -> ${test['estimated_process_capex_usd']:,.0f}")
    print(f"La Mina gercek deger: ${LA_MINA_DATA_POINT.process_capex_usd:,.0f}")

    print("\n--- Ornek kullanim: 30,000 tpd yeni proje icin tahmin ---")
    result = estimate_process_capex(target_capacity_tpd=30000)
    print(f"Tahmini Process Plant CAPEX: ${result['estimated_process_capex_usd']:,.0f}")
    print(f"Kullanilan ustel: {result['scaling_exponent']}")
    print(result["note"])

    print("\n--- Ornek kullanim: 100,000 tpd (Altar'in Faz II ustune) icin tahmin ---")
    result2 = estimate_process_capex(target_capacity_tpd=100000)
    print(f"Tahmini Process Plant CAPEX: ${result2['estimated_process_capex_usd']:,.0f}")
