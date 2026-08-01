"""
Tenor-Verim (Grade-Recovery) Modulu
========================================
Kaynak: Aranzazu Mine NI 43-101 Teknik Raporu (Aura Minerals Inc. / SLR
Consulting, 28 Mart 2025, gecerlilik tarihi 31 Aralik 2024) - Bolum 13.5
(Recovery Projections for the Cash Flow Model), Tablo 13-18/13-19 ve
Sekil 13-14/13-15/13-16/13-20/13-21/13-22.

GUNCELLEME NOTU (2025 rapor verisiyle degistirildi): Bu modulun onceki
versiyonu basit dogrusal korelasyonlar iceriyordu (kaynagi tam net
belirtilmemis). Bu versiyon, raporun ACIKCA "mevcut nakit akisi modelinde
kullanildigi" belirtilen RESMI denklemleri (Tablo 13-19) kullanir -
LOGARITMIK form (Cu, Au icin), dogrusal (Ag icin). Ayrica cok daha genis
bir tenor araligini (0.70-1.60% Cu - Tablo 13-18'de tablo halinde
verilmis) kapsar; onceki surumdeki 1.0-1.8% sinirindan cok daha genistir.

IKI FARKLI VERI SETI MEVCUT (rapor ikisini de sunuyor, farkli amaclarla):

1. PLANT_DATA (resmi model) - Eylul-Aralik 2024 gunluk isletme verisinden
   turetilmis, raporun "nakit akisi modelinde kullanilacak" diye ACIKCA
   sectigi denklem (Tablo 13-19). Bu donemde flotasyon devresi dizel
   katkili calisiyordu (molibden kurtarma icin eklenmisti, bakir
   kurtarmayi da olumlu etkiledi) - yani PLANT_DATA denklemi bu spesifik
   isletme kosuluna ozeldir.

2. DRILL_DATA (variability test) - 210 karot orneginden (TUM yatak
   genelinde, farkli mineralojik zonlardan - GH Pillar, BW, Mexicana
   South, AA) turetilmis denklem (Sekil 13-14/13-15/13-16). COK DUSUK
   R^2 (0.05-0.11) - yani tenor tek basina kurtarmayi zayif aciklamakta,
   saha/mineraloji degiskenligi cok daha baskin bir faktordur. Buna
   karsin cok daha genis bir tenor araligini (gercek karot orneklerinin
   gozlemlenen araligi) kapsar ve FARKLI ZONLARIN mineralojik
   cesitliligini icerir - bu da onu "benzer olmayan/degisken
   yataklanma" senaryolari icin KABA bir referans yapar. Kesinlikle
   PLANT_DATA modelinin yerine gecmez, sadece tamamlayici/ihtiyatli bir
   ikinci gorus olarak kullanilmalidir.

ONEMLI UYARI: DRILL_DATA denklemlerinin R^2 degerleri COK DUSUKTUR
(0.05-0.11). Bu denklemler "kesin tahmin" degil, KABA BIR EGILIM
GOSTERGESIDIR - kullanicilar bu modelle yapilan tahminlerin genis bir
belirsizlik araligi tasidigini bilmelidir.

NOT: Bu korelasyonlar Aranzazu'ya (skarn tipi Cu-Au-Ag yatagi, kalkopirit
agirlikli) ozeldir. Farkli mineralojide (orn. porfiri) baska bir maden
icin dogrudan kullanilmamalidir - her maden/proje kendi korelasyonuyla
calismali (DRILL_DATA modeli bile, ayni yatagin ic degiskenligini
yansitir - farkli bir yatagin degil).
"""

import math
from dataclasses import dataclass


@dataclass
class GradeRecoveryModel:
    metal: str
    form: str  # "log" -> a*ln(grade)+b, "linear" -> a*grade+b
    a: float
    b: float
    valid_grade_min: float
    valid_grade_max: float
    source: str
    r_squared: float = None
    dataset: str = ""  # "plant_data" veya "drill_data"

    def predict_recovery(self, head_grade: float) -> float:
        """Tenore (head grade) bagli verim oranini tahmin eder (0-1 araliginda)."""
        if head_grade <= 0:
            raise ValueError("Tenor pozitif olmali.")
        if self.form == "log":
            recovery = self.a * math.log(head_grade) + self.b
        else:
            recovery = self.a * head_grade + self.b
        return max(0.0, min(1.0, recovery))

    def is_extrapolating(self, head_grade: float) -> bool:
        """Verilen tenor, modelin test edildigi aralik disinda mi kontrol eder."""
        return not (self.valid_grade_min <= head_grade <= self.valid_grade_max)


