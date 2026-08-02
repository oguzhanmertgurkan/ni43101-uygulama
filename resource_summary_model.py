"""
Mineral Kaynak Ozeti ve NSR (Net Smelter Return) Modulu
===========================================================
Kaynak: Aranzazu Mine NI 43-101 Teknik Raporu (Aura Minerals Inc. / SLR
Consulting, 28 Mart 2025, gecerlilik tarihi 31 Aralik 2024) - Bolum 14
(Mineral Resource Estimates), Tablo 14-1 ve 14-2.

Icerik:
1. NSR (Net Smelter Return) hesabi - raporun KENDI KULLANDIGI, ACIKCA
   BELIRTILMIS formul (Tablo 14-1, Not 7): kaynak siniri belirlemede
   kullanilan GERCEK denklem. Bu, "1 birim tenorun $ olarak degeri ne"
   sorusuna hizli bir cevap saglar - CAPEX/OPEX modulundeki gibi genel
   bir muhendislik yontemi degil, DOGRUDAN bu rapora/bu metal fiyati
   varsayimina OZEL bir denklemdir.
2. Aranzazu Mineral Kaynak ozet tablolari (Tablo 14-1: kaynaklar REZERVLERI
   DAHIL EDEREK, Tablo 14-2: kaynaklar REZERVLERI HARIC TUTARAK) - GERCEK,
   dogrulanmis rapor verisi.

ONEMLI SINIRLAMA - NSR FORMULU SADECE BU RAPORA OZELDIR:
NSR katsayilari (74.553 / 47.932 / 0.431), raporun kullandigi METAL
FIYATI VARSAYIMLARINA (Au $2,000/oz, Cu $4.20/lb, Ag $25/oz), KURTARMA
ORANLARINA (%91.3 Cu, %79.5 Au, %62.8 Ag) VE USD/MXN KURUNA (1:20.5)
GOMULUDUR. Farkli bir metal fiyati senaryosu icin (orn. Cu $5.00/lb)
bu katsayilar GECERSIZDIR - yeniden hesaplanmalari gerekir. Bu modul
BILINCLI OLARAK "genel bir NSR hesaplayici" SUNMAZ (cunku smelter/
refining deduction oranlari projeye/sozlesmeye ozeldir ve raporda
ayrintili verilmez) - sadece RAPORUN KENDI sabit katsayili denklemini
uygular, "bu rapordaki varsayimlarla NSR ne olurdu" sorusuna cevap verir.

MIMARI NOT: Kaynak/rezerv siniflandirmasi (Measured/Indicated/Inferred,
CIM 2014 tanimlari) burada YENIDEN HESAPLANMAZ - bu, Qualified Person (QP)
tarafindan yapilmis resmi bir siniflandirmadir, sadece rapor edilen
sonuclar referans olarak sunulur.
"""

from dataclasses import dataclass


def calculate_nsr(
    cu_pct: float,
    au_gpt: float,
    ag_gpt: float,
) -> dict:
    """
    Aranzazu raporunun (Tablo 14-1, Not 7) ACIKCA belirttigi NSR formulunu
    uygular:

        NSR ($/t) = 74.553 x Cu(%) + 47.932 x Au(g/t) + 0.431 x Ag(g/t)

    Bu katsayilar, raporun metal fiyati varsayimlarina (Au $2,000/oz,
    Cu $4.20/lb, Ag $25/oz), kurtarma oranlarina (%91.3 Cu, %79.5 Au,
    %62.8 Ag) ve USD/MXN kuruna (1:20.5) GOMULUDUR - farkli bir fiyat
    senaryosu icin GECERSIZDIR.
    """
    if cu_pct < 0 or au_gpt < 0 or ag_gpt < 0:
        raise ValueError("Tenor degerleri negatif olamaz.")

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
        "formula": "NSR ($/t) = 74.553 x Cu(%) + 47.932 x Au(g/t) + 0.431 x Ag(g/t)",
        "price_assumptions": (
            "Au $2,000/oz, Cu $4.20/lb, Ag $25/oz | Kurtarma: %91.3 Cu, "
            "%79.5 Au, %62.8 Ag | USD/MXN 1:20.5"
        ),
        "source": "Aranzazu NI 43-101 (SLR, 28 Mart 2025), Tablo 14-1, Not 7",
        "note": (
            "Bu katsayilar SADECE bu rapordaki metal fiyati/kurtarma "
            "varsayimlariyla gecerlidir - farkli bir fiyat senaryosu icin "
            "YENIDEN HESAPLANMALIDIR (bu modul boyle bir yeniden hesaplama "
            "araci SUNMAZ, cunku smelter/refining kesinti oranlari rapor "
            "tarafindan ayrintili verilmemistir)."
        ),
    }


