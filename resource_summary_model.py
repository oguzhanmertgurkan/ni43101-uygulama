"""
Mineral Kaynak Özeti ve NSR (Net Smelter Return) Modülü
===========================================================
Kaynak: Aranzazu Mine NI 43-101 Teknik Raporu (Aura Minerals Inc. / SLR
Consulting, 28 Mart 2025, geçerlilik tarihi 31 Aralık 2024) - Bölüm 14
(Mineral Resource Estimates), Tablo 14-1 ve 14-2.

İçerik:
1. NSR (Net Smelter Return) hesabı - raporun KENDİ KULLANDIĞI, AÇIKÇA
   BELİRTİLMİŞ formül (Tablo 14-1, Not 7): kaynak sınırı belirlemede
   kullanılan GERÇEK denklem. Bu, "1 birim tenörün $ olarak değeri ne"
   sorusuna hızlı bir cevap sağlar - CAPEX/OPEX modülündeki gibi genel
   bir mühendislik yöntemi değil, DOĞRUDAN bu rapora/bu metal fiyatı
   varsayımına ÖZEL bir denklemdir.
2. Aranzazu Mineral Kaynak özet tabloları (Tablo 14-1: kaynaklar REZERVLERİ
   DAHİL EDEREK, Tablo 14-2: kaynaklar REZERVLERİ HARİÇ TUTARAK) - GERÇEK,
   doğrulanmış rapor verisi.

ÖNEMLİ SINIRLAMA - NSR FORMÜLÜ SADECE BU RAPORA ÖZELDİR:
NSR katsayıları (74.553 / 47.932 / 0.431), raporun kullandığı METAL
FİYATI VARSAYIMLARINA (Au $2,000/oz, Cu $4.20/lb, Ag $25/oz), VERİM
ORANLARINA (%91.3 Cu, %79.5 Au, %62.8 Ag) VE USD/MXN KURUNA (1:20.5)
GÖMÜLÜDÜR. Farklı bir metal fiyatı senaryosu için (orn. Cu $5.00/lb)
bu katsayılar GEÇERSİZDİR - yeniden hesaplanmaları gerekir. Bu modül
BİLİNÇLİ OLARAK "genel bir NSR hesaplayıcı" SUNMAZ (çünkü smelter/
refining deduction oranları projeye/sözleşmeye özeldir ve raporda
ayrıntılı verilmez) - sadece RAPORUN KENDİ sabit katsayılı denklemini
uygular, "bu rapordaki varsayımlarla NSR ne olurdu" sorusuna cevap verir.

MİMARİ NOT: Kaynak/rezerv sınıflandırması (Measured/Indicated/Inferred,
CIM 2014 tanımları) burada YENİDEN HESAPLANMAZ - bu, Qualified Person (QP)
tarafından yapılmış resmi bir sınıflandırmadır, sadece rapor edilen
sonuçlar referans olarak sunulur.
"""

from dataclasses import dataclass


def calculate_nsr(
    cu_pct: float,
    au_gpt: float,
    ag_gpt: float,
) -> dict:
    """
    Aranzazu raporunun (Tablo 14-1, Not 7) AÇIKÇA belirttiği NSR formülünü
    uygular:

        NSR ($/t) = 74.553 x Cu(%) + 47.932 x Au(g/t) + 0.431 x Ag(g/t)

    Bu katsayılar, raporun metal fiyatı varsayımlarına (Au $2,000/oz,
    Cu $4.20/lb, Ag $25/oz), verim oranlarına (%91.3 Cu, %79.5 Au,
    %62.8 Ag) ve USD/MXN kuruna (1:20.5) GÖMÜLÜDÜR - farklı bir fiyat
    senaryosu için GEÇERSİZDİR.
    """
    if cu_pct < 0 or au_gpt < 0 or ag_gpt < 0:
        raise ValueError("Tenör değerleri negatif olamaz.")

    cu_term = 74.553 * cu_pct
    au_term = 47.932 * au_gpt
    ag_term = 0.431 * ag_gpt
    nsr_usd_per_t = cu_term + au_term + ag_term

    return {
        "cu_pct": cu_pct,
        "au_gpt": au_gpt,
        "ag_gpt": ag_gpt,
        "cu_contribution_usd_per_t": round(cu_term, 2),
        "au_contribution_usd_per_t": round(au_term, 2),
        "ag_contribution_usd_per_t": round(ag_term, 2),
        "nsr_usd_per_t": round(nsr_usd_per_t, 2),
        "formula": "NSR (\\$/t) = 74.553 x Cu(%) + 47.932 x Au(g/t) + 0.431 x Ag(g/t)",
        "price_assumptions": (
            "Au \\$2,000/oz, Cu \\$4.20/lb, Ag \\$25/oz | Verim: %91.3 Cu, "
            "%79.5 Au, %62.8 Ag | USD/MXN 1:20.5"
        ),
        "source": "Aranzazu NI 43-101 (SLR, 28 Mart 2025), Tablo 14-1, Not 7",
        "note": (
            "Bu katsayılar SADECE bu rapordaki metal fiyatı/verim "
            "varsayımlarıyla geçerlidir - farklı bir fiyat senaryosu için "
            "YENİDEN HESAPLANMALIDIR (bu modül böyle bir yeniden hesaplama "
            "araçı SUNMAZ, çünkü smelter/rafine kesinti oranları rapor "
            "tarafından ayrıntılı verilmemiştir)."
        ),
    }