# ============================================================
# 1) PLANT_DATA (RESMI MODEL) - Tablo 13-19, Eylul-Aralik 2024
#    gunluk isletme verisi - raporun nakit akisi modelinde
#    FIILEN KULLANDIGI denklemler
# ============================================================

ARANZAZU_CU = GradeRecoveryModel(
    metal="Cu", form="log", a=0.0448, b=0.9089,
    valid_grade_min=0.70, valid_grade_max=1.60,
    source=(
        "Aranzazu NI 43-101 (SLR, 28 Mart 2025), Tablo 13-19 - "
        "Eylul-Aralik 2024 gunluk isletme verisi (resmi nakit akisi "
        "modeli denklemi, Sekil 13-20)"
    ),
    r_squared=0.2423,
    dataset="plant_data",
)

ARANZAZU_AU = GradeRecoveryModel(
    metal="Au", form="log", a=0.077, b=0.8432,
    valid_grade_min=0.10, valid_grade_max=1.00,
    source=(
        "Aranzazu NI 43-101 (SLR, 28 Mart 2025), Tablo 13-19 - "
        "Eylul-Aralik 2024 gunluk isletme verisi (resmi nakit akisi "
        "modeli denklemi, Sekil 13-21)"
    ),
    r_squared=0.1449,
    dataset="plant_data",
)

ARANZAZU_AG = GradeRecoveryModel(
    metal="Ag", form="linear", a=0.0089, b=0.4601,
    valid_grade_min=8.00, valid_grade_max=26.00,
    source=(
        "Aranzazu NI 43-101 (SLR, 28 Mart 2025), Tablo 13-19 - "
        "Eylul-Aralik 2024 gunluk isletme verisi (resmi nakit akisi "
        "modeli denklemi, Sekil 13-22)"
    ),
    r_squared=0.4640,
    dataset="plant_data",
)

MODELS = {"Cu": ARANZAZU_CU, "Au": ARANZAZU_AU, "Ag": ARANZAZU_AG}


# ============================================================
# 2) DRILL_DATA (ALTERNATIF / VARIABILITY TEST) - 210 karot
#    orneginden (Sekil 13-14/13-15/13-16), TUM yatak genelinde
#    (farkli mineralojik zonlar dahil) - COK DUSUK R^2, ama COK
#    DAHA GENIS tenor araligi. "Degisken/farkli yataklanma"
#    senaryolari icin KABA bir referans - PLANT_DATA'nin yerine
#    GECMEZ.
# ============================================================

ARANZAZU_CU_DRILLDATA = GradeRecoveryModel(
    metal="Cu", form="log", a=0.05726, b=0.85589,
    valid_grade_min=0.5, valid_grade_max=3.0,
    source=(
        "Aranzazu NI 43-101 (SLR, 28 Mart 2025), Sekil 13-14 - 210 karot "
        "orneginden (2024 variability test, tum yatak/zonlar) turetilmis "
        "egilim - DUSUK R^2 (0.107), sadece kaba egilim gostergesi"
    ),
    r_squared=0.1073,
    dataset="drill_data",
)

ARANZAZU_AU_DRILLDATA = GradeRecoveryModel(
    metal="Au", form="linear", a=0.040202, b=0.75054,
    valid_grade_min=0.1, valid_grade_max=2.0,
    source=(
        "Aranzazu NI 43-101 (SLR, 28 Mart 2025), Sekil 13-15 - 210 karot "
        "orneginden (2024 variability test) turetilmis egilim - COK DUSUK "
        "R^2 (0.055), sadece kaba egilim gostergesi"
    ),
    r_squared=0.0545,
    dataset="drill_data",
)

ARANZAZU_AG_DRILLDATA = GradeRecoveryModel(
    metal="Ag", form="linear", a=0.002738, b=0.62084,
    valid_grade_min=6.0, valid_grade_max=70.0,
    source=(
        "Aranzazu NI 43-101 (SLR, 28 Mart 2025), Sekil 13-16 - 210 karot "
        "orneginden (2024 variability test) turetilmis egilim - DUSUK R^2 "
        "(0.089), sadece kaba egilim gostergesi"
    ),
    r_squared=0.0894,
    dataset="drill_data",
)