def check_nsr_against_cutoff(
    nsr_usd_per_t: float,
    cutoff_usd_per_t: float = 50.0,
) -> dict:
    """
    Hesaplanan NSR'yi, raporun Mineral Kaynak siniri icin kullandigi
    kesim degeriyle ($50/t, Tablo 14-1 Not 5) karsilastirir. SADECE
    bilgi amaclidir - madencilik/isleme karari icin QP degerlendirmesi
    gerekir.
    """
    above_cutoff = nsr_usd_per_t >= cutoff_usd_per_t

    return {
        "nsr_usd_per_t": nsr_usd_per_t,
        "cutoff_usd_per_t": cutoff_usd_per_t,
        "above_cutoff": above_cutoff,
        "note": (
            f"Hesaplanan NSR (${nsr_usd_per_t}/t), rapordaki Mineral Kaynak "
            f"kesim degerinin (${cutoff_usd_per_t}/t) "
            + ("USTUNDE - bu tenor rapor varsayimlarinda ekonomik sinirin icinde."
               if above_cutoff else
               "ALTINDA - bu tenor rapor varsayimlarinda ekonomik sinirin disinda kalabilir.")
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


# Tablo 14-1: Mineral Kaynaklar REZERVLERI DAHIL EDEREK raporlanmis
# (Inclusive of Mineral Reserves) - 31 Aralik 2024
ARANZAZU_RESOURCES_INCLUSIVE = [
    ResourceCategory("Measured", 11834, 1.28, 0.90, 19, 334546, 342, 7388),
    ResourceCategory("Indicated", 8279, 1.03, 0.57, 18, 187374, 152, 4872),
    ResourceCategory("Total Measured + Indicated", 20113, 1.18, 0.76, 19, 521919, 494, 12260),
    ResourceCategory("Inferred", 5623, 0.82, 0.44, 14, 101897, 79, 2496),
]

# Tablo 14-2: Mineral Kaynaklar REZERVLERI HARIC TUTARAK raporlanmis
# (Exclusive of Mineral Reserves) - 31 Aralik 2024
ARANZAZU_RESOURCES_EXCLUSIVE = [
    ResourceCategory("Measured", 6069, 1.06, 0.80, 17, 141893, 155, 3262),
    ResourceCategory("Indicated", 4167, 0.81, 0.47, 14, 74710, 64, 1915),
    ResourceCategory("Total Measured + Indicated", 10236, 0.96, 0.67, 16, 216603, 219, 5178),
    ResourceCategory("Inferred", 5623, 0.82, 0.44, 14, 101897, 79, 2496),
]

ARANZAZU_RESOURCE_SOURCE = (
    "Aranzazu NI 43-101 (SLR, 28 Mart 2025), Tablo 14-1 (Inclusive) / "
    "14-2 (Exclusive), 31 Aralik 2024 itibariyle. CIM (2014) tanimlarina "
    "gore siniflandirilmis, NSR kesim degeri $45-50/t, min. 2.0m madencilik "
    "genisligi varsayimlarina dayanir."
)


if __name__ == "__main__":
    print("Mineral Kaynak Ozeti ve NSR Modulu - Dogrulama\n" + "-" * 55)

    print("--- 1. NSR Hesabi (Tablo 14-1, Not 7 formulu) ---")
    test_cases = [
        (1.51, 0.76, 21.03, "2024 fiili ortalama tenor"),
        (1.18, 0.76, 19, "Toplam M+I kaynak ortalama tenoru"),
        (0.5, 0.3, 10, "Dusuk tenor senaryosu"),
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