def check_nsr_against_cutoff(
    nsr_usd_per_t: float,
    cutoff_usd_per_t: float = 50.0,
) -> dict:
    """
    Hesaplanan NSR'yi, raporun Mineral Kaynak sınırı için kullandığı
    kesim değeriyle ($50/t, Tablo 14-1 Not 5) karşılaştırır. SADECE
    bilgi amaçlıdır - madencilik/işleme kararı için QP değerlendirmesi
    gerekir.
    """
    above_cutoff = nsr_usd_per_t >= cutoff_usd_per_t

    return {
        "nsr_usd_per_t": nsr_usd_per_t,
        "cutoff_usd_per_t": cutoff_usd_per_t,
        "above_cutoff": above_cutoff,
        "note": (
            f"Hesaplanan NSR (\\${nsr_usd_per_t}/t), rapordaki Mineral Kaynak "
            f"kesim değerinin (\\${cutoff_usd_per_t}/t) "
            + ("ÜSTÜNDE - bu tenör rapor varsayımlarında ekonomik sınırın içinde."
               if above_cutoff else
               "ALTINDA - bu tenör rapor varsayımlarında ekonomik sınırın dışında kalabilir.")
        ),
        "source": "Aranzazu NI 43-101 (SLR, 28 Mart 2025), Tablo 14-1, Not 5",
    }


@dataclass
class ResourceCategory:
    category: str
    tonnage_000t: float
    cu_pct: float
    au_gpt: float
    ag_gpt: float
    cu_contained_000lb: float
    au_contained_000oz: float
    ag_contained_000oz: float


# Tablo 14-1: Mineral Kaynaklar REZERVLERİ DAHİL EDEREK raporlanmış
# (Inclusive of Mineral Reserves) - 31 Aralık 2024
ARANZAZU_RESOURCES_INCLUSIVE = [
    ResourceCategory("Measured", 11834, 1.28, 0.90, 19, 334546, 342, 7388),
    ResourceCategory("Indicated", 8279, 1.03, 0.57, 18, 187374, 152, 4872),
    ResourceCategory("Total Measured + Indicated", 20113, 1.18, 0.76, 19, 521919, 494, 12260),
    ResourceCategory("Inferred", 5623, 0.82, 0.44, 14, 101897, 79, 2496),
]

# Tablo 14-2: Mineral Kaynaklar REZERVLERİ HARİÇ TUTARAK raporlanmış
# (Exclusive of Mineral Reserves) - 31 Aralık 2024
ARANZAZU_RESOURCES_EXCLUSIVE = [
    ResourceCategory("Measured", 6069, 1.06, 0.80, 17, 141893, 155, 3262),
    ResourceCategory("Indicated", 4167, 0.81, 0.47, 14, 74710, 64, 1915),
    ResourceCategory("Total Measured + Indicated", 10236, 0.96, 0.67, 16, 216603, 219, 5178),
    ResourceCategory("Inferred", 5623, 0.82, 0.44, 14, 101897, 79, 2496),
]

ARANZAZU_RESOURCE_SOURCE = (
    "Aranzazu NI 43-101 (SLR, 28 Mart 2025), Tablo 14-1 (Inclusive) / "
    "14-2 (Exclusive), 31 Aralık 2024 itibarıyla. CIM (2014) tanımlarına "
    "göre sınıflandırılmış, NSR kesim değeri \\$45-50/t, min. 2.0m madencilik "
    "genişliği varsayımlarına dayanır."
)


if __name__ == "__main__":
    print("Mineral Kaynak Özeti ve NSR Modülü - Doğrulama\n" + "-" * 55)

    print("--- 1. NSR Hesabı (Tablo 14-1, Not 7 formülü) ---")
    test_cases = [
        (1.51, 0.76, 21.03, "2024 fiili ortalama tenör"),
        (1.18, 0.76, 19, "Toplam M+I kaynak ortalama tenörü"),
        (0.5, 0.3, 10, "Düşük tenör senaryosu"),
    ]
    for cu, au, ag, label in test_cases:
        nsr_sonuc = calculate_nsr(cu, au, ag)
        print(f"[{label}] Cu={cu}%, Au={au}g/t, Ag={ag}g/t -> NSR = ${nsr_sonuc['nsr_usd_per_t']}/t")
        kesim = check_nsr_against_cutoff(nsr_sonuc["nsr_usd_per_t"])
        print(f"    {kesim['note']}")

    print("\n--- 2. Aranzazu Mineral Kaynaklar (Tablo 14-1, Inclusive) ---")
    for r in ARANZAZU_RESOURCES_INCLUSIVE:
        print(
            f"  [{r.category}] {r.tonnage_000t:,.0f} bin ton @ Cu={r.cu_pct}%, "
            f"Au={r.au_gpt}g/t, Ag={r.ag_gpt}g/t"
        )

    print("\n--- 3. Aranzazu Mineral Kaynaklar (Tablo 14-2, Exclusive) ---")
    for r in ARANZAZU_RESOURCES_EXCLUSIVE:
        print(
            f"  [{r.category}] {r.tonnage_000t:,.0f} bin ton @ Cu={r.cu_pct}%, "
            f"Au={r.au_gpt}g/t, Ag={r.ag_gpt}g/t"
        )
