"""
CAPEX Ölçekleme Modülü
========================
Kaynak 1: Altar Project NI 43-101 PEA (Aldebaran Resources, Eylül 2025)
          Initial Processing CAPEX: $579M @ 60,000 tpd (greenfield, Cu porfiri)
Kaynak 2: La Mina Project PEA (GoldMining Inc., Nisan 2026 - basın bülteni,
          tam NI 43-101 raporu henüz SEDAR'a dosyalanmadı)
          Process Plant CAPEX: $224.7M @ 15,000 tpd (greenfield, Au-Cu porfiri)

Yöntem: "six-tenths rule" (güç yasası ölçekleme) - endüstride CAPEX
tahmininde standart bir yaklaşımdır:
    Cost_B = Cost_A * (Capacity_B / Capacity_A) ^ n
Üstel katsayı (n) genelde 0.6-0.7 aralığındadır (proses tesisleri için,
ekipmanın hacim/kapasite arttıkça birim maliyetinin azalması prensibine
dayanır - "economies of scale").

Elimizdeki 2 veri noktasından n ampirik olarak hesaplanmıştır - değeri
0.6-0.7 aralığına düştüğü için bu, farklı kaynaklardan gelen bu 2 verinin
birbiriyle makul bir şekilde tutarlı olduğunun bağımsız bir göstergesidir.

ÖNEMLİ SINIRLAMA: Sadece 2 veri noktası var. Bu, bir doğru geçirmek için
yeterli ama güvenilir bir eğri için yetersiz. Üçüncü, dördüncü veri noktası
eklendikçe bu model daha sağlam hale gelecek.
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
    source="Altar PEA Tablo 21-5 (Initial Processing Capex), Eylül 2025",
)

LA_MINA_DATA_POINT = CapexDataPoint(
    project="La Mina Project",
    capacity_tpd=15000,
    process_capex_usd=224_700_000,
    base_year=2026,
    source="La Mina PEA basın bülteni (Nisan 2026) - tam rapor henüz yok",
)


def fit_scaling_exponent(point_a: CapexDataPoint, point_b: CapexDataPoint) -> float:
    """
    İki veri noktasından güç yasası üstelini (n) hesaplar:
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
    Hedef kapasite için Process Plant CAPEX tahmini yapar.
    exponent verilmezse, elimizdeki 2 veri noktasından hesaplanan değer kullanılır.

    UYARI: Bu tahmin enflasyon/maliyet endeksi düzeltmesi içermez - referans
    projenin baz yılı (base_year) ile bugün arasındaki fark ayrı ele alınmalı.
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
            f"n={exponent:.3f} üsteliyle ölçeklenmiştir. Enflasyon/maliyet endeksi "
            f"düzeltmesi bu hesaba dahil DEĞİLDİR."
        ),
    }


if __name__ == "__main__":
    print("CAPEX Ölçekleme Modeli - Doğrulama\n" + "-" * 55)

    n = fit_scaling_exponent(LA_MINA_DATA_POINT, ALTAR_DATA_POINT)
    print(f"2 veri noktasından hesaplanan ölçekleme üsteli (n): {n:.4f}")
    print("(Endüstri standardı 'six-tenths rule' aralığı: 0.6 - 0.7)")
    in_range = 0.5 <= n <= 0.8
    print(f"  -> {'ARALIK İÇİNDE, veri tutarlı görünüyor' if in_range else 'ARALIK DIŞI, dikkatli yorumlanmalı'}\n")

    # Çapraz kontrol (bilgi amaçlı - n zaten bu 2 noktadan türetildiği için
    # birebir eşleşmesi beklenir, gerçek bir "test" değil, sadece matematiğin
    # doğru çalıştığını göstermek için)
    test = estimate_process_capex(target_capacity_tpd=15000, reference=ALTAR_DATA_POINT, exponent=n)
    print(f"Kontrol: Altar referansından 15,000 tpd için tahmin -> ${test['estimated_process_capex_usd']:,.0f}")
    print(f"La Mina gerçek değer: ${LA_MINA_DATA_POINT.process_capex_usd:,.0f}")

    print("\n--- Örnek kullanım: 30,000 tpd yeni proje için tahmin ---")
    result = estimate_process_capex(target_capacity_tpd=30000)
    print(f"Tahmini Process Plant CAPEX: ${result['estimated_process_capex_usd']:,.0f}")
    print(f"Kullanılan üstel: {result['scaling_exponent']}")
    print(result["note"])

    print("\n--- Örnek kullanım: 100,000 tpd (Altar'ın Faz II üstüne) için tahmin ---")
    result2 = estimate_process_capex(target_capacity_tpd=100000)
    print(f"Tahmini Process Plant CAPEX: ${result2['estimated_process_capex_usd']:,.0f}")