DRILLDATA_MODELS = {
    "Cu": ARANZAZU_CU_DRILLDATA,
    "Au": ARANZAZU_AU_DRILLDATA,
    "Ag": ARANZAZU_AG_DRILLDATA,
}


def predict_recovery(metal: str, head_grade: float, dataset: str = "plant_data") -> dict:
    """
    Verilen metal ve tenor icin verim tahmini dondurur.

    metal: "Cu", "Au" veya "Ag"
    head_grade: Cu icin % cinsinden, Au/Ag icin g/t cinsinden
    dataset: "plant_data" (varsayilan, RESMI model - Tablo 13-19) veya
             "drill_data" (variability test, genis aralik, DUSUK R^2 -
             kaba egilim gostergesi, kesin tahmin degil)
    """
    if dataset not in ("plant_data", "drill_data"):
        raise ValueError('dataset "plant_data" veya "drill_data" olmali.')

    models = MODELS if dataset == "plant_data" else DRILLDATA_MODELS
    if metal not in models:
        raise ValueError(f"Desteklenmeyen metal: {metal}. Secenekler: {list(models)}")

    model = models[metal]
    recovery = model.predict_recovery(head_grade)
    extrapolating = model.is_extrapolating(head_grade)

    warning_parts = []
    if extrapolating:
        warning_parts.append(
            f"UYARI: Girilen tenor ({head_grade}) modelin test edildigi aralik "
            f"[{model.valid_grade_min}-{model.valid_grade_max}] disinda - "
            f"tahmin guvenilirligi dusuk olabilir."
        )
    if dataset == "drill_data":
        warning_parts.append(
            f"DIKKAT: Bu model dusuk R^2 ({model.r_squared}) ile kaba bir "
            f"egilimdir - tenor, kurtarmayi zayif aciklamaktadir (saha/"
            f"mineraloji degiskenligi cok daha baskindir). Kesin tahmin "
            f"degil, sadece yon gostergesi olarak kullanilmalidir."
        )

    return {
        "metal": metal,
        "head_grade": head_grade,
        "dataset": dataset,
        "predicted_recovery_pct": round(recovery * 100, 2),
        "extrapolating": extrapolating,
        "r_squared": model.r_squared,
        "warning": " ".join(warning_parts) if warning_parts else None,
        "source": model.source,
    }


if __name__ == "__main__":
    print("Aranzazu Tenor-Verim Modeli - Dogrulama (2025 TR verisi)\n" + "-" * 60)

    print("\n=== 1) PLANT_DATA (resmi model, Tablo 13-19) ===")
    test_cases_plant = [
        ("Cu", 0.70, "LOM plan alt sinir (2031 civari)"),
        ("Cu", 1.40, "LOM plan ust sinir (2025 baslangici)"),
        ("Cu", 1.51, "2022-24 fiili ortalama (dogrulama)"),
        ("Au", 0.40, "LOM plan (2032 civari)"),
        ("Au", 0.90, "LOM plan (2025 civari)"),
        ("Ag", 14.0, "LOM plan alt sinir (2030 civari)"),
        ("Ag", 20.0, "LOM plan ust sinir (2025 civari)"),
    ]
    for metal, grade, label in test_cases_plant:
        result = predict_recovery(metal, grade, dataset="plant_data")
        flag = " <-- EKSTRAPOLASYON" if result["extrapolating"] else ""
        print(f"[{label}] {metal} tenor: {grade} -> Verim: %{result['predicted_recovery_pct']}{flag}")

    print("\n=== 2) DRILL_DATA (variability test, genis aralik, DUSUK R^2) ===")
    test_cases_drill = [
        ("Cu", 0.53, "En dusuk gozlemlenen variability tenoru"),
        ("Cu", 8.71, "En yuksek gozlemlenen variability tenoru"),
        ("Cu", 0.47, "Altar Project (farkli maden, extrapolasyon testi)"),
        ("Au", 5.40, "En yuksek gozlemlenen Au variability tenoru"),
        ("Ag", 111.0, "En yuksek gozlemlenen Ag variability tenoru"),
    ]
    for metal, grade, label in test_cases_drill:
        result = predict_recovery(metal, grade, dataset="drill_data")
        flag = " <-- EKSTRAPOLASYON" if result["extrapolating"] else ""
        print(f"[{label}] {metal} tenor: {grade} -> Verim: %{result['predicted_recovery_pct']}{flag}")
        if result["warning"]:
            print(f"    {result['warning']}")
